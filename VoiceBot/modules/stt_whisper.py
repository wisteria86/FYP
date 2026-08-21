"""
Speech-to-Text Module.

This module provides a concrete implementation of the ISTTModel interface
using the `faster-whisper` library for rapid, local, offline transcription.
"""
# Path: modules/stt_whisper.py
import io
import os
import numpy as np
import soundfile as sf

# On Windows, let CTranslate2 reuse CUDA/cuDNN DLLs bundled with PyTorch.
try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
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
            compute_type = "float16" if resolved_device == "cuda" else "int8"
            self.model = WhisperModel(
                self.model_size,
                device=resolved_device,
                compute_type=compute_type,
                cpu_threads=max(1, cpu_threads),
                num_workers=max(1, num_workers),
            )
            logger.info("Faster-Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import ctranslate2
            return "cuda" in ctranslate2.get_supported_compute_types("cuda")
        except Exception:
            return False

    def transcribe(self, audio_data: bytes) -> str:
        """
        Converts WAV audio bytes to text using the faster-whisper model.

        Args:
            audio_data (bytes): The raw WAV audio data to transcribe.

        Returns:
            str: The transcribed text. Returns an empty string on failure.
        """
        try:
            logger.debug("Decoding audio bytes for faster-whisper...")
            
            wav_io = io.BytesIO(audio_data)
            segments, info = self.model.transcribe(
                wav_io,
                beam_size=3,
                condition_on_previous_text=False,
                vad_filter=True
            )
            # Short utterances from the tiny model often have avg_logprob below
            # -1 despite being valid. no_speech_prob is the appropriate guard.
            good_segments = [
                segment for segment in segments
                if getattr(segment, "no_speech_prob", 0.0) < 0.6
            ]
            text = "".join([s.text for s in good_segments]).strip()
            return text
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return ""
