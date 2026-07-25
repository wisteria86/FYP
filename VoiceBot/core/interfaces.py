# Path: core/interfaces.py
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Callable
import threading

class IAudioInput(ABC):
    """Interface for capturing audio from a source."""
    @abstractmethod
    def capture_audio(self, on_speech_started: Optional[Callable] = None, abort_event: Optional[threading.Event] = None, silence_timeout: Optional[float] = None, vad_threshold: float = 1.5) -> Optional[bytes]:
        pass

class IAudioOutput(ABC):
    """Interface for playing audio back to the user."""
    @abstractmethod
    def play_audio(self, audio_data: bytes) -> None:
        pass

    @abstractmethod
    def play_stream(self, audio_chunks: Iterator[bytes], cancel_event: Optional[threading.Event] = None) -> None:
        pass

class ISTTModel(ABC):
    """Interface for Speech-to-Text models."""
    @abstractmethod
    def transcribe(self, audio_data: bytes) -> str:
        pass

class ILLMModel(ABC):
    """Interface for Large Language Models."""
    @abstractmethod
    def generate_response(self, text: str) -> Iterator[str]:
        pass

    @abstractmethod
    def generate_proactive_response(self, system_note: str) -> Iterator[str]:
        pass

    @abstractmethod
    def save_profile(self, new_summary: str, new_goal: Optional[str] = None):
        pass

class ITTSModel(ABC):
    """Interface for Text-to-Speech models."""
    @abstractmethod
    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        pass