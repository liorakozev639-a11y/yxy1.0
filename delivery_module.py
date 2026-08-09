"""Synchronous web delivery module for plan display.

The module builds a frontend-safe plan payload and persists the delivery job in
PostgreSQL. PDF, email, calendar, MQ, and background-worker integrations are
intentionally outside this MVP.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

try:
    import psycopg
except ImportError:  # pragma: no cover - allows the pure demo to run without psycopg
    psycopg = None


class DeliveryError(ValueError):
    """Raised when a plan cannot be delivered as a web view."""


@dataclass(frozen=True, slots=True)
class PlanItem:
    id: str
    title: str
    category: str
    start_at: datetime
    end_at: datetime
    status: str = "pending"


@dataclass(frozen=True, slots=True)
class Plan:
    id: str
    session_id: str
    title: str
    status: str
    version: int
    items: tuple[PlanItem, ...]


@dataclass(frozen=True, slots=True)
class WebDelivery:
    id: str
    session_id: str
    plan_id: str
    channel: str
    status: str
    payload: dict[str, Any]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.id,
            "session_id": self.session_id,
            "plan_id": self.plan_id,
            "channel": self.channel,
            "status": self.status,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }


class WebDeliveryRepository(Protocol):
    def save_or_get_web(
        self,
        *,
        delivery_id: str,
        session_id: str,
        plan_id: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> WebDelivery:
        """Persist one web delivery and return the idempotent record."""


DELIVERY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS delivery_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel = 'web'),
    status TEXT NOT NULL CHECK (status IN ('ready', 'failed')),
    payload_json JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, plan_id, channel)
);
"""


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _validate_plan(session_id: str, plan: Plan) -> list[PlanItem]:
    if not session_id:
        raise DeliveryError("session_id 不能为空")
    if plan.session_id != session_id:
        raise DeliveryError("计划不属于当前会话")
    if plan.status not in {"draft", "confirmed"}:
        raise DeliveryError(f"当前计划状态不能展示: {plan.status}")
    if plan.version <= 0:
        raise DeliveryError("计划版本必须大于 0")
    if not plan.items:
        raise DeliveryError("计划至少需要包含一个任务")

    ids = [item.id for item in plan.items]
    if len(ids) != len(set(ids)):
        raise DeliveryError("计划中存在重复的任务 ID")

    ordered = sorted(plan.items, key=lambda item: (item.start_at, item.end_at, item.id))
    for item in ordered:
        if not item.id or not item.title or not item.category:
            raise DeliveryError("任务 ID、标题和分类不能为空")
        if item.start_at >= item.end_at:
            raise DeliveryError("任务结束时间必须晚于开始时间")
        if (item.start_at.tzinfo is None) != (item.end_at.tzinfo is None):
            raise DeliveryError("任务开始和结束时间必须使用相同的时区格式")

    for left, right in zip(ordered, ordered[1:]):
        if left.end_at > right.start_at:
            raise DeliveryError(f"任务时间冲突: {left.id} 与 {right.id}")
    return ordered


def build_web_payload(session_id: str, plan: Plan) -> dict[str, Any]:
    """Build the JSON view model consumed by the frontend timeline."""
    ordered = _validate_plan(session_id, plan)
    return {
        "channel": "web",
        "view": "plan",
        "session_id": session_id,
        "plan_id": plan.id,
        "title": plan.title,
        "status": plan.status,
        "version": plan.version,
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "start_at": item.start_at.isoformat(),
                "end_at": item.end_at.isoformat(),
                "status": item.status,
            }
            for item in ordered
        ],
    }


class WebDeliveryService:
    """Orchestrate validation, view generation, and PostgreSQL persistence."""

    def __init__(self, repository: WebDeliveryRepository) -> None:
        self.repository = repository

    def deliver(
        self,
        session_id: str,
        plan: Plan,
        now: datetime | None = None,
    ) -> WebDelivery:
        current = now or datetime.now(timezone.utc)
        payload = build_web_payload(session_id, plan)
        return self.repository.save_or_get_web(
            delivery_id=make_id("delivery"),
            session_id=session_id,
            plan_id=plan.id,
            payload=payload,
            now=current,
        )


class PostgreSQLDeliveryRepository:
    """PostgreSQL persistence adapter; no in-memory production store is used."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise DeliveryError("database_url 不能为空")
        if psycopg is None:
            raise DeliveryError("运行 PostgreSQL 适配器需要安装 psycopg")
        self.database_url = database_url
        with psycopg.connect(self.database_url) as connection:
            connection.execute(DELIVERY_SCHEMA_SQL)

    def save_or_get_web(
        self,
        *,
        delivery_id: str,
        session_id: str,
        plan_id: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> WebDelivery:
        query = """
        INSERT INTO delivery_jobs
            (id, session_id, plan_id, channel, status, payload_json,
             attempts, created_at, updated_at)
        VALUES (%s, %s, %s, 'web', 'ready', %s::jsonb, 0, %s, %s)
        ON CONFLICT (session_id, plan_id, channel)
        DO UPDATE SET
            status = 'ready',
            payload_json = EXCLUDED.payload_json,
            updated_at = EXCLUDED.updated_at
        RETURNING id, session_id, plan_id, channel, status,
                  payload_json, created_at
        """
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                query,
                (
                    delivery_id,
                    session_id,
                    plan_id,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            ).fetchone()
        if row is None:
            raise DeliveryError("网页交付记录保存失败")

        stored_payload = row[5]
        if isinstance(stored_payload, str):
            stored_payload = json.loads(stored_payload)
        return WebDelivery(
            id=row[0],
            session_id=row[1],
            plan_id=row[2],
            channel=row[3],
            status=row[4],
            payload=stored_payload,
            created_at=row[6],
        )


def demo() -> None:
    """Run the pure web-view part without contacting external services."""
    tz = timezone.utc
    start = datetime(2026, 8, 8, 10, 0, tzinfo=tz)
    plan = Plan(
        id="plan_demo",
        session_id="sess_demo",
        title="周六半日安排",
        status="confirmed",
        version=1,
        items=(
            PlanItem(
                id="item_walk",
                title="去公园散步",
                category="活力充电",
                start_at=start,
                end_at=start.replace(minute=40),
                status="pending",
            ),
        ),
    )
    print(json.dumps(build_web_payload("sess_demo", plan), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
