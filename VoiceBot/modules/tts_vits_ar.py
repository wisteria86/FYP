"""
Arabic VITS ONNX Text-to-Speech Module.

Implements ITTSModel using a Piper-style VITS ONNX model
(rhasspy/piper-voices  ar_JO-kareem-medium) for Arabic speech synthesis.
Integrates with ConversationManager's streaming pipeline identically to
KokoroTTS and VitsJaTTS — same method signatures, same yield pattern, same
cancel_event awareness.

Pipeline per sentence:
  text → Arabic normalization → phonemizer/espeak-ng G2P → phoneme IDs
       (via config.json phoneme_id_map)
       → onnxruntime InferenceSession → float32 PCM → trim silence → yield bytes

G2P back-end:
  phonemizer (pip package) + espeak-ng system binary, language "ar".
  The kareem-medium piper config uses phoneme_type=espeak / espeak.voice=ar.
  espeak-ng handles undiacritized Arabic via built-in letter-to-sound rules —
  no separate tashkeel/diacritization library is needed for this model.

The InferenceSession is configured for maximum CPU throughput:
  - All available logical cores via intra/inter_op_num_threads
  - ORT_ENABLE_ALL graph optimization
  - CPUExecutionProvider explicitly set (avoids fallback warning noise)

Model ships as fp32 ONNX (preferred for CPU — no fp16 slowdown).
An optional int8 quantized copy is generated on first run if VITS_AR_QUANTIZE=True.
"""
# Path: modules/tts_vits_ar.py
import os
import re
import json
import logging
from typing import Iterator

import numpy as np

from core.interfaces import ITTSModel
from utils.logger import get_logger

logger = get_logger(__name__)

# Arabic-Indic digit map: ٠١٢٣٤٥٦٧٨٩ → 0123456789
# espeak-ng reads Western Arabic numerals correctly; Eastern Arabic variants may
# produce incorrect phoneme output if not converted first.
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Characters that are safe to strip before phonemization without corrupting
# the Arabic script.  We keep Arabic letters, spaces, Western and Eastern digits,
# and common punctuation that espeak handles (period, comma, question mark, etc.).
# Crucially we do NOT strip Arabic diacritics (harakat / tashkeel) if present —
# they improve G2P accuracy and espeak handles them transparently.
_KEEP_PATTERN = re.compile(
    r"[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF"  # Arabic script blocks
    r"\uFB50-\uFDFF\uFE70-\uFEFF"                 # Arabic Presentation Forms
    r"0-9\s.,;:!?\-\u2013\u2014]",                # digits, spaces, basic punctuation
    flags=re.UNICODE,
)


def _normalize_arabic(text: str) -> str:
    """
    Lightweight Arabic text normalization before phonemization.

    1. Convert Eastern Arabic-Indic digits (٠–٩) to Western (0–9) so espeak
       reads numbers correctly.
    2. Strip characters outside the Arabic script and basic punctuation blocks
       without touching the script itself (no tatweel removal, no ligature
       substitution — espeak handles those internally).

    Right-to-left ordering is preserved; we never reorder characters.
    """
    text = text.translate(_ARABIC_INDIC_DIGITS)
    text = _KEEP_PATTERN.sub(" ", text)
    # Collapse repeated whitespace created by stripping
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


class VitsArTTS(ITTSModel):
    """
    Arabic TTS backed by a Piper-style VITS ONNX model (kareem-medium, ar_JO).

    Mirrors VitsJaTTS in interface contract so ConversationManager's tts_worker
    thread and audio_queue pipeline work without modification.

    Attributes
    ----------
    output_sample_rate : int
        The model's native audio sample rate (read from config.json).
        main.py reads this to initialize SpeakerPlayer at the correct rate —
        no resampling is performed anywhere in the pipeline.
    """

    def __init__(self, onnx_path: str, config_path: str, speaker_id: int = 0) -> None:
        """
        Load the ONNX model and parse the Piper-style config.

        Parameters
        ----------
        onnx_path  : Absolute path to the (optionally quantized) .onnx file.
        config_path: Absolute path to the accompanying .onnx.json config.
        speaker_id : Speaker index for multi-speaker models (0-indexed).
        """
        self.speaker_id = speaker_id

        # ------------------------------------------------------------------ #
        # Parse config.json — phoneme map + audio settings                   #
        # ------------------------------------------------------------------ #
        logger.info(f"Loading VITS Arabic config from: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # phoneme_id_map: {"a": [4], "i": [5], "^": [1], …}
        self.phoneme_id_map: dict = cfg.get("phoneme_id_map", {})
        if not self.phoneme_id_map:
            raise RuntimeError(
                "[VitsArTTS] 'phoneme_id_map' is missing or empty in config JSON. "
                "This model may not be in the expected Piper-style format."
            )

        # Special token IDs (standard Piper spec)
        self._pad_id = self.phoneme_id_map.get("_", [0])[0]   # blank / interleaved
        self._bos_id = self.phoneme_id_map.get("^", [1])[0]   # beginning of sentence
        self._eos_id = self.phoneme_id_map.get("$", [2])[0]   # end of sentence

        # Audio settings
        audio_cfg = cfg.get("audio", {})
        self.output_sample_rate: int = int(
            audio_cfg.get("sample_rate", cfg.get("sample_rate", 22050))
        )
        logger.info(f"VITS Arabic model native sample rate: {self.output_sample_rate} Hz")

        # espeak-ng voice to use for G2P (from piper config; default: "ar")
        espeak_cfg = cfg.get("espeak", {})
        self._espeak_voice: str = espeak_cfg.get("voice", "ar")
        logger.info(f"espeak-ng G2P voice: '{self._espeak_voice}'")

        # Number of speakers (determines whether to pass a sid tensor)
        self._n_speakers: int = int(
            cfg.get("num_speakers", cfg.get("n_speakers", 1))
        )
        self._has_sid = self._n_speakers > 1
        if self._has_sid:
            logger.info(
                f"Multi-speaker model ({self._n_speakers} speakers). "
                f"Using speaker_id={self.speaker_id}"
            )

        # ------------------------------------------------------------------ #
        # Build InferenceSession with explicit CPU tuning                     #
        # Model is fp32 (preferred for CPU) or int8 (quantized cache).       #
        # ------------------------------------------------------------------ #
        try:
            import onnxruntime as ort  # type: ignore
        except ImportError:
            raise RuntimeError(
                "[VitsArTTS] 'onnxruntime' is not installed. Run: pip install onnxruntime"
            )

        # Read thread counts from config (0 → ORT uses all logical cores)
        try:
            from config import Config
            intra_threads = Config.ORT_INTRA_THREADS
            inter_threads = Config.ORT_INTER_THREADS
        except Exception:
            intra_threads = inter_threads = 0

        cpu_count = os.cpu_count() or 4
        resolved_intra = intra_threads if intra_threads > 0 else cpu_count
        resolved_inter = inter_threads if inter_threads > 0 else max(1, cpu_count // 2)

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = resolved_intra
        opts.inter_op_num_threads = resolved_inter
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info(
            f"Loading VITS Arabic ONNX session: {onnx_path} "
            f"(intra_threads={resolved_intra}, inter_threads={resolved_inter})"
        )
        try:
            self._session = ort.InferenceSession(
                onnx_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            raise RuntimeError(
                f"[VitsArTTS] Failed to create ONNX InferenceSession from '{onnx_path}': {exc}"
            ) from exc

        # Inspect actual input/output names so we bind correctly regardless of
        # minor graph differences between model variants.
        self._input_names  = [inp.name for inp in self._session.get_inputs()]
        self._output_names = [out.name for out in self._session.get_outputs()]
        logger.info(f"ONNX graph inputs:  {self._input_names}")
        logger.info(f"ONNX graph outputs: {self._output_names}")

        # ------------------------------------------------------------------ #
        # Verify phonemizer + espeak-ng are available at init time            #
        # ------------------------------------------------------------------ #
        try:
            import phonemizer  # type: ignore  # noqa: F401
            from phonemizer.backend import EspeakBackend  # type: ignore
            # Probe that espeak-ng binary is actually on PATH
            EspeakBackend.is_espeak_ng()
        except ImportError:
            raise RuntimeError(
                "[VitsArTTS] 'phonemizer' is not installed. Run: pip install phonemizer\n"
                "Also ensure espeak-ng is installed as a system binary:\n"
                "  Windows: download installer from https://github.com/espeak-ng/espeak-ng/releases\n"
                "  Linux:   sudo apt install espeak-ng\n"
                "  macOS:   brew install espeak-ng"
            )
        except Exception as exc:
            raise RuntimeError(
                f"[VitsArTTS] espeak-ng binary not found or not functional: {exc}\n"
                "Install espeak-ng as a system binary:\n"
                "  Windows: download installer from https://github.com/espeak-ng/espeak-ng/releases\n"
                "  Linux:   sudo apt install espeak-ng\n"
                "  macOS:   brew install espeak-ng"
            ) from exc

        logger.info("✅ VitsArTTS initialized successfully.")

    # ------------------------------------------------------------------ #
    # Internal: text → phoneme ID sequence                                #
    # ------------------------------------------------------------------ #

    def _text_to_ids(self, text: str) -> list[int]:
        """
        Convert Arabic text to a Piper-style interleaved phoneme ID sequence.

        Format: [BOS, PAD, p1_id, PAD, p2_id, PAD, …, pN_id, PAD, EOS]

        Steps:
        1. Normalize: convert Arabic-Indic digits, strip unsupported chars.
        2. Phonemize via espeak-ng (language 'ar') → IPA phoneme string.
        3. Map each IPA character/cluster to a token ID via phoneme_id_map.
        """
        from phonemizer import phonemize  # type: ignore

        normalized = _normalize_arabic(text)
        if not normalized:
            return []

        try:
            phoneme_str: str = phonemize(
                normalized,
                backend="espeak",
                language=self._espeak_voice,
                with_stress=True,       # retain stress marks for natural prosody
                preserve_punctuation=False,
                njobs=1,                # single-threaded — called from tts_worker thread
            )
        except Exception as exc:
            logger.warning(f"[VitsArTTS] phonemizer G2P failed for '{text[:40]}…': {exc}")
            return []

        # phonemize returns one string per input sentence with IPA chars separated
        # by spaces (or concatenated, depending on version).  We iterate character
        # by character and match against the phoneme_id_map — same approach piper
        # uses internally for espeak-backed models.
        ids: list[int] = [self._bos_id, self._pad_id]
        skipped = 0

        # Try multi-char clusters first (up to 3 chars), then single char
        i = 0
        phonemes_seq = phoneme_str.replace("\n", " ").strip()
        # Build list of space-separated tokens if any, else iterate chars
        tokens = phonemes_seq.split() if " " in phonemes_seq else list(phonemes_seq)

        for token in tokens:
            if token in self.phoneme_id_map:
                ids.extend(self.phoneme_id_map[token])
                ids.append(self._pad_id)
            else:
                # Try character-by-character fallback for unsplit IPA strings
                matched_any = False
                for ch in token:
                    if ch in self.phoneme_id_map:
                        ids.extend(self.phoneme_id_map[ch])
                        ids.append(self._pad_id)
                        matched_any = True
                    else:
                        logger.debug(f"[VitsArTTS] Unknown phoneme skipped: '{ch}'")
                        skipped += 1
                if not matched_any and token.strip():
                    skipped += 1

        ids.append(self._eos_id)

        if skipped:
            logger.debug(f"[VitsArTTS] {skipped} phoneme(s) not in map.")

        return ids

    # ------------------------------------------------------------------ #
    # Internal: run ONNX inference                                        #
    # ------------------------------------------------------------------ #

    def _infer(self, ids: list[int], speed: float) -> np.ndarray:
        """
        Run VITS ONNX inference and return a 1-D float32 audio array.

        Builds the feed dict dynamically by matching against the session's
        declared input names.  Supports both standard VITS input layouts
        (input / input_lengths / scales) and multi-speaker layouts (+ sid).
        """
        input_ids    = np.array([ids], dtype=np.int64)          # (1, T)
        input_len    = np.array([len(ids)], dtype=np.int64)     # (1,)
        noise_scale  = 0.667
        length_scale = 1.0 / max(speed, 0.1)                   # higher = slower
        noise_scale_w = 0.8
        scales = np.array([[noise_scale, length_scale, noise_scale_w]], dtype=np.float32)

        # Build a candidate set for common Piper input name variants
        candidate_feed: dict = {
            # Standard VITS / Piper names
            "input":          input_ids,
            "input_ids":      input_ids,
            "text":           input_ids,
            "input_lengths":  input_len,
            "input_lengths0": input_len,
            "lengths":        input_len,
            "scales":         scales,
            "scales0":        scales,
        }
        if self._has_sid:
            sid = np.array([self.speaker_id], dtype=np.int64)
            candidate_feed["sid"]        = sid
            candidate_feed["speaker_id"] = sid
            candidate_feed["spk_id"]     = sid

        # Only pass tensors whose names actually exist in the graph
        feed = {name: candidate_feed[name]
                for name in self._input_names
                if name in candidate_feed}

        if len(feed) < len(self._input_names):
            missing = set(self._input_names) - set(feed)
            logger.warning(
                f"[VitsArTTS] Could not map graph inputs: {missing}. "
                "Attempting inference anyway — output may be garbage."
            )

        output = self._session.run(None, feed)[0]  # shape: (1, 1, T) or (1, T)
        audio  = output.squeeze()                   # → (T,)
        return audio.astype(np.float32)

    # ------------------------------------------------------------------ #
    # ITTSModel contract                                                  #
    # ------------------------------------------------------------------ #

    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """
        Synthesize Arabic *text* into raw float32 PCM audio bytes.

        Mirrors KokoroTTS.synthesize() and VitsJaTTS.synthesize() exactly:
          - Single yield per call (full sentence).
          - Trims leading/trailing silence.
          - Yields raw float32 little-endian bytes for SpeakerPlayer.play_stream().

        Parameters
        ----------
        text  : Arabic sentence to synthesize (diacritized or plain).
        speed : Speaking rate multiplier (1.0 = normal, 1.2 = faster).
        """
        if not text.strip():
            return

        try:
            ids = self._text_to_ids(text)
            if not ids:
                logger.warning("[VitsArTTS] Empty phoneme sequence — skipping synthesis.")
                return

            audio_np = self._infer(ids, speed)

            # Trim robotic silence from edges (same approach as KokoroTTS / VitsJaTTS)
            threshold = 0.005
            nonsilent = np.where(np.abs(audio_np) > threshold)[0]
            if len(nonsilent) > 0:
                pad   = 400  # ~18 ms lead-in/lead-out at 22 kHz
                start = max(0, nonsilent[0] - pad)
                end   = min(len(audio_np), nonsilent[-1] + pad)
                audio_np = audio_np[start:end]

            yield audio_np.tobytes()

        except Exception as exc:
            logger.error(f"[VitsArTTS] Error during synthesis for '{text[:60]}': {exc}")


# --------------------------------------------------------------------------- #
# Smoke test — run with: python modules/tts_vits_ar.py                        #
# Synthesizes a short Arabic sentence and writes it to test_vits_ar.wav.      #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    import soundfile as sf  # type: ignore

    # Resolve project root
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _root)

    from config import Config
    from modules.model_downloader import download_vits_ar_model
    from utils.ui import CLI

    print("=" * 60)
    print("VitsArTTS Smoke Test")
    print("=" * 60)

    with CLI.status("Downloading / verifying Arabic model…"):
        onnx_path, config_path = download_vits_ar_model(
            repo_id         = Config.VITS_AR_HF_REPO_ID,
            onnx_filename   = Config.VITS_AR_ONNX_FILE,
            config_filename = Config.VITS_AR_CONFIG_FILE,
            cache_dir       = Config.VITS_AR_CACHE_DIR,
            revision        = Config.VITS_AR_HF_REVISION,
            quantize        = Config.VITS_AR_QUANTIZE,
        )

    print(f"Using ONNX:   {onnx_path}")
    print(f"Using config: {config_path}")

    with CLI.status("Initializing VitsArTTS…"):
        tts = VitsArTTS(onnx_path, config_path, speaker_id=Config.VITS_AR_SPEAKER_ID)

    print(f"Model sample rate: {tts.output_sample_rate} Hz")

    test_text = "مرحباً، أنا مساعدك الصوتي. كيف يمكنني مساعدتك اليوم؟"
    print(f"Synthesizing: {test_text}")

    with CLI.status("Synthesizing…"):
        chunks = list(tts.synthesize(test_text, speed=1.0))

    if not chunks:
        print("❌ No audio produced. Check G2P output and phoneme_id_map.")
        sys.exit(1)

    audio_bytes = b"".join(chunks)
    audio_np    = np.frombuffer(audio_bytes, dtype=np.float32)
    out_path    = os.path.join(_root, "test_vits_ar_output.wav")
    sf.write(out_path, audio_np, tts.output_sample_rate)
    print(f"✅ Audio written to: {out_path} ({len(audio_np)} samples @ {tts.output_sample_rate} Hz)")
    print("Play it to verify Arabic speech quality.")
