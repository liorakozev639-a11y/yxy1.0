import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mock_task_generation import (
    MockTaskGenerator,
    build_generation_context,
    validate_brief,
    validate_candidates,
)


class MockTaskGenerationTests(unittest.TestCase):
    def context(self, *, energy="low", budget=20):
        now = datetime(2026, 9, 19, 9, tzinfo=timezone.utc)
        session = SimpleNamespace(
            id="sess_mock",
            preferences={
                "categories": ["energy", "calm"],
                "budget": "low",
                "outing": "home",
                "company": "solo",
                "energy_level": energy,
            },
        )
        profile = SimpleNamespace(
            scores={"活力充电": 0.8, "松弛疗愈": 0.6},
            constraints={
                "categories": ["活力充电", "松弛疗愈"],
                "budget_limit": budget,
                "max_duration": 270,
                "outing": "home",
                "company": "solo",
                "energy_level": energy,
            },
            confidence=0.8,
            rule_version="profile-rule-v1",
        )
        questionnaire = SimpleNamespace(
            mode="quick", question_ids=["q1", "q2"], submitted=True
        )
        questions = {
            "q1": SimpleNamespace(id="q1", prompt="喜欢轻量活动吗？", dimension="energy"),
            "q2": SimpleNamespace(id="q2", prompt="喜欢安静休息吗？", dimension="calm"),
        }
        answers = [
            SimpleNamespace(question_id="q1", value=4, skipped=False),
            SimpleNamespace(question_id="q2", value=None, skipped=True),
        ]
        request = SimpleNamespace(free_start=now, free_end=now + timedelta(hours=3), density="balanced")
        return build_generation_context(session, questionnaire, questions, answers, profile, request)

    def test_skipped_answer_is_unknown_not_preference(self):
        context = self.context()
        self.assertIn("question:q1", context["sources"])
        self.assertNotIn("question:q2", context["sources"])
        self.assertIn("q2", context["unknown_question_ids"])
        self.assertNotIn("profile:松弛疗愈", context["sources"])

    def test_brief_cannot_relax_hard_constraints(self):
        context = self.context()
        brief = MockTaskGenerator().write_brief(context)
        self.assertEqual(validate_brief(brief, context), [])
        brief["hard_constraints"]["budget_limit"] = 100
        self.assertIn("hard_constraints", validate_brief(brief, context))

    def test_fabricated_evidence_and_invalid_load_are_rejected(self):
        context = self.context()
        generator = MockTaskGenerator()
        brief = generator.write_brief(context)
        candidate = generator.generate_tasks(context, brief, 1, set())[0]
        candidate["evidence_refs"] = ["question:q2"]
        candidate["physical_load"] = 5
        accepted, rejected = validate_candidates([candidate], context, set())
        self.assertEqual(accepted, [])
        self.assertIn("unknown_evidence", rejected[0]["reasons"])
        self.assertIn("physical_load", rejected[0]["reasons"])

    def test_generator_never_reuses_excluded_signature(self):
        context = self.context(energy="medium")
        generator = MockTaskGenerator()
        brief = generator.write_brief(context)
        first = generator.generate_tasks(context, brief, 10, set())
        accepted, rejected = validate_candidates(first, context, set())
        self.assertFalse(rejected)
        self.assertEqual(len(accepted), 10)
        signatures = {task["semantic_signature"] for task in accepted}
        self.assertEqual(len(signatures), 10)
        later = generator.generate_tasks(context, brief, 1, signatures)
        self.assertTrue(later)
        self.assertNotIn(later[0]["semantic_signature"], signatures)

    def test_malformed_model_fields_are_rejected_without_crashing(self):
        context = self.context()
        generator = MockTaskGenerator()
        candidate = generator.generate_tasks(context, generator.write_brief(context), 1, set())[0]
        candidate["evidence_refs"] = [{"invalid": "ref"}]
        candidate["outing"] = ["home"]
        accepted, rejected = validate_candidates([candidate], context, set())
        self.assertEqual(accepted, [])
        self.assertIn("unknown_evidence", rejected[0]["reasons"])
        self.assertIn("outing", rejected[0]["reasons"])


if __name__ == "__main__":
    unittest.main()
