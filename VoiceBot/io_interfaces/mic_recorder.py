"""
Microphone Audio Input Module.

Provides a concrete implementation of the IAudioInput interface for capturing
audio directly from the system's default microphone. Utilizes WebRTC VAD
(Voice Activity Detection) to intelligently segment speech and detect silence.
"""
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
    def __init__(self, sample_rate: int = 16000, channels: int = 1, record_seconds: int = 5) -> None:
        """
        Initializes the microphone recorder with Voice Activity Detection (VAD).

        Args:
            sample_rate (int): Audio sampling rate in Hz (default: 16000, required by Whisper).
            channels (int): Number of audio channels (default: 1 for mono).
            record_seconds (int): Legacy parameter for fixed-length recording (default: 5).
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.record_seconds = record_seconds # kept for compatibility
        self.vad = webrtcvad.Vad(1) # Reduced from 3 to 1 to make it more sensitive to speech
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * (self.frame_duration_ms / 1000.0))
        logger.info(f"Initialized MicRecorder with VAD (Rate: {self.sample_rate}Hz, Channels: {self.channels})")

    def capture_audio(
        self, 
        on_speech_started: Optional[Callable] = None, 
        abort_event: Optional[threading.Event] = None, 
        silence_timeout: Optional[float] = None, 
        vad_threshold: float = 1.5
    ) -> Optional[bytes]:
        """
        Captures audio from the microphone until silence is detected.

        Uses WebRTC VAD to wait for speech to start, then records continuously until
        `vad_threshold` seconds of silence are detected. If `silence_timeout` is reached
        before any speech begins, a TimeoutError is raised.

        Args:
            on_speech_started (Optional[Callable]): Callback triggered when speech is first detected.
            abort_event (Optional[threading.Event]): If set, immediately stops recording and returns None.
            silence_timeout (Optional[float]): Max seconds to wait for speech before raising TimeoutError.
            vad_threshold (float): Seconds of continuous silence required to finalize the recording.

        Returns:
            Optional[bytes]: The captured WAV audio data, or None if aborted/failed.
        
        Raises:
            TimeoutError: If `silence_timeout` is exceeded before speech starts.
        """
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
            return audio_data.tobytes()
            
        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to capture audio: {e}")
            return None