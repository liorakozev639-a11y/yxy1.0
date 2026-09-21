import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mock_task_service import MockTaskGenerationService
from mvp_orchestrator import GeneratePlanRequest, MVPOrchestrator
from questionnaire_module import Answer, Question, QuestionnaireSession
from test_mock_task_service import FakeGeneratedRepository


class NoOldTaskBank:
    def search_tasks(self, **kwargs):
        raise AssertionError("mock mode must not query the public task bank")


class Sessions:
    def __init__(self):
        self.session = SimpleNamespace(
            id="sess_mock",
            preferences={
                "categories": ["energy", "calm"],
                "duration": "half",
                "budget": "low",
                "outing": "home",
                "company": "solo",
                "energy_level": "low",
            },
        )

    def require_active(self, session_id):
        if session_id != self.session.id:
            raise AssertionError("unknown session")
        return self.session


class Profiles:
    def __init__(self):
        self.saved = []

    def next_version(self, session_id):
        return len(self.saved) + 1

    def save(self, profile):
        self.saved.append(profile)


class Plans:
    def __init__(self):
        self.saved = []

    def save(self, plan):
        self.saved.append(plan)
        return plan

    def get(self, session_id):
        return self.saved[-1] if self.saved else None


class Delivery:
    def deliver(self, session_id, plan):
        return {"session_id": session_id, "status": "ready"}


class MockOrchestratorTests(unittest.TestCase):
    def test_generate_plan_uses_mock_tasks_and_keeps_response_contract(self):
        questions = [
            Question("q1", "quick", "活力充电", "energy", "喜欢轻量活动吗？"),
            Question("q2", "quick", "松弛疗愈", "calm", "喜欢安静休息吗？"),
        ]
        questionnaire = QuestionnaireSession("sess_mock", "quick", ["q1", "q2"], submitted=True)
        answers = [
            Answer("sess_mock", "q1", 4, False, datetime.now(timezone.utc)),
            Answer("sess_mock", "q2", None, True, datetime.now(timezone.utc)),
        ]
        questionnaire_service = SimpleNamespace(
            repository=SimpleNamespace(
                get_questionnaire=lambda _: questionnaire,
                get_answers=lambda _: answers,
            ),
            questions={question.id: question for question in questions},
        )
        generated_repo = FakeGeneratedRepository()
        orchestrator = MVPOrchestrator(
            sessions=Sessions(),
            questionnaire=questionnaire_service,
            tasks=NoOldTaskBank(),
            profiles=Profiles(),
            plans=Plans(),
            delivery=Delivery(),
            mock_generation=MockTaskGenerationService(generated_repo),
        )
        start = datetime(2026, 9, 19, 9, tzinfo=timezone.utc)
        result = orchestrator.generate_plan(
            "sess_mock", GeneratePlanRequest(start, start + timedelta(hours=3))
        )
        self.assertEqual(set(result), {"profile", "recommendation", "plan", "delivery"})
        recommendation = result["recommendation"]
        self.assertEqual(recommendation["generation_mode"], "mock")
        self.assertEqual(len(recommendation["tasks"]), 10)
        self.assertTrue(all(task["id"].startswith("mock_") for task in recommendation["tasks"]))
        scheduled_ids = {
            item["task_id"] for item in result["plan"]["items"] if item["kind"] == "task"
        }
        self.assertTrue(scheduled_ids)
        self.assertTrue(scheduled_ids <= set(recommendation["task_ids"]))
        self.assertTrue(all(generated_repo.get_task("sess_mock", task_id) for task_id in scheduled_ids))
        self.assertTrue(all(item.get("first_action") for item in result["plan"]["items"] if item["kind"] == "task"))
        repeated = orchestrator.generate_plan(
            "sess_mock", GeneratePlanRequest(start, start + timedelta(hours=3))
        )
        self.assertEqual(repeated["plan"]["plan_id"], result["plan"]["plan_id"])
        self.assertEqual(len(orchestrator.plans.saved), 1)


if __name__ == "__main__":
    unittest.main()
