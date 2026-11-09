import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from core.training_service import TrainingService
from domain.conversation import SessionAction
from domain.errors import DomainError
from intelligence.scenario_contracts import learner_definition
from services.training_orchestrator import TrainingOrchestrator


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name)/'test.db')
        self.runtime = self.training.context.runtime
        self.session = self.training.create_session('demo','english-speaking','beginner','english-01')
        self.sid = self.session['id']

    def tearDown(self):
        self.temp.cleanup()

    def payload(self,text='Hello, call me Amna.',request='r1',**kwargs):
        return SimpleNamespace(text=text,duration_seconds=0,request_id=request,expected_revision=None,
            addressed_participant_ids=kwargs.get('addressed',[]),recognition=kwargs.get('recognition',{}))

    def action(self,kind,data=None,key=None):
        return self.runtime.action(self.sid,SessionAction(action=kind,data=data or {},request_id=key or kind))

    def evaluated(self,met=True):
        context=self.runtime.evaluation_context(self.sid)
        user=next(t for t in context['transcript'] if t['role']=='user')
        return context['revision'],{'criteria':[{'objective_id':o['id'],'met':met,'quotes':[user['text']],'turn_ids':[user['id']]} for o in context['rubric']]}

    def test_opening_roster_and_prompt_have_one_identity(self):
        self.assertEqual(self.session['counterpart'],'Alex')
        self.assertIn("I'm Alex",self.session['turns'][0]['text'])
        self.runtime.start(self.sid,self.payload())
        context=self.training.prompt(self.sid)['context']
        self.assertEqual(context['you']['name'],'Alex')
        self.assertEqual(context['learner_name'],'Amna')
        self.assertNotEqual(context['you']['name'],context['learner_name'])

    def test_private_constraints_are_projected_by_role(self):
        session=self.training.create_session('demo','negotiation','beginner')
        sid=session['id'];definition,_=self.runtime.read(sid)
        public=json.dumps(session)
        self.assertNotIn('private_knowledge',public)
        self.assertNotIn('seller',learner_definition(definition)['negotiation'])
        self.assertNotIn('"minimum"',json.dumps(learner_definition(definition)))
        speaker=self.runtime.speakers(sid)[0]
        prompt=self.runtime.prompt(sid,speaker,[])['context']
        self.assertEqual(prompt['you']['private_knowledge'],definition['negotiation']['seller'])
        self.assertNotIn('preparation_brief',json.dumps(prompt))
        self.assertNotIn('maximum',json.dumps(prompt))

    def test_direct_address_wins_over_turn_count(self):
        group=self.training.create_session('demo','english-speaking','advanced','english-22')
        ai=[p for p in group['runtime']['definition']['participants'] if p['kind']=='ai']
        self.runtime.start(group['id'],self.payload('I have a question.',addressed=[ai[1]['id']]))
        self.assertEqual(self.runtime.speakers(group['id'])[0]['id'],ai[1]['id'])

    def test_interrupted_unheard_text_never_enters_context(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        speaker=self.runtime.speakers(self.sid)[0]
        uid=self.runtime.create_utterance(self.sid,generation,speaker)
        self.runtime.sentence(self.sid,uid,'Nice to meet you.',True)
        self.runtime.sentence(self.sid,uid,'Your appointment is confirmed.',True)
        self.runtime.acknowledge(self.sid,uid,0)
        self.action('interrupt')
        self.runtime.acknowledge(self.sid,uid,1)
        history=self.runtime.prompt(self.sid,speaker,[])['context']['recent_dialogue']
        self.assertIn('Nice to meet you.',json.dumps(history))
        self.assertNotIn('appointment is confirmed',json.dumps(history))
        self.assertFalse(self.runtime.active(self.sid,generation))
        self.assertIsNone(self.runtime.sentence(self.sid,uid,'Late speech.',True))

    def test_duplicate_and_concurrent_turns_do_not_duplicate_evidence(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        with self.assertRaises(DomainError):self.runtime.start(self.sid,self.payload())
        with self.assertRaises(DomainError):self.runtime.start(self.sid,self.payload(request='r2'))
        self.runtime.finish(self.sid,generation,{'text':'saved'})
        self.assertEqual(self.runtime.start(self.sid,self.payload())[1],{'text':'saved'})
        self.assertEqual(sum(t['role']=='user' for t in self.training.session(self.sid)['turns']),1)

    def test_keywords_alone_do_not_complete(self):
        self.runtime.start(self.sid,self.payload('The words are hello, my name is Alex and goodbye. I refuse to introduce myself.'))
        self.assertEqual(self.runtime.progress(self.sid)['outcome'],'pending')
        revision,result=self.evaluated(False)
        self.assertTrue(self.runtime.save_evaluation(self.sid,revision,result))
        self.assertFalse(self.runtime.view(self.sid)['completed'])

    def test_evaluation_requires_real_evidence_and_current_revision(self):
        self.runtime.start(self.sid,self.payload())
        revision,result=self.evaluated()
        result['criteria'][0]['quotes']=['invented evidence']
        self.assertFalse(self.runtime.save_evaluation(self.sid,revision,result))
        revision,result=self.evaluated()
        self.action('correct',{'turn_id':result['criteria'][0]['turn_ids'][0],'text':'Hello, my name is Amina.'})
        self.assertFalse(self.runtime.save_evaluation(self.sid,revision,result))
        row=self.training.session(self.sid)['turns'][-1]
        self.assertEqual(row['original_text'],'Hello, call me Amna.')

    def test_support_cannot_manufacture_independent_completion(self):
        self.action('coach')
        self.runtime.start(self.sid,self.payload())
        revision,result=self.evaluated()
        self.assertTrue(self.runtime.save_evaluation(self.sid,revision,result))
        self.assertFalse(self.runtime.view(self.sid)['completed'])
        self.assertEqual(self.runtime.view(self.sid)['evaluation']['criteria'][0]['support'],'supported')

    def test_uncertain_recognition_not_used_as_achievement(self):
        self.runtime.start(self.sid,self.payload(recognition={'unreliable':True}))
        revision,result=self.evaluated()
        self.runtime.save_evaluation(self.sid,revision,result)
        self.assertFalse(self.runtime.view(self.sid)['completed'])

    def test_completed_progress_survives_pause_restart_and_extra_practice(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        revision,result=self.evaluated()
        self.runtime.save_evaluation(self.sid,revision,result)
        self.runtime.finish(self.sid,generation,{})
        self.action('pause')
        self.assertTrue(TrainingService(self.training.path).context.runtime.view(self.sid)['completed'])
        self.action('extra_practice')
        self.runtime.start(self.sid,self.payload('Could you repeat that?',request='r2'))
        self.assertTrue(self.runtime.view(self.sid)['completed'])
        reviews=self.training.context.progress.learning_reviews('demo')
        self.assertEqual(sorted(r['interval_days'] for r in reviews),[1,7,30])
        revision,result=self.evaluated(False)
        self.runtime.save_evaluation(self.sid,revision,result)
        self.assertTrue(all(c['met'] for c in self.runtime.progress(self.sid)['criteria']))
        assessment=self.training.assess(self.sid)
        self.assertEqual(assessment['scores']['task_achievement'],100)

    def test_no_zopa_offer_cannot_be_accepted(self):
        self.training.scenario_preview('demo','negotiation','beginner')
        case=self.training.create_session('demo','negotiation','beginner')
        self.sid=case['id']
        self.action('offer',dict(price=11000,seats=20,delivery_days=30,support_months=3,rationale='Based on the supplied benchmark.'))
        offer=self.runtime.view(self.sid)['offers'][0]
        self.assertEqual(offer['seller_response'],'rejected')
        with self.assertRaises(DomainError):self.action('accept',{'offer_id':offer['id']})

    def test_feasible_offer_needs_explicit_confirmation(self):
        self.sid=self.training.create_session('demo','negotiation','beginner')['id']
        self.action('offer',dict(price=11000,seats=20,delivery_days=30,support_months=3,rationale='Based on the supplied benchmark.'))
        offer=self.runtime.view(self.sid)['offers'][0]
        self.assertEqual(offer['status'],'proposed')
        self.action('accept',{'offer_id':offer['id']})
        self.assertEqual(self.runtime.view(self.sid)['offers'][0]['status'],'accepted')

    def test_private_preparation_cannot_become_public_assessment_memory(self):
        self.sid=self.training.create_session('demo','negotiation','beginner')['id']
        self.action('prepare',dict(target='SECRET TARGET',alternative='SECRET ALTERNATIVE',walk_away='SECRET LIMIT',reason='Internal budget'))
        context=self.runtime.evaluation_context(self.sid)
        private=next(t for t in context['transcript'] if t['id']==-1)
        result={'criteria':[dict(objective_id=o['id'],met=False,quotes=[],turn_ids=[]) for o in context['rubric']],
                'observations':[dict(turn_id=-1,quote=private['text'],kind='proposal')]}
        self.assertTrue(self.runtime.save_evaluation(self.sid,context['revision'],result))
        prompt=json.dumps(self.runtime.prompt(self.sid,self.runtime.speakers(self.sid)[0],[]))
        self.assertNotIn('SECRET',prompt)

    def test_supported_practice_and_progress_survive_unreviewed_pause(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        revision,result=self.evaluated(False)
        result['criteria'][0]['met']=True
        self.runtime.save_evaluation(self.sid,revision,result)
        self.runtime.finish(self.sid,generation,{})
        self.runtime.start(self.sid,self.payload('Could you repeat that?',request='r2'))
        self.action('pause')
        self.assertTrue(self.runtime.progress(self.sid)['criteria'][0]['met'])
        self.assertFalse(self.runtime.view(self.sid)['completed'])

    def test_voice_delivery_invalidates_an_older_evaluation(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        revision,result=self.evaluated()
        uid=self.runtime.create_utterance(self.sid,generation,self.runtime.speakers(self.sid)[0])
        self.runtime.sentence(self.sid,uid,'What is your name?',True)
        self.runtime.finish(self.sid,generation,{})
        self.assertFalse(self.runtime.ready_for_review(self.sid))
        self.runtime.acknowledge(self.sid,uid,0)
        self.assertTrue(self.runtime.ready_for_review(self.sid))
        self.assertFalse(self.runtime.save_evaluation(self.sid,revision,result))

    def test_fact_repair_only_resolves_after_delivery_and_does_not_repeat(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        speaker=self.runtime.speakers(self.sid)[0]
        original=self.runtime.create_utterance(self.sid,generation,speaker)
        self.runtime.sentence(self.sid,original,'An incorrect assertion.',False)
        report={'contradictions':[{'quote':'An incorrect assertion.','fact_index':0}]}
        self.runtime.record_repairs(self.sid,original,report)
        repair=self.runtime.view(self.sid)['repairs'][0]
        uid=self.runtime.create_utterance(self.sid,generation,speaker)
        correction='I need to correct an earlier statement: '+repair['binding_fact']
        self.runtime.sentence(self.sid,uid,correction,True)
        self.assertFalse(self.runtime.view(self.sid)['repairs'][0].get('resolved',False))
        self.runtime.acknowledge(self.sid,uid,0)
        self.assertTrue(self.runtime.view(self.sid)['repairs'][0]['resolved'])
        self.runtime.record_repairs(self.sid,original,report)
        self.assertEqual(len(self.runtime.view(self.sid)['repairs']),1)
        self.assertEqual(self.runtime.prompt(self.sid,speaker,[])['context']['corrections_to_acknowledge'],[])

    def test_duplicate_names_still_route_by_id_and_identity_checks_keep_learner_separate(self):
        group=self.training.create_session('demo','english-speaking','advanced','english-22')
        definition,state=self.runtime.read(group['id'])
        ai=[p for p in definition['participants'] if p['kind']=='ai']
        ai[1]['name']=ai[0]['name']
        with self.runtime.connect() as db:
            db.execute('UPDATE conversation_runtime SET definition_json=? WHERE session_id=?',(json.dumps(definition),group['id']))
        self.runtime.start(group['id'],self.payload(addressed=[ai[1]['id']]))
        self.assertEqual(self.runtime.speakers(group['id'])[0]['id'],ai[1]['id'])
        speaker=ai[0]
        self.assertEqual(self.runtime.validate_sentence(group['id'],speaker,"I'm Amna."),f"I'm {speaker['name']}.")
        self.assertEqual(self.runtime.validate_sentence(group['id'],speaker,f"Hello {speaker['name']}."),'Hello Amna.')

    def test_named_address_selects_speaker_without_requiring_rotation(self):
        group=self.training.create_session('demo','english-speaking','advanced','english-22')
        ai=[p for p in group['runtime']['definition']['participants'] if p['kind']=='ai']
        self.runtime.start(group['id'],self.payload(f"{ai[1]['name']}, what concerns you?"))
        selected=self.runtime.speakers(group['id'])
        self.assertEqual([p['id'] for p in selected],[ai[1]['id']])
        self.assertTrue(selected[0]['_directed'])

    def test_support_ladder_escalates_and_urdu_is_separate(self):
        for i in range(4):self.action('coach',key=f'help{i}')
        coach=self.runtime.view(self.sid)['coach']
        self.assertEqual([c['level'] for c in coach],[0,1,2,3])
        self.assertEqual(len({c['text'] for c in coach}),4)
        self.action('preferences',{'coach_language':'Urdu'})
        with self.runtime.connect() as db:
            definition,state=self.runtime.read(self.sid,db);state['coach']=[]
            db.execute('UPDATE conversation_runtime SET state_json=? WHERE session_id=?',(json.dumps(state),self.sid))
        self.action('coach',key='urdu')
        self.assertIn('اپنے',self.runtime.view(self.sid)['coach'][-1]['text'])
        self.assertNotIn('coach',self.runtime.prompt(self.sid,self.runtime.speakers(self.sid)[0],[])['context'])

    def test_no_deal_requires_preparation_and_ethical_evidence(self):
        self.training.scenario_preview('demo','negotiation','beginner')
        self.sid=self.training.create_session('demo','negotiation','beginner')['id']
        self.action('prepare',dict(target='8500',alternative='8500 for delivery in 45 days',walk_away='9000',reason='Approved budget; later delivery is tolerable'))
        self.runtime.start(self.sid,self.payload('My limit cannot meet your price. I will choose the alternative. Thank you for discussing the options.'))
        revision,result=self.evaluated()
        result.update(business_outcome='justified_no_deal',ethical=True)
        self.assertTrue(self.runtime.save_evaluation(self.sid,revision,result))
        self.assertTrue(self.runtime.view(self.sid)['completed'])
        self.assertEqual(self.runtime.view(self.sid)['offers'],[])

    def test_authority_and_conditional_terms_cannot_be_bypassed(self):
        self.sid=self.training.create_session('demo','negotiation','beginner')['id']
        terms=dict(price=11000,seats=20,delivery_days=30,support_months=3,rationale='Benchmark package')
        self.action('offer',{**terms,'condition':'Only if my manager agrees'},key='conditional')
        offer=self.runtime.view(self.sid)['offers'][-1]
        with self.assertRaises(DomainError):self.action('accept',{'offer_id':offer['id']},key='trycondition')
        definition,_=self.runtime.read(self.sid)
        for person in definition['participants']:person['can_finalize']=False
        with self.runtime.connect() as db:
            db.execute('UPDATE conversation_runtime SET definition_json=? WHERE session_id=?',(json.dumps(definition),self.sid))
        self.action('offer',terms,key='unauthorized')
        offer=self.runtime.view(self.sid)['offers'][-1]
        self.assertEqual(offer['seller_response'],'approval_required')
        with self.assertRaises(DomainError):self.action('accept',{'offer_id':offer['id']},key='tryapproval')

    def test_long_resumed_conversation_preserves_identity_and_earlier_attributed_facts(self):
        generation,_=self.runtime.start(self.sid,self.payload('My name is Amna. My meeting is at the library.'))
        revision,result=self.evaluated(False)
        result['observations']=[dict(turn_id=result['criteria'][0]['turn_ids'][0],quote='My meeting is at the library.',kind='answer')]
        self.runtime.save_evaluation(self.sid,revision,result)
        self.runtime.finish(self.sid,generation,{})
        for i in range(35):
            generation,_=self.runtime.start(self.sid,self.payload(f'I have another thought, number {i}.',request=f'long{i}'))
            self.runtime.finish(self.sid,generation,{})
        resumed=TrainingService(self.training.path).context.runtime
        context=resumed.prompt(self.sid,resumed.speakers(self.sid)[0],[])['context']
        self.assertEqual(context['learner_name'],'Amna')
        self.assertEqual(len(context['recent_dialogue']),12)
        self.assertIn('library',json.dumps(context['attributed_memory']))

    def test_urdu_caption_is_tied_to_the_exact_character_utterance(self):
        generation,_=self.runtime.start(self.sid,self.payload())
        uid=self.runtime.create_utterance(self.sid,generation,self.runtime.speakers(self.sid)[0])
        self.runtime.sentence(self.sid,uid,'Nice to meet you.',False)
        revision,result=self.evaluated(False)
        result['captions']=[dict(utterance_id=uid,source_text='Nice to meet you.',text='آپ سے مل کر خوشی ہوئی۔')]
        self.runtime.save_evaluation(self.sid,revision,result)
        self.assertEqual(self.training.session(self.sid)['turns'][-1]['caption_text'],'آپ سے مل کر خوشی ہوئی۔')

    def test_malformed_private_case_and_duplicate_ids_are_rejected(self):
        from domain.conversation import ScenarioDefinition
        from pydantic import ValidationError
        definition,_=self.runtime.read(self.sid)
        definition['negotiation']={'public':{},'buyer':'not an object','seller':{}}
        with self.assertRaises(ValidationError):ScenarioDefinition(**definition)
        definition['negotiation']=None
        definition['participants'][1]['id']=definition['participants'][0]['id']
        with self.assertRaises(ValidationError):ScenarioDefinition(**definition)


class StructuredTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_contribution_is_bounded_and_uses_the_preceding_delivered_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            training=TrainingService(Path(directory)/'group.db')
            session=training.create_session('demo','english-speaking','advanced','english-22')
            prompts=[]
            class Provider:
                def generate_contextual_response(self,prompt):
                    prompts.append(prompt)
                    yield 'I can explain the timing.' if len(prompts)==1 else 'I can explain the budget.'
                def plan_turn(self,context):
                    return {'speaker_ids':[p['id'] for p in context['participants'] if p['id'] not in {'p0',context['first_speaker']}][:1],'purpose':'Offer a budget concern.'}
            # The planner sees public roles, not character-private information.
            provider=Provider()
            payload=SimpleNamespace(text='What should we consider?',duration_seconds=0,request_id='group',expected_revision=None,addressed_participant_ids=[],recognition={},synthesize_audio=False)
            result=await TrainingOrchestrator(training,provider,None,Mock(),24000,'test').run_turn(session['id'],payload)
            self.assertEqual(len(result['responses']),2)
            self.assertNotEqual(result['responses'][0]['participant_id'],result['responses'][1]['participant_id'])
            self.assertIn('I can explain the timing.',json.dumps(prompts[1]['context']['recent_dialogue']))

    async def test_review_coalescing_rechecks_the_latest_transcript(self):
        import threading
        from services.structured_orchestrator import review_session, BACKGROUND
        with tempfile.TemporaryDirectory() as directory:
            training=TrainingService(Path(directory)/'review.db');runtime=training.context.runtime
            sid=training.create_session('demo','english-speaking','beginner','english-01')['id']
            entered,release=threading.Event(),threading.Event();contexts=[]
            class Provider:
                def evaluate_runtime(self,context):
                    contexts.append(context)
                    if len(contexts)==1:entered.set();release.wait(5)
                    return {'criteria':[dict(objective_id=o['id'],met=False,quotes=[],turn_ids=[]) for o in context['rubric']]}
            provider=Provider()
            task=asyncio.create_task(review_session(training,provider,sid))
            await asyncio.to_thread(entered.wait,3)
            try:
                payload=SimpleNamespace(text='Hello, call me Amna.',duration_seconds=0,request_id='later',expected_revision=None,addressed_participant_ids=[],recognition={})
                generation,_=runtime.start(sid,payload);runtime.finish(sid,generation,{})
                await review_session(training,provider,sid)
            finally:release.set()
            await task
            while BACKGROUND:await asyncio.gather(*list(BACKGROUND))
            self.assertEqual(len(contexts),2)
            self.assertEqual(runtime.view(sid)['evaluation']['revision'],runtime.view(sid)['evidence_revision'])

    async def test_offline_turn_is_labelled_and_never_grades(self):
        with tempfile.TemporaryDirectory() as directory:
            training=TrainingService(Path(directory)/'test.db')
            session=training.create_session('demo','english-speaking','beginner','english-01')
            payload=SimpleNamespace(text='Hello, call me Nida.',duration_seconds=0,request_id='one',expected_revision=None,addressed_participant_ids=[],recognition={},synthesize_audio=False)
            service=TrainingOrchestrator(training,None,None,Mock(),24000,'test')
            result=await service.run_turn(session['id'],payload)
            self.assertTrue(result['guided_practice'])
            self.assertIsNone(result['assessment'])
            self.assertNotEqual(result['session_progress']['outcome'],'success')

    async def test_stream_has_identity_and_delivery_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            training=TrainingService(Path(directory)/'test.db')
            session=training.create_session('demo','english-speaking','beginner','english-01')
            class Provider:
                def generate_contextual_response(self,prompt):
                    assert prompt['context']['you']['name']=='Alex'
                    yield 'Hello Nida. '
                    yield 'How are you?'
            payload=SimpleNamespace(text='Hello, call me Nida.',duration_seconds=0,request_id='one',expected_revision=None,addressed_participant_ids=[],recognition={},synthesize_audio=False)
            calls=[]
            result=await TrainingOrchestrator(training,Provider(),None,Mock(),24000,'test').run_turn(session['id'],payload,lambda *args:calls.append(args))
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[0][2]['segment'],0)
            self.assertEqual(result['responses'][0]['utterance_id'],calls[0][2]['utterance_id'])
            context=training.prompt(session['id'])['context']
            self.assertNotIn('Hello Nida.',json.dumps(context['recent_dialogue']))
