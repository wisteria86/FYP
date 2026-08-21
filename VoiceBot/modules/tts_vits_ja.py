"""
Japanese VITS ONNX Text-to-Speech Module.

Implements ITTSModel using a Piper-style VITS ONNX model (ayousanz/piper-plus-
tsukuyomi-chan) for Japanese speech synthesis. Integrates with ConversationManager's
streaming pipeline identically to KokoroTTS — same method signatures, same yield
pattern, same cancel_event awareness.

Pipeline per sentence:
  text → pyopenjtalk G2P → phoneme IDs (via config.json phoneme_id_map)
       → onnxruntime InferenceSession → float32 PCM → trim silence → yield bytes

The InferenceSession is configured for maximum CPU throughput:
  - All available logical cores via intra/inter_op_num_threads
  - ORT_ENABLE_ALL graph optimization
  - CPUExecutionProvider explicitly set (avoids fallback warning noise)
"""
# Path: modules/tts_vits_ja.py
import os
import json
import logging
from typing import Iterator

import numpy as np

from core.interfaces import ITTSModel
from utils.logger import get_logger

logger = get_logger(__name__)


class VitsJaTTS(ITTSModel):
    """
    Japanese TTS backed by a Piper-style VITS ONNX model.

    Mirrors KokoroTTS in interface contract so ConversationManager's tts_worker
    thread and audio_queue pipeline work without modification.

    Attributes
    ----------
    output_sample_rate : int
        The model's native audio sample rate (read from config.json).
        main.py reads this to initialize SpeakerPlayer at the correct rate.
    """

    def __init__(self, onnx_path: str, config_path: str, speaker_id: int = 0) -> None:
        """
        Load the ONNX model and parse the Piper-style config.

        Parameters
        ----------
        onnx_path  : Absolute path to the (optionally quantized) .onnx file.
        config_path: Absolute path to the accompanying config.json.
        speaker_id : Speaker index for multi-speaker models (0-indexed).
        """
        self.speaker_id = speaker_id

        # ------------------------------------------------------------------ #
        # Parse config.json — phoneme map + audio settings                   #
        # ------------------------------------------------------------------ #
        logger.info(f"Loading VITS config from: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # phoneme_id_map: {"a": [4], "i": [5], "^": [1], …}
        self.phoneme_id_map: dict = cfg.get("phoneme_id_map", {})
        if not self.phoneme_id_map:
            raise RuntimeError(
                "[VitsJaTTS] 'phoneme_id_map' is missing or empty in config.json. "
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
        logger.info(f"VITS model native sample rate: {self.output_sample_rate} Hz")

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
        # ------------------------------------------------------------------ #
        try:
            import onnxruntime as ort  # type: ignore
        except ImportError:
            raise RuntimeError(
                "[VitsJaTTS] 'onnxruntime' is not installed. Run: pip install onnxruntime"
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
            f"Loading VITS ONNX session: {onnx_path} "
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
                f"[VitsJaTTS] Failed to create ONNX InferenceSession from '{onnx_path}': {exc}"
            ) from exc

        # Inspect actual input/output names so we bind correctly regardless of
        # minor graph differences between model variants (MB-iSTFT-VITS2 vs VITS).
        self._input_names = [inp.name for inp in self._session.get_inputs()]
        self._output_names = [out.name for out in self._session.get_outputs()]
        logger.info(f"ONNX graph inputs:  {self._input_names}")
        logger.info(f"ONNX graph outputs: {self._output_names}")

        # Verify G2P library is available
        try:
            import pyopenjtalk  # type: ignore  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "[VitsJaTTS] 'pyopenjtalk' is not installed. Run: pip install pyopenjtalk"
            )

        logger.info("✅ VitsJaTTS initialized successfully.")

    # ------------------------------------------------------------------ #
    # Internal: text → phoneme ID sequence                                #
    # ------------------------------------------------------------------ #

    def _text_to_ids(self, text: str) -> list[int]:
        """
        Convert Japanese text to a Piper-style interleaved phoneme ID sequence.

        Format: [BOS, PAD, p1_id, PAD, p2_id, PAD, …, pN_id, PAD, EOS]

        pyopenjtalk.g2p returns space-separated ASCII phoneme labels that
        correspond to keys in the model's phoneme_id_map.
        """
        import pyopenjtalk  # type: ignore

        try:
            phoneme_str: str = pyopenjtalk.g2p(text, kana=False)
        except Exception as exc:
            logger.warning(f"[VitsJaTTS] pyopenjtalk G2P failed for '{text}': {exc}")
            return []

        phonemes = phoneme_str.split()

        ids: list[int] = [self._bos_id, self._pad_id]
        skipped = 0
        for p in phonemes:
            if p in self.phoneme_id_map:
                ids.extend(self.phoneme_id_map[p])
                ids.append(self._pad_id)
            else:
                skipped += 1
                logger.debug(f"[VitsJaTTS] Unknown phoneme skipped: '{p}'")

        ids.append(self._eos_id)

        if skipped:
            logger.debug(f"[VitsJaTTS] {skipped}/{len(phonemes)} phonemes not in map.")

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
        input_ids   = np.array([ids], dtype=np.int64)          # (1, T)
        input_len   = np.array([len(ids)], dtype=np.int64)     # (1,)
        noise_scale = 0.667
        length_scale = 1.0 / max(speed, 0.1)                   # higher = slower
        noise_scale_w = 0.8
        scales = np.array([noise_scale, length_scale, noise_scale_w], dtype=np.float32)

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
            candidate_feed["sid"] = sid
            candidate_feed["speaker_id"] = sid
            candidate_feed["spk_id"] = sid

        # Piper-plus multi-speaker / multi-lingual features (dummy values)
        candidate_feed["lid"] = np.array([0], dtype=np.int64)
        candidate_feed["prosody_features"] = np.zeros((1, len(ids), 3), dtype=np.int64)
        candidate_feed["speaker_embedding"] = np.zeros((1, 256), dtype=np.float32)
        candidate_feed["speaker_embedding_mask"] = np.zeros((1, 1), dtype=np.int64)

        # Only pass tensors whose names actually exist in the graph
        feed = {name: candidate_feed[name]
                for name in self._input_names
                if name in candidate_feed}

        if len(feed) < len(self._input_names):
            missing = set(self._input_names) - set(feed)
            logger.warning(
                f"[VitsJaTTS] Could not map graph inputs: {missing}. "
                "Attempting inference anyway — output may be garbage."
            )

        output = self._session.run(None, feed)[0]  # shape: (1, 1, T) or (1, T)
        audio = output.squeeze()                   # → (T,)
        return audio.astype(np.float32)

    # ------------------------------------------------------------------ #
    # ITTSModel contract                                                  #
    # ------------------------------------------------------------------ #

    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """
        Synthesize Japanese *text* into raw float32 PCM audio bytes.

        Mirrors KokoroTTS.synthesize() exactly:
          - Single yield per call (full sentence).
          - Trims leading/trailing silence.
          - Yields raw float32 little-endian bytes for SpeakerPlayer.play_stream().

        Parameters
        ----------
        text  : Japanese sentence to synthesize.
        speed : Speaking rate multiplier (1.0 = normal, 1.2 = faster).
        """
        if not text.strip():
            return

        try:
            ids = self._text_to_ids(text)
            if not ids:
                logger.warning("[VitsJaTTS] Empty phoneme sequence — skipping synthesis.")
                return

            audio_np = self._infer(ids, speed)

            # Trim robotic silence from edges (same approach as KokoroTTS)
            threshold = 0.005
            nonsilent = np.where(np.abs(audio_np) > threshold)[0]
            if len(nonsilent) > 0:
                pad = 400  # ~18 ms of lead-in/lead-out at 22 kHz
                start = max(0, nonsilent[0] - pad)
                end   = min(len(audio_np), nonsilent[-1] + pad)
                audio_np = audio_np[start:end]

            yield audio_np.tobytes()

        except Exception as exc:
            logger.error(f"[VitsJaTTS] Error during synthesis for '{text}': {exc}")


# --------------------------------------------------------------------------- #
# Smoke test — run with: python modules/tts_vits_ja.py                        #
# Synthesizes a short Japanese sentence and writes it to test_vits_ja.wav.    #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    import soundfile as sf  # type: ignore

    # Resolve project root
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _root)

    from config import Config
    from modules.model_downloader import download_vits_ja_model
    from utils.ui import CLI

    print("=" * 60)
    print("VitsJaTTS Smoke Test")
    print("=" * 60)

    with CLI.status("Downloading / verifying model…"):
        onnx_path, config_path = download_vits_ja_model(
            repo_id        = Config.VITS_JA_HF_REPO_ID,
            onnx_filename  = Config.VITS_JA_ONNX_FILE,
            config_filename= Config.VITS_JA_CONFIG_FILE,
            cache_dir      = Config.VITS_JA_CACHE_DIR,
            revision       = Config.VITS_JA_HF_REVISION,
            quantize       = Config.VITS_JA_QUANTIZE,
        )

    print(f"Using ONNX: {onnx_path}")
    print(f"Using config: {config_path}")

    with CLI.status("Initializing VitsJaTTS…"):
        tts = VitsJaTTS(onnx_path, config_path, speaker_id=Config.VITS_JA_SPEAKER_ID)

    print(f"Model sample rate: {tts.output_sample_rate} Hz")

    test_text = "こんにちは、私はVoiceBotです。今日は何を勉強しますか？"
    print(f"Synthesizing: {test_text}")

    with CLI.status("Synthesizing…"):
        chunks = list(tts.synthesize(test_text, speed=1.0))

    if not chunks:
        print("❌ No audio produced. Check G2P output and phoneme_id_map.")
        sys.exit(1)

    audio_bytes = b"".join(chunks)
    audio_np = np.frombuffer(audio_bytes, dtype=np.float32)
    out_path = os.path.join(_root, "test_vits_ja_output.wav")
    sf.write(out_path, audio_np, tts.output_sample_rate)
    print(f"✅ Audio written to: {out_path} ({len(audio_np)} samples @ {tts.output_sample_rate} Hz)")
    print("Play it to verify Japanese speech quality.")
