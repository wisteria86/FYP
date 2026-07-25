# Path: io_interfaces/mic_recorder.py
import io
import sounddevice as sd
import soundfile as sf
import numpy as np
import webrtcvad
import threading
from typing import Optional, Callable
from core.interfaces import IAudioInput
from utils.logger import get_logger

logger = get_logger(__name__)

class MicRecorder(IAudioInput):
    """
    Concrete implementation of audio input using the sounddevice library
    and WebRTC VAD for silence detection.
    """
    def __init__(self, sample_rate: int = 16000, channels: int = 1, record_seconds: int = 5):
        self.sample_rate = sample_rate
        self.channels = channels
        self.record_seconds = record_seconds # kept for compatibility
        self.vad = webrtcvad.Vad(1) # Reduced from 3 to 1 to make it more sensitive to speech
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * (self.frame_duration_ms / 1000.0))
        logger.info(f"Initialized MicRecorder with VAD (Rate: {self.sample_rate}Hz, Channels: {self.channels})")

    def capture_audio(self, on_speech_started: Optional[Callable] = None, abort_event: Optional[threading.Event] = None, silence_timeout: Optional[float] = None, vad_threshold: float = 1.5) -> Optional[bytes]:
        audio_buffer = []
        started_recording = False
        silence_frames = 0
        pre_speech_frames = 0
        consecutive_speech_frames = 0
        silence_threshold_seconds = vad_threshold
        silence_threshold_frames = int((silence_threshold_seconds * 1000) / self.frame_duration_ms)
        timeout_frames = int((silence_timeout * 1000) / self.frame_duration_ms) if silence_timeout else float('inf')

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, dtype='int16', blocksize=self.frame_size) as stream:
                while True:
                    if abort_event and abort_event.is_set():
                        return None
                        
                    data, overflowed = stream.read(self.frame_size)
                    if overflowed:
                        logger.warning("Audio buffer overflowed.")

                    audio_bytes = data.tobytes()
                    is_speech = self.vad.is_speech(audio_bytes, self.sample_rate)

                    if is_speech:
                        if not started_recording:
                            consecutive_speech_frames += 1
                            if consecutive_speech_frames > 2: # Require ~60ms of continuous speech to trigger
                                logger.info("🗣️ Speech detected, recording started!")
                                started_recording = True
                                if on_speech_started:
                                    on_speech_started()
                        else:
                            silence_frames = 0 # Any speech resets silence
                    else:
                        if not started_recording:
                            consecutive_speech_frames = 0
                        else:
                            silence_frames += 1

                    if started_recording:
                        audio_buffer.append(data)
                        if silence_frames > silence_threshold_frames:
                            logger.info("✅ Silence detected, recording complete.")
                            break
                    else:
                        pre_speech_frames += 1
                        if pre_speech_frames > timeout_frames:
                            raise TimeoutError("Silence timeout reached without detecting any speech.")
                                
            if not audio_buffer:
                return None
                
            audio_data = np.concatenate(audio_buffer, axis=0)
            wav_io = io.BytesIO()
            sf.write(wav_io, audio_data, self.sample_rate, format='WAV', subtype='PCM_16')
            return wav_io.getvalue()
            
        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to capture audio: {e}")
            return None