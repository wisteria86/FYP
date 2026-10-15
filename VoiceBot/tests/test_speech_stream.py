import unittest
from unittest.mock import Mock
import numpy as np
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from api.routers.speech_stream import install_speech_stream
from modules.stt_router import SpeechRecognitionRouter


class SpeechStreamTests(unittest.TestCase):
    def setUp(self):
        self.primary=Mock()
        self.primary.accept_audio.return_value='Hello'
        self.primary.finish_stream.return_value={'text':'Hello neighbour.','final':True,'engine':'nemotron'}
        self.router=SpeechRecognitionRouter(self.primary,Mock())
        self.session={'user_id':'learner','training_language':'English','status':'active'}
        self.authorize=Mock(return_value=self.session)
        app=FastAPI()
        install_speech_stream(app,lambda:self.router,self.authorize,Mock())
        self.client=TestClient(app)
        self.headers={'origin':'http://localhost:8000'}

    def test_pcm_partials_and_final_are_separate(self):
        with self.client.websocket_connect('/api/sessions/test/speech-stream',headers=self.headers) as socket:
            socket.send_json({'sample_rate':48000})
            self.assertEqual(socket.receive_json()['type'],'ready')
            socket.send_bytes(np.zeros(4096,dtype='<f4').tobytes())
            partial=socket.receive_json()
            self.assertEqual(partial['text'],'Hello');self.assertFalse(partial['final'])
            socket.send_json({'type':'finish'})
            final=socket.receive_json()
            self.assertEqual(final['text'],'Hello neighbour.');self.assertTrue(final['final'])
        self.primary.create_stream.assert_called_once()
        self.primary.finish_stream.assert_called_once()

    def test_auth_and_origin_are_required(self):
        for headers in ({'origin':'https://untrusted.example'},self.headers):
            self.authorize.side_effect=HTTPException(401)
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect('/api/sessions/test/speech-stream',headers=headers):pass

    def test_non_english_and_cpu_connections_use_http_fallback(self):
        for primary,language in ((None,'English'),(self.primary,'Arabic')):
            self.router.primary=primary;self.session['training_language']=language
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect('/api/sessions/test/speech-stream',headers=self.headers):pass

    def test_invalid_audio_returns_recoverable_error(self):
        with self.client.websocket_connect('/api/sessions/test/speech-stream',headers=self.headers) as socket:
            socket.send_json({'sample_rate':16000});socket.receive_json()
            socket.send_bytes(np.array([np.nan],dtype='<f4').tobytes())
            self.assertEqual(socket.receive_json()['type'],'error')
