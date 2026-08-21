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
from collections import deque
from typing import Optional, Callable
from core.interfaces import IAudioInput
from utils.logger import get_logger

logger = get_logger(__name__)

class MicRecorder(IAudioInput):
    """
    Concrete implementation of audio input using the sounddevice library
    and WebRTC VAD for silence detection.
    """
    @staticmethod
    def _find_capture_rate(device: int, channels: int) -> int:
        for rate in (48000, 32000, 16000):
            try:
                sd.check_input_settings(
                    device=device,
                    channels=channels,
                    dtype="int16",
                    samplerate=rate,
                )
                return rate
            except Exception:
                pass
        raise RuntimeError("Microphone does not support a WebRTC-VAD-compatible sample rate.")

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        record_seconds: int = 5,
        device: Optional[str] = None,
    ) -> None:
        """
        Initializes the microphone recorder with Voice Activity Detection (VAD).

        Args:
            sample_rate (int): Legacy parameter, ignored. Capture rate is auto-detected.
            channels (int): Number of audio channels (default: 1 for mono).
            record_seconds (int): Legacy parameter for fixed-length recording (default: 5).
        """
        self.channels = channels
        self.record_seconds = record_seconds # kept for compatibility
        self.device = self._resolve_device(device)
        self.sample_rate = self._find_capture_rate(self.device, self.channels)
        self.vad = webrtcvad.Vad(1) # Mode 1 is less aggressive to avoid dropping valid consonants
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * (self.frame_duration_ms / 1000.0))
        
        info = sd.query_devices(self.device)
        hostapi = sd.query_hostapis(info["hostapi"])
        logger.info(
            "Microphone initialized:\n"
            f"  Name: {info['name']}\n"
            f"  Device ID: {self.device}\n"
            f"  Host API: {hostapi['name']}\n"
            f"  Channels: {info['max_input_channels']}\n"
            f"  Device default rate: {info['default_samplerate']} Hz\n"
            f"  Capture rate: {self.sample_rate} Hz"
        )

    @staticmethod
    def _resolve_device(configured_device: Optional[str]) -> int:
        """Resolve an input device and fail clearly when Windows exposes none."""
        devices = sd.query_devices()
        input_devices = [
            (index, item) for index, item in enumerate(devices)
            if item.get("max_input_channels", 0) > 0
        ]
        if not input_devices:
            raise RuntimeError(
                "No microphone is visible to VoiceBot. Windows/PortAudio reports zero "
                "input devices. Enable the microphone in Settings > System > Sound > "
                "Input and Settings > Privacy & security > Microphone, then restart."
            )

        if configured_device:
            try:
                index = int(configured_device)
                if any(candidate == index for candidate, _ in input_devices):
                    return index
            except ValueError:
                wanted = configured_device.casefold()
                for index, item in input_devices:
                    if wanted in item["name"].casefold():
                        return index
            available = ", ".join(f"{i}: {d['name']}" for i, d in input_devices)
            raise RuntimeError(
                f"MIC_DEVICE '{configured_device}' is not a valid input. Available: {available}"
            )

        default_input = sd.default.device[0]
        if isinstance(default_input, int) and default_input >= 0:
            return default_input
        return input_devices[0][0]

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
        # Preserve 300 ms before the VAD trigger so initial consonants are not lost.
        pre_roll = deque(maxlen=max(1, int(300 / self.frame_duration_ms)))
        started_recording = False
        silence_frames = 0
        pre_speech_frames = 0
        consecutive_speech_frames = 0
        recorded_chunks = 0
        silence_threshold_seconds = vad_threshold
        silence_threshold_frames = int((silence_threshold_seconds * 1000) / self.frame_duration_ms)
        timeout_frames = int((silence_timeout * 1000) / self.frame_duration_ms) if silence_timeout else float('inf')
        max_recording_frames = int((self.record_seconds * 1000) / self.frame_duration_ms) if self.record_seconds > 0 else int((60 * 1000) / self.frame_duration_ms)

        try:
            with sd.InputStream(device=self.device, samplerate=self.sample_rate, channels=self.channels, dtype='int16', blocksize=self.frame_size) as stream:
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
                            if consecutive_speech_frames >= 2: # Require exactly 60ms of continuous speech to trigger
                                logger.info("🗣️ Speech detected, recording started!")
                                started_recording = True
                                audio_buffer.extend(pre_roll)
                                if on_speech_started:
                                    threading.Thread(target=on_speech_started, daemon=True).start()
                        else:
                            silence_frames = 0 # Any speech resets silence
                    else:
                        if not started_recording:
                            consecutive_speech_frames = 0
                        else:
                            silence_frames += 1

                    if started_recording:
                        audio_buffer.append(data)
                        recorded_chunks += 1
                        if silence_frames > silence_threshold_frames:
                            logger.info("✅ Silence detected, recording complete.")
                            break
                        if recorded_chunks > max_recording_frames:
                            logger.info("⏳ Maximum recording duration reached, forcing cut-off.")
                            break
                    else:
                        pre_roll.append(data.copy())
                        pre_speech_frames += 1
                        if pre_speech_frames > timeout_frames:
                            raise TimeoutError("Silence timeout reached without detecting any speech.")
            if not audio_buffer:
                return None
                
            audio_data = np.concatenate(audio_buffer, axis=0)
            duration = len(audio_data) / self.sample_rate
            samples = audio_data.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(samples ** 2))
            peak = np.max(np.abs(samples))
            dbfs = 20 * np.log10(max(rms, 1e-9))
            logger.info(
                f"Captured {duration:.2f}s | "
                f"RMS={rms:.4f} | "
                f"dBFS={dbfs:.1f} | "
                f"Peak={peak:.3f}"
            )
            wav_io = io.BytesIO()
            sf.write(wav_io, audio_data, self.sample_rate, format='WAV', subtype='PCM_16')
            return wav_io.getvalue()
            
        except TimeoutError:
            raise
        except Exception:
            logger.exception("Failed to capture audio.")
            return None
