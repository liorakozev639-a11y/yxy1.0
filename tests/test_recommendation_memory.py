from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg

from mvp_orchestrator import PostgreSQLPlanRepository
from recommendation_memory import RecommendationMemory
from session_module import PostgresSessionRepository, SessionService
from task_repository import PUBLIC_TASKS, TaskRepository


class RecommendationMemoryLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(self.database_url)
        PostgreSQLPlanRepository(self.database_url)
        self.sessions = SessionService(self.repository)
        self.session_id = self.sessions.create()["session_id"]
        self.other_session_id = self.sessions.create()["session_id"]
        self.task = next(
            task
            for task in PUBLIC_TASKS
            if task.feedback_group == "growth_reading_writing"
        )
        self.plan_id = f"plan_memory_{self.session_id}"
        self.item_id = f"item_memory_{self.session_id}"
        self.sibling_item_id = f"item_memory_sibling_{self.session_id}"
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
                (self.plan_id, self.session_id, now, now + timedelta(hours=2), now),
            )
            for item_id in (self.item_id, self.sibling_item_id):
                connection.execute(
                    """
                    INSERT INTO plan_items
                        (id, plan_id, task_id, title, category, start_at, end_at,
                         kind, status, locked)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'task', 'completed', FALSE)
                    """,
                    (
                        item_id,
                        self.plan_id,
                        self.task.id,
                        self.task.title,
                        self.task.category,
                        now,
                        now + timedelta(minutes=self.task.duration),
                    ),
                )
        self.memory = RecommendationMemory(
            self.database_url,
            self.sessions,
            TaskRepository(),
        )

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)
        self.repository.delete(self.other_session_id)

    def test_recording_same_group_is_idempotent_and_session_scoped(self) -> None:
        first = self.memory.record_plan_item_exclusion(
            self.session_id,
            self.plan_id,
            self.item_id,
            "low_rating",
        )
        second = self.memory.record_plan_item_exclusion(
            self.session_id,
            self.plan_id,
            self.sibling_item_id,
            "skipped",
        )

        self.assertEqual(first["feedback_group"], "growth_reading_writing")
        self.assertEqual(second["feedback_group"], "growth_reading_writing")
        self.assertEqual(
            self.memory.list_excluded_groups(self.session_id),
            {"growth_reading_writing"},
        )
        self.assertEqual(self.memory.list_excluded_groups(self.other_session_id), set())
        self.assertEqual(
            self.memory.summary(self.session_id)["excluded_group_count"],
            1,
        )
        self.assertGreaterEqual(
            self.memory.summary(self.session_id)["excluded_task_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
