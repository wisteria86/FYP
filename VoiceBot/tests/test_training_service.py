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
        from domain.errors import DomainError
        with self.assertRaises(DomainError):
            self.service.search("annual leave", "another-user")

    def test_posture_is_included_when_available(self):
        session = self.service.create_session("demo", "presentations", "intermediate", posture_enabled=True)
        self.service.add_turn(session["id"], "user", "The main result is a ten percent improvement. Next, I recommend we approve the pilot because the evidence supports it.")
        self.service.add_posture(session["id"], {"slouching": 80, "head_position": 90, "shoulder_alignment": 85, "body_orientation": 95})
        result = self.service.assess(session["id"])
        self.assertNotIn("posture", result["scores"])
        self.assertEqual(result["visual_scores"]["slouching"], 80)

    def test_session_initializes_with_scenario_opening(self):
        session = self.service.create_session("demo", "communication", "intermediate")
        self.assertEqual(len(session["turns"]), 1)
        opening = session["turns"][0]
        self.assertEqual(opening["role"], "assistant")
        self.assertIn("customer onboarding report", opening["text"].lower())
        self.assertTrue(opening['text'].endswith('?'))
        self.assertEqual(len(session["participants"]), 2)

    def test_lesson_type_controls_ai_participant_count(self):
        individual = self.service.create_session("demo", "active-listening", "intermediate")
        negotiation = self.service.create_session("demo", "negotiation", "intermediate")
        group = self.service.create_session("demo", "presentations", "advanced")
        self.assertEqual(len([p for p in individual["participants"] if p["participant_type"] == "ai"]), 1)
        self.assertEqual(len([p for p in negotiation["participants"] if p["participant_type"] == "ai"]), 1)
        self.assertEqual(len([p for p in group["participants"] if p["participant_type"] == "ai"]), 3)

        activity_types = {item["primary_skill_id"]: item["scenario_type"] for item in self.service.activities()}
        self.assertEqual(activity_types["negotiation"], "roleplay")
        self.assertEqual(activity_types["presentations"], "multi_ai_roleplay")

    def test_scenario_preview_does_not_create_a_session(self):
        before = len(self.service.history("demo"))
        preview = self.service.scenario_preview("demo", "presentations", "advanced")
        self.assertEqual(preview["scenario_type"], "multi_ai_roleplay")
        self.assertEqual(len(preview["participants"]), 3)
        self.assertTrue(preview["objectives"])
        self.assertEqual(len(self.service.history("demo")), before)

    def test_prompt_includes_live_query_and_objective_context(self):
        session = self.service.create_session("demo", "negotiation", "intermediate")
        prompt = self.service.prompt(session["id"])
        self.assertIn("LIVE QUERY SUPPORT", prompt)
        self.assertIn("Client", prompt)
        self.assertIn("Discover the true priority", prompt)
        self.assertNotIn("no more than 18 words", prompt)

    def test_fallback_reply_answers_scenario_and_objective_queries(self):
        session = self.service.create_session("demo", "conflict-resolution", "intermediate")
        self.service.add_turn(session["id"], "user", "Wait, what is this scenario and what should I do?")
        reply = self.service.fallback_reply(session["id"])
        self.assertIn("Frustrated colleague", reply)
        self.assertIn(session['situation'], reply)
        self.assertIn("De-escalate", reply)

    def test_language_lesson_uses_its_own_teaching_persona(self):
        session = self.service.create_session("demo", "english-speaking", "beginner", "english-01")
        self.service.add_turn(
            session["id"], "user",
            "Well, the name is Visteria, how's playing? The name is Visteria.",
        )
        prompt = self.service.prompt(session["id"])
        self.assertIn("patient conversational English partner", prompt)
        self.assertIn("everyday greetings are not workplace problem solving", prompt)
        self.assertIn("workplace English may discuss work", prompt)
        self.assertNotIn("what specific action do you propose", prompt)
        reply = self.service.fallback_reply(session["id"])
        self.assertIn("Nice to meet you, Visteria", reply)
        self.assertIn("How's it going?", reply)
        self.assertNotIn("specific action", reply)

    def test_live_failure_continues_until_language_success_requirements_are_met(self):
        session = self.service.create_session("demo", "english-speaking", "beginner", "english-01")
        self.service.add_turn(session["id"], "user", "Hello, my name is Visteria.")
        first = self.service.evaluate_progress(session["id"])
        self.assertEqual(first["outcome"], "failure")
        self.assertTrue(first["continue_session"])
        self.service.add_turn(session["id"], "assistant", "Nice to meet you. How are you?", speaker_name="Neighbour")
        self.service.add_turn(session["id"], "user", "I am doing very well today, thank you for asking.")
        self.service.add_turn(session["id"], "assistant", "It was nice meeting you.", speaker_name="Neighbour")
        self.service.add_turn(session["id"], "user", "Goodbye, it was very nice meeting you too.")
        self.service.add_turn(session["id"], "assistant", "Before you go, how would you greet me tomorrow?", speaker_name="Neighbour")
        self.service.add_turn(session["id"], "user", "Good morning, Alex. It is lovely to see you again.")
        self.service.add_turn(session["id"], "assistant", "And what would you say after meeting someone new?", speaker_name="Neighbour")
        self.service.add_turn(session["id"], "user", "I would say that it was nice to meet them.")
        finished = self.service.evaluate_progress(session["id"])
        self.assertEqual(finished["outcome"], "success")
        self.assertFalse(finished["continue_session"])

    def test_all_english_lessons_expose_teaching_content_before_roleplay(self):
        for sequence in range(1, 31):
            preview = self.service.scenario_preview(
                "demo", "english-speaking", "beginner", f"english-{sequence:02d}"
            )
            design = preview["learning_design"]
            self.assertTrue(design["focus"])
            self.assertGreaterEqual(len(design["examples"]), 3)
            self.assertEqual(len(design["targets"]), 3)
            self.assertGreaterEqual(design["minimum_turns"], 3)
            self.assertGreaterEqual(design["max_answer_seconds"], 18)

    def test_language_assessment_uses_transcript_grounded_corrections(self):
        session = self.service.create_session("demo", "english-speaking", "beginner", "english-01")
        self.service.add_turn(session["id"], "user", "Hello, my name Abdul and I good today.", 4)
        assessment = self.service.assess(session["id"], {
            "scores": {"fluency": 54, "vocabulary": 61, "grammar": 42, "comprehension": 70, "delivery": 64},
            "strengths": ["You used 'Hello' appropriately.", "You answered the introduction question."],
            "improvements": ["Use 'is' in 'My name is Abdul'.", "Use 'am' in 'I am good today'."],
            "corrections": [{"original": "my name Abdul", "improved": "my name is Abdul", "reason": "The sentence needs the verb 'is'."}],
        })
        self.assertEqual(assessment["scores"]["grammar"], 42)
        self.assertIn("My name is Abdul", assessment["improvements"][0])
        self.assertTrue(any("my name is Abdul" in item for item in assessment["evidence"]))

    def test_round_robin_selects_one_next_speaker_instead_of_blocking_on_two(self):
        session = self.service.create_session("demo", "english-speaking", "intermediate", "english-20")
        self.service.add_turn(session["id"], "user", "I think our first priority should be understanding the deadline.")
        speakers = self.service.response_speakers(session["id"])
        self.assertEqual(len(speakers), 1)
        self.assertEqual(speakers[0]["name"], "Second Participant")

    def test_platform_catalog_and_dashboard_are_database_backed(self):
        activities = self.service.activities()
        resources = self.service.resources()
        dashboard = self.service.dashboard()
        self.assertEqual(len(activities), 42)
        english = [item for item in activities if item["training_language"] == "English"]
        self.assertEqual(len(english), 30)
        self.assertEqual([item["sequence_number"] for item in english], list(range(1, 31)))
        self.assertTrue(all(item["subskills"] for item in activities))
        self.assertEqual(len(resources), 7)
        self.assertTrue(all(item["content_text"] for item in resources))
        self.assertEqual(dashboard["user"]["name"], "Demo Learner")
        self.assertIn("practice_minutes", dashboard)
        self.assertIn("progress_history", dashboard)

    def test_english_lesson_controls_real_roleplay_mode_and_caption_policy(self):
        preview = self.service.scenario_preview("demo", "english-speaking", "advanced", "english-23")
        self.assertEqual(preview["roleplay_mode"], "learner_with_ai_team")
        self.assertEqual(preview["participants"], ["AI Teammate", "Decision-maker"])
        session = self.service.create_session("demo", "english-speaking", "advanced", "english-23")
        self.assertEqual([person["name"] for person in self.service.response_speakers(session["id"])], ["AI Teammate", "Decision-maker"])

        beginner = self.service.create_session("demo", "english-speaking", "beginner", "english-01")
        policy = self.service.caption_preferences(beginner["id"])
        self.assertTrue(policy["translate"])
        self.assertEqual(policy["language"], "Urdu")


if __name__ == "__main__":
    unittest.main()
