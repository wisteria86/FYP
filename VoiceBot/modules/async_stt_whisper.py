# Path: modules/async_stt_whisper.py
"""Async wrapper for the WhisperSTT model.
Implements the IAsyncSTTModel interface using run_in_executor to
execute the synchronous transcribe method without blocking the event loop.
"""

import asyncio
from typing import AsyncIterator

from core.async_interfaces import IAsyncSTTModel
from modules.stt_whisper import WhisperSTT

class AsyncWhisperSTT(IAsyncSTTModel):
    """Asynchronous STT model that delegates to WhisperSTT.
    The async ``transcribe`` method accepts an async iterator of audio
    byte chunks, concatenates them, and then runs the original
    ``WhisperSTT.transcribe`` method in a thread pool.
    """

    def __init__(self, model_size: str = "small.en"):
        self._sync_impl = WhisperSTT(model_size)

    async def transcribe(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        # Gather all incoming audio chunks into a single bytes object.
        audio_data = b""
        async for chunk in audio_chunks:
            audio_data += chunk
        loop = asyncio.get_running_loop()
        # Run the blocking transcribe method in the default executor.
        result = await loop.run_in_executor(None, self._sync_impl.transcribe, audio_data)
        # Yield the result as a single item to satisfy the async iterator contract.
        yield result
