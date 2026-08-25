from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import HTTPException

from execution_service import ExecutionService
from mvp_orchestrator import PostgreSQLPlanRepository
from review_service import ReviewService
from session_module import PostgresSessionRepository, SessionService


class ReviewServiceLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")

        self.repository = PostgresSessionRepository(self.database_url)
        self.sessions = SessionService(self.repository)
        PostgreSQLPlanRepository(self.database_url)
        self.session_id = self.sessions.create()["session_id"]
        self.now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.plan_id = f"plan_review_{self.session_id}"
        self.completed_item_id = f"item_review_completed_{self.session_id}"
        self.pending_item_id = f"item_review_pending_{self.session_id}"
        self.active_item_id = f"item_review_active_{self.session_id}"

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
                    self.now + timedelta(minutes=5),
                    self.now,
                ),
            )
            connection.execute(
                """
                INSERT INTO plan_items
                    (id, plan_id, task_id, title, category, start_at, end_at,
                     kind, status, locked)
                VALUES
                    (%s, %s, 'task_completed', '完成的任务', '自我成长', %s, %s,
                     'task', 'completed', FALSE),
                    (%s, %s, 'task_pending', '未开始任务', '松弛疗愈', %s, %s,
                     'task', 'pending', FALSE),
                    (%s, %s, 'task_active', '进行中任务', '活力充电', %s, %s,
                     'task', 'active', FALSE)
                """,
                (
                    self.completed_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=50),
                    self.now - timedelta(minutes=30),
                    self.pending_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=40),
                    self.now - timedelta(minutes=10),
                    self.active_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=35),
                    self.now - timedelta(minutes=5),
                ),
            )

        execution = ExecutionService(self.database_url, self.sessions)
        self.service = ReviewService(self.database_url, self.sessions, execution)

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)

    def test_refresh_marks_expired_items_once_and_returns_summary(self) -> None:
        first = self.service.refresh_plan(
            self.session_id,
            self.plan_id,
            now=self.now,
        )
        second = self.service.refresh_plan(
            self.session_id,
            self.plan_id,
            now=self.now + timedelta(minutes=1),
        )

        self.assertEqual(first["summary"]["needs_adjustment_count"], 2)
        self.assertEqual(first["reminders"]["needs_adjustment_count"], 2)
        self.assertEqual(second["summary"]["needs_adjustment_count"], 2)
        self.assertEqual(len(first["events"]), 2)
        self.assertEqual(second["events"], [])

    def test_reflection_requires_completed_item_and_overwrites_previous_value(self) -> None:
        with self.assertRaises(HTTPException) as unfinished:
            self.service.save_reflection(
                self.session_id,
                self.plan_id,
                self.pending_item_id,
                "satisfied",
            )
        self.assertEqual(unfinished.exception.status_code, 409)

        first = self.service.save_reflection(
            self.session_id,
            self.plan_id,
            self.completed_item_id,
            "satisfied",
        )
        second = self.service.save_reflection(
            self.session_id,
            self.plan_id,
            self.completed_item_id,
            "neutral",
        )

        self.assertEqual(first["sentiment"], "satisfied")
        self.assertEqual(second["sentiment"], "neutral")

    def test_finished_review_aggregates_outcomes_and_sentiment(self) -> None:
        self.service.refresh_plan(self.session_id, self.plan_id, now=self.now)
        self.service.save_reflection(
            self.session_id,
            self.plan_id,
            self.completed_item_id,
            "satisfied",
        )

        review = self.service.get_review(
            self.session_id,
            self.plan_id,
            now=self.now + timedelta(minutes=10),
        )

        self.assertEqual(review["status"], "finished")
        self.assertEqual(review["summary"]["total_tasks"], 3)
        self.assertEqual(review["summary"]["completed_count"], 1)
        self.assertEqual(review["summary"]["unfinished_count"], 2)
        self.assertEqual(review["summary"]["satisfied_count"], 1)
        self.assertEqual(review["summary"]["neutral_count"], 0)
        self.assertTrue(review["suggestions"])


if __name__ == "__main__":
    unittest.main()
