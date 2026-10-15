import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from core.training_service import TrainingService
from domain.entities import Assessment, AssessmentMetric, TrainingSession, SessionStatus
from domain.errors import DomainError
from integrations.vision import LandmarkVisionAdapter


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = TrainingService(Path(self.temp.name)/'test.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_completed_domain_session_is_immutable(self):
        session = TrainingSession('s','u','scenario')
        session.start()
        session.complete()
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        with self.assertRaises(ValueError): session.cancel()

    def test_unavailable_modality_not_fabricated(self):
        result = Assessment('a','s')
        result.add_metric(AssessmentMetric('m','a','clarity','language',80))
        result.add_metric(AssessmentMetric('v','a','posture','visual',None,availability_status='unavailable'))
        self.assertEqual(result.calculate_overall_score(),80)
        with self.assertRaises(ValueError):
            AssessmentMetric('v','a','posture','visual',50,availability_status='unavailable')

    def test_assessment_idempotent_under_concurrent_completion(self):
        session = self.service.create_session('demo','communication','beginner')
        self.service.add_turn(session['id'],'user','I understand. I will finish the corrected report tomorrow because testing found a problem.')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.service.assess(session['id']),range(2)))
        self.assertEqual(results[0],results[1])
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assessments WHERE session_id=?',(session['id'],)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT sessions FROM proficiency WHERE user_id=? AND skill_id=?',('demo','communication')).fetchone()[0],1)
        self.assertIsNotNone(self.service.dashboard()['persistent_plan'])

    def test_cancel_does_not_award_proficiency(self):
        session = self.service.create_session('demo','communication','beginner')
        self.service.cancel_session(session['id'])
        with self.assertRaises(ValueError): self.service.assess(session['id'])
        self.assertEqual(self.service.dashboard()['completed_sessions'],0)

    def test_admin_is_explicit_and_catalog_is_extensible(self):
        admin = self.service.context.administration
        with self.assertRaises(DomainError): admin.save_configuration({'email':'learner@example.com'},100)
        with patch('config.Config.ADMIN_EMAILS',{'owner@example.com'}):
            user = {'email':'owner@example.com'}
            admin.save_skill(user,'new-skill',{'name':'New skill','description':'Test','category':'workplace','active':True})
            admin.save_configuration(user,12)
            self.assertEqual(admin.document_chunk_limit(),12)
        self.assertIn('new-skill',[s['id'] for s in self.service.skills()])

    def test_posture_requires_visible_body_not_just_a_face(self):
        adapter = LandmarkVisionAdapter()
        self.assertFalse(adapter.analyze_posture([]).available)
        points = [{'x':.5,'y':.5,'z':0,'visibility':1} for _ in range(33)]
        points[0].update(y=.2)
        points[11].update(x=.3,y=.4)
        points[12].update(x=.7,y=.4)
        points[23].update(x=.4,y=.8)
        points[24].update(x=.6,y=.8)
        self.assertTrue(adapter.analyze_posture(points).available)
        points[24]['visibility']=0
        self.assertFalse(adapter.analyze_posture(points).available)

    def test_new_catalog_activity_can_run_without_static_skill_constants(self):
        admin=self.service.context.administration
        with patch('config.Config.ADMIN_EMAILS',{'owner@example.com'}):
            user={'email':'owner@example.com'}
            admin.save_skill(user,'custom-skill',{'name':'Custom skill','description':'Custom','category':'workplace','active':True})
            admin.save_subskill(user,'custom-clarity',{'skill_id':'custom-skill','name':'clarity','description':'Clarity','active':True})
            admin.save_activity(user,'custom-activity',{'skill_id':'custom-skill','title':'Custom activity','description':'Custom',
                'context':'A colleague wants a clear update','objectives':['Explain clearly'],'success_criteria':['A clear update'],
                'opening_situation':'What happened?','learner_role':'Learner','ai_roles':['Colleague'],
                'roleplay_mode':'one_to_one','difficulty':'beginner','estimated_minutes':10})
        session=self.service.create_session('demo','custom-skill','beginner',activity_id='custom-activity')
        self.assertEqual(session['title'],'Custom activity')
        self.service.add_turn(session['id'],'user','I will send the report tomorrow because the team needs the final results.')
        self.assertIsNotNone(self.service.assess(session['id']))

    def test_failed_document_does_not_destroy_ready_documents(self):
        with patch.dict(os.environ,{'HIKARI_SKIP_MODELS':'true'}):
            self.service.add_document('demo','old.txt','Annual leave requires manager approval.')
        with patch.dict(os.environ,{'HIKARI_SKIP_MODELS':'false'}), patch.object(self.service.context.knowledge.embedder,'generate_embedding',side_effect=RuntimeError('offline')):
            with self.assertRaises(DomainError): self.service.add_document('demo','new.txt','A different policy.')
        statuses={doc['name']:doc['status'] for doc in self.service.documents()}
        self.assertEqual(statuses,{'old.txt':'ready','new.txt':'failed'})
