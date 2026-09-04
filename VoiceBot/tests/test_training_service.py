import tempfile
import unittest
from pathlib import Path

from core.training_service import TrainingService


class TrainingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = TrainingService(Path(self.temp.name) / "test.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_training_cycle_persists_progress(self):
        session = self.service.create_session("demo", "communication", "beginner")
        self.service.add_turn(session["id"], "user", "I understand the delay. Because testing found a defect, I will send a corrected build tomorrow and confirm the plan with the team.", 8)
        self.service.add_turn(session["id"], "assistant", "What impact will that have?")
        result = self.service.assess(session["id"])
        self.assertGreater(result["overall"], 0)
        dashboard = self.service.dashboard()
        self.assertEqual(dashboard["completed_sessions"], 1)
        self.assertTrue(dashboard["recent_sessions"])

    def test_document_retrieval_is_isolated_and_ranked(self):
        self.service.add_document("demo", "leave-policy.txt", "Employees must ask their manager for annual leave at least seven days before departure.")
        matches = self.service.search("How early must I ask for annual leave?", "demo")
        self.assertEqual(matches[0]["name"], "leave-policy.txt")
        self.assertEqual(self.service.search("annual leave", "another-user"), [])

    def test_posture_is_included_when_available(self):
        session = self.service.create_session("demo", "presentations", "intermediate")
        self.service.add_turn(session["id"], "user", "The main result is a ten percent improvement. Next, I recommend we approve the pilot because the evidence supports it.")
        self.service.add_posture(session["id"], {"slouching": 80, "head_position": 90, "shoulder_alignment": 85, "body_orientation": 95})
        result = self.service.assess(session["id"])
        self.assertIn("posture", result["scores"])


if __name__ == "__main__":
    unittest.main()
