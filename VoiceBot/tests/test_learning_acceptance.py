"""Executable prototype learning acceptance scenarios; no cloud/model dependencies."""
import tempfile
import unittest
from pathlib import Path
from core.training_service import TrainingService
from intelligence.learning_rubrics import valid_scores


class LearningAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.training=TrainingService(Path(self.temp.name)/'learning.db')

    def tearDown(self): self.temp.cleanup()

    def test_repeated_greeting_never_counts_as_mastery(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        for _ in range(12): self.training.add_turn(session['id'],'user','Hello, my name is Alex. Goodbye.')
        progress=self.training.evaluate_progress(session['id'])
        self.assertEqual(progress['meaningful_turns'],1)
        self.assertTrue(progress['continue_session'])

    def test_greetings_complete_when_three_distinct_responses_demonstrate_targets(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        for line in ['Hello Alex, my name is Maya. It is nice to meet you.',
                     'I am doing well today, thank you. It is lovely to meet a friendly neighbour.',
                     'It was nice meeting you. Goodbye, see you soon.']:
            self.training.add_turn(session['id'],'user',line)
        self.assertEqual(self.training.evaluate_progress(session['id'])['outcome'],'success')

    def test_complete_concise_answer_does_not_need_word_or_turn_quota(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','Hello, my name is Maya. Goodbye!')
        progress=self.training.evaluate_progress(session['id'])
        self.assertEqual(progress['outcome'],'success')
        self.assertLess(progress['word_count'],progress['word_target'])
        self.assertEqual(progress['missing'],[])
        self.assertNotIn('?',self.training.fallback_reply(session['id']))

    def test_completion_review_accepts_paraphrases_and_is_persisted(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        quote='Good day! Call me Visteria. It was a pleasure to meet you; take care.'
        self.training.add_turn(session['id'],'user',quote)
        criteria=self.training.evaluate_progress(session['id'])['criteria']
        review={'criteria':[{'name':c['name'],'met':True,'evidence':[quote]} for c in criteria]}
        self.assertTrue(self.training.save_completion_review(session['id'],review,1))
        reloaded=TrainingService(self.training.path)
        progress=reloaded.evaluate_progress(session['id'])
        self.assertEqual(progress['outcome'],'success')
        self.assertEqual(progress['evaluation_mode'],'meaning-based review')
        self.assertFalse(progress['missing'])

    def test_review_can_reject_keyword_only_answer(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','The words are hello, my name is Alex, and goodbye. I refuse to introduce myself.')
        criteria=self.training.evaluate_progress(session['id'])['criteria']
        review={'criteria':[{'name':c['name'],'met':False,'evidence':[]} for c in criteria]}
        self.assertTrue(self.training.save_completion_review(session['id'],review,1))
        self.assertEqual(self.training.evaluate_progress(session['id'])['outcome'],'failure')

    def test_completion_review_rejects_invented_or_assistant_only_evidence(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','I need some help.')
        criteria=self.training.evaluate_progress(session['id'])['criteria']
        for quote in ['I am a completely invented quotation.',session['turns'][0]['text']]:
            review={'criteria':[{'name':c['name'],'met':True,'evidence':[quote]} for c in criteria]}
            self.assertFalse(self.training.save_completion_review(session['id'],review,1))
        self.assertFalse(self.training.save_completion_review(session['id'],{'criteria':[]},1))

    def test_completion_review_cannot_apply_to_a_newer_learner_turn(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','Hi, my name is Maya.')
        criteria=self.training.evaluate_progress(session['id'])['criteria']
        review={'criteria':[{'name':c['name'],'met':False,'evidence':[]} for c in criteria]}
        self.assertTrue(self.training.save_completion_review(session['id'],review,1))
        self.training.add_turn(session['id'],'user','Goodbye, see you soon.')
        self.assertFalse(self.training.save_completion_review(session['id'],review,1))
        self.assertEqual(self.training.evaluate_progress(session['id'])['evaluation_mode'],'rule-based fallback')

    def test_incomplete_answer_requests_objective_not_more_words(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','Hello, my name is Maya.')
        progress=self.training.evaluate_progress(session['id'])
        self.assertEqual(progress['missing'],['close politely'])

    def test_feeling_is_not_identity_but_natural_name_paraphrase_is(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user',"Hi, I'm fine. Goodbye.")
        self.assertIn('introduce yourself',self.training.evaluate_progress(session['id'])['missing'])
        self.training.add_turn(session['id'],'user','The name is Visteria.')
        self.assertEqual(self.training.evaluate_progress(session['id'])['outcome'],'success')

    def test_prompt_keeps_early_commitments_and_avoids_forced_drills(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','My name is Visteria and I live next door.')
        for index in range(14):
            self.training.add_turn(session['id'],'assistant',f'Context {index}.')
        prompt=self.training.prompt(session['id'])
        self.assertIn('Visteria',prompt)
        self.assertIn('Never contradict',prompt)
        self.assertNotIn('say exactly "A more natural way',prompt)

    def test_opening_identity_matches_context(self):
        preview=self.training.scenario_preview('demo','english-speaking','beginner','english-02')
        self.assertIn("I'm Maya",preview['opening'])
        self.assertIn('Your partner is Maya',preview['situation'])

    def test_greeting_fallback_advances_without_treating_feeling_as_name(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','Hello, my name is Alex.')
        self.training.add_turn(session['id'],'user','I am doing well today, thank you.')
        reply=self.training.fallback_reply(session['id'])
        self.assertIn('goodbye',reply.lower())
        self.assertNotIn('Doing!',reply)
        self.assertNotIn('How are you today',reply)

    def test_irrelevant_workplace_speech_cannot_complete(self):
        session=self.training.create_session('demo','negotiation','beginner')
        for line in ['I enjoy green apples and sunny parks.','My favourite film has a wonderful soundtrack.','Yesterday the weather was pleasant and warm.','My neighbour has a very friendly small dog.']:
            self.training.add_turn(session['id'],'user',line)
        self.assertEqual(self.training.evaluate_progress(session['id'])['outcome'],'failure')

    def test_workplace_success_has_quoted_objective_evidence(self):
        session=self.training.create_session('demo','active-listening','beginner')
        for line in ['I understand your concern and appreciate your patience.','Could you explain when the issue began and what happened?','To confirm, you need reliable service and an explanation of the problem.']:
            self.training.add_turn(session['id'],'user',line)
        progress=self.training.evaluate_progress(session['id'])
        self.assertEqual(progress['outcome'],'success')
        self.assertTrue(all(item['evidence'] for item in progress['criteria']))
        assessment=self.training.assess(session['id'])
        self.assertIn('acknowledgement',assessment['scores'])
        self.assertIn('summarising',assessment['scores'])

    def test_empty_attempt_scores_zero_and_does_not_claim_success(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        result=self.training.assess(session['id'])
        self.assertEqual(result['overall'],0)
        self.assertIn('not mastery',result['feedback'])

    def test_invalid_ai_scores_are_rejected(self):
        scores=valid_scores({'grammar':float('nan'),'fluency':True,'comprehension':101,'vocabulary':45},{'grammar','fluency','comprehension','vocabulary'})
        self.assertEqual(scores,{'vocabulary':45})

    def test_identical_phrase_is_not_a_real_correction(self):
        from intelligence.replies import redundant_correction
        self.assertTrue(redundant_correction('A more natural way is: "I am doing well."','I am doing well today, thank you.'))
        self.assertFalse(redundant_correction('A more natural way is: "I am happy."','I is happy.'))

    def test_invented_correction_not_shown(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        self.training.add_turn(session['id'],'user','Hello, my name is Alex.')
        result=self.training.assess(session['id'],{'corrections':[{'original':'I is happy','improved':'I am happy','reason':'A correction'}]})
        self.assertFalse(any('I is happy' in item for item in result['evidence']))

    def test_plan_moves_to_next_english_lesson_after_mastery(self):
        session=self.training.create_session('demo','english-speaking','beginner','english-01')
        for line in ['Hello, my name is Alex.','I am well today, thank you.','Goodbye, it was nice meeting you.','Good morning, it is good to see you again.','I would say it is nice to meet you.']:
            self.training.add_turn(session['id'],'user',line)
        self.training.assess(session['id'],{'scores':{'fluency':80,'grammar':80,'vocabulary':80,'comprehension':80}})
        self.assertEqual(self.training.dashboard()['plan'][0]['activity_id'],'english-02')
        self.assertEqual(self.training.dashboard()['recommendation']['activity_id'],'english-02')

    def test_documents_shared_only_inside_organization_with_upload_authorization(self):
        from services.auth_service import AuthService
        from domain.errors import DomainError
        from unittest.mock import patch
        import os
        auth=AuthService(self.training.path)
        owner,_=auth.register('Owner','owner@example.com','password123','Company A')
        outsider,_=auth.register('Other','other@example.com','password123','Company B')
        learner,_=auth.register('Learner','member@example.com','password123','Company C')
        with self.training.connect() as db:
            organization=db.execute('SELECT organization_id FROM organization_memberships WHERE user_id=?',(owner['id'],)).fetchone()[0]
            db.execute('DELETE FROM organization_memberships WHERE user_id=?',(learner['id'],))
            db.execute("INSERT INTO organization_memberships VALUES (?,?,'learner',datetime('now'))",(organization,learner['id']))
        with patch.dict(os.environ,{'HIKARI_SKIP_MODELS':'true'}):
            self.training.add_document(owner['id'],'policy.txt','Annual leave requires manager approval.')
            self.assertTrue(self.training.search('annual leave',learner['id']))
            self.assertEqual(self.training.search('annual leave',outsider['id']),[])
            with self.assertRaises(DomainError):self.training.add_document(learner['id'],'blocked.txt','Another policy.')
