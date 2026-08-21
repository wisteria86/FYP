"""
Speech-to-Text Module.

This module provides a concrete implementation of the ISTTModel interface
using the `faster-whisper` library for rapid, local, offline transcription.
"""
# Path: modules/stt_whisper.py
import io
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from core.interfaces import ISTTModel
from utils.logger import get_logger

logger = get_logger(__name__)

class WhisperSTT(ISTTModel):
    """
    Concrete implementation of the STT interface using faster-whisper.

    This class loads a pre-trained Whisper model and handles the conversion
    of raw audio bytes into transcribed text strings.
    """
    def __init__(self, model_size: str = "small.en") -> None:
        """
        Initializes the faster-whisper model.

        Args:
            model_size (str): The size/name of the Whisper model to load (e.g., 'tiny.en', 'small.en').
        """
        self.model_size = model_size
        logger.info(f"Loading faster-whisper model ('{model_size}'). This might take a moment...")
        
        try:
            # Using int8 computation for fast CPU performance
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info("Faster-Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

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
            
            # Read raw 16-bit PCM bytes (16kHz, 1-channel expected)
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            logger.info("Transcribing audio...")
            
            from config import Config
            lang = Config.COMMUNICATION_LANGUAGE.lower() if Config.COMMUNICATION_LANGUAGE else None
            
            # Map full names to ISO codes for Whisper
            lang_map = {
                "english": "en", "japanese": "ja", "spanish": "es", "french": "fr",
                "german": "de", "chinese": "zh", "korean": "ko", "italian": "it",
                "russian": "ru", "portuguese": "pt", "dutch": "nl", "arabic": "ar"
            }
            if lang in lang_map:
                lang = lang_map[lang]
                
            if lang == "auto" or lang not in lang_map.values():
                # Fallback to auto-detect if the string isn't a known ISO code
                if len(lang) != 2:
                    lang = None
                
            segments, info = self.model.transcribe(
                audio_array, 
                beam_size=5, 
                language=lang,
                condition_on_previous_text=False,
                initial_prompt="日常会話です。よろしくお願いします。",
                vad_filter=True,
                vad_parameters=dict(threshold=0.2, min_speech_duration_ms=200)
            )
            # Hallucination guard: ignore segments with very low confidence
            good_segments = [s for s in segments if s.avg_logprob > -1.0]
            text = "".join([s.text for s in good_segments]).strip()
            return text
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return ""