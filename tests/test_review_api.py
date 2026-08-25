from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi.testclient import TestClient

from main import create_app
from mvp_orchestrator import PostgreSQLPlanRepository
from questionnaire_module import PostgresQuestionnaireRepository, QuestionnaireService
from session_module import PostgresSessionRepository, SessionService


class ReviewApiLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")

        self.repository = PostgresSessionRepository(self.database_url)
        sessions = SessionService(self.repository)
        PostgreSQLPlanRepository(self.database_url)
        questionnaire = QuestionnaireService(
            sessions,
            PostgresQuestionnaireRepository(self.database_url),
        )
        self.client = TestClient(create_app(sessions, questionnaire))
        self.session_id = self.client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.plan_id = f"plan_review_api_{self.session_id}"
        self.completed_item_id = f"item_review_api_completed_{self.session_id}"
        self.pending_item_id = f"item_review_api_pending_{self.session_id}"

        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "ALTER TABLE plans ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft'"
            )
            connection.execute(
                """
                INSERT INTO plans
                    (id, session_id, density, free_start, free_end, version,
                     parent_plan_id, unscheduled_task_ids, created_at, status)
                VALUES (%s, %s, 'balanced', %s, %s, 1, NULL, '[]'::jsonb, %s, 'draft')
                """,
                (
                    self.plan_id,
                    self.session_id,
                    self.now - timedelta(hours=1),
                    self.now + timedelta(minutes=2),
                    self.now,
                ),
            )
            connection.execute(
                """
                INSERT INTO plan_items
                    (id, plan_id, task_id, title, category, start_at, end_at,
                     kind, status, locked)
                VALUES
                    (%s, %s, 'task_completed', '已完成任务', '自我成长', %s, %s,
                     'task', 'completed', FALSE),
                    (%s, %s, 'task_pending', '待处理任务', '松弛疗愈', %s, %s,
                     'task', 'pending', FALSE)
                """,
                (
                    self.completed_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=40),
                    self.now - timedelta(minutes=10),
                    self.pending_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=30),
                    self.now - timedelta(minutes=5),
                ),
            )

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)
        self.client.close()

    def test_refresh_reflection_and_review_routes(self) -> None:
        refreshed = self.client.post(
            f"/api/v1/plans/{self.plan_id}/execution/refresh"
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertIn("reminders", refreshed.json()["data"])

        reflection = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.completed_item_id}/reflection",
            json={"sentiment": "satisfied"},
        )
        self.assertEqual(reflection.status_code, 200, reflection.text)
        self.assertEqual(reflection.json()["data"]["sentiment"], "satisfied")

        review = self.client.get(f"/api/v1/plans/{self.plan_id}/review")
        self.assertEqual(review.status_code, 200, review.text)
        self.assertIn("suggestions", review.json()["data"])

    def test_reflection_rejects_invalid_and_unfinished_items(self) -> None:
        invalid = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.completed_item_id}/reflection",
            json={"sentiment": "bad"},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)

        unfinished = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.pending_item_id}/reflection",
            json={"sentiment": "neutral"},
        )
        self.assertEqual(unfinished.status_code, 409, unfinished.text)


if __name__ == "__main__":
    unittest.main()
