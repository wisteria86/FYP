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
