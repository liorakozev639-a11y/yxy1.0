"""PostgreSQL persistence for quick-mode recommendation snapshots and choices."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class QuickRecommendationStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS quick_recommendation_runs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                available_minutes INTEGER NOT NULL CHECK (available_minutes BETWEEN 1 AND 480),
                energy_level TEXT NOT NULL CHECK (energy_level IN ('low', 'medium', 'high')),
                tasks_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quick_runs_session_time
            ON quick_recommendation_runs(session_id, created_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS quick_recommendation_feedback (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES quick_recommendation_runs(id) ON DELETE CASCADE,
                task_id TEXT,
                action TEXT NOT NULL CHECK (action IN ('liked', 'disliked', 'rest_selected')),
                created_at TIMESTAMPTZ NOT NULL,
                CHECK (
                    (action = 'rest_selected' AND task_id IS NULL)
                    OR (action IN ('liked', 'disliked') AND task_id IS NOT NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_task_unique
            ON quick_recommendation_feedback(run_id, task_id)
            WHERE task_id IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_rest_unique
            ON quick_recommendation_feedback(run_id)
            WHERE action = 'rest_selected'
            """,
        )
        with self._connect() as connection:
            for statement in statements:
                connection.execute(statement)

    def save_run(
        self,
        session_id: str,
        user_id: str,
        available_minutes: int,
        energy_level: str,
        tasks: list[dict[str, Any]],
    ) -> str:
        run_id = _make_id("quick")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO quick_recommendation_runs
                    (id, session_id, user_id, available_minutes, energy_level,
                     tasks_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, session_id, user_id, available_minutes, energy_level,
                    Jsonb(tasks), datetime.now(timezone.utc),
                ),
            )
        return run_id

    def latest_run(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, available_minutes, energy_level, tasks_json
                    FROM quick_recommendation_runs
                    WHERE session_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    SELECT action, task_id
                    FROM quick_recommendation_feedback
                    WHERE run_id = %s
                    ORDER BY created_at, id
                    """,
                    (row["id"],),
                )
                feedback = [dict(item) for item in cursor.fetchall()]
        return {
            "run_id": row["id"],
            "available_minutes": row["available_minutes"],
            "energy_level": row["energy_level"],
            "tasks": row["tasks_json"],
            "feedback": feedback,
        }

    def save_feedback(
        self,
        session_id: str,
        run_id: str,
        action: str,
        task_id: str | None,
    ) -> dict[str, Any]:
        if action not in {"liked", "disliked", "rest_selected"}:
            raise ValueError("不支持的极简反馈")
        if (action == "rest_selected") != (task_id is None):
            raise ValueError("任务反馈必须指定任务，休息选择不能附任务")
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT session_id, tasks_json
                    FROM quick_recommendation_runs
                    WHERE id = %s FOR UPDATE
                    """,
                    (run_id,),
                )
                run = cursor.fetchone()
                if run is None or run["session_id"] != session_id:
                    raise LookupError("推荐记录不存在")
                if task_id is not None and task_id not in {
                    task["id"] for task in run["tasks_json"]
                }:
                    raise LookupError("任务不属于本轮推荐")
                now = datetime.now(timezone.utc)
                if action == "rest_selected":
                    cursor.execute(
                        """
                        INSERT INTO quick_recommendation_feedback
                            (id, run_id, task_id, action, created_at)
                        VALUES (%s, %s, NULL, %s, %s)
                        ON CONFLICT (run_id) WHERE action = 'rest_selected'
                        DO NOTHING
                        """,
                        (_make_id("qfeedback"), run_id, action, now),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO quick_recommendation_feedback
                            (id, run_id, task_id, action, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (run_id, task_id) WHERE task_id IS NOT NULL
                        DO UPDATE SET action = EXCLUDED.action,
                                      created_at = EXCLUDED.created_at
                        """,
                        (_make_id("qfeedback"), run_id, task_id, action, now),
                    )
        return {"run_id": run_id, "action": action, "task_id": task_id}
