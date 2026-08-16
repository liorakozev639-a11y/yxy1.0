from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import HTTPException

from feedback_service import FeedbackService
from session_module import PostgresSessionRepository, SessionService


class FeedbackServiceLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(self.database_url)
        self.sessions = SessionService(self.repository)
        session = self.sessions.create()
        self.session_id = session["session_id"]
        self.plan_id = f"plan_feedback_test_{self.session_id}"
        self.item_id = f"item_feedback_test_{self.session_id}"
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
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
                    now,
                    now + timedelta(hours=2),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO plan_items
                    (id, plan_id, task_id, title, category, start_at, end_at,
                     kind, status, locked)
                VALUES (%s, %s, 'task_feedback', '反馈测试任务', '自我成长', %s, %s,
                        'task', 'completed', FALSE)
                """,
                (
                    self.item_id,
                    self.plan_id,
                    now,
                    now + timedelta(minutes=30),
                ),
            )
        self.service = FeedbackService(self.database_url, self.sessions)

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)

    def test_save_and_update_feedback(self) -> None:
        first = self.service.save(
            self.session_id,
            self.plan_id,
            self.item_id,
            rating=4,
            reasons=["很容易开始", "符合当前状态"],
        )
        self.assertEqual(first["rating"], 4)
        self.assertEqual(first["reasons"], ["很容易开始", "符合当前状态"])

        updated = self.service.save(
            self.session_id,
            self.plan_id,
            self.item_id,
            rating=5,
            reasons=["下次还想做"],
        )
        self.assertEqual(updated["rating"], 5)
        self.assertEqual(self.service.list_for_plan(self.session_id, self.plan_id), [updated])

    def test_rejects_unfinished_item_and_too_many_reasons(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE plan_items SET status = 'active' WHERE id = %s",
                (self.item_id,),
            )
        with self.assertRaises(HTTPException) as unfinished:
            self.service.save(
                self.session_id,
                self.plan_id,
                self.item_id,
                rating=4,
                reasons=[],
            )
        self.assertEqual(unfinished.exception.status_code, 409)

        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE plan_items SET status = 'completed' WHERE id = %s",
                (self.item_id,),
            )
        with self.assertRaises(HTTPException) as too_many:
            self.service.save(
                self.session_id,
                self.plan_id,
                self.item_id,
                rating=4,
                reasons=["1", "2", "3", "4"],
            )
        self.assertEqual(too_many.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
