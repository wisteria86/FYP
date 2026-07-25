# Path: core/async_interfaces.py
"""Asynchronous interface definitions for the voice assistant.
These mirror the synchronous interfaces in `core/interfaces.py` but use `async`
methods and `AsyncIterator` where appropriate. Keeping the original sync
interfaces untouched preserves backward compatibility.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Optional
import threading
import asyncio
import functools


class IAsyncAudioInput(ABC):
    """Async interface for capturing audio.
    The method yields raw PCM bytes as they become available.
    """

    @abstractmethod
    async def capture(self, on_speech_started: Optional[Callable] = None,
                     abort_event: Optional[threading.Event] = None,
                     silence_timeout: Optional[float] = None,
                     vad_threshold: float = 1.5) -> AsyncIterator[bytes]:
        """Yield audio chunks until speech ends or aborted."""
        raise NotImplementedError

    async def capture_in_executor(self, *args, **kwargs) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.capture, *args, **kwargs))


class IAsyncAudioOutput(ABC):
    """Async interface for playing audio."""

    @abstractmethod
    async def play(self, audio_stream: AsyncIterator[bytes],
                   cancel_event: Optional[threading.Event] = None) -> None:
        """Consume an async audio stream and playback.
        Implementations may run the actual playback in a thread pool.
        """
        raise NotImplementedError

    @abstractmethod
    async def play_once(self, audio_data: bytes) -> None:
        """Play a single pre‑recorded audio blob (convenience method)."""
        raise NotImplementedError

    async def play_in_executor(self, *args, **kwargs) -> None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.play, *args, **kwargs))


class IAsyncSTTModel(ABC):
    """Async interface for speech‑to‑text models."""

    @abstractmethod
    async def transcribe(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Yield transcription strings (often a single final result)."""
        raise NotImplementedError

    async def transcribe_in_executor(self, *args, **kwargs) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.transcribe, *args, **kwargs))


class IAsyncLLMModel(ABC):
    """Async interface for large language model back‑ends."""

    @abstractmethod
    async def generate(self, prompt: str) -> AsyncIterator[str]:
        """Yield token‑by‑token response for the given prompt."""
        raise NotImplementedError

    @abstractmethod
    async def generate_proactive(self, system_note: str) -> AsyncIterator[str]:
        """Yield a proactive response without a direct user prompt."""
        raise NotImplementedError

    async def generate_in_executor(self, *args, **kwargs) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.generate, *args, **kwargs))


class IAsyncTTSModel(ABC):
    """Async interface for text‑to‑speech models."""

    @abstractmethod
    async def synthesize(self, text: str, speed: float = 1.0) -> AsyncIterator[bytes]:
        """Yield audio byte chunks for the synthesized speech."""
        raise NotImplementedError

    async def synthesize_in_executor(self, *args, **kwargs) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.synthesize, *args, **kwargs))
