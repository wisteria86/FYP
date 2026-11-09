import isolated_environment  # noqa: F401  (must come before the server)
import json
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

os.environ['HIKARI_SKIP_MODELS']='true'
import api.server as server
from core.training_service import TrainingService
from services.auth_service import AuthService


class ConversationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.previous=(server.training,server.auth_service,server._llm_model,server._tts_model)
        path=Path(self.temp.name)/'api.db'
        server.training=TrainingService(path)
        server.auth_service=AuthService(path)
        server._llm_model=server._tts_model=None
        self.user,token=server.auth_service.register('Learner','runtime@example.com','test-password-123','Runtime Test')
        self.client=TestClient(server.app)
        self.client.cookies.set(server.Config.AUTH_COOKIE_NAME,token)

    def tearDown(self):
        self.client.close()
        server.training,server.auth_service,server._llm_model,server._tts_model=self.previous
        self.temp.cleanup()

    def create(self,skill='english-speaking',activity='english-01'):
        result=self.client.post('/api/sessions',json={'skill_id':skill,'activity_id':activity,'difficulty':'beginner'})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def test_preview_never_exposes_counterpart_constraints(self):
        response=self.client.post('/api/scenarios/preview',json={'skill_id':'negotiation'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('private_knowledge',response.text)
        self.assertNotIn('"seller"',response.text)
        self.assertIn('preparation_brief',response.text)

    def test_legacy_chat_adapter_uses_an_owned_persistent_session(self):
        first=self.client.post('/api/chat',json={'text':'Hello, call me Zara.','synthesize_audio':False,'request_id':'chat-one'})
        self.assertEqual(first.status_code,200,first.text)
        sid=first.json()['session_id']
        second=self.client.post('/api/chat',json={'session_id':sid,'text':'Nice to meet you.','synthesize_audio':False,'request_id':'chat-two'})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(len([t for t in server.training.session(sid)['turns'] if t['role']=='user']),2)
        self.assertEqual(second.json()['runtime']['learner_name'],'Zara')

    def test_new_turn_is_idempotent_and_does_not_auto_finish(self):
        session=self.create();sid=session['id']
        payload={'text':'Hello, my name is Zara. Goodbye.','synthesize_audio':False,'request_id':'one'}
        first=self.client.post(f'/api/sessions/{sid}/turn',json=payload)
        second=self.client.post(f'/api/sessions/{sid}/turn',json=payload)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json(),second.json())
        self.assertTrue(first.json()['guided_practice'])
        self.assertIsNone(first.json()['assessment'])
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/complete').status_code,409)
        self.assertEqual(len([t for t in server.training.session(sid)['turns'] if t['role']=='user']),1)

    def test_revision_and_pause_controls(self):
        sid=self.create()['id']
        action={'action':'pause','request_id':'pause','expected_revision':0}
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/actions',json=action).status_code,200)
        duplicate=self.client.post(f'/api/sessions/{sid}/actions',json=action)
        self.assertEqual(duplicate.status_code,200)
        stale=self.client.post(f'/api/sessions/{sid}/actions',json={**action,'action':'resume','request_id':'resume'})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/turn',json={'text':'Hello'}).status_code,409)

    def test_foreign_runtime_and_actions_are_rejected(self):
        sid=self.create()['id']
        _,other=server.auth_service.register('Other Learner','other-runtime@example.com','test-password-123','Other Organization')
        self.client.cookies.set(server.Config.AUTH_COOKIE_NAME,other)
        self.assertEqual(self.client.get(f'/api/sessions/{sid}/runtime').status_code,403)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/actions',json={'action':'coach','request_id':'help'}).status_code,403)
        self.assertEqual(self.client.delete(f'/api/sessions/{sid}/conversation-data').status_code,403)

    def test_delete_removes_text_memory_and_private_preparation(self):
        sid=self.create()['id']
        self.client.post(f'/api/sessions/{sid}/turn',json={'text':'Hello, call me Zara.','synthesize_audio':False})
        response=self.client.delete(f'/api/sessions/{sid}/conversation-data')
        self.assertEqual(response.status_code,200,response.text)
        result=self.client.get(f'/api/sessions/{sid}').json()
        self.assertEqual(result['turns'],[])
        self.assertIsNone(result.get('runtime'))

    def test_voice_stream_segments_have_acknowledgement_identifiers(self):
        import numpy as np
        class Provider:
            def generate_contextual_response(self,prompt):yield 'Hello. It is nice to meet you.'
        server._llm_model=Provider()
        class TTS:
            def synthesize(self,text):yield np.zeros(800,dtype=np.float32).tobytes()
        server._tts_model=TTS()
        sid=self.create()['id']
        response=self.client.post(f'/api/sessions/{sid}/voice-stream',json={'text':'Hello there','synthesize_audio':False})
        events=[json.loads(line) for line in response.text.splitlines()]
        segments=[e for e in events if e['type']=='segment_end']
        self.assertTrue(segments,response.text)
        for segment in segments:
            self.assertIn('event_id',segment)
            self.assertIn('revision',segment)
            acknowledged=self.client.post(f'/api/sessions/{sid}/playback',json={'utterance_id':segment['utterance_id'],'segment':segment['segment']})
            self.assertEqual(acknowledged.status_code,200)

    def test_semantic_success_offers_choice_before_debrief(self):
        sid=self.create()['id']
        self.client.post(f'/api/sessions/{sid}/turn',json={'text':'Hello, call me Zara. It was nice meeting you. Goodbye!','synthesize_audio':False})
        runtime=server.training.context.runtime
        context=runtime.evaluation_context(sid);turn=next(t for t in context['transcript'] if t['role']=='user')
        result={'criteria':[{'objective_id':o['id'],'met':True,'quotes':[turn['text']],'turn_ids':[turn['id']]} for o in context['rubric']]}
        self.assertTrue(runtime.save_evaluation(sid,context['revision'],result))
        self.assertEqual(server.training.session(sid)['status'],'active')
        self.assertTrue(self.client.get(f'/api/sessions/{sid}/runtime').json()['completed'])
        complete=self.client.post(f'/api/sessions/{sid}/complete')
        self.assertEqual(complete.status_code,200,complete.text)
        self.assertEqual(server.training.session(sid)['status'],'completed')
