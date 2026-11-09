import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from api.schemas import RoleplayTurn
from core.training_service import TrainingService
from intelligence.conversation_direction import numeric_text, grounded_reply
from intelligence.replies import valid_caption
from services.training_orchestrator import TrainingOrchestrator
from services.structured_orchestrator import wait_for_delivery, schedule_review, PENDING_REVIEWS
from legacy_fixture import previous_engine


class ConversationRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.training=TrainingService(Path(self.temp.name)/'regression.db')
        self.runtime=self.training.context.runtime

    def tearDown(self):self.temp.cleanup()

    def session(self,skill='english-speaking',activity='english-20'):
        return self.training.create_session('demo',skill,'intermediate',activity)

    def provider(self,reply='Here is my proposal.'):
        class Provider:
            def generate_contextual_response(self,prompt):yield reply
        return Provider()

    def orchestrator(self,provider):return TrainingOrchestrator(self.training,provider,None,Mock(),24000,'test')

    async def test_negotiation_identity_and_spoken_numbers_follow_the_actual_party(self):
        session=self.session('negotiation',None);sid=session['id']
        provider=self.provider();provider.generate_contextual_response=Mock(side_effect=AssertionError('Bounded replies must not need a provider'))
        service=self.orchestrator(provider)
        introduction=await service.run_turn(sid,RoleplayTurn(text='First tell me who are you',synthesize_audio=False))
        self.assertIn('supplier',introduction['text'].lower());self.assertNotIn('client',introduction['text'].lower())
        scope=await service.run_turn(sid,RoleplayTurn(text='I will offer you ten seeds',synthesize_audio=False))
        self.assertIn('10 seats',scope['text']);self.assertIn('20 seats',scope['text'])
        # N7: an unreasoned low offer earns a question, not instant agreement.
        price=await service.run_turn(sid,RoleplayTurn(text='Okay I will take it for ten thousand',synthesize_audio=False))
        self.assertNotIn('works',price['text'])
        self.assertIn('USD 10,000',price['text'])
        self.assertNotIn('minimum',price['text'])
        self.assertEqual(numeric_text('ten thousand dollars'),'10000 dollars')

    async def test_old_frozen_case_roles_are_corrected_without_changing_prices(self):
        sid=self.session('negotiation',None)['id'];definition,_=self.runtime.read(sid)
        seller=next(p for p in definition['participants'] if p.get('party')=='seller')
        seller.pop('party');seller['role']='Client';seller['relationship']='Client in the negotiation'
        with self.runtime.connect() as db:db.execute('UPDATE conversation_runtime SET definition_json=? WHERE session_id=?',(json.dumps(definition),sid))
        fixed,_=self.runtime.read(sid)
        person=next(p for p in fixed['participants'] if p['id']==seller['id'])
        self.assertEqual(person['party'],'seller');self.assertEqual(person['role'],'Supplier representative')
        self.assertEqual(fixed['negotiation'],definition['negotiation'])
        self.assertEqual(self.training.session(sid)['participants'][1]['scenario_role'],'Supplier representative')

    async def test_other_person_request_and_uncertainty_select_the_other_stakeholder(self):
        previous_engine(self)
        sid=self.session()['id'];service=self.orchestrator(self.provider('We can begin with a demonstration.'))
        for text in ['The other person is going to tell me','They will tell the plan',"I'm not really that sure"]:
            last=next(t for t in reversed(self.training.session(sid)['turns']) if t['role']=='assistant')['participant_id']
            result=await service.run_turn(sid,RoleplayTurn(text=text,synthesize_audio=False))
            self.assertTrue(result['responses'])
            self.assertNotEqual(result['responses'][0]['participant_id'],last)
        self.assertIn('12 new colleagues',json.dumps(self.runtime.read(sid)[0]['facts']))

    async def test_case_pack_scene_keeps_moving_on_prepared_lines_during_an_outage(self):
        sid=self.session(activity='english-01')['id']
        class RateLimited(Exception):status_code=429
        class Provider:
            def generate_contextual_response(self,prompt):
                raise RateLimited()
                yield ''
        first=await self.orchestrator(Provider()).run_turn(sid,RoleplayTurn(text='Hello, call me Zara.',synthesize_audio=False))
        self.assertEqual(first['responses'][0]['response_mode'],'scripted')
        self.assertFalse(first['runtime']['failed_turn_id'])
        self.assertEqual(first['runtime']['provider_status']['component'],'scripted')

    async def test_provider_outage_is_a_retryable_notice_and_not_character_dialogue(self):
        previous_engine(self)
        sid=self.session(activity='english-02')['id']
        class RateLimited(Exception):status_code=429
        class Provider:
            failed=False
            def generate_contextual_response(self,prompt):
                if not self.failed:self.failed=True;raise RateLimited()
                yield 'Nice to meet you, Zara.'
        service=self.orchestrator(Provider())
        first=await service.run_turn(sid,RoleplayTurn(text='Hello, call me Zara.',synthesize_audio=False,request_id='first'))
        self.assertEqual(first['responses'],[])
        self.assertTrue(first['runtime']['failed_turn_id'])
        self.assertEqual(len(self.training.session(sid)['turns']),2)
        second=await service.run_turn(sid,RoleplayTurn(text='Hello, call me Zara.',retry_last_turn=True,synthesize_audio=False,request_id='retry'))
        self.assertIn('Zara',second['text'])
        self.assertEqual(sum(t['role']=='user' for t in self.training.session(sid)['turns']),1)
        self.assertIsNone(second['runtime']['failed_turn_id'])

    async def test_delivery_wait_does_not_discard_the_second_speaker_at_ten_seconds(self):
        sid=self.session()['id'];generation,_=self.runtime.start(sid,RoleplayTurn(text='What should we consider?'))
        person=self.runtime.speakers(sid)[0];uid=self.runtime.create_utterance(sid,generation,person)
        self.runtime.sentence(sid,uid,'I suggest a demonstration first.',True)
        async def acknowledge_after_wait(_):self.runtime.acknowledge(sid,uid,0)
        with patch('services.structured_orchestrator.time.monotonic',side_effect=[0,11,12]),patch('services.structured_orchestrator.asyncio.sleep',acknowledge_after_wait):
            self.assertTrue(await wait_for_delivery(self.runtime,sid,uid,generation))

    async def test_group_responses_do_not_call_a_second_model_to_select_speakers(self):
        previous_engine(self)
        sid=self.session()['id'];provider=self.provider('I can explain my part of the workshop.')
        provider.plan_turn=Mock(side_effect=AssertionError('Director must be local'))
        result=await self.orchestrator(provider).run_turn(sid,RoleplayTurn(text='What should we consider?',synthesize_audio=False))
        self.assertEqual(len(result['responses']),2)
        provider.plan_turn.assert_not_called()

    async def test_repeated_questions_are_not_streamed_again(self):
        sid=self.session(activity='english-01')['id']
        self.runtime.start(sid,RoleplayTurn(text='Hello, my name is Zara.'))
        speaker=self.runtime.speakers(sid)[0]
        self.assertEqual(self.runtime.validate_sentence(sid,speaker,"What's your name?"),'')

    async def test_background_review_is_deferred_and_coalesced(self):
        sid=self.session()['id'];provider=self.provider();provider.evaluate_runtime=Mock()
        schedule_review(self.training,provider,sid)
        first=PENDING_REVIEWS[(str(self.training.path),sid)]
        schedule_review(self.training,provider,sid)
        second=PENDING_REVIEWS[(str(self.training.path),sid)]
        await asyncio.sleep(0)
        provider.evaluate_runtime.assert_not_called()
        self.assertTrue(first.cancelled())
        second.cancel();await asyncio.gather(second,return_exceptions=True)
        PENDING_REVIEWS.pop((str(self.training.path),sid),None)

    async def test_bad_negotiation_subtitle_is_rejected(self):
        self.assertFalse(valid_caption("We're negotiating a price.",'ہم مذاق کر رہے ہیں۔'))
        self.assertTrue(valid_caption("We're negotiating a price.",'ہم قیمت پر مذاکرات کر رہے ہیں۔'))

    async def test_unfinished_condition_is_not_agreement_and_the_invited_person_explains(self):
        previous_engine(self)
        sid=self.session()['id'];service=self.orchestrator(self.provider())
        incomplete=await service.run_turn(sid,RoleplayTurn(text='Okay, if I do this',synthesize_audio=False))
        self.assertIn("don't want to assume",incomplete['text'])
        other=await service.run_turn(sid,RoleplayTurn(text='The other person is going to tell me',synthesize_audio=False))
        self.assertIn('demonstration',other['text'])
        self.assertNotIn('wait for',other['text'])

    async def test_yes_to_either_or_question_cannot_finalize_a_deal(self):
        sid=self.session('negotiation',None)['id'];generation,_=self.runtime.start(sid,RoleplayTurn(text='I have an alternative.'))
        speaker=self.runtime.speakers(sid)[0];uid=self.runtime.create_utterance(sid,generation,speaker)
        self.runtime.sentence(sid,uid,'Would you like our package at USD 10000 or different terms?',False)
        self.runtime.finish(sid,generation,{})
        provider=self.provider();provider.generate_contextual_response=Mock(side_effect=RuntimeError('prepared line only'))
        reply=await self.orchestrator(provider).run_turn(sid,RoleplayTurn(text='Yes, I can',synthesize_audio=False))
        self.assertIn('Do you mean',reply['text'])
        self.assertEqual(self.runtime.view(sid)['offers'],[])
        self.assertNotIn('lock in',self.runtime.validate_sentence(sid,speaker,"Let's lock in the package."))
