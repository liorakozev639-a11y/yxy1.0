"""Session-scoped PostgreSQL storage for mock-generated task candidates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import psycopg
from psycopg.types.json import Jsonb


class PostgresGeneratedTaskRepository:
    def __init__(
        self,
        database_url: str,
        *,
        connect: Callable[[str], Any] | None = None,
        schema_init: bool = True,
    ) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self._connect = connect or psycopg.connect
        if schema_init:
            self.init_schema()

    def init_schema(self) -> None:
        with self._connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_generation_runs (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    generation_key TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'mock',
                    context_json JSONB NOT NULL,
                    brief_json JSONB NOT NULL,
                    rejected_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (session_id, generation_key)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    generation_key TEXT,
                    ordinal INTEGER NOT NULL DEFAULT 0,
                    semantic_signature TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (session_id, semantic_signature)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_generated_tasks_session ON generated_tasks(session_id, created_at)"
            )

    def get_run(self, session_id: str, generation_key: str) -> dict[str, Any] | None:
        with self._connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT rejected_json FROM ai_generation_runs
                WHERE session_id = %s AND generation_key = %s
                """,
                (session_id, generation_key),
            ).fetchone()
            if row is None:
                return None
            tasks = connection.execute(
                """
                SELECT payload_json FROM generated_tasks
                WHERE session_id = %s AND generation_key = %s
                ORDER BY ordinal, id
                """,
                (session_id, generation_key),
            ).fetchall()
        return {"tasks": [dict(task[0]) for task in tasks], "rejected": list(row[0])}

    def save_run(
        self,
        session_id: str,
        generation_key: str,
        context: dict[str, Any],
        brief: dict[str, Any],
        tasks: list[dict[str, Any]],
        rejected: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._connect(self.database_url) as connection:
            inserted = connection.execute(
                """
                INSERT INTO ai_generation_runs
                    (session_id, generation_key, source, context_json,
                     brief_json, rejected_json, created_at)
                VALUES (%s, %s, 'mock', %s, %s, %s, %s)
                ON CONFLICT (session_id, generation_key) DO NOTHING
                RETURNING generation_key
                """,
                (
                    session_id,
                    generation_key,
                    Jsonb(context),
                    Jsonb(brief),
                    Jsonb(rejected),
                    now,
                ),
            ).fetchone()
            if inserted is not None:
                for ordinal, task in enumerate(tasks):
                    connection.execute(
                        """
                        INSERT INTO generated_tasks
                            (id, session_id, generation_key, ordinal,
                             semantic_signature, payload_json, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            task["id"],
                            session_id,
                            generation_key,
                            ordinal,
                            task["semantic_signature"],
                            Jsonb(task),
                            now,
                        ),
                    )
        saved = self.get_run(session_id, generation_key)
        if saved is None:
            raise RuntimeError("模拟生成记录保存失败")
        return saved

    def save_task(self, session_id: str, task: dict[str, Any]) -> dict[str, Any]:
        if task["session_id"] != session_id:
            raise ValueError("任务不属于当前会话")
        with self._connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO generated_tasks
                    (id, session_id, semantic_signature, payload_json, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    task["id"],
                    session_id,
                    task["semantic_signature"],
                    Jsonb(task),
                    datetime.now(timezone.utc),
                ),
            )
        return task

    def get_task(self, session_id: str, task_id: str) -> dict[str, Any] | None:
        with self._connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM generated_tasks
                WHERE session_id = %s AND id = %s
                """,
                (session_id, task_id),
            ).fetchone()
        return dict(row[0]) if row is not None else None

    def list_tasks(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM generated_tasks
                WHERE session_id = %s ORDER BY created_at, id
                """,
                (session_id,),
            ).fetchall()
        return [dict(row[0]) for row in rows]
