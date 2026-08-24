"""Session-scoped negative recommendation memory backed by PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from session_module import SessionService
from task_repository import TaskRepository


ExclusionSource = Literal["low_rating", "skipped"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class RecommendationMemory:
    """Stores task groups a single browser session does not want to see again."""

    def __init__(
        self,
        database_url: str,
        sessions: SessionService,
        tasks: TaskRepository,
    ) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.sessions = sessions
        self.tasks = tasks
        self.init_schema()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_task_exclusions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    task_id TEXT NOT NULL,
                    feedback_group TEXT NOT NULL,
                    source TEXT NOT NULL CHECK (source IN ('low_rating', 'skipped')),
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (session_id, feedback_group)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_task_exclusions_session
                ON session_task_exclusions(session_id, created_at)
                """
            )

    def record_plan_item_exclusion(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        source: ExclusionSource,
    ) -> dict[str, Any]:
        if source not in {"low_rating", "skipped"}:
            raise ValueError("source 只能是 low_rating 或 skipped")
        self.sessions.require_active(session_id)

        task_id = self._find_plan_item_task_id(session_id, plan_id, item_id)
        feedback_group = self._feedback_group_for(task_id)
        now = utc_now()

        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO session_task_exclusions
                    (id, session_id, task_id, feedback_group, source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, feedback_group) DO NOTHING
                RETURNING id, session_id, task_id, feedback_group, source, created_at
                """,
                (make_id("exclude"), session_id, task_id, feedback_group, source, now),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """
                    SELECT id, session_id, task_id, feedback_group, source, created_at
                    FROM session_task_exclusions
                    WHERE session_id = %s AND feedback_group = %s
                    """,
                    (session_id, feedback_group),
                ).fetchone()

        if row is None:
            raise RuntimeError("推荐排除记录保存失败")
        return self._payload(row)

    def list_excluded_groups(self, session_id: str) -> set[str]:
        self.sessions.require_active(session_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT feedback_group
                FROM session_task_exclusions
                WHERE session_id = %s
                """,
                (session_id,),
            ).fetchall()
        return {row[0] for row in rows}

    def summary(self, session_id: str) -> dict[str, int]:
        excluded_groups = self.list_excluded_groups(session_id)
        excluded_task_count = sum(
            task.feedback_group in excluded_groups
            for task in self.tasks.public_tasks
        )
        return {
            "excluded_group_count": len(excluded_groups),
            "excluded_task_count": excluded_task_count,
        }

    def _find_plan_item_task_id(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
    ) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT i.task_id
                FROM plans AS p
                JOIN plan_items AS i ON i.plan_id = p.id
                WHERE p.id = %s AND p.session_id = %s AND i.id = %s
                """,
                (plan_id, session_id, item_id),
            ).fetchone()
        if row is None or row[0] is None:
            raise HTTPException(status_code=404, detail="计划任务不存在")
        return str(row[0])

    def _feedback_group_for(self, task_id: str) -> str:
        task = next(
            (candidate for candidate in self.tasks.public_tasks if candidate.id == task_id),
            None,
        )
        return task.feedback_group if task and task.feedback_group else f"custom:{task_id}"

    @staticmethod
    def _payload(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "session_id": row[1],
            "task_id": row[2],
            "feedback_group": row[3],
            "source": row[4],
            "created_at": row[5].isoformat(),
        }
