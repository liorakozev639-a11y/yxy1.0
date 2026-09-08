from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

import psycopg

from feedback_service import FeedbackService
from history_insight_service import HistoryInsightService
from mvp_orchestrator import PostgreSQLPlanRepository
from session_module import PostgresSessionRepository, SessionService
from task_repository import TaskRepository
from user_history_service import UserHistoryService


class HistoryInsightServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.database_url = database_url
        self.sessions = SessionService(PostgresSessionRepository(database_url))
        PostgreSQLPlanRepository(database_url)
        FeedbackService(database_url, self.sessions)
        self.history = UserHistoryService(database_url, TaskRepository())
        self.service = HistoryInsightService(database_url)
        self.user = self.history.ensure_user()
        self.session_id = self.sessions.create()["session_id"]
        self.addCleanup(self.sessions.repository.delete, self.session_id)
        self.tasks = TaskRepository().public_tasks

    def _insert_plan_item(
        self,
        *,
        plan_number: int,
        task_index: int,
        status: str = "completed",
        created_at: datetime | None = None,
    ) -> tuple[str, str]:
        task = self.tasks[task_index]
        created = created_at or datetime.now(timezone.utc).replace(microsecond=0)
        plan_id = f"plan_history_{plan_number}_{self.session_id}"
        item_id = f"item_history_{plan_number}_{self.session_id}"
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO plans (
                        id, session_id, density, free_start, free_end, version,
                        parent_plan_id, unscheduled_task_ids, created_at, status
                    ) VALUES (%s, %s, 'balanced', %s, %s, %s, NULL, '[]'::jsonb, %s, 'confirmed')
                    """,
                    (
                        plan_id,
                        self.session_id,
                        created,
                        created + timedelta(hours=2),
                        plan_number,
                        created,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO plan_items (
                        id, plan_id, task_id, title, category, start_at, end_at,
                        kind, status, locked, replacement_history
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'task', %s, FALSE, '[]'::jsonb)
                    """,
                    (
                        item_id,
                        plan_id,
                        task.id,
                        task.title,
                        task.category,
                        created,
                        created + timedelta(minutes=task.duration),
                        status,
                    ),
                )
        return plan_id, item_id

    def test_empty_history_returns_empty_state(self) -> None:
        insight = self.service.insight(self.user["user_id"])

        self.assertFalse(insight["has_history"])
        self.assertEqual(insight["summary"]["completed_count"], 0)
        self.assertEqual(insight["recent_plans"], [])
        self.assertIn("完成或跳过几个任务后", insight["empty_state"])

    def test_history_insight_aggregates_user_learning_signals(self) -> None:
        completed_plan_id, completed_item_id = self._insert_plan_item(
            plan_number=1,
            task_index=0,
            status="completed",
        )
        skipped_plan_id, skipped_item_id = self._insert_plan_item(
            plan_number=2,
            task_index=1,
            status="needs_adjustment",
        )
        replaced_plan_id, replaced_item_id = self._insert_plan_item(
            plan_number=3,
            task_index=2,
            status="pending",
        )
        now = datetime.now(timezone.utc)
        self.history.record_action(
            self.user["user_id"], self.session_id, completed_plan_id, completed_item_id, "completed", now
        )
        self.history.record_action(
            self.user["user_id"], self.session_id, skipped_plan_id, skipped_item_id, "skipped", now
        )
        self.history.record_action(
            self.user["user_id"], self.session_id, replaced_plan_id, replaced_item_id, "replaced_from", now
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO task_feedback (
                    id, session_id, plan_id, item_id, rating, reasons_json, created_at, updated_at
                ) VALUES ('feedback_history_test', %s, %s, %s, 1, '[]'::jsonb, %s, %s)
                """,
                (self.session_id, completed_plan_id, completed_item_id, now, now),
            )

        insight = self.service.insight(self.user["user_id"])

        self.assertTrue(insight["has_history"])
        self.assertEqual(insight["summary"]["completed_count"], 1)
        self.assertEqual(insight["summary"]["skipped_count"], 1)
        self.assertEqual(insight["summary"]["replaced_count"], 1)
        self.assertEqual(insight["summary"]["low_rating_count"], 1)
        self.assertEqual(insight["summary"]["this_week_completed_count"], 1)
        self.assertEqual(insight["this_week_completed_tasks"][0]["title"], self.tasks[0].title)
        self.assertEqual(insight["favorite_categories"][0]["category"], self.tasks[0].category)
        self.assertGreaterEqual(insight["avoided_groups"][0]["negative_count"], 1)
        self.assertTrue(insight["learning_notes"])
        self.assertTrue(insight["next_recommendation_strategy"])

    def test_recent_plans_are_limited_to_five_newest(self) -> None:
        base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
        for index in range(6):
            plan_id, item_id = self._insert_plan_item(
                plan_number=10 + index,
                task_index=index,
                created_at=base + timedelta(minutes=index),
            )
            self.history.record_action(
                self.user["user_id"],
                self.session_id,
                plan_id,
                item_id,
                "completed",
                base + timedelta(minutes=index),
            )

        insight = self.service.insight(self.user["user_id"])

        self.assertEqual(len(insight["recent_plans"]), 5)
        self.assertEqual(
            insight["recent_plans"][0]["plan_id"],
            f"plan_history_15_{self.session_id}",
        )


if __name__ == "__main__":
    unittest.main()
