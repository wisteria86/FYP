"""Bridge blocking TTS generators to async transport without buffering a reply."""
import asyncio
import threading


async def audio_chunks(synthesize, text):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    cancelled = threading.Event()

    def produce():
        try:
            for pcm in synthesize(text):
                if cancelled.is_set():
                    break
                if pcm:
                    loop.call_soon_threadsafe(queue.put_nowait, ('audio', pcm))
        except Exception as exc:
            if not cancelled.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, ('error', exc))
        finally:
            if not cancelled.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, ('done', None))

    worker = loop.run_in_executor(None, produce)
    try:
        while True:
            kind, value = await queue.get()
            if kind == 'done':
                break
            if kind == 'error':
                raise value
            yield value
        await worker
    finally:
        cancelled.set()
