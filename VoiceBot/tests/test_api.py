import os
import io
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

os.environ["HIKARI_SKIP_MODELS"] = "true"

from fastapi.testclient import TestClient

import api.server as server
from core.training_service import TrainingService


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_training = server.training
        server.training = TrainingService(Path(self.temp.name) / "api.db")
        self.client = TestClient(server.app)
        server.metrics.reset()

    def tearDown(self):
        self.client.close()
        server.training = self.original_training
        server._tts_model = None
        self.temp.cleanup()

    def test_roleplay_assessment_dashboard_and_upload(self):
        created = self.client.post("/api/sessions", json={"skill_id": "active-listening", "difficulty": "beginner"})
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["id"]
        reply = self.client.post(f"/api/sessions/{session_id}/turn", json={"text": "I understand your concern. Could you explain when the problem started?"})
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()["text"])
        result = self.client.post(f"/api/sessions/{session_id}/complete")
        self.assertEqual(result.status_code, 200)
        self.assertIn("scores", result.json())
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["completed_sessions"], 1)
        document = self.client.post("/api/documents", files={"file": ("policy.txt", b"Verify urgent access requests with a manager.", "text/plain")}, data={"user_id": "demo"})
        self.assertEqual(document.status_code, 200)
        self.assertEqual(len(self.client.get("/api/documents").json()), 1)
        mic = self.client.post("/api/monitor/microphone", json={"event": "transcribed", "device": "Test microphone", "duration_ms": 321, "peak_percent": 64, "transcript": "Please confirm the deadline."})
        self.assertEqual(mic.status_code, 200)
        monitor = self.client.get("/api/monitor/snapshot")
        self.assertEqual(monitor.status_code, 200)
        telemetry = monitor.json()
        self.assertGreaterEqual(telemetry["http"]["requests"], 6)
        self.assertEqual(telemetry["pipeline"]["latest_roleplay"]["category"], "roleplay")
        self.assertIn("process_rss_mb", telemetry["system"])
        self.assertEqual(telemetry["recent"][0]["transcript"], "Please confirm the deadline.")

    def test_streamed_tts_returns_audio_and_merges_turn_metrics(self):
        class FakeTTS:
            def synthesize_streaming(self, text, speed=1.0):
                yield np.zeros(2400, dtype=np.float32).tobytes()
                yield np.zeros(1200, dtype=np.float32).tobytes()

        created = self.client.post("/api/sessions", json={"skill_id": "active-listening"}).json()
        turn = self.client.post(
            f"/api/sessions/{created['id']}/turn",
            json={"text": "Could you clarify that?", "synthesize_audio": False},
        ).json()
        server._tts_model = FakeTTS()
        streamed = self.client.post(
            "/api/tts/stream",
            json={"text": turn["text"], "correlation_id": turn["correlation_id"]},
        )
        self.assertEqual(streamed.status_code, 200)
        events = [line for line in streamed.text.splitlines() if line]
        self.assertEqual(len(events), 3)
        self.assertIn('"type": "audio"', events[0])
        self.assertIn('"type": "done"', events[-1])
        latest = self.client.get("/api/monitor/snapshot").json()["pipeline"]["latest_roleplay"]
        self.assertEqual(latest["tts_chunks"], 2)
        self.assertIsNotNone(latest["first_audio_total_ms"])

    def test_private_reasoning_can_never_reach_display_or_tts(self):
        self.assertEqual(
            server._public_reply("<think>private chain</think> Please confirm the deadline."),
            "Please confirm the deadline.",
        )
        self.assertEqual(server._public_reply("<think>unfinished private chain"), "")
        self.assertEqual(server._public_reply("A normal spoken reply."), "A normal spoken reply.")

    def test_audio_buffer_edges_are_faded_to_prevent_clicks(self):
        wav_bytes = server._pcm_to_wav(np.ones(1000, dtype=np.float32).tobytes(), 24000)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[-1], 0)
        self.assertGreater(samples[len(samples) // 2], 30000)


if __name__ == "__main__":
    unittest.main()
