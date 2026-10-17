import os
import io
import tempfile
import unittest
import wave
import json
from pathlib import Path

import numpy as np

os.environ["HIKARI_SKIP_MODELS"] = "true"

from fastapi.testclient import TestClient

import api.server as server
from core.training_service import TrainingService
from services.auth_service import AuthService


class ApiTests(unittest.TestCase):
    def test_semantic_completion_is_used_for_stream_reply_and_persisted_assessment(self):
        quote='Good day! Call me Visteria. It was a pleasure meeting you; take care.'
        class Judge:
            def evaluate_objectives(self,prompt):
                return {'criteria':[{'name':name,'met':True,'evidence':[quote]} for name in json.loads(prompt)['criteria']]}
            def generate_contextual_response(self,prompt):
                raise AssertionError('Do not ask another question after semantic success')
        class FakeTTS:
            def synthesize_streaming(self,text,speed=1.0):
                yield np.zeros(2400,dtype=np.float32).tobytes()
        server._llm_model=Judge();server._tts_model=FakeTTS()
        created=self.client.post('/api/sessions',json={'skill_id':'english-speaking','activity_id':'english-01'}).json()
        response=self.client.post(f"/api/sessions/{created['id']}/voice-stream",json={'text':quote})
        events=[json.loads(line) for line in response.text.splitlines() if line]
        result=next(event['result'] for event in events if event['type']=='result')
        self.assertEqual(result['session_progress']['evaluation_mode'],'meaning-based review')
        self.assertEqual(result['session_progress']['outcome'],'success')
        self.assertNotIn('?',result['text'])
        self.assertTrue(result['assessment'])
        self.assertEqual(server.training.session(created['id'])['status'],'completed')
        self.assertEqual(self.client.post(f"/api/sessions/{created['id']}/complete").status_code,200)

    def test_complete_answer_streams_closing_without_another_llm_question(self):
        class UnexpectedLLM:
            def generate_contextual_response(self, prompt):
                raise AssertionError('Completed objectives must not generate another question')
        class FakeTTS:
            def __init__(self): self.texts=[]
            def synthesize_streaming(self,text,speed=1.0):
                self.texts.append(text)
                yield np.zeros(2400,dtype=np.float32).tobytes()
        server._llm_model=UnexpectedLLM()
        server._tts_model=FakeTTS()
        created=self.client.post('/api/sessions',json={'skill_id':'english-speaking','activity_id':'english-01'}).json()
        response=self.client.post(f"/api/sessions/{created['id']}/voice-stream",json={'text':'Hello, my name is Maya. Goodbye!'})
        events=[json.loads(line) for line in response.text.splitlines() if line]
        result=next(event['result'] for event in events if event['type']=='result')
        self.assertEqual(result['session_progress']['outcome'],'success')
        self.assertEqual(server.training.session(created['id'])['status'],'completed')
        self.assertEqual(len(result['responses']),1)
        self.assertTrue(server._tts_model.texts)
        self.assertTrue(all('?' not in text for text in server._tts_model.texts))

    def test_partial_transcription_is_provisional_and_does_not_create_turns(self):
        class FakeSTT:
            def transcribe_detailed(self,data,language,context):
                return {'text':'Hello neighbour.','confidence':.9,'detected_language':'en'}
        server._stt_model=FakeSTT()
        response=self.client.post('/api/transcribe',files={'file':('prefix.webm',b'fake audio','audio/webm')},data={'partial':'true','language':'English','duration_ms':'2000'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['partial'])
        self.assertEqual(response.json()['text'],'Hello neighbour.')
        self.assertEqual(self.client.get('/api/sessions').json(),[])

    def test_kokoro_style_synthesize_only_supports_opening_and_repeated_turns(self):
        class SynthesizeOnly:
            def synthesize(self, text, speed=1.0):
                yield np.zeros(2400, dtype=np.float32).tobytes()
        server._engine_name='kokoro'
        server._tts_model=SynthesizeOnly()
        opening=self.client.post('/api/tts/stream',json={'text':'Hello there.'})
        self.assertIn('"type": "audio"',opening.text)
        session=self.client.post('/api/sessions',json={'skill_id':'active-listening'}).json()
        for text in ('Could you clarify the problem?', 'I understand your concern. What happened next?'):
            response=self.client.post(f"/api/sessions/{session['id']}/voice-stream",json={'text':text})
            events=[json.loads(line) for line in response.text.splitlines() if line]
            self.assertTrue(any(event['type']=='audio' for event in events))
            self.assertTrue(any(event['type']=='result' for event in events))
            self.assertFalse(any(event['type'] in ('error','speech_error') for event in events))

    def test_missing_tts_still_returns_voice_turn_text(self):
        server._tts_model=None
        session=self.client.post('/api/sessions',json={'skill_id':'communication','difficulty':'beginner'}).json()
        response=self.client.post(f"/api/sessions/{session['id']}/voice-stream",json={'text':'Could you explain the situation?','synthesize_audio':False})
        events=[json.loads(line) for line in response.text.splitlines() if line]
        self.assertEqual(response.status_code,200)
        self.assertTrue(any(event['type']=='speech_error' for event in events))
        result=next(event['result'] for event in events if event['type']=='result')
        self.assertTrue(result['text'])

    def test_premature_completion_keeps_session_active(self):
        created=self.client.post('/api/sessions',json={'skill_id':'english-speaking','difficulty':'beginner','activity_id':'english-01'})
        identifier=created.json()['id']
        server.training.add_turn(identifier,'user','Hello there.')
        result=self.client.post(f'/api/sessions/{identifier}/complete')
        self.assertEqual(result.status_code,409)
        self.assertEqual(server.training.session(identifier)['status'],'active')
        self.assertEqual(self.client.get('/api/dashboard').json()['completed_sessions'],0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_training = server.training
        self.original_auth_service = server.auth_service
        self.original_llm = server._llm_model
        self.original_stt = server._stt_model
        self.original_engine = server._engine_name
        path = Path(self.temp.name) / "api.db"
        server.training = TrainingService(path)
        server.auth_service = AuthService(path)
        self.user, token = server.auth_service.register(
            "Test Learner", "learner@example.com", "training123", "Test Organization"
        )
        self.client = TestClient(server.app)
        self.client.cookies.set(server.Config.AUTH_COOKIE_NAME, token)
        server.metrics.reset()

    def tearDown(self):
        self.client.close()
        server.training = self.original_training
        server.auth_service = self.original_auth_service
        server._llm_model = self.original_llm
        server._stt_model = self.original_stt
        server._engine_name = self.original_engine
        server._tts_model = None
        self.temp.cleanup()

    def test_roleplay_assessment_dashboard_and_upload(self):
        created = self.client.post("/api/sessions", json={"skill_id": "active-listening", "difficulty": "beginner"})
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["id"]
        reply = self.client.post(f"/api/sessions/{session_id}/turn", json={"text": "I understand your concern. Could you explain when the problem started?"})
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()["text"])
        server.training.add_turn(session_id,'user','To confirm, the service is unreliable and you need a clear explanation of what happened.')
        server.training.add_turn(session_id,'user','What would help you most? I appreciate your patience and will investigate the problem with the team.')
        result = self.client.post(f"/api/sessions/{session_id}/complete")
        self.assertEqual(result.status_code, 200)
        self.assertIn("scores", result.json())
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["completed_sessions"], 1)
        document = self.client.post("/api/documents", files={"file": ("policy.txt", b"Verify urgent access requests with a manager.", "text/plain")})
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

    def test_voice_turn_stream_audio_precedes_result(self):
        server._engine_name = "kokoro"
        class FakeLLM:
            def generate_contextual_response(self, prompt):
                yield "<think>private reasoning</think> Hello there. "
                yield "Could you explain the problem?"
        class FakeTTS:
            texts = []
            def synthesize_streaming(self, text, speed=1.0):
                self.texts.append(text)
                yield np.zeros(2400, dtype=np.float32).tobytes()
        server._llm_model = FakeLLM()
        server._tts_model = FakeTTS()
        created = self.client.post("/api/sessions", json={"skill_id": "active-listening"}).json()
        response = self.client.post(f"/api/sessions/{created['id']}/voice-stream", json={"text": "Could you clarify that?"})
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[0]["type"], "speech_text")
        self.assertLess(next(i for i,e in enumerate(events) if e['type']=='audio'), len(events)-1)
        self.assertEqual(events[-1]["type"], "result")
        self.assertTrue(events[-1]["result"]["responses"])
        self.assertEqual(server._tts_model.texts, ["Hello there.", "Could you explain the problem?"])

    def test_chattts_starts_from_first_complete_sentence(self):
        class FakeLLM:
            def generate_contextual_response(self, prompt):
                yield "<think>private reasoning</think> Hello there. "
                yield "Could you explain the problem?"
        class FakeTTS:
            def __init__(self): self.texts = []
            def synthesize_streaming(self, text, speed=1.0):
                self.texts.append(text)
                yield np.zeros(2400, dtype=np.float32).tobytes()
        server._engine_name = "chattts"
        server._llm_model = FakeLLM()
        server._tts_model = FakeTTS()
        created = self.client.post("/api/sessions", json={"skill_id": "active-listening"}).json()
        response = self.client.post(f"/api/sessions/{created['id']}/voice-stream", json={"text": "Could you clarify that?"})
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e["type"] for e in events], ["speech_text", "audio", "speech_text", "audio", "result"])
        self.assertEqual(server._tts_model.texts, ["Hello there.", "Could you explain the problem?"])

    def test_transcription_runtime_failure_is_not_reported_as_no_speech(self):
        class BrokenSTT:
            def transcribe_detailed(self, *args):
                raise RuntimeError("Speech recognition failed")
        server._stt_model = BrokenSTT()
        response = self.client.post("/api/transcribe", files={"file": ("voice.wav", b"audio", "audio/wav")})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Speech recognition failed", response.json()["detail"])

    def test_uncertain_one_word_capture_is_retried_and_english_is_forced(self):
        class FakeSTT:
            def __init__(self): self.args = None
            def transcribe_detailed(self, data, language, context):
                self.args = (data, language, context)
                return {"text":"Pike","confidence":.42,"detected_language":"en","language_probability":1.0}

        fake = FakeSTT(); server._stt_model = fake
        response = self.client.post(
            "/api/transcribe",
            files={"file":("speech.webm",b"audio","audio/webm")},
            data={"language":"English","context":"Intermediate Conversation Checkpoint","duration_ms":"2340"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["needs_retry"])
        self.assertEqual(fake.args[1], "en")

    def test_audio_buffer_edges_are_faded_to_prevent_clicks(self):
        wav_bytes = server._pcm_to_wav(np.ones(1000, dtype=np.float32).tobytes(), 24000)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[-1], 0)
        self.assertGreater(samples[len(samples) // 2], 30000)

    def test_session_creation_includes_opening_turn_and_answers_live_queries(self):
        created = self.client.post("/api/sessions", json={"skill_id": "communication", "difficulty": "intermediate"}).json()
        self.assertEqual(len(created["turns"]), 1)
        self.assertEqual(created["turns"][0]["role"], "assistant")
        self.assertIn("Team lead", created["counterpart"])
        self.assertEqual(len(created["participants"]), 2)

        # Test live query about what to do
        query_response = self.client.post(
            f"/api/sessions/{created['id']}/turn",
            json={"text": "What is this scenario and what are my objectives?", "synthesize_audio": False}
        ).json()
        self.assertIn("Team lead", query_response["text"])
        self.assertIn("Explain the issue without blame", query_response["text"])

        group = self.client.post(
            "/api/sessions", json={"skill_id": "presentations", "difficulty": "advanced"}
        ).json()
        self.assertEqual(len([p for p in group["participants"] if p["participant_type"] == "ai"]), 3)

    def test_session_data_is_private_to_its_owner(self):
        created = self.client.post("/api/sessions", json={"skill_id": "communication"}).json()
        _, other_token = server.auth_service.register(
            "Other Learner", "other@example.com", "training123", "Other Organization"
        )
        self.client.cookies.set(server.Config.AUTH_COOKIE_NAME, other_token)
        self.assertEqual(self.client.get(f"/api/sessions/{created['id']}").status_code, 403)

    def test_multi_ai_turn_returns_ordered_attributed_speakers(self):
        class FakeLLM:
            def generate_contextual_response(self, prompt):
                if "First Greetings" in prompt:
                    yield "I understand, but what specific action do you propose we take next?"
                    return
                speaker = "AI Teammate" if "Your Name: AI Teammate" in prompt else "Decision-maker"
                yield f"{speaker} continues the shared conversation."

            def translate_caption(self, text, target_language):
                return f"{target_language} caption"

        server._llm_model = FakeLLM()
        created = self.client.post(
            "/api/sessions",
            json={
                "skill_id": "english-speaking", "activity_id": "english-23",
                "difficulty": "advanced",
            },
        ).json()
        result = self.client.post(
            f"/api/sessions/{created['id']}/turn",
            json={"text": "I recommend the proposal because it will reduce delays.", "synthesize_audio": False},
        ).json()
        self.assertEqual([item["speaker"] for item in result["responses"]], ["AI Teammate", "Decision-maker"])
        self.assertEqual([item["text"].split()[0] for item in result["responses"]], ["AI", "Decision-maker"])
        stored = self.client.get(f"/api/sessions/{created['id']}").json()
        self.assertEqual(
            [turn["speaker_name"] for turn in stored["turns"][-2:]],
            ["AI Teammate", "Decision-maker"],
        )
        beginner = self.client.post(
            "/api/sessions",
            json={"skill_id": "english-speaking", "activity_id": "english-01", "difficulty": "beginner"},
        ).json()
        self.assertEqual(beginner["turns"][0]["caption_text"], "Urdu caption")
        beginner_turn = self.client.post(
            f"/api/sessions/{beginner['id']}/turn",
            json={"text": "Hello, my name is Ayesha.", "synthesize_audio": False},
        ).json()
        self.assertEqual(beginner_turn["responses"][0]["caption_language"], "Urdu")
        self.assertEqual(beginner_turn["responses"][0]["caption_text"], "Urdu caption")
        self.assertIn("Nice to meet you, Ayesha", beginner_turn["responses"][0]["text"])
        self.assertNotIn("specific action", beginner_turn["responses"][0]["text"])

    def test_learner_pages_receive_persisted_catalog_data(self):
        activities = self.client.get("/api/training/activities")
        resources = self.client.get("/api/resources")
        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(activities.status_code, 200)
        self.assertEqual(len(activities.json()), 42)
        self.assertEqual(len(resources.json()), 7)
        self.assertIn("practice_minutes", dashboard.json())
        self.assertIn("progress_history", dashboard.json())


if __name__ == "__main__":
    unittest.main()
