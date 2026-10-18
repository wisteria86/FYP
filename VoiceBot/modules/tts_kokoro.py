"""
Text-to-Speech Module.

This module provides a high-performance implementation of the ITTSModel interface
using the Kokoro-ONNX runtime. It generates extremely fast, natural-sounding
speech locally without requiring a GPU or network access.
"""
# Path: modules/tts_kokoro.py
import os
import re
import time
import threading
import urllib.request
import numpy as np
from typing import Iterator
from core.interfaces import ITTSModel
from utils.logger import get_logger
from utils.ui import CLI
from kokoro_onnx import Kokoro

logger = get_logger(__name__)

class _TimedCalls:
    """Delegate to a runtime object, timing selected calls on the current thread."""
    def __init__(self, target, method, key, local):
        self._target, self._method, self._key, self._local = target, method, key, local

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name != self._method:
            return value
        def measured(*args, **kwargs):
            started = time.perf_counter()
            try:
                return value(*args, **kwargs)
            finally:
                timing = getattr(self._local, 'current', None)
                if timing is not None:
                    timing[self._key] = timing.get(self._key, 0) + (time.perf_counter() - started) * 1000
        return measured


class _TimedPCM(bytes):
    def __new__(cls, pcm, timing):
        instance = super().__new__(cls, pcm)
        instance.timing = timing
        return instance


class KokoroTTS(ITTSModel):
    """
    High-performance TTS implementation using Kokoro-ONNX.
    
    Supports incremental synthesis. It manages the downloading
    and loading of the ONNX models automatically upon instantiation.
    """
    
    @property
    def output_sample_rate(self) -> int:
        return 24000
        
    def __init__(self, lang: str = "a", voice: str = "af_heart") -> None:
        """
        Initializes the Kokoro TTS engine and ensures models are present.

        Args:
            lang (str): The language code (e.g., 'a' for American English).
            voice (str): The specific voice model to use (e.g., 'af_heart').
        """
        self.lang = "en-us" if lang == "a" else lang
        self.voice = voice
        self._inference_lock=threading.Lock()
        self._timing_local = threading.local()
        
        # Ensure models directory exists
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        custom_model = os.getenv("KOKORO_MODEL_PATH", "").strip()
        self._custom_model = bool(custom_model)
        self.model_path = (
            os.path.abspath(os.path.expanduser(custom_model)) if custom_model
            else os.path.join(self.models_dir, "kokoro-v1.0.onnx")
        )
        self.chunk_chars = int(os.getenv("KOKORO_CHUNK_CHARS", "180"))
        if self.chunk_chars < 1:
            raise ValueError("KOKORO_CHUNK_CHARS must be positive")
        self.voices_path = os.path.join(self.models_dir, "voices-v1.0.bin")
        
        self._ensure_models_downloaded()
        
        try:
            with CLI.status("Loading Kokoro-ONNX TTS Model...", spinner="dots"):
                if hasattr(Kokoro,'from_session'):
                    import onnxruntime as ort
                    options=ort.SessionOptions()
                    threads = int(os.getenv("KOKORO_CPU_THREADS", "0"))
                    if threads < 0:
                        raise ValueError("KOKORO_CPU_THREADS must be zero (automatic) or positive")
                    options.intra_op_num_threads = threads
                    options.inter_op_num_threads=1
                    from kokoro_onnx.session import resolve_providers
                    providers = resolve_providers()
                    requested = os.getenv("ONNX_PROVIDER")
                    if requested and requested not in ort.get_available_providers():
                        raise ValueError(f"ONNX_PROVIDER={requested} is unavailable")
                    session=ort.InferenceSession(self.model_path,sess_options=options,providers=providers)
                    logger.info(
                        "Kokoro model=%s bytes=%s ORT=%s providers=%s threads=%s",
                        self.model_path, os.path.getsize(self.model_path), ort.__version__,
                        session.get_providers(), threads,
                    )
                    self.kokoro=Kokoro.from_session(session,self.voices_path)
                else:
                    self.kokoro=Kokoro(self.model_path,self.voices_path)
            self.kokoro.sess = _TimedCalls(self.kokoro.sess, 'run', 'onnx_inference_ms', self._timing_local)
            self.kokoro.tokenizer = _TimedCalls(self.kokoro.tokenizer, 'phonemize', 'phonemization_ms', self._timing_local)
            logger.info("Initialized Kokoro-ONNX TTS Engine.")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro-ONNX: {e}")
            raise

    def _download_with_retry(self, url, dest, expected_size, max_retries=3):
        """Robust downloader with retries and size validation."""
        for attempt in range(max_retries):
            try:
                # If file exists but is way too small, it's a corrupted/partial download
                if os.path.exists(dest) and os.path.getsize(dest) < expected_size:
                    os.remove(dest)
                    
                if not os.path.exists(dest):
                    urllib.request.urlretrieve(url, dest)
                    logger.info(f"Downloaded successfully to {dest}")
                return # Success
                
            except urllib.error.ContentTooShortError:
                logger.warning(f"Connection dropped during download (attempt {attempt + 1}/{max_retries}). Retrying...")
            except Exception as e:
                logger.warning(f"Download error: {e}. Retrying...")
                
        raise Exception(f"Failed to download {url} after {max_retries} attempts. Please check your internet connection.")

    def _ensure_models_downloaded(self):
        """Downloads the ONNX models if they don't exist or are corrupted."""
        model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
        
        # model is ~325MB, voices is ~80MB. We use safe minimums to detect partial downloads.
        if self._custom_model:
            if not os.path.isfile(self.model_path) or os.path.getsize(self.model_path) == 0:
                raise FileNotFoundError(f"KOKORO_MODEL_PATH is missing or empty: {self.model_path}")
        elif not os.path.exists(self.model_path) or os.path.getsize(self.model_path) < 300_000_000:
            with CLI.status("Downloading kokoro-v1.0.onnx (325MB - This may take a while)...", spinner="arrow3"):
                self._download_with_retry(model_url, self.model_path, 300_000_000)
                
        if not os.path.exists(self.voices_path) or os.path.getsize(self.voices_path) < 2_000_000:
            with CLI.status("Downloading voices-v1.0.bin (3MB)...", spinner="arrow3"):
                self._download_with_retry(voices_url, self.voices_path, 2_000_000)

    def _text_chunks(self, text: str) -> Iterator[str]:
        """Group short sentences; split long replies near the chunk limit."""
        remaining = text.strip()
        while len(remaining) > self.chunk_chars:
            window = remaining[:self.chunk_chars + 1]
            boundaries = [
                match.start() for match in re.finditer(r"(?<=[.!?;])\s+", window)
                if match.start() >= self.chunk_chars // 2
            ]
            split = boundaries[-1] if boundaries else remaining.rfind(" ", 0, self.chunk_chars + 1)
            if split <= 0:
                split = self.chunk_chars
            yield remaining[:split]
            remaining = remaining[split:].lstrip()
        if remaining:
            yield remaining

    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """Yield playable PCM as each bounded text chunk finishes synthesis."""
        for chunk in self._text_chunks(text):
            yield from self._synthesize_chunk(chunk, speed)

    def _synthesize_chunk(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """
        Synthesizes text into streaming audio bytes using the ONNX model.

        Generates audio for one bounded text chunk. It strips any
        synthetic robotic silence from the edges before yielding the raw audio bytes.

        Args:
            text (str): The string of text to convert to speech.
            speed (float): Playback speed multiplier (default: 1.0).

        Yields:
            bytes: The synthesized raw PCM audio data.
        """
        try:
            text_or_phonemes = text
            is_phonemes = False

            if self.lang == "j":
                try:
                    from misaki import ja
                    g2p = ja.JAG2P()
                    text_or_phonemes, _ = g2p(text)
                    is_phonemes = True
                except ImportError:
                    logger.warning("misaki[ja] is not installed. Japanese TTS may fail. Please run `pip install misaki[ja] unidic-lite`.")

            # Bound CPU work and avoid overlapping inference on the shared
            # voice engine when several playback requests arrive together.
            started = time.perf_counter()
            with self._inference_lock:
                acquired = time.perf_counter()
                timing = {'onnx_inference_ms': 0.0, 'phonemization_ms': 0.0}
                self._timing_local.current = timing
                try:
                    samples, sample_rate = self.kokoro.create(
                        text_or_phonemes,voice=self.voice,speed=speed,
                        lang=self.lang,is_phonemes=is_phonemes
                    )
                finally:
                    self._timing_local.current = None
                synthesis_ms = (time.perf_counter() - acquired) * 1000
                timing.update(
                    lock_wait_ms=(acquired - started) * 1000,
                    synthesis_ms=synthesis_ms,
                    other_synthesis_ms=max(0, synthesis_ms - timing['onnx_inference_ms'] - timing['phonemization_ms']),
                    chars=len(text), audio_seconds=len(samples) / sample_rate,
                )
            
            logger.debug(
                "Kokoro chars=%s lock_wait_ms=%.1f synthesis_ms=%.1f audio_seconds=%.2f",
                len(text), (acquired - started) * 1000,
                (time.perf_counter() - acquired) * 1000, len(samples) / sample_rate,
            )
            # The samples are already a numpy array of floats
            audio_np = np.array(samples, dtype=np.float32)
            
            # Trim silence (robotic padding) from the ends
            threshold = 0.01
            non_silent_indices = np.where(np.abs(audio_np) > threshold)[0]
            if len(non_silent_indices) > 0:
                start_idx = max(0, non_silent_indices[0] - 200) # Leave a tiny pad
                end_idx = min(len(audio_np), non_silent_indices[-1] + 200)
                audio_np = audio_np[start_idx:end_idx]
                
            timing = {key: round(value, 2) for key, value in timing.items()}
            logger.info("Kokoro timing %s", timing)
            yield _TimedPCM(audio_np.tobytes(), timing)
            
        except Exception as e:
            logger.error(f"Error during TTS synthesis stream: {e}")
            raise
