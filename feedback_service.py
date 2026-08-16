"""PostgreSQL-backed feedback for completed plan items."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class FeedbackService:
    def __init__(self, database_url: str, sessions: Any) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.sessions = sessions
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_feedback (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    UNIQUE(plan_id, item_id)
                )
                """
            )

    @staticmethod
    def _validate_reasons(reasons: list[str] | None) -> list[str]:
        values = reasons or []
        if len(values) > 3:
            raise HTTPException(status_code=400, detail="反馈原因最多选择 3 个")
        cleaned: list[str] = []
        for reason in values:
            if not isinstance(reason, str) or not reason.strip():
                raise HTTPException(status_code=400, detail="反馈原因必须是非空文本")
            cleaned.append(reason.strip())
        return cleaned

    def _require_item(
        self,
        connection: psycopg.Connection,
        session_id: str,
        plan_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        row = connection.execute(
            """
            SELECT i.id, i.status, p.status AS plan_status
            FROM plan_items AS i
            JOIN plans AS p ON p.id = i.plan_id
            WHERE p.id = %s AND p.session_id = %s AND i.id = %s
            FOR UPDATE OF p, i
            """,
            (plan_id, session_id, item_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="任务不存在或不属于当前计划")
        if row["plan_status"] == "superseded":
            raise HTTPException(status_code=409, detail="当前计划已被新版本替代")
        return row

    @staticmethod
    def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
        reasons = row["reasons_json"]
        return {
            "feedback_id": row["id"],
            "session_id": row["session_id"],
            "plan_id": row["plan_id"],
            "item_id": row["item_id"],
            "rating": row["rating"],
            "reasons": reasons if isinstance(reasons, list) else [],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    def save(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        *,
        rating: int,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise HTTPException(status_code=400, detail="评分必须是 1 到 5")
        cleaned_reasons = self._validate_reasons(reasons)
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            item = self._require_item(connection, session_id, plan_id, item_id)
            if item["status"] != "completed":
                raise HTTPException(status_code=409, detail="只有已完成任务可以评价")
            row = connection.execute(
                """
                INSERT INTO task_feedback
                    (id, session_id, plan_id, item_id, rating, reasons_json,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_id, item_id)
                DO UPDATE SET
                    rating = EXCLUDED.rating,
                    reasons_json = EXCLUDED.reasons_json,
                    updated_at = EXCLUDED.updated_at
                RETURNING id, session_id, plan_id, item_id, rating,
                          reasons_json, created_at, updated_at
                """,
                (
                    make_id("feedback"),
                    session_id,
                    plan_id,
                    item_id,
                    rating,
                    Jsonb(cleaned_reasons),
                    now,
                    now,
                ),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=500, detail="反馈保存失败")
            return self._row_payload(row)

    def list_for_plan(self, session_id: str, plan_id: str) -> list[dict[str, Any]]:
        self.sessions.require_active(session_id)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM plans WHERE id = %s AND session_id = %s",
                (plan_id, session_id),
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="计划不存在或不属于当前会话")
            rows = connection.execute(
                """
                SELECT id, session_id, plan_id, item_id, rating, reasons_json,
                       created_at, updated_at
                FROM task_feedback
                WHERE plan_id = %s AND session_id = %s
                ORDER BY updated_at, id
                """,
                (plan_id, session_id),
            ).fetchall()
        return [self._row_payload(row) for row in rows]
