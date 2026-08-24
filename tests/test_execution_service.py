from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg

from execution_service import ExecutionService
from mvp_orchestrator import PostgreSQLPlanRepository
from recommendation_memory import RecommendationMemory
from session_module import PostgresSessionRepository, SessionService
from task_repository import PUBLIC_TASKS, TaskRepository


class ExecutionServiceLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(self.database_url)
        self.sessions = SessionService(self.repository)
        PostgreSQLPlanRepository(self.database_url)
        self.session = self.sessions.create()
        self.session_id = self.session["session_id"]
        self.plan_id = f"plan_exec_test_{self.session_id}"
        self.item_id = f"item_exec_test_{self.session_id}"
        self.late_item_id = f"item_late_test_{self.session_id}"
        self.task = next(
            task for task in PUBLIC_TASKS
            if task.feedback_group == "energy_mobility_home"
        )
        self.now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
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
                    self.now + timedelta(hours=3),
                    self.now,
                ),
            )
            connection.execute(
                """
                INSERT INTO plan_items
                    (id, plan_id, task_id, title, category, start_at, end_at,
                     kind, status, locked)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        'task', 'pending', FALSE),
                       (%s, %s, 'task_late', '测试超时任务', '松弛疗愈', %s, %s,
                        'task', 'pending', FALSE)
                """,
                (
                    self.item_id,
                    self.plan_id,
                    self.task.id,
                    self.task.title,
                    self.task.category,
                    self.now - timedelta(minutes=5),
                    self.now + timedelta(minutes=20),
                    self.late_item_id,
                    self.plan_id,
                    self.now - timedelta(minutes=40),
                    self.now - timedelta(minutes=10),
                ),
            )
        self.memory = RecommendationMemory(
            self.database_url,
            self.sessions,
            TaskRepository(),
        )
        self.service = ExecutionService(
            self.database_url,
            self.sessions,
            memory=self.memory,
        )

    def tearDown(self) -> None:
        self.repository.delete(self.session_id)

    def test_start_and_complete_persist_status_and_events(self) -> None:
        started = self.service.execute(
            self.session_id,
            self.plan_id,
            self.item_id,
            "start",
            now=self.now,
        )
        self.assertEqual(started["status"], "active")

        completed = self.service.execute(
            self.session_id,
            self.plan_id,
            self.item_id,
            "complete",
            now=self.now + timedelta(minutes=5),
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(
            [event["event_type"] for event in self.service.events(
                self.session_id, self.plan_id, self.item_id
            )],
            ["started", "completed"],
        )

    def test_deadline_marks_pending_item_for_adjustment_once(self) -> None:
        first = self.service.check_deadline(
            self.session_id,
            self.plan_id,
            self.late_item_id,
            now=self.now,
        )
        second = self.service.check_deadline(
            self.session_id,
            self.plan_id,
            self.late_item_id,
            now=self.now + timedelta(minutes=1),
        )
        self.assertEqual(first["status"], "needs_adjustment")
        self.assertEqual(second["status"], "needs_adjustment")
        self.assertEqual(
            len(self.service.events(self.session_id, self.plan_id, self.late_item_id)),
            1,
        )

    def test_execution_skip_records_an_exclusion(self) -> None:
        payload = self.service.execute(
            self.session_id,
            self.plan_id,
            self.item_id,
            "skip",
            now=self.now - timedelta(minutes=10),
        )

        self.assertEqual(payload["status"], "needs_adjustment")
        self.assertEqual(payload["events"][0]["event_type"], "skipped")
        self.assertEqual(
            payload["recommendation_memory"]["excluded_group_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
