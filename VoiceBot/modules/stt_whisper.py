"""
Speech-to-Text Module.

This module provides a concrete implementation of the ISTTModel interface
using the `faster-whisper` library for rapid, local, offline transcription.
"""
# Path: modules/stt_whisper.py
import io
import math
import os
import site
import importlib.util
import numpy as np
import soundfile as sf

# Keep DLL directory handles alive; closing them removes the search path.
_cuda_dll_handles = []
_torch_spec = importlib.util.find_spec("torch")
_bundled_cudnn = bool(_torch_spec and _torch_spec.origin and os.path.isfile(
    os.path.join(os.path.dirname(_torch_spec.origin), "lib", "cudnn64_9.dll")
))
if os.name == "nt":
    for package_root in site.getsitepackages():
        for library in ("cublas", "cudnn", "cuda_nvrtc"):
            # Mixing different cuDNN 9 sublibrary versions in one process
            # breaks both engines. Prefer PyTorch's complete matching set.
            if library == "cudnn" and _bundled_cudnn:
                continue
            library_dir = os.path.join(package_root, "nvidia", library, "bin")
            if os.path.isdir(library_dir):
                _cuda_dll_handles.append(os.add_dll_directory(library_dir))
                os.environ["PATH"] = library_dir + os.pathsep + os.environ.get("PATH", "")

# PyTorch may bundle a different CUDA major version, so also register the
# separate CUDA 12 wheels above for CTranslate2.
try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        _cuda_dll_handles.append(os.add_dll_directory(_torch_lib))
except Exception:
    pass

from faster_whisper import WhisperModel
from core.interfaces import ISTTModel
from utils.logger import get_logger
from config import Config

logger = get_logger(__name__)

class WhisperSTT(ISTTModel):
    """
    Concrete implementation of the STT interface using faster-whisper.

    This class loads a pre-trained Whisper model and handles the conversion
    of raw audio bytes into transcribed text strings.
    """
    def __init__(
        self,
        model_size: str = "tiny",
        cpu_threads: int = 4,
        num_workers: int = 1,
        device: str = "auto",
    ) -> None:
        """
        Initializes the faster-whisper model.

        Args:
            model_size (str): The size/name of the Whisper model to load (e.g., 'tiny.en', 'small.en').
        """
        self.model_size = model_size
        logger.info(f"Loading faster-whisper model ('{model_size}'). This might take a moment...")
        
        try:
            # Using int8 computation for fast CPU performance
            resolved_device = "cuda" if device == "auto" and self._cuda_available() else device
            if resolved_device == "auto":
                resolved_device = "cpu"
            compute_type = Config.WHISPER_COMPUTE_TYPE
            if compute_type == "auto":
                compute_type = "int8_float16" if resolved_device == "cuda" else "int8"
            if resolved_device == 'cpu' and compute_type in {'float16','int8_float16','bfloat16','int8_bfloat16'}:
                compute_type = 'int8'
            self.device = resolved_device
            self.compute_type = compute_type
            self.model = WhisperModel(
                self.model_size,
                device=resolved_device,
                compute_type=compute_type,
                cpu_threads=max(1, cpu_threads),
                num_workers=max(1, num_workers),
                download_root=Config.WHISPER_CACHE_DIR,
            )
            if resolved_device == "cuda":
                # Initialize CUDA/cuDNN during startup, not the learner's first
                # utterance. This also catches missing runtime DLLs immediately.
                segments, _ = self.model.transcribe(
                    np.zeros(16000, dtype=np.float32), language="en",
                    vad_filter=False, beam_size=1, condition_on_previous_text=False,
                )
                list(segments)
            logger.info("Faster-Whisper model loaded successfully.")
            logger.info("Whisper runtime: model=%s device=%s precision=%s", self.model_size, self.device, self.compute_type)
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import ctranslate2
            return bool(ctranslate2.get_supported_compute_types("cuda"))
        except Exception:
            return False

    def transcribe_detailed(self, audio_data: bytes, language: str | None = None,
                            initial_prompt: str | None = None) -> dict:
        """
        Converts WAV audio bytes to text using the faster-whisper model.

        Args:
            audio_data (bytes): The raw WAV audio data to transcribe.

        Returns:
            str: The transcribed text. Returns an empty string on failure.
        """
        try:
            logger.debug("Decoding audio bytes for faster-whisper...")
            
            def decode(vad_filter: bool) -> dict:
                # A fresh buffer is required because the decoder consumes it.
                segments, info = self.model.transcribe(
                    io.BytesIO(audio_data),
                    beam_size=5,
                    task="transcribe",
                    temperature=0.0,
                    condition_on_previous_text=False,
                    vad_filter=vad_filter,
                    language=language,
                    initial_prompt=initial_prompt,
                    word_timestamps=False,
                )
                good_segments = [
                    segment for segment in segments
                    if getattr(segment, "no_speech_prob", 0.0) < 0.75
                ]
                text = "".join(segment.text for segment in good_segments).strip()
                log_probs = [getattr(segment, "avg_logprob", -0.7) for segment in good_segments]
                confidence = math.exp(sum(log_probs) / len(log_probs)) if log_probs else 0.0
                return {
                    "text": text,
                    "confidence": round(max(0.0, min(1.0, confidence)), 3),
                    "detected_language": getattr(info, "language", language),
                    "language_probability": round(float(getattr(info, "language_probability", 1.0 if language else 0.0)), 3),
                }

            # Browser calls are already trimmed by the client VAD. Faster-Whisper's
            # VAD can reject a quiet, short sentence a second time, so retry the
            # same recording without it before reporting "No speech detected".
            result = decode(vad_filter=True)
            return result if result["text"] else decode(vad_filter=False)
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            # A broken CUDA runtime is not the same as an empty microphone.
            raise RuntimeError("Speech recognition failed; check the backend speech diagnostics.") from e

    def runtime_info(self) -> dict:
        return {"model": self.model_size, "device": self.device,
                "compute_type": self.compute_type, "task": "transcribe"}

    def transcribe(self, audio_data: bytes) -> str:
        """Compatibility text-only transcription API."""
        return self.transcribe_detailed(audio_data)["text"]
