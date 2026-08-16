"""Live PostgreSQL acceptance test for plan management endpoints."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import create_app
from questionnaire_module import PostgresQuestionnaireRepository, QuestionnaireService
from session_module import PostgresSessionRepository, SessionService


class PlanModuleLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(database_url)
        sessions = SessionService(self.repository)
        questionnaire = QuestionnaireService(
            sessions,
            PostgresQuestionnaireRepository(database_url),
        )
        self.client = TestClient(create_app(sessions, questionnaire))
        created = self.client.post("/api/v1/sessions")
        self.assertEqual(created.status_code, 201)
        self.session_id = created.json()["data"]["session_id"]

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)
        self.client.close()

    def test_plan_mutation_and_confirmation(self) -> None:
        sid = self.session_id
        preferences = {
            "categories": ["energy"],
            "duration": "day",
            "budget": "high",
            "outing": "any",
            "company": "both",
            "city_or_campus": "测试校园",
            "rest_only": False,
        }
        self.assertEqual(
            self.client.put(f"/api/v1/sessions/{sid}/preferences", json=preferences).status_code,
            200,
        )
        started = self.client.post(
            f"/api/v1/sessions/{sid}/questionnaire/start",
            json={"mode": "quick"},
        ).json()["data"]
        for question in started["questions"]:
            response = self.client.patch(
                f"/api/v1/sessions/{sid}/questionnaire/answers/{question['id']}",
                json={"value": 3},
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/questionnaire/submit").status_code,
            200,
        )
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        generated = self.client.post(
            f"/api/v1/sessions/{sid}/plan/generate",
            json={
                "free_start": now.isoformat(),
                "free_end": (now + timedelta(hours=8)).isoformat(),
                "density": "balanced",
            },
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        plan = generated.json()["data"]["plan"]
        self.assertEqual(plan["session_id"], sid)
        self.assertTrue(plan["items"])

        updated = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/custom-tasks",
            json={
                "expected_version": plan["version"],
                "title": "写下今天的复盘",
                "duration_minutes": 20,
                "category": "自我成长",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        plan = updated.json()["data"]
        self.assertEqual(plan["version"], 2)
        custom = next(item for item in plan["items"] if item["title"] == "写下今天的复盘")

        skipped = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/items/{custom['id']}/skip",
            json={"expected_version": plan["version"]},
        )
        self.assertEqual(skipped.status_code, 200, skipped.text)
        plan = skipped.json()["data"]
        self.assertEqual(plan["version"], 3)

        confirmed = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/confirm",
            json={"expected_version": plan["version"]},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["data"]["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
