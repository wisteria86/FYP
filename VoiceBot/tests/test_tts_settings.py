import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ["HIKARI_SKIP_MODELS"] = "true"

from config import Config
import api.server as server


class TTSSettingsTests(unittest.TestCase):
    def setUp(self):
        self._runtime_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self._original_settings_path = server._settings_path
        self._original_engine = server._engine_name
        self._original_model = server._tts_model
        self._original_sample_rate = server._tts_sample_rate
        server._settings_path = Path(self._runtime_dir.name) / "runtime_settings.json"
        server._engine_name = "kokoro"
        server._tts_model = None
        server._tts_sample_rate = 24000
        self.client = TestClient(server.app)

    def tearDown(self):
        self.client.close()
        model = server._tts_model
        if model is not None and model is not self._original_model and hasattr(model, "close"):
            model.close()
        server._settings_path = self._original_settings_path
        server._engine_name = self._original_engine
        server._tts_model = self._original_model
        server._tts_sample_rate = self._original_sample_rate
        self._runtime_dir.cleanup()

    def test_default_engine_is_kokoro(self):
        self.assertEqual(Config.TTS_ENGINE, "kokoro")
        self.assertEqual(server._saved_engine(), "kokoro")

    def test_tts_engines_endpoint(self):
        res = self.client.get("/api/tts/engines")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["active"], "kokoro")
        self.assertEqual(data["default"], "kokoro")
        self.assertIn("voices", data)
        self.assertGreater(len(data["voices"]), 0)
        
        # Verify Kokoro is in engines catalog with default=True
        kokoro_entry = next((e for e in data["engines"] if e["id"] == "kokoro"), None)
        self.assertIsNotNone(kokoro_entry)
        self.assertTrue(kokoro_entry.get("default"))
        self.assertTrue(kokoro_entry.get("active"))

    def test_select_voice_within_kokoro(self):
        res = self.client.post("/api/tts/engine", json={"engine": "kokoro", "voice": "af_bella"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["active"], "kokoro")
        self.assertEqual(data["current_voice"], "af_bella")

        # Reset back to af_heart
        res2 = self.client.post("/api/tts/engine", json={"engine": "kokoro", "voice": "af_heart"})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["current_voice"], "af_heart")

    def test_forced_chattts_cuda_never_silently_falls_back_to_cpu(self):
        from modules.tts_chattts import ChatTTSModel
        import torch

        with patch.object(torch.cuda, "is_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "configured for CUDA"):
                ChatTTSModel._resolve_device("cuda:0")


if __name__ == "__main__":
    unittest.main()
