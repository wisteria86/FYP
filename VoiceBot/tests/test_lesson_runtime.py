import tempfile
import unittest
from pathlib import Path
from core.training_service import TrainingService


class LessonRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.service=TrainingService(Path(self.temp.name)/'runtime.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_varies_but_start_preserves_exact_briefing(self):
        first=self.service.scenario_preview('demo','english-speaking','beginner','english-01')
        second=self.service.scenario_preview('demo','english-speaking','beginner','english-01')
        self.assertNotEqual(first['situation'],second['situation'])
        self.assertEqual(first['objectives'],second['objectives'])
        session=self.service.create_session('demo','english-speaking','beginner','english-01',preview_id=first['preview_id'])
        self.assertEqual(session['situation'],first['situation'])
        self.assertEqual(session['turns'][0]['text'],first['opening'])
        with self.assertRaises(ValueError):
            self.service.create_session('demo','english-speaking','beginner','english-01',preview_id=first['preview_id'])

    def test_language_does_not_accept_posture_or_documents(self):
        session=self.service.create_session('demo','english-speaking','beginner','english-01')
        with self.assertRaises(ValueError):self.service.add_posture(session['id'],{'slouching':100})
        with self.assertRaises(ValueError):self.service.scenario_preview('demo','english-speaking','beginner','english-01',document_ids=['foreign'])

    def test_company_lesson_requires_authorized_documents_and_varies(self):
        with self.assertRaises(ValueError):self.service.scenario_preview('demo','company-knowledge','beginner')
        self.service.add_document('demo','travel.txt','Overseas travel requires team lead Jordan approval before booking.')
        first=self.service.scenario_preview('demo','company-knowledge','beginner')
        second=self.service.scenario_preview('demo','company-knowledge','beginner')
        self.assertNotEqual(first['opening'],second['opening'])
        session=self.service.create_session('demo','company-knowledge','beginner',preview_id=first['preview_id'])
        self.assertTrue(session['document_ids'])
        empty=self.service.context.knowledge.policy_observations(session,['Hello there, how are you?'])
        self.assertFalse(any(item['met'] for item in empty))
        good=self.service.context.knowledge.policy_observations(session,['Overseas travel requires team lead Jordan approval before booking. I will request approval and check any exception.'])
        self.assertTrue(all(item['met'] for item in good))

    def test_preview_cannot_change_skill(self):
        preview=self.service.scenario_preview('demo','communication','beginner')
        with self.assertRaises(ValueError):self.service.create_session('demo','interviews','beginner',preview_id=preview['preview_id'])

    def test_posture_toggle_does_not_change_prepared_case(self):
        first=self.service.scenario_preview('demo','presentations','beginner')
        configured=self.service.scenario_preview('demo','presentations','beginner',posture_enabled=True,preview_id=first['preview_id'])
        self.assertEqual(configured['situation'],first['situation'])
        self.assertEqual(configured['opening'],first['opening'])
        self.assertTrue(configured['posture_enabled'])

    def test_session_snapshot_survives_template_changes(self):
        preview=self.service.scenario_preview('demo','communication','beginner')
        session=self.service.create_session('demo','communication','beginner',preview_id=preview['preview_id'])
        with self.service.connect() as db:
            db.execute("UPDATE scenario_templates SET context='Changed case',objectives_json='[\"New goal\"]' WHERE activity_id=?",(preview['activity_id'],))
            db.execute("UPDATE training_activities SET title='Changed title',posture_mode='optional' WHERE id=?",(preview['activity_id'],))
        saved=self.service.session(session['id'])
        self.assertEqual(saved['title'],preview['title'])
        self.assertEqual(saved['objectives'],preview['objectives'])
        self.assertEqual(saved['situation'],preview['situation'])
        self.assertFalse(saved['posture_enabled'])

    def test_deleted_document_invalidates_unused_briefing(self):
        document=self.service.add_document('demo','rule.txt','Overseas travel requires team lead Jordan approval before booking.')
        preview=self.service.scenario_preview('demo','company-knowledge','beginner',document_ids=[document['id']])
        with self.service.connect() as db:
            db.execute("UPDATE documents SET status='unavailable' WHERE id=?",(document['id'],))
        with self.assertRaises(ValueError):self.service.create_session('demo','company-knowledge','beginner',preview_id=preview['preview_id'])
