import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
os.environ['HIKARI_SKIP_MODELS']='true'
from fastapi.testclient import TestClient
import api.server as server
from services.speech_activity import SpeechActivity
from services.auth_service import AuthService


class STTSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=(server._stt_model,server._settings_path,server.auth_service,server._stt_activity)
        server._stt_model=Mock(runtime_info=lambda:{'engine':'nemotron','device':'cuda'})
        server._settings_path=Path(self.temp.name)/'settings.json'
        server._persist_runtime_settings({'tts_engine':'kokoro','kokoro_voice':'af_bella'})
        server._stt_activity=SpeechActivity()
        server.auth_service=AuthService(Path(self.temp.name)/'auth.db')
        _,token=server.auth_service.register('Learner','speech-settings@example.invalid','test-only-password-123')
        self.client=TestClient(server.app)
        self.client.cookies.set(server.Config.AUTH_COOKIE_NAME,token)

    def tearDown(self):
        self.client.close()
        server._stt_model,server._settings_path,server.auth_service,server._stt_activity=self.old
        self.temp.cleanup()

    def test_three_modes_and_cpu_choice_are_exposed(self):
        state=self.client.get('/api/stt/engines').json()
        self.assertEqual(len(state['engines']),3)
        self.assertIn('whisper_small_onnx',[item['id'] for item in state['engines']])

    def test_successful_switch_persists_without_erasing_tts(self):
        candidate=Mock(runtime_info=lambda:{'engine':'whisper_small_onnx','device':'cpu'})
        with patch('modules.stt_router.create_stt',return_value=candidate):
            response=self.client.post('/api/stt/engine',json={'engine':'whisper_small_onnx','device':'cpu'})
        self.assertEqual(response.status_code,200)
        self.assertIs(server._stt_model,candidate)
        saved=server._saved_settings()
        self.assertEqual(saved['stt_engine'],'whisper_small_onnx')
        self.assertEqual(saved['kokoro_voice'],'af_bella')
        server._persist_runtime_settings({'tts_engine':'chattts'})
        self.assertEqual(server._saved_settings()['stt_engine'],'whisper_small_onnx')

    def test_failed_switch_preserves_previous_model_and_settings(self):
        original=server._stt_model
        with patch('modules.stt_router.create_stt',side_effect=FileNotFoundError('missing weights')):
            response=self.client.post('/api/stt/engine',json={'engine':'whisper_medium_onnx'})
        self.assertEqual(response.status_code,503)
        self.assertIs(server._stt_model,original)
        self.assertNotIn('stt_engine',server._saved_settings())

    def test_cannot_switch_during_recognition(self):
        with server._stt_activity.use(),patch('modules.stt_router.create_stt') as factory:
            response=self.client.post('/api/stt/engine',json={'engine':'nemotron','device':'cpu'})
        self.assertEqual(response.status_code,409);factory.assert_not_called()

    def test_selection_requires_authentication(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.post('/api/stt/engine',json={'engine':'nemotron'}).status_code,401)


class SpeechActivityTests(unittest.TestCase):
    def test_switch_blocks_new_recognition_and_releases_after_failure(self):
        activity=SpeechActivity()
        with activity.switch():
            with self.assertRaises(RuntimeError):
                with activity.use():pass
        with activity.use():pass
        self.assertEqual(activity.users,0)
