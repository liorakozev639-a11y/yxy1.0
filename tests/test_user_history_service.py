from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg

from mvp_orchestrator import PostgreSQLPlanRepository
from session_module import PostgresSessionRepository, SessionService
from task_repository import TaskRepository
from user_history_service import UserHistoryService


class UserHistoryServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.environ["SESSION_DATABASE_URL"]
        self.sessions = SessionService(PostgresSessionRepository(database_url))
        self.tasks = TaskRepository()
        self.plan_repository = PostgreSQLPlanRepository(database_url)
        self.history = UserHistoryService(database_url)
        created = self.sessions.create()
        self.session_id = created["session_id"]
        self.addCleanup(self.sessions.repository.delete, self.session_id)
        self.task = self.tasks.public_tasks[0]
        self.plan_id = f"plan_test_{self.session_id}"
        self.item_id = f"item_test_{self.session_id}"
        start_at = datetime.now(timezone.utc).replace(microsecond=0)
        end_at = start_at + timedelta(minutes=self.task.duration)
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO plans (
                        id, session_id, density, free_start, free_end, version,
                        parent_plan_id, unscheduled_task_ids, created_at
                    ) VALUES (%s, %s, 'balanced', %s, %s, 1, NULL, '[]'::jsonb, %s)
                    """,
                    (self.plan_id, self.session_id, start_at, end_at, start_at),
                )
                cursor.execute(
                    """
                    INSERT INTO plan_items (
                        id, plan_id, task_id, title, category, start_at, end_at,
                        kind, status, locked, replacement_history
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'task', 'planned', FALSE, '[]'::jsonb)
                    """,
                    (
                        self.item_id,
                        self.plan_id,
                        self.task.id,
                        self.task.title,
                        self.task.category,
                        start_at,
                        end_at,
                    ),
                )

    def test_ensure_user_creates_and_restores_anonymous_user(self) -> None:
        created = self.history.ensure_user()
        restored = self.history.ensure_user(created["user_id"])

        self.assertTrue(created["created"])
        self.assertFalse(restored["created"])
        self.assertEqual(restored["user_id"], created["user_id"])

    def test_record_completed_action_updates_summary_and_weights(self) -> None:
        user = self.history.ensure_user()
        record = self.history.record_action(
            user["user_id"],
            self.session_id,
            self.plan_id,
            self.item_id,
            "completed",
        )

        summary = self.history.summary(user["user_id"])
        weights = self.history.preference_weights(user["user_id"])

        self.assertEqual(record["action"], "completed")
        self.assertEqual(summary["completed_count"], 1)
        self.assertIn(self.task.category, summary["top_completed_categories"])
        self.assertGreater(weights["category_boosts"][self.task.category], 0)
        self.assertEqual(weights["preferred_duration_minutes"], self.task.duration)

    def test_one_negative_action_is_counted_but_not_excluded(self) -> None:
        user = self.history.ensure_user()
        self.history.record_action(
            user["user_id"], self.session_id, self.plan_id, self.item_id, "skipped"
        )

        self.assertEqual(self.history.summary(user["user_id"])["skipped_count"], 1)
        self.assertEqual(self.history.summary(user["user_id"])["avoided_group_count"], 1)
        self.assertEqual(self.history.excluded_groups(user["user_id"]), set())

    def test_two_negative_actions_exclude_the_task_group(self) -> None:
        user = self.history.ensure_user()
        for action in ("skipped", "replaced_from"):
            self.history.record_action(
                user["user_id"], self.session_id, self.plan_id, self.item_id, action
            )

        groups = self.history.excluded_groups(user["user_id"])

        self.assertEqual(len(groups), 1)
        self.assertEqual(self.history.summary(user["user_id"])["replaced_count"], 1)
        self.assertEqual(self.history.summary(user["user_id"])["avoided_group_count"], 1)
        self.assertIn(self.task.feedback_group, groups)


if __name__ == "__main__":
    unittest.main()
