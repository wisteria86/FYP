# Path: core/async_pipeline.py
"""Asynchronous conversation pipeline orchestrator.
It uses the async interfaces defined in `core.async_interfaces` and wraps
the existing synchronous implementations with lightweight async adapters.
"""

import asyncio
import threading
from typing import Optional

from core.async_interfaces import (
    IAsyncAudioInput,
    IAsyncAudioOutput,
    IAsyncSTTModel,
    IAsyncLLMModel,
    IAsyncTTSModel,
)


class ConversationManager:
    """Orchestrates a single turn of voice interaction using async calls.

    The manager expects implementations that provide async wrapper methods
    (see modifications in `modules/*` and `io_interfaces/*`). The overall flow
    is:
        1. Capture audio (async)
        2. Transcribe (async)
        3. Generate LLM response (async)
        4. Synthesize TTS (async)
        5. Play audio (async)
    """

    def __init__(
        self,
        audio_in: IAsyncAudioInput,
        stt: IAsyncSTTModel,
        llm: IAsyncLLMModel,
        tts: IAsyncTTSModel,
        audio_out: IAsyncAudioOutput,
        *,
        abort_event: Optional[threading.Event] = None,
    ):
        self.audio_in = audio_in
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.audio_out = audio_out
        self.abort_event = abort_event or threading.Event()
        # Simple in‑memory conversation buffer (could be persisted later)
        self.history: list[dict] = []

    async def _run_turn(self):
        # 1. Capture audio from microphone (async wrapper returns bytes)
        audio_bytes = await self.audio_in.capture()
        if not audio_bytes:
            return

        # 2. Transcribe audio to text
        async for transcription in self.stt.transcribe(audio_bytes):
            user_text = transcription.strip()
            break  # our wrapper yields a single result
        else:
            return

        # Append user utterance to history for context (optional)
        self.history.append({"role": "user", "content": user_text})

        # 3. Generate LLM response (async wrapper yields full text)
        async for llm_chunk in self.llm.generate(user_text):
            # our wrapper yields a single chunk – the full response
            bot_response = llm_chunk.strip()
            break
        else:
            return

        # Append assistant response to history (trim later if needed)
        self.history.append({"role": "assistant", "content": bot_response})

        # 4. Synthesize speech (async yields audio bytes chunks)
        async for audio_chunk in self.tts.synthesize(bot_response):
            # 5. Play each chunk as it arrives
            await self.audio_out.play(audio_chunk)

    async def run(self):
        """Main loop – runs forever until the abort_event is set."""
        while not self.abort_event.is_set():
            try:
                await self._run_turn()
            except Exception as e:
                # Log via the standard logger (import lazily to avoid circular deps)
                from utils.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"Error in conversation turn: {e}")
                # Continue to next iteration
                await asyncio.sleep(0.1)

        # Clean shutdown
        from utils.logger import get_logger
        get_logger(__name__).info("Conversation manager stopped.")
