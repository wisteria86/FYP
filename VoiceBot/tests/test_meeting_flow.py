import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from api.schemas import RoleplayTurn
from core.training_service import TrainingService
from domain.conversation import SessionAction
from intelligence.conversation_direction import addressed_people, choose_speakers, reply_handoff, proactive_reaction
from services.training_orchestrator import TrainingOrchestrator
from legacy_fixture import previous_engine


class MeetingFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        previous_engine(self)
        self.temp=tempfile.TemporaryDirectory()
        self.training=TrainingService(Path(self.temp.name)/'meeting.db')
        self.runtime=self.training.context.runtime
        self.sid=self.training.create_session('demo','english-speaking','advanced','english-27')['id']
        self.definition,_=self.runtime.read(self.sid)
        self.alex,self.sam=[p for p in self.definition['participants'] if p['kind']=='ai']

    def tearDown(self):self.temp.cleanup()

    def select(self,text,**kwargs):
        generation,_=self.runtime.start(self.sid,RoleplayTurn(text=text,**kwargs))
        selected=self.runtime.speakers(self.sid)
        self.runtime.finish(self.sid,generation,{})
        return selected

    def runner(self,provider):return TrainingOrchestrator(self.training,provider,None,Mock(),24000,'test')

    async def test_natural_vocatives_without_required_punctuation(self):
        for text in ['Sam, why are you changing the plan','Okay Sam, can you tell me more about it',
                     'Okay, Sam can you tell me more about it','Can you tell me about it, Sam',
                     'Can you tell me more Sam','Thanks Sam why did you change it']:
            with self.subTest(text=text):
                self.assertEqual([p['id'] for p in self.select(text)],[self.sam['id']])

    async def test_mentions_do_not_override_vocatives_or_selected_person(self):
        people=[self.alex,self.sam]
        self.assertEqual(addressed_people('Tell me about Sam',people),[])
        self.assertEqual(addressed_people('Sam said the plan changed',people),[])
        self.assertEqual([p['id'] for p in addressed_people('Alex, why did Sam change the plan?',people)],[self.alex['id']])
        self.assertEqual(self.select('Sam can you explain?',addressed_participant_ids=[self.alex['id']])[0]['id'],self.alex['id'])

    async def test_focus_survives_reload_and_unpunctuated_followups(self):
        self.select('Okay Sam can you explain?')
        reopened=TrainingService(self.training.path).context.runtime
        self.assertEqual(reopened.view(self.sid)['conversation_focus'],self.sam['id'])
        self.assertEqual(self.select('Okay get me about this')[0]['id'],self.sam['id'])
        self.assertEqual(self.select('What the heck are you talking about')[0]['id'],self.sam['id'])

    async def test_ambiguous_duplicate_names_ask_for_role(self):
        self.alex['name']=self.sam['name']='Sam'
        selected=choose_speakers(self.definition,{'latest_input':'Okay Sam can you explain?'},[])
        self.assertEqual(len(selected),1)
        self.assertTrue(selected[0]['_ambiguous'])

    async def test_action_owner_does_not_change_when_colleague_reacts(self):
        self.select('Alex what is your concern?')
        self.assertEqual(self.select('Why did you do it man')[0]['id'],self.sam['id'])
        bad='I changed the plan because the timeline was unsafe.'
        repaired=self.runtime.validate_sentence(self.sid,self.alex,bad)
        self.assertEqual(repaired,"Sam made that change; I didn't.")
        self.assertEqual(self.runtime.validate_sentence(self.sid,self.alex,'Alex, I want advance notice.'),'I want advance notice.')

    async def test_case_has_distinct_interests_and_known_unknowns(self):
        self.assertNotEqual(self.alex['goals'],self.sam['goals'])
        self.assertEqual(self.definition['actions'][0]['participant_id'],self.sam['id'])
        self.assertIn('not been confirmed',str(self.definition['facts']))
        for text in ['The security patch needs three additional days.',
                     'The three-day delay fits within our current buffer.',
                     'The final delivery date remains unchanged.']:
            self.assertIn("haven't",self.runtime.validate_sentence(self.sid,self.sam,text))
        self.assertNotIn('two hours',self.runtime.validate_sentence(self.sid,self.sam,'The test takes two hours.'))
        self.assertEqual(self.runtime.validate_sentence(self.sid,self.sam,'Could we set aside two hours to estimate the work?'),
            'Could we set aside two hours to estimate the work?')

    async def test_saved_case_does_not_acquire_new_fictional_facts(self):
        old=dict(self.definition);old.pop('actions')
        old['facts']=['Mediate a disagreement between two colleagues.']
        with self.runtime.connect() as db:
            db.execute('UPDATE conversation_runtime SET definition_json=? WHERE session_id=?',(json.dumps(old),self.sid))
            db.execute("UPDATE turns SET text=? WHERE session_id=? AND role='assistant'",('We cannot continue like this. Sam keeps changing the plan after we agree on it.',self.sid))
        actual,_=self.runtime.read(self.sid)
        self.assertEqual(actual['facts'],old['facts'])
        self.assertEqual(actual['actions'][0]['reason'],'')
        self.assertEqual(actual['actions'][0]['participant_id'],self.sam['id'])

    async def test_near_duplicate_statements_do_not_repeat(self):
        generation,_=self.runtime.start(self.sid,RoleplayTurn(text='Alex explain your concern.'))
        uid=self.runtime.create_utterance(self.sid,generation,self.alex)
        line='I need advance notice because I already arranged the team around Tuesday.'
        self.runtime.sentence(self.sid,uid,line,False)
        self.runtime.finish(self.sid,generation,{})
        self.select('Okay get me about this')
        self.assertEqual(self.runtime.validate_sentence(self.sid,self.alex,line.replace('need','want')),'')

    async def test_repetition_repair_does_not_become_an_identical_loop(self):
        repairs=[]
        for _ in range(3):
            generation,_=self.runtime.start(self.sid,RoleplayTurn(text='Why did you do it then?'))
            repair=self.runtime.repetition_repair(self.sid,self.sam)
            repairs.append(repair)
            uid=self.runtime.create_utterance(self.sid,generation,self.sam)
            self.runtime.sentence(self.sid,uid,repair,False)
            self.runtime.finish(self.sid,generation,{})
        self.assertEqual(len(set(repairs)),3)

    async def test_colleague_question_gets_real_answer_without_another_learner_turn(self):
        class Provider:
            def generate_contextual_response(inner,prompt):
                if prompt['context']['you']['name']=='Sam':yield "I missed a test in the plan. Alex, can we discuss changes before I edit it next time?"
                else:yield "Yes, tell me before changing it so I can check the team's availability."
        result=await self.runner(Provider()).run_turn(self.sid,RoleplayTurn(text='Okay Sam can you explain?',synthesize_audio=False))
        self.assertEqual([r['speaker'] for r in result['responses']],['Sam','Alex'])
        self.assertEqual(sum(t['role']=='user' for t in self.training.session(self.sid)['turns']),1)

    async def test_handoff_distinguishes_question_to_learner_from_named_colleague(self):
        self.assertIsNone(reply_handoff(self.definition,self.sam,'What would you suggest?'))
        self.assertEqual(reply_handoff(self.definition,self.sam,'Alex, would that help?')['id'],self.alex['id'])
        self.assertEqual(reply_handoff(self.definition,self.sam,'Alex, I understand your concern. Can we discuss changes first?')['id'],self.alex['id'])

    async def test_collective_invitation_includes_people_who_have_already_spoken(self):
        speakers=choose_speakers(self.definition,{'latest_input':'Both of you, suggest a next step'},
            [{'participant_id':self.alex['id']},{'participant_id':self.sam['id']}])
        self.assertEqual({p['id'] for p in speakers},{self.alex['id'],self.sam['id']})

    async def test_colleague_keeps_contributing_without_being_named(self):
        class Provider:
            def __init__(inner):inner.counts={}
            def generate_contextual_response(inner,prompt):
                name=prompt['context']['you']['name'];index=inner.counts.get(name,0);inner.counts[name]=index+1
                lines={'Alex':[
                    'We should confirm availability before settling on a revised review date.',
                    'The team had already arranged its work around the original Tuesday review.',
                    'Future changes need joint approval before the shared plan is edited.'],
                    'Sam':[
                    'Alex, I can estimate the missing test while you check availability.',
                    'The end-to-end check still needs to stay in our plan.',
                    'We can bring both pieces of information together before deciding the date.']}
                yield lines[name][index]
        runner=self.runner(Provider())
        for text in ['We need a practical next step.','Can we discuss what happens next?','I think we should confirm availability first.']:
            result=await runner.run_turn(self.sid,RoleplayTurn(text=text,synthesize_audio=False))
            self.assertEqual({r['speaker'] for r in result['responses']},{'Alex','Sam'})
            self.assertLessEqual(len(result['responses']),2)

    async def test_reactions_leave_personal_questions_and_repairs_alone(self):
        for learner in ['Sam, who are you?','Could you repeat that?','What do you mean?','Just you, Sam.']:
            self.assertIsNone(proactive_reaction(self.definition,{'latest_input':learner},self.sam,
                'I moved the review to include the missing test in the plan.',[]))
        self.assertIsNone(proactive_reaction(self.definition,{'latest_input':'Can we decide?'},self.sam,'Could you clarify what you mean by that?',[]))
        self.assertIsNone(proactive_reaction(self.definition,{'completed':True},self.sam,'We have agreed everything needed for the meeting today.',[]))

    async def test_colleague_can_follow_acknowledgement_with_a_useful_contribution(self):
        class Provider:
            def generate_contextual_response(inner,prompt):
                if prompt['context']['you']['name']=='Alex':yield 'We need to check availability before choosing the review date.'
                else:yield 'Alex, I understand the scheduling concern. I can estimate the test while you check availability. This third sentence should be left out.'
        result=await self.runner(Provider()).run_turn(self.sid,RoleplayTurn(text='What should our next step be?',synthesize_audio=False))
        self.assertEqual(len(result['responses']),2)
        self.assertIn('I can estimate the test',result['responses'][1]['text'])
        self.assertNotIn('third sentence',result['responses'][1]['text'])

    async def test_requested_speakers_are_not_displaced_by_proactive_selection(self):
        class Provider:
            def generate_contextual_response(inner,prompt):yield 'I can contribute my perspective on this shared plan.'
        with patch.object(self.runtime,'handoff',side_effect=AssertionError('Already requested speaker must retain their place')):
            result=await self.runner(Provider()).run_turn(self.sid,RoleplayTurn(text='Please each share your view.',
                addressed_participant_ids=[self.alex['id'],self.sam['id']],synthesize_audio=False))
        self.assertEqual([r['speaker'] for r in result['responses']],['Alex','Sam'])

    async def test_three_colleagues_get_space_without_turn_number_rotation(self):
        people=[{**self.alex,'id':f'a{i}','name':name,'topics':['review'],'goals':['Check availability']} for i,name in enumerate(['Alex','Sam','Maya','Robin'])]
        people[2].update(topics=['budget'],goals=['Keep costs bounded'],role='Finance partner')
        people[3].update(topics=['quality'],goals=['Keep quality consistent'],role='Quality partner')
        definition={**self.definition,'participants':people}
        history=[];heard=set()
        for _ in range(5):
            history.append({'participant_id':'a0'})
            selected=proactive_reaction(definition,{'latest_input':'We need to agree a review date.'},people[0],
                'We should check availability before we settle the review date.',history)
            heard.add(selected['id']);history.append({'participant_id':selected['id']})
        self.assertEqual(heard,{'a1','a2','a3'})

    async def test_affected_colleague_can_react_once_without_being_asked(self):
        text='I moved the review because a test was missing. I should have checked with Alex.'
        history=[{'participant_id':self.alex['id']}]
        self.assertEqual(reply_handoff(self.definition,self.sam,text,history)['id'],self.alex['id'])
        history.append({'participant_id':self.alex['id']})
        self.assertIsNone(reply_handoff(self.definition,self.sam,text,history))

    async def test_provider_identity_is_reasserted_after_history_and_stream_closes(self):
        from modules.llm_brain import LLMBrain
        class Stream:
            closed=False
            def __iter__(self):
                for text in ['My concern is notice.','Sam, can we discuss changes first?']:
                    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])
            def close(self):self.closed=True
        stream=Stream();brain=LLMBrain.__new__(LLMBrain)
        brain._create=Mock(return_value=stream)
        brain.model_name='test';brain.base_url='local'
        iterator=brain.generate_contextual_response(self.runtime.prompt(self.sid,self.alex,[]))
        next(iterator);iterator.close()
        self.assertTrue(stream.closed)
        last=brain._create.call_args.kwargs['messages'][-1]
        self.assertEqual(last['role'],'system')
        self.assertIn('"name": "Alex"',last['content'])

    async def test_voice_prefetch_happens_before_ack_but_is_not_shared(self):
        drafted=threading.Event();observed=[]
        class Provider:
            def generate_contextual_response(inner,prompt):
                if prompt['context']['you']['name']=='Sam':yield 'Alex, can you explain your concern?'
                else:
                    observed.append(prompt['context']);drafted.set()
                    yield 'I need to know before the plan changes.'
        async def delivery(runtime,sid,uid,generation):
            self.assertTrue(await asyncio.to_thread(drafted.wait,2))
            self.assertNotIn('I need to know before',str(self.training.session(sid)['turns']))
            self.assertEqual(observed[0]['pending_predecessor']['speaker'],'Sam')
            runtime.acknowledge(sid,uid,0)
            return True
        with patch('services.structured_orchestrator.wait_for_delivery',delivery):
            result=await self.runner(Provider()).run_turn(self.sid,RoleplayTurn(text='Sam can you explain?'),lambda *args:None)
        self.assertEqual([r['speaker'] for r in result['responses']],['Sam','Alex'])

    def batch_provider(self,first='I moved the review because the agreed plan left out a test.'):
        class Provider:
            supports_group_response=True
            calls=0
            closed=False
            def generate_group_response(inner,prompt):
                inner.calls+=1
                try:
                    yield {'participant_id':prompt['speaker_ids'][0],'text':first}
                    yield {'participant_id':prompt['speaker_ids'][1],'text':"Sam, I need notice before changes so I can check the team's availability."}
                finally:inner.closed=True
            def generate_contextual_response(inner,prompt):
                raise AssertionError('A second provider request must not be needed')
        return Provider()

    async def test_public_group_uses_one_request_and_two_distinct_speakers(self):
        provider=self.batch_provider()
        result=await self.runner(provider).run_turn(self.sid,RoleplayTurn(text='Sam explain the change',synthesize_audio=False))
        self.assertEqual([r['speaker'] for r in result['responses']],['Sam','Alex'])
        self.assertEqual(provider.calls,1)
        self.assertTrue(provider.closed)

    async def test_group_draft_is_discarded_on_interruption_before_ack(self):
        provider=self.batch_provider()
        async def interrupt(runtime,sid,uid,generation):
            runtime.action(sid,SessionAction(action='interrupt',request_id='batch-interrupt'))
            return False
        with patch('services.structured_orchestrator.wait_for_delivery',interrupt):
            result=await self.runner(provider).run_turn(self.sid,RoleplayTurn(text='Sam explain the change'),lambda *args:None)
        self.assertEqual(len(result['responses']),1)
        self.assertNotIn('need notice before changes',str(self.training.session(self.sid)['turns']))
        self.assertTrue(provider.closed)

    async def test_group_prompt_refuses_private_or_different_participant_knowledge(self):
        self.select('Sam explain the change')
        for change in [{'private_knowledge':{'secret':'Do not disclose'}},{'public_knowledge':['Only Sam knows this']}]:
            definition=json.loads(json.dumps(self.definition))
            definition['participants'][-1].update(change)
            with self.runtime.connect() as db:
                db.execute('UPDATE conversation_runtime SET definition_json=? WHERE session_id=?',(json.dumps(definition),self.sid))
            self.assertIsNone(self.runtime.group_prompt(self.sid,self.runtime.speakers(self.sid),[]))

    async def test_invalidated_primary_does_not_supply_context_to_batched_second(self):
        provider=self.batch_provider('I changed the plan for a security patch needing three additional days.')
        provider.generate_contextual_response=Mock(return_value=iter(['We should check the missing test before setting a date.']))
        result=await self.runner(provider).run_turn(self.sid,RoleplayTurn(text='Sam explain the change',synthesize_audio=False))
        self.assertNotIn('three additional days',str(result['responses']))
        # The validated clarification can legitimately yield the floor without a second reply.
        self.assertTrue(provider.closed)

    async def test_interruption_discards_prefetched_speaker_and_focus_ignores_unheard(self):
        drafted=threading.Event()
        class Provider:
            def generate_contextual_response(inner,prompt):
                if prompt['context']['you']['name']=='Sam':yield 'Alex, can you explain your concern?'
                else:
                    drafted.set();yield 'This must never be heard.'
        async def interrupt(runtime,sid,uid,generation):
            self.assertTrue(await asyncio.to_thread(drafted.wait,2))
            runtime.action(sid,SessionAction(action='interrupt',request_id='interrupt-draft'))
            return False
        with patch('services.structured_orchestrator.wait_for_delivery',interrupt):
            result=await self.runner(Provider()).run_turn(self.sid,RoleplayTurn(text='Sam can you explain?'),lambda *args:None)
        self.assertEqual(len(result['responses']),1)
        self.assertNotIn('This must never be heard',str(self.training.session(self.sid)['turns']))
        self.assertNotIn('can you explain your concern',str(self.runtime.prompt(self.sid,self.sam,[])['context']['recent_dialogue']))
