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


class FakeRecommendationMemory:
    def __init__(self, excluded_groups):
        self.excluded_groups = set(excluded_groups)

    def list_excluded_groups(self, session_id):
        if session_id != "sess_integration":
            raise AssertionError("unexpected session")
        return set(self.excluded_groups)


class FakeOrchestrator:
    def build_profile_insight(self, session_id):
        return {
            "session_id": session_id,
            "profile_version": 1,
            "summary": "你当前更偏向活力充电。",
            "top_dimensions": [
                {"dimension": "energy", "label": "活力充电", "score": 0.8},
            ],
            "constraint_cards": [],
            "suggestions": [],
        }

    def generate_plan(self, session_id, request, user_id=None):
        return {
            "profile": {"session_id": session_id},
            "recommendation": {"covered_categories": []},
            "plan": {"plan_id": "plan_api", "items": []},
            "delivery": {"channel": "web", "status": "ready"},
        }

    def get_plan(self, session_id):
        return {"plan_id": "plan_api", "session_id": session_id, "items": []}


class MVPIntegrationTests(unittest.TestCase):
    def test_initial_recommendation_uses_session_exclusions(self):
        orchestrator = MVPOrchestrator(
            sessions=FakeSessionService({}),
            questionnaire=None,
            tasks=TaskRepository(),
            profiles=None,
            plans=None,
            delivery=None,
            memory=FakeRecommendationMemory({"recovery_quiet_home"}),
        )
        profile = {
            "session_id": "sess_integration",
            "scores": {"松弛疗愈": 1.0},
            "constraints": {
                "budget_limit": 40,
                "max_duration": 270,
                "outing": "home",
                "company": "solo",
                "scenarios": None,
            },
        }

        result = orchestrator._recommend(profile, ["松弛疗愈"])

        self.assertTrue(result["tasks"])
        self.assertTrue(
            all(
                task["feedback_group"] != "recovery_quiet_home"
                for task in result["tasks"]
            )
        )
        self.assertEqual(result["recommendation_memory"]["excluded_group_count"], 1)

    def test_questionnaire_recommendation_returns_ten_tasks(self):
        orchestrator = MVPOrchestrator(
            sessions=FakeSessionService({}),
            questionnaire=None,
            tasks=TaskRepository(),
            profiles=None,
            plans=None,
            delivery=None,
        )
        profile = {
            "session_id": "sess_integration",
            "scores": {category: 1.0 for category in CATEGORIES},
            "constraints": {
                "budget_limit": 80,
                "max_duration": 270,
                "outing": "any",
                "company": "both",
                "scenarios": None,
            },
        }

        result = orchestrator._recommend(profile, list(CATEGORIES))

        self.assertEqual(len(result["tasks"]), 10)
        self.assertEqual(len(result["task_ids"]), 10)

    def test_group_nearby_medium_tasks_cover_selected_categories(self):
        selected_categories = ["松弛疗愈", "社交连接", "乐享探索"]

        candidates = TaskRepository().search_tasks(
            session_id="sess_group_nearby",
            budget_limit=40,
            max_duration=270,
            outing="nearby",
            company="group",
            categories=selected_categories,
        )

        self.assertEqual(
            {task.category for task in candidates},
            set(selected_categories),
        )

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
            "categories": ["energy", "recovery", "social", "explore", "growth"],
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
        task_item = next(item for item in result["plan"]["items"] if item["kind"] == "task")
        self.assertIn("match_score", task_item)
        self.assertIn("matched_preferences", task_item)
        self.assertIn("warning_text", task_item)

    def test_api_exposes_generate_and_get_plan_routes(self):
        from fastapi.testclient import TestClient
        from main import create_app

        client = TestClient(
            create_app(
                FakeSessionService({}),
                FakeQuestionnaireService(
                    FakeQuestionnaireRepository(
                        QuestionnaireSession(
                            session_id="sess_api",
                            mode="quick",
                            question_ids=[],
                            submitted=True,
                        ),
                        [],
                    ),
                    [],
                ),
                FakeOrchestrator(),
            )
        )
        generated = client.post(
            "/api/v1/sessions/sess_api/plan/generate",
            json={
                "free_start": "2026-08-09T10:00:00Z",
                "free_end": "2026-08-09T14:00:00Z",
                "density": "balanced",
            },
        )
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["data"]["delivery"]["channel"], "web")

        restored = client.get("/api/v1/sessions/sess_api/plan")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["data"]["plan_id"], "plan_api")
        client.close()

    def test_api_exposes_profile_insight_route(self):
        from fastapi.testclient import TestClient
        from main import create_app

        client = TestClient(
            create_app(
                FakeSessionService({}),
                FakeQuestionnaireService(
                    FakeQuestionnaireRepository(
                        QuestionnaireSession(
                            session_id="sess_api",
                            mode="quick",
                            question_ids=[],
                            submitted=True,
                        ),
                        [],
                    ),
                    [],
                ),
                FakeOrchestrator(),
            )
        )

        response = client.get("/api/v1/sessions/sess_api/profile/insight")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["profile_version"], 1)
        self.assertIn("活力充电", response.json()["data"]["summary"])
        client.close()


if __name__ == "__main__":
    unittest.main()
