import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from mvp_orchestrator import GeneratePlanRequest, MVPOrchestrator
from questionnaire_module import Answer, Question, QuestionnaireSession
from task_repository import CATEGORIES, TaskRepository


class FakeSessionService:
    def __init__(self, preferences):
        self.session = type(
            "SessionValue",
            (),
            {"id": "sess_integration", "preferences": preferences},
        )()

    def require_active(self, session_id):
        if session_id != self.session.id:
            raise AssertionError("unexpected session")
        return self.session


class FakeQuestionnaireRepository:
    def __init__(self, questionnaire, answers):
        self.questionnaire = questionnaire
        self.answers = answers

    def get_questionnaire(self, session_id):
        return self.questionnaire if session_id == self.questionnaire.session_id else None

    def get_answers(self, session_id):
        return list(self.answers) if session_id == self.questionnaire.session_id else []


class FakeQuestionnaireService:
    def __init__(self, repository, questions):
        self.repository = repository
        self.questions = {question.id: question for question in questions}


class FakeProfileRepository:
    def __init__(self):
        self.saved = []

    def next_version(self, session_id):
        return len(self.saved) + 1

    def save(self, profile):
        self.saved.append(profile)

    def get(self, session_id):
        for profile in reversed(self.saved):
            if profile.session_id == session_id:
                return profile
        return None


class FakePlanRepository:
    def __init__(self):
        self.saved = []

    def save(self, plan):
        self.saved.append(plan)

    def get(self, session_id):
        for plan in reversed(self.saved):
            if plan.session_id == session_id:
                return plan
        return None


class FakeDeliveryService:
    def __init__(self):
        self.deliveries = []

    def deliver(self, session_id, plan, now=None):
        delivery = {
            "session_id": session_id,
            "plan_id": plan.id,
            "channel": "web",
            "status": "ready",
            "payload": {"items": [item.id for item in plan.items]},
        }
        self.deliveries.append(delivery)
        return delivery


class MVPIntegrationTests(unittest.TestCase):
    def test_generate_plan_completes_profile_recommendation_schedule_delivery(self):
        now = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)
        questions = [
            Question(
                id=f"q_{index}",
                mode="quick",
                category=category,
                dimension=dimension,
                prompt=f"偏好 {category}",
            )
            for index, (category, dimension) in enumerate(
                zip(CATEGORIES, ["energy", "recovery", "social", "exploration", "growth"]),
                start=1,
            )
        ]
        questionnaire = QuestionnaireSession(
            session_id="sess_integration",
            mode="quick",
            question_ids=[question.id for question in questions],
            submitted=True,
        )
        answers = [
            Answer(
                session_id="sess_integration",
                question_id=question.id,
                value=4,
                skipped=False,
                answered_at=now,
            )
            for question in questions
        ]
        preferences = {
            "categories": list(CATEGORIES),
            "duration": "half",
            "budget": "medium",
            "outing": "home",
            "company": "both",
            "city_or_campus": "测试校园",
        }
        questionnaire_service = FakeQuestionnaireService(
            FakeQuestionnaireRepository(questionnaire, answers),
            questions,
        )
        delivery = FakeDeliveryService()
        orchestrator = MVPOrchestrator(
            sessions=FakeSessionService(preferences),
            questionnaire=questionnaire_service,
            tasks=TaskRepository(),
            profiles=FakeProfileRepository(),
            plans=FakePlanRepository(),
            delivery=delivery,
        )

        result = orchestrator.generate_plan(
            "sess_integration",
            GeneratePlanRequest(
                free_start=now,
                free_end=now + timedelta(hours=4),
                density="balanced",
            ),
        )

        self.assertEqual(result["delivery"]["channel"], "web")
        self.assertEqual(result["profile"]["rule_version"], "profile-rule-v1")
        self.assertEqual(result["plan"]["session_id"], "sess_integration")
        self.assertTrue(result["plan"]["items"])
        self.assertTrue(any(item["kind"] == "rest" for item in result["plan"]["items"]))
        self.assertEqual(set(result["recommendation"]["covered_categories"]), set(CATEGORIES))


if __name__ == "__main__":
    unittest.main()
