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
from task_repository import PUBLIC_TASKS


class PhaseTwoApiLiveTests(unittest.TestCase):
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
        created = self.client.post("/api/v1/sessions")
        self.assertEqual(created.status_code, 201)
        self.session_id = created.json()["data"]["session_id"]
        self.plan_id = f"plan_phase_two_{self.session_id}"
        self.item_id = f"item_phase_two_{self.session_id}"
        self.late_item_id = f"item_phase_two_late_{self.session_id}"
        self.task = next(
            task for task in PUBLIC_TASKS
            if task.feedback_group == "growth_reading_writing"
        )
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.now = now
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
                (self.plan_id, self.session_id, now, now + timedelta(hours=2), now),
            )
            connection.execute(
                """
                INSERT INTO plan_items
                    (id, plan_id, task_id, title, category, start_at, end_at,
                     kind, status, locked)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        'task', 'pending', FALSE),
                       (%s, %s, 'task_phase_two_late', '第二阶段超时任务', '松弛疗愈', %s, %s,
                        'task', 'pending', FALSE)
                """,
                (
                    self.item_id,
                    self.plan_id,
                    self.task.id,
                    self.task.title,
                    self.task.category,
                    now,
                    now + timedelta(minutes=30),
                    self.late_item_id,
                    self.plan_id,
                    now - timedelta(minutes=30),
                    now - timedelta(minutes=5),
                ),
            )

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)
        self.client.close()

    def test_execution_and_feedback_routes(self) -> None:
        started = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.item_id}/execution/start",
            json={"now": self.now.isoformat()},
        )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["data"]["status"], "active")

        completed = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.item_id}/execution/complete",
            json={"now": (self.now + timedelta(minutes=5)).isoformat()},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["data"]["status"], "completed")

        feedback = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.item_id}/feedback",
            json={"rating": 1, "reasons": ["不喜欢"]},
        )
        self.assertEqual(feedback.status_code, 200, feedback.text)
        self.assertEqual(feedback.json()["data"]["rating"], 1)
        self.assertEqual(
            feedback.json()["data"]["recommendation_memory"]["excluded_group_count"],
            1,
        )

        listed = self.client.get(f"/api/v1/plans/{self.plan_id}/feedback")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()["data"]), 1)

    def test_deadline_route_marks_task_for_adjustment(self) -> None:
        response = self.client.post(
            f"/api/v1/plans/{self.plan_id}/items/{self.late_item_id}/execution/check-deadline",
            json={"now": self.now.isoformat()},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["status"], "needs_adjustment")


if __name__ == "__main__":
    unittest.main()
