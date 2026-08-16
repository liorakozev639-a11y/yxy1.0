"""PostgreSQL-backed plan editing for the MVP result page."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from mvp_orchestrator import GeneratePlanRequest
from task_repository import CATEGORIES, TaskRepository


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class PlanManagementService:
    """Read and mutate plans while keeping every user change versioned."""

    def __init__(self, database_url: str, sessions: Any, orchestrator: Any) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.sessions = sessions
        self.orchestrator = orchestrator
        self.tasks = TaskRepository()
        self.init_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "ALTER TABLE plans ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft'"
            )

    def get(self, session_id: str, plan_id: str | None = None) -> dict[str, Any] | None:
        self.sessions.require_active(session_id)
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if plan_id:
                    cursor.execute(
                        """
                        SELECT id, session_id, density, free_start, free_end, version,
                               parent_plan_id, unscheduled_task_ids, status
                        FROM plans
                        WHERE id = %s AND session_id = %s
                        """,
                        (plan_id, session_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, session_id, density, free_start, free_end, version,
                               parent_plan_id, unscheduled_task_ids, status
                        FROM plans
                        WHERE session_id = %s AND status <> 'superseded'
                        ORDER BY version DESC, created_at DESC
                        LIMIT 1
                        """,
                        (session_id,),
                    )
                plan = cursor.fetchone()
                if plan is None:
                    return None
                cursor.execute(
                    """
                    SELECT id, task_id, title, category, start_at, end_at,
                           kind, status, locked
                    FROM plan_items
                    WHERE plan_id = %s
                    ORDER BY start_at, end_at, id
                    """,
                    (plan["id"],),
                )
                items = cursor.fetchall()
        return self._payload(plan, items)

    def session_id_for_plan(self, plan_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM plans WHERE id = %s",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        return row[0]

    @staticmethod
    def _payload(plan: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "plan_id": plan["id"],
            "session_id": plan["session_id"],
            "density": plan["density"],
            "free_start": plan["free_start"].isoformat(),
            "free_end": plan["free_end"].isoformat(),
            "version": int(plan["version"]),
            "parent_plan_id": plan["parent_plan_id"],
            "status": plan["status"],
            "unscheduled_task_ids": list(plan["unscheduled_task_ids"] or []),
            "items": [
                {
                    "id": item["id"],
                    "task_id": item["task_id"],
                    "title": item["title"],
                    "category": item["category"],
                    "start_at": item["start_at"].isoformat(),
                    "end_at": item["end_at"].isoformat(),
                    "kind": item["kind"],
                    "status": item["status"],
                    "locked": bool(item["locked"]),
                }
                for item in items
            ],
        }

    def _require(self, session_id: str, plan_id: str) -> dict[str, Any]:
        plan = self.get(session_id, plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        if plan["status"] == "superseded":
            raise HTTPException(status_code=409, detail="计划版本已被替代")
        return plan

    @staticmethod
    def _check_version(plan: dict[str, Any], expected_version: int | None) -> None:
        if expected_version is not None and expected_version != plan["version"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "计划版本已变化，请刷新后重试",
                    "current_version": plan["version"],
                },
            )

    @staticmethod
    def _find_item(plan: dict[str, Any], item_id: str) -> dict[str, Any]:
        for item in plan["items"]:
            if item["id"] == item_id:
                return item
        raise HTTPException(status_code=404, detail="计划任务不存在")

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="时间格式不合法") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _ensure_slot(plan: dict[str, Any], start_at: datetime, end_at: datetime, ignore_id: str | None = None) -> None:
        free_start = PlanManagementService._parse_time(plan["free_start"])
        free_end = PlanManagementService._parse_time(plan["free_end"])
        if start_at >= end_at or start_at < free_start or end_at > free_end:
            raise HTTPException(status_code=400, detail="任务时间超出可用时间或结束时间不晚于开始时间")
        for item in plan["items"]:
            if item["id"] == ignore_id or item["status"] == "skipped":
                continue
            left = PlanManagementService._parse_time(item["start_at"])
            right = PlanManagementService._parse_time(item["end_at"])
            if start_at < right and end_at > left:
                raise HTTPException(status_code=409, detail="任务时间与现有计划冲突")

    def _save_version(self, plan: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        new_plan_id = make_id("plan")
        now = datetime.now(timezone.utc)
        new_items = []
        for item in items:
            copied = dict(item)
            copied["id"] = make_id("item")
            new_items.append(copied)
        with self._connect() as connection:
            connection.execute(
                "UPDATE plans SET status = 'superseded' WHERE id = %s",
                (plan["plan_id"],),
            )
            connection.execute(
                """
                INSERT INTO plans
                    (id, session_id, density, free_start, free_end, version,
                     parent_plan_id, unscheduled_task_ids, created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
                """,
                (
                    new_plan_id,
                    plan["session_id"],
                    plan["density"],
                    self._parse_time(plan["free_start"]),
                    self._parse_time(plan["free_end"]),
                    plan["version"] + 1,
                    plan["plan_id"],
                    Jsonb(plan["unscheduled_task_ids"]),
                    now,
                ),
            )
            for item in new_items:
                connection.execute(
                    """
                    INSERT INTO plan_items
                        (id, plan_id, task_id, title, category, start_at, end_at,
                         kind, status, locked)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item["id"],
                        new_plan_id,
                        item["task_id"],
                        item["title"],
                        item["category"],
                        self._parse_time(item["start_at"]),
                        self._parse_time(item["end_at"]),
                        item["kind"],
                        item["status"],
                        item["locked"],
                    ),
                )
        refreshed = self.get(plan["session_id"], new_plan_id)
        if refreshed is None:
            raise HTTPException(status_code=503, detail="计划版本保存失败")
        return refreshed

    def edit_item(self, session_id: str, plan_id: str, item_id: str, expected_version: int, start_at: str, end_at: str) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        self._find_item(plan, item_id)
        start = self._parse_time(start_at)
        end = self._parse_time(end_at)
        self._ensure_slot(plan, start, end, item_id)
        items = [dict(item) for item in plan["items"]]
        for item in items:
            if item["id"] == item_id:
                item["start_at"] = start.isoformat()
                item["end_at"] = end.isoformat()
                item["locked"] = True
        return self._save_version(plan, items)

    def skip_item(self, session_id: str, plan_id: str, item_id: str, expected_version: int) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        self._find_item(plan, item_id)
        items = [dict(item) for item in plan["items"]]
        for item in items:
            if item["id"] == item_id:
                item["status"] = "skipped"
        return self._save_version(plan, items)

    def replace_item(self, session_id: str, plan_id: str, item_id: str, expected_version: int, replacement_task_id: str | None = None) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        current = self._find_item(plan, item_id)
        session = self.sessions.require_active(session_id)
        budget_limit = {"low": 20, "medium": 40, "high": 80}.get(session.preferences.get("budget"), 40)
        max_duration = {"half": 270, "day": 480}.get(session.preferences.get("duration"), 270)
        candidates = self.tasks.search_tasks(
            session_id=session_id,
            budget_limit=budget_limit,
            max_duration=max_duration,
            outing=session.preferences.get("outing", "any"),
            company=session.preferences.get("company", "both"),
            categories=[current["category"]],
        )
        used_ids = {item["task_id"] for item in plan["items"]}
        candidate = next(
            (task for task in candidates if task.id == replacement_task_id),
            None,
        ) if replacement_task_id else None
        if candidate is None:
            candidate = next((task for task in candidates if task.id not in used_ids), None)
        if candidate is None:
            raise HTTPException(status_code=409, detail="当前约束下没有可替换任务")
        start = self._parse_time(current["start_at"])
        end = start + timedelta(minutes=candidate.duration)
        self._ensure_slot(plan, start, end, item_id)
        items = [dict(item) for item in plan["items"]]
        for item in items:
            if item["id"] == item_id:
                item.update(
                    task_id=candidate.id,
                    title=candidate.title,
                    category=candidate.category,
                    end_at=end.isoformat(),
                    status="pending",
                )
        return self._save_version(plan, items)

    def add_custom_task(self, session_id: str, plan_id: str, expected_version: int, title: str, duration_minutes: int, category: str | None = None) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        if not title.strip() or duration_minutes <= 0:
            raise HTTPException(status_code=422, detail="自定义任务标题和时长必须有效")
        category = category or "自我成长"
        if category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="自定义任务分类不受支持")
        cursor = self._parse_time(plan["free_start"])
        active = sorted(
            (item for item in plan["items"] if item["status"] != "skipped"),
            key=lambda item: item["start_at"],
        )
        for item in active:
            item_start = self._parse_time(item["start_at"])
            item_end = self._parse_time(item["end_at"])
            if cursor + timedelta(minutes=duration_minutes) <= item_start:
                break
            cursor = max(cursor, item_end + timedelta(minutes=15))
        end = cursor + timedelta(minutes=duration_minutes)
        self._ensure_slot(plan, cursor, end)
        items = [dict(item) for item in plan["items"]]
        items.append(
            {
                "id": make_id("item"),
                "task_id": make_id("custom"),
                "title": title.strip(),
                "category": category,
                "start_at": cursor.isoformat(),
                "end_at": end.isoformat(),
                "kind": "task",
                "status": "pending",
                "locked": True,
            }
        )
        return self._save_version(plan, items)

    def confirm(self, session_id: str, plan_id: str, expected_version: int) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        with self._connect() as connection:
            connection.execute("UPDATE plans SET status = 'confirmed' WHERE id = %s", (plan_id,))
        confirmed = self.get(session_id, plan_id)
        if confirmed is None:
            raise HTTPException(status_code=503, detail="计划确认失败")
        return confirmed

    def replan(self, session_id: str, plan_id: str, expected_version: int, density: str | None = None) -> dict[str, Any]:
        plan = self._require(session_id, plan_id)
        self._check_version(plan, expected_version)
        result = self.orchestrator.generate_plan(
            session_id,
            GeneratePlanRequest(
                free_start=self._parse_time(plan["free_start"]),
                free_end=self._parse_time(plan["free_end"]),
                density=density or plan["density"],
            ),
        )
        return result["plan"]
