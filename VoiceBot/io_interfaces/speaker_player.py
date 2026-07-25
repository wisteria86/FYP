# Path: io_interfaces/speaker_player.py
import io
import sounddevice as sd
import soundfile as sf
import numpy as np
from typing import Iterator, Optional
import threading
from core.interfaces import IAudioOutput
from utils.logger import get_logger

logger = get_logger(__name__)

class SpeakerPlayer(IAudioOutput):
    """
    Concrete implementation for playing audio out of speakers
    using the sounddevice library.
    """
    def __init__(self):
        self.sample_rate = 24000
        self.channels = 1
        logger.info("Initialized SpeakerPlayer.")

    def play_audio(self, audio_data: bytes) -> None:
        """
        Plays WAV formatted audio bytes through the default system speakers.
        """
        if not audio_data:
            logger.warning("No audio data provided to play.")
            return
            
        try:
            logger.debug("🔊 Playing audio response...")
            try:
                wav_io = io.BytesIO(audio_data)
                audio_array, sample_rate = sf.read(wav_io)
            except Exception as format_err:
                logger.warning(f"WAV header not recognized, falling back to raw PCM ({format_err})")
                audio_array = np.frombuffer(audio_data, dtype=np.float32)
                sample_rate = 24000
            
            sd.play(audio_array, sample_rate)
            sd.wait()
            logger.debug("✅ Audio playback complete.")
            
        except Exception as e:
            logger.error(f"Failed to play audio through speakers: {e}")

    def play_stream(self, audio_stream: Iterator[bytes], cancel_event: Optional[threading.Event] = None) -> None:
        """
        Plays streaming raw PCM audio chunks via speakers.
        Abortable in real-time if cancel_event is set.
        """
        try:
            with sd.OutputStream(samplerate=self.sample_rate, channels=self.channels, dtype='float32') as stream:
                for chunk in audio_stream:
                    if cancel_event and cancel_event.is_set():
                        break
                        
                    # Slice the chunk into tiny segments (e.g. 50ms) to allow rapid cancellation mid-chunk
                    chunk_np = np.frombuffer(chunk, dtype=np.float32)
                    segment_size = int(self.sample_rate * 0.05)
                    
                    for i in range(0, len(chunk_np), segment_size):
                        if cancel_event and cancel_event.is_set():
                            break
                        segment = chunk_np[i:i+segment_size]
                        # Ensure correct shape (N, channels)
                        segment = segment.reshape(-1, 1)
                        stream.write(segment)
                        
                    if cancel_event and cancel_event.is_set():
                        break
                        
        except Exception as e:
            logger.error(f"Error playing audio stream: {e}")