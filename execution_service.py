"""PostgreSQL-backed execution state and event persistence."""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from execution_module import ExecutionError, PlanItem, execute_action, expire_if_needed


logger = logging.getLogger(__name__)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ExecutionService:
    """Apply execution actions and persist an append-only event trail."""

    def __init__(
        self,
        database_url: str,
        sessions: Any,
        memory: Any | None = None,
        user_history: Any | None = None,
    ) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.sessions = sessions
        self.memory = memory
        self.user_history = user_history
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_execution_events_item_time
                ON execution_events(item_id, occurred_at)
                """
            )

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        return now or datetime.now(timezone.utc)

    def _load_item(self, connection, session_id: str, plan_id: str, item_id: str) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT p.session_id, p.status AS plan_status,
                       i.id, i.title, i.start_at, i.end_at, i.status
                FROM plans AS p
                JOIN plan_items AS i ON i.plan_id = p.id
                WHERE p.id = %s AND p.session_id = %s AND i.id = %s
                FOR UPDATE OF p, i
                """,
                (plan_id, session_id, item_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="计划任务不存在")
        if row["plan_status"] == "superseded":
            raise HTTPException(status_code=409, detail="计划版本已被替代")
        return row

    @staticmethod
    def _to_item(row: dict[str, Any]) -> PlanItem:
        return PlanItem(
            id=row["id"],
            title=row["title"],
            start_at=row["start_at"],
            end_at=row["end_at"],
            status=row["status"],
        )

    @staticmethod
    def _event_payload(event) -> dict[str, Any]:
        return {
            "item_id": event.item_id,
            "event_type": event.event_type,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "occurred_at": event.occurred_at.isoformat(),
        }

    def _save_events(
        self,
        connection,
        session_id: str,
        plan_id: str,
        item: PlanItem,
        previous_count: int,
    ) -> list[dict[str, Any]]:
        created = item.events[previous_count:]
        for event in created:
            connection.execute(
                """
                INSERT INTO execution_events
                    (id, session_id, plan_id, item_id, event_type,
                     from_status, to_status, occurred_at, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    make_id("event"),
                    session_id,
                    plan_id,
                    event.item_id,
                    event.event_type,
                    event.from_status,
                    event.to_status,
                    event.occurred_at,
                    Jsonb({}),
                ),
            )
        return [self._event_payload(event) for event in created]

    @staticmethod
    def _payload(plan_id: str, item: PlanItem, events: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "plan_id": plan_id,
            "item": item.to_dict(),
            "status": item.status,
            "needs_adjustment": item.status == "needs_adjustment",
            "events": events,
        }

    def execute(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        action: str,
        now: datetime | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        current = self._now(now)
        with self._connect() as connection:
            row = self._load_item(connection, session_id, plan_id, item_id)
            item = self._to_item(row)
            previous_count = len(item.events)
            try:
                execute_action(item, action, current)
            except ExecutionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            events = self._save_events(
                connection,
                session_id,
                plan_id,
                item,
                previous_count,
            )
            connection.execute(
                "UPDATE plan_items SET status = %s WHERE id = %s AND plan_id = %s",
                (item.status, item.id, plan_id),
            )
        payload = self._payload(plan_id, item, events)
        if action == "skip" and self.memory is not None:
            self.memory.record_plan_item_exclusion(
                session_id,
                plan_id,
                item_id,
                "skipped",
            )
        if self.user_history is not None and user_id and action in {"complete", "skip"}:
            try:
                self.user_history.record_action(
                    user_id,
                    session_id,
                    plan_id,
                    item_id,
                    "completed" if action == "complete" else "skipped",
                )
            except Exception:
                logger.exception("用户历史写入失败，不影响执行流程")
        if self.memory is not None:
            payload["recommendation_memory"] = self.memory.summary(session_id)
        return payload

    def check_deadline(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._now(now)
        with self._connect() as connection:
            row = self._load_item(connection, session_id, plan_id, item_id)
            item = self._to_item(row)
            previous_count = len(item.events)
            try:
                expire_if_needed(item, current)
            except ExecutionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            events = self._save_events(
                connection,
                session_id,
                plan_id,
                item,
                previous_count,
            )
            if events:
                connection.execute(
                    "UPDATE plan_items SET status = %s WHERE id = %s AND plan_id = %s",
                    (item.status, item.id, plan_id),
                )
        return self._payload(plan_id, item, events)

    def refresh_items(
        self,
        session_id: str,
        plan_id: str,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Check every runnable task deadline for one plan.

        ``check_deadline`` remains the only place that changes an expired
        item, which keeps manual and batch deadline checks idempotent.
        """
        self.sessions.require_active(session_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT i.id
                FROM plan_items AS i
                JOIN plans AS p ON p.id = i.plan_id
                WHERE p.id = %s
                  AND p.session_id = %s
                  AND p.status <> 'superseded'
                  AND i.kind = 'task'
                  AND i.status IN ('pending', 'active')
                ORDER BY i.start_at, i.id
                """,
                (plan_id, session_id),
            ).fetchall()
        return [
            self.check_deadline(session_id, plan_id, row[0], now=now)
            for row in rows
        ]

    def events(
        self,
        session_id: str,
        plan_id: str,
        item_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.sessions.require_active(session_id)
        query = """
            SELECT id, item_id, event_type, from_status, to_status, occurred_at
            FROM execution_events
            WHERE session_id = %s AND plan_id = %s
        """
        values: list[Any] = [session_id, plan_id]
        if item_id:
            query += " AND item_id = %s"
            values.append(item_id)
        query += " ORDER BY occurred_at, id"
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, values)
                rows = cursor.fetchall()
        return [
            {
                "event_id": row["id"],
                "item_id": row["item_id"],
                "event_type": row["event_type"],
                "from_status": row["from_status"],
                "to_status": row["to_status"],
                "occurred_at": row["occurred_at"].isoformat(),
            }
            for row in rows
        ]
