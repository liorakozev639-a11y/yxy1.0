from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from task_repository import TaskRepository


HistoryAction = Literal["completed", "skipped", "replaced_from", "replaced_to"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class UserHistoryService:
    def __init__(self, database_url: str, tasks: TaskRepository | None = None) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.tasks = tasks or TaskRepository()
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                linked_account_id TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_task_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
                task_id TEXT,
                feedback_group TEXT NOT NULL,
                category TEXT NOT NULL,
                action TEXT NOT NULL CHECK (
                    action IN ('completed', 'skipped', 'replaced_from', 'replaced_to')
                ),
                duration_minutes INTEGER NOT NULL,
                outing TEXT,
                company TEXT,
                occurred_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_user_task_history_user_time
            ON user_task_history(user_id, occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_user_task_history_user_group
            ON user_task_history(user_id, feedback_group)
            """,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def ensure_user(self, user_id: str | None = None) -> dict[str, Any]:
        user_id = user_id or make_id("user")
        current = utc_now()
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_profiles (id, created_at, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """,
                    (user_id, current, current),
                )
                created = cursor.fetchone() is not None
                if not created:
                    cursor.execute(
                        "UPDATE user_profiles SET updated_at = %s WHERE id = %s",
                        (current, user_id),
                    )
        return {"user_id": user_id, "created": created}

    def _plan_item_context(
        self,
        connection,
        session_id: str,
        plan_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    plans.session_id,
                    plans.id AS plan_id,
                    plan_items.id AS item_id,
                    plan_items.task_id,
                    plan_items.category,
                    EXTRACT(EPOCH FROM (plan_items.end_at - plan_items.start_at)) / 60
                        AS duration_minutes
                FROM plans
                JOIN plan_items ON plan_items.plan_id = plans.id
                WHERE plans.session_id = %s AND plans.id = %s AND plan_items.id = %s
                """,
                (session_id, plan_id, item_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="计划任务不存在")
        row["duration_minutes"] = int(row["duration_minutes"])
        return dict(row)

    def _task_for(self, task_id: str | None):
        if not task_id:
            return None
        return next((task for task in self.tasks.public_tasks if task.id == task_id), None)

    def _feedback_group_for(self, task_id: str | None) -> str:
        task = self._task_for(task_id)
        return task.feedback_group if task is not None else f"custom:{task_id}"

    def record_action(
        self,
        user_id: str,
        session_id: str,
        plan_id: str,
        item_id: str,
        action: HistoryAction,
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        if action not in {"completed", "skipped", "replaced_from", "replaced_to"}:
            raise ValueError(f"不支持的历史行为: {action}")
        self.ensure_user(user_id)
        occurred_at = occurred_at or utc_now()
        with self._connect() as connection:
            context = self._plan_item_context(connection, session_id, plan_id, item_id)
            task = self._task_for(context["task_id"])
            values = {
                "id": make_id("history"),
                "user_id": user_id,
                "session_id": context["session_id"],
                "plan_id": context["plan_id"],
                "item_id": context["item_id"],
                "task_id": context["task_id"],
                "feedback_group": self._feedback_group_for(context["task_id"]),
                "category": context["category"],
                "action": action,
                "duration_minutes": context["duration_minutes"],
                "outing": task.outing if task is not None else None,
                "company": task.company if task is not None else None,
                "occurred_at": occurred_at,
            }
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_task_history (
                        id, user_id, session_id, plan_id, item_id, task_id,
                        feedback_group, category, action, duration_minutes,
                        outing, company, occurred_at
                    ) VALUES (
                        %(id)s, %(user_id)s, %(session_id)s, %(plan_id)s, %(item_id)s,
                        %(task_id)s, %(feedback_group)s, %(category)s, %(action)s,
                        %(duration_minutes)s, %(outing)s, %(company)s, %(occurred_at)s
                    )
                    RETURNING *
                    """,
                    values,
                )
                row = cursor.fetchone()
        return dict(row)

    def summary(self, user_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE action = 'completed') AS completed_count,
                        COUNT(*) FILTER (WHERE action = 'skipped') AS skipped_count,
                        COUNT(*) FILTER (WHERE action = 'replaced_from') AS replaced_count,
                        COUNT(DISTINCT feedback_group) FILTER (
                            WHERE action IN ('skipped', 'replaced_from')
                        ) AS avoided_group_count
                    FROM user_task_history
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                counts = dict(cursor.fetchone())
                cursor.execute(
                    """
                    SELECT category
                    FROM user_task_history
                    WHERE user_id = %s AND action = 'completed'
                    GROUP BY category
                    ORDER BY COUNT(*) DESC, category
                    LIMIT 3
                    """,
                    (user_id,),
                )
                categories = [row["category"] for row in cursor.fetchall()]
        return {
            "completed_count": int(counts["completed_count"] or 0),
            "skipped_count": int(counts["skipped_count"] or 0),
            "replaced_count": int(counts["replaced_count"] or 0),
            "top_completed_categories": categories,
            "avoided_group_count": int(counts["avoided_group_count"] or 0),
        }

    def preference_weights(self, user_id: str | None) -> dict[str, Any]:
        empty = {
            "category_boosts": {},
            "group_boosts": {},
            "group_penalties": {},
            "preferred_duration_minutes": None,
        }
        if not user_id:
            return empty
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT category, feedback_group, duration_minutes, action
                    FROM user_task_history
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        category_counts: dict[str, int] = {}
        group_counts: dict[str, int] = {}
        negative_counts: dict[str, int] = {}
        completed_durations: list[int] = []
        for row in rows:
            if row["action"] == "completed":
                category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
                group_counts[row["feedback_group"]] = group_counts.get(row["feedback_group"], 0) + 1
                completed_durations.append(int(row["duration_minutes"]))
            elif row["action"] in {"skipped", "replaced_from"}:
                group = row["feedback_group"]
                negative_counts[group] = negative_counts.get(group, 0) + 1
        return {
            "category_boosts": {
                category: min(0.3, count * 0.05) for category, count in category_counts.items()
            },
            "group_boosts": {
                group: min(0.4, count * 0.08) for group, count in group_counts.items()
            },
            "group_penalties": {
                group: min(0.7, count * 0.15) for group, count in negative_counts.items()
            },
            "preferred_duration_minutes": (
                round(sum(completed_durations) / len(completed_durations))
                if completed_durations
                else None
            ),
        }

    def excluded_groups(self, user_id: str | None) -> set[str]:
        if not user_id:
            return set()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT feedback_group
                    FROM user_task_history
                    WHERE user_id = %s AND action IN ('skipped', 'replaced_from')
                    GROUP BY feedback_group
                    HAVING COUNT(*) >= 2
                    """,
                    (user_id,),
                )
                return {row[0] for row in cursor.fetchall()}
