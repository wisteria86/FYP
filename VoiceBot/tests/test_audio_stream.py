import asyncio
import threading
import unittest
from services.audio_stream import audio_chunks


class AudioStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_chunk_does_not_wait_for_utterance_completion(self):
        release=threading.Event()
        def synthesize(text):
            yield b'first'
            if not release.wait(2):
                raise RuntimeError('Consumer waited for complete utterance')
            yield b'last'
        stream=audio_chunks(synthesize, 'Hello.')
        try:
            self.assertEqual(await asyncio.wait_for(anext(stream), 1), b'first')
            release.set()
            self.assertEqual(await anext(stream), b'last')
            with self.assertRaises(StopAsyncIteration):
                await anext(stream)
        finally:
            release.set()
            await stream.aclose()

    async def test_generator_errors_reach_transport(self):
        def synthesize(text):
            yield b'first'
            raise ValueError('synthesis failed')
        stream=audio_chunks(synthesize, 'Hello.')
        self.assertEqual(await anext(stream), b'first')
        with self.assertRaisesRegex(ValueError, 'synthesis failed'):
            await anext(stream)
