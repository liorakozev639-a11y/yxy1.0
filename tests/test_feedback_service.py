from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import HTTPException

from feedback_service import FeedbackService
from mvp_orchestrator import PostgreSQLPlanRepository
from recommendation_memory import RecommendationMemory
from session_module import PostgresSessionRepository, SessionService
from task_repository import PUBLIC_TASKS, TaskRepository


class FeedbackServiceLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(self.database_url)
        self.sessions = SessionService(self.repository)
        PostgreSQLPlanRepository(self.database_url)
        session = self.sessions.create()
        self.session_id = session["session_id"]
        self.plan_id = f"plan_feedback_test_{self.session_id}"
        self.item_id = f"item_feedback_test_{self.session_id}"
        self.second_item_id = f"item_feedback_second_{self.session_id}"
        self.low_task = next(
            task for task in PUBLIC_TASKS
            if task.feedback_group == "growth_reading_writing"
        )
        self.high_task = next(
            task for task in PUBLIC_TASKS
            if task.feedback_group == "growth_digital_organize"
        )
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'task', 'completed', FALSE),
                       (%s, %s, %s, %s, %s, %s, %s, 'task', 'completed', FALSE)
                """,
                (
                    self.item_id,
                    self.plan_id,
                    self.low_task.id,
                    self.low_task.title,
                    self.low_task.category,
                    now,
                    now + timedelta(minutes=30),
                    self.second_item_id,
                    self.plan_id,
                    self.high_task.id,
                    self.high_task.title,
                    self.high_task.category,
                    now + timedelta(minutes=35),
                    now + timedelta(minutes=65),
                ),
            )
        self.memory = RecommendationMemory(
            self.database_url,
            self.sessions,
            TaskRepository(),
        )
        self.service = FeedbackService(
            self.database_url,
            self.sessions,
            memory=self.memory,
        )

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

    def test_low_rating_records_an_exclusion_but_high_rating_does_not(self) -> None:
        low = self.service.save(
            self.session_id,
            self.plan_id,
            self.item_id,
            rating=1,
            reasons=[],
        )
        self.assertEqual(low["recommendation_memory"]["excluded_group_count"], 1)

        high = self.service.save(
            self.session_id,
            self.plan_id,
            self.second_item_id,
            rating=5,
            reasons=[],
        )
        self.assertNotIn("recommendation_memory", high)
        self.assertEqual(self.memory.summary(self.session_id)["excluded_group_count"], 1)

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
