"""PostgreSQL-backed refresh and post-plan review for execution items."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row


ReflectionSentiment = Literal["satisfied", "neutral", "dissatisfied"]
VALID_SENTIMENTS = {"satisfied", "neutral", "dissatisfied"}
UNFINISHED_STATUSES = {"pending", "active", "needs_adjustment", "missed", "overdue"}


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ReviewService:
    """Refresh task deadlines, store optional reflections, and build reviews."""

    def __init__(self, database_url: str, sessions: Any, execution: Any) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.sessions = sessions
        self.execution = execution
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_completion_reflections (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
                    sentiment TEXT NOT NULL CHECK (
                        sentiment IN ('satisfied', 'neutral', 'dissatisfied')
                    ),
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (plan_id, item_id)
                )
                """
            )

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        return now or datetime.now(timezone.utc)

    def _require_plan(
        self,
        connection: psycopg.Connection,
        session_id: str,
        plan_id: str,
        *,
        lock: bool = False,
    ) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        query = """
            SELECT id, session_id, free_end, status
            FROM plans
            WHERE id = %s AND session_id = %s
        """
        if lock:
            query += " FOR UPDATE"
        row = connection.execute(query, (plan_id, session_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="计划不存在或不属于当前会话")
        if row["status"] == "superseded":
            raise HTTPException(status_code=409, detail="当前计划已被新版本替代")
        return row

    def _task_items(
        self,
        connection: psycopg.Connection,
        plan_id: str,
    ) -> list[dict[str, Any]]:
        return connection.execute(
            """
            SELECT id, title, category, start_at, end_at, status
            FROM plan_items
            WHERE plan_id = %s AND kind = 'task'
            ORDER BY start_at, id
            """,
            (plan_id,),
        ).fetchall()

    @staticmethod
    def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "total_tasks": len(items),
            "completed_count": sum(item["status"] == "completed" for item in items),
            "skipped_count": sum(item["status"] == "skipped" for item in items),
            "unfinished_count": sum(item["status"] in UNFINISHED_STATUSES for item in items),
            "needs_adjustment_count": sum(
                item["status"] == "needs_adjustment" for item in items
            ),
        }

    @staticmethod
    def _reminders(items: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
        ending_soon = timedelta(minutes=10)
        return {
            "startable_titles": [
                item["title"]
                for item in items
                if item["status"] == "pending"
                and item["start_at"] <= now < item["end_at"]
            ],
            "ending_soon_titles": [
                item["title"]
                for item in items
                if item["status"] == "active"
                and timedelta(0) <= item["end_at"] - now <= ending_soon
            ],
            "needs_adjustment_count": sum(
                item["status"] == "needs_adjustment" for item in items
            ),
        }

    @staticmethod
    def _item_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "item_id": item["id"],
            "title": item["title"],
            "category": item["category"],
            "start_at": item["start_at"].isoformat(),
            "end_at": item["end_at"].isoformat(),
            "status": item["status"],
        }

    def refresh_plan(
        self,
        session_id: str,
        plan_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._now(now)
        with self._connect() as connection:
            self._require_plan(connection, session_id, plan_id)

        checked = self.execution.refresh_items(session_id, plan_id, now=current)
        events = [event for result in checked for event in result["events"]]

        with self._connect() as connection:
            self._require_plan(connection, session_id, plan_id)
            items = self._task_items(connection, plan_id)
        return {
            "plan_id": plan_id,
            "items": [self._item_payload(item) for item in items],
            "summary": self._summary(items),
            "reminders": self._reminders(items, current),
            "events": events,
        }

    def save_reflection(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        sentiment: ReflectionSentiment | str,
    ) -> dict[str, Any]:
        if sentiment not in VALID_SENTIMENTS:
            raise HTTPException(status_code=400, detail="完成感受不受支持")
        current = self._now(None)
        with self._connect() as connection:
            self._require_plan(connection, session_id, plan_id, lock=True)
            item = connection.execute(
                """
                SELECT id, status
                FROM plan_items
                WHERE id = %s AND plan_id = %s AND kind = 'task'
                FOR UPDATE
                """,
                (item_id, plan_id),
            ).fetchone()
            if item is None:
                raise HTTPException(status_code=404, detail="计划任务不存在")
            if item["status"] != "completed":
                raise HTTPException(status_code=409, detail="只有已完成任务可以记录感受")
            row = connection.execute(
                """
                INSERT INTO task_completion_reflections
                    (id, session_id, plan_id, item_id, sentiment, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_id, item_id)
                DO UPDATE SET sentiment = EXCLUDED.sentiment, updated_at = EXCLUDED.updated_at
                RETURNING id, session_id, plan_id, item_id, sentiment, created_at, updated_at
                """,
                (
                    make_id("reflection"),
                    session_id,
                    plan_id,
                    item_id,
                    sentiment,
                    current,
                    current,
                ),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="完成感受保存失败")
        return {
            "reflection_id": row["id"],
            "session_id": row["session_id"],
            "plan_id": row["plan_id"],
            "item_id": row["item_id"],
            "sentiment": row["sentiment"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    @staticmethod
    def _suggestions(summary: dict[str, int]) -> list[str]:
        total = summary["total_tasks"]
        completed = summary["completed_count"]
        completion_rate = completed / total if total else 0
        suggestions: list[str] = []
        if completion_rate >= 0.75:
            suggestions.append("下次可以维持当前计划密度。")
        elif completion_rate < 0.5:
            suggestions.append("下次建议选择更轻的计划密度或缩短时段。")
        if summary["unfinished_count"]:
            suggestions.append("下次预留更多缓冲和休息时间。")
        if summary["dissatisfied_count"]:
            suggestions.append("下次优先替换感受不佳的任务。")
        if summary["skipped_count"]:
            suggestions.append("已记录跳过偏好，后续会避开相似任务。")
        return suggestions or ["这次计划已完成，可以按自己的节奏继续安排下一段留白。"]

    def get_review(
        self,
        session_id: str,
        plan_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._now(now)
        refreshed = self.refresh_plan(session_id, plan_id, now=current)
        with self._connect() as connection:
            plan = self._require_plan(connection, session_id, plan_id)
            rows = connection.execute(
                """
                SELECT i.id, i.title, i.status, r.sentiment
                FROM plan_items AS i
                LEFT JOIN task_completion_reflections AS r
                  ON r.plan_id = i.plan_id AND r.item_id = i.id
                WHERE i.plan_id = %s AND i.kind = 'task'
                ORDER BY i.start_at, i.id
                """,
                (plan_id,),
            ).fetchall()

        summary = dict(refreshed["summary"])
        sentiments = {"satisfied": 0, "neutral": 0, "dissatisfied": 0}
        items: list[dict[str, Any]] = []
        for row in rows:
            sentiment = row["sentiment"]
            if sentiment in sentiments:
                sentiments[sentiment] += 1
            outcome = "completed" if row["status"] == "completed" else (
                "skipped" if row["status"] == "skipped" else "unfinished"
            )
            items.append(
                {
                    "item_id": row["id"],
                    "title": row["title"],
                    "outcome": outcome,
                    "sentiment": sentiment,
                }
            )
        summary.update({f"{name}_count": count for name, count in sentiments.items()})
        return {
            "plan_id": plan_id,
            "status": "finished" if current >= plan["free_end"] else "in_progress",
            "ends_at": plan["free_end"].isoformat(),
            "summary": summary,
            "items": items,
            "suggestions": self._suggestions(summary),
        }
