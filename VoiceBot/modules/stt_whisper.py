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
    """
    def __init__(self, model_size: str = "small.en"):
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
        """
        try:
            logger.debug("Decoding audio bytes for faster-whisper...")
            
            wav_io = io.BytesIO(audio_data)
            audio_array, sample_rate = sf.read(wav_io)

            if audio_array.ndim > 1:
                audio_array = np.mean(audio_array, axis=1)
            
            audio_array = audio_array.astype(np.float32)

            if sample_rate != 16000:
                logger.warning(f"Audio sample rate is {sample_rate}Hz, but Whisper expects 16000Hz. "
                               "Transcription accuracy may be degraded.")

            logger.info("Transcribing audio...")
            
            segments, info = self.model.transcribe(audio_array, beam_size=5)
            # Hallucination guard: ignore segments with very low confidence
            good_segments = [s for s in segments if s.avg_logprob > -1.0]
            text = "".join([s.text for s in good_segments]).strip()
            return text
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return ""