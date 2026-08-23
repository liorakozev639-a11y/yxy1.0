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
from recommendation_module import build_reason_tags, build_reason_text
from task_repository import CATEGORIES, Task, TaskRepository


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _task_matches_outing(task: Task, user_outing: str) -> bool:
    allowed = {
        "home": {"home"},
        "nearby": {"home", "nearby"},
        "city": {"home", "nearby", "city"},
        "any": {"home", "nearby", "city"},
    }
    return task.outing in allowed.get(user_outing, {"home", "nearby", "city"})


def _task_matches_company(task: Task, user_company: str) -> bool:
    return user_company == "both" or task.company in {user_company, "both"}


def select_replacement_task(
    *,
    candidates: list[Task],
    category: str,
    used_task_ids: set[str],
    budget_limit: int,
    max_duration: int,
    outing: str,
    company: str,
    preferred_task_id: str | None = None,
) -> Task | None:
    available = [
        task
        for task in candidates
        if task.status == "approved"
        and task.category == category
        and task.id not in used_task_ids
    ]
    if preferred_task_id:
        preferred = next(
            (task for task in available if task.id == preferred_task_id),
            None,
        )
        if preferred is not None:
            return preferred

    tiers = (
        lambda task: (
            task.budget <= budget_limit
            and task.duration <= max_duration
            and _task_matches_outing(task, outing)
            and _task_matches_company(task, company)
        ),
        lambda task: (
            task.duration <= max_duration
            and _task_matches_outing(task, outing)
            and _task_matches_company(task, company)
        ),
        lambda task: task.duration <= max_duration and _task_matches_company(task, company),
        lambda task: task.duration <= max_duration,
        lambda task: True,
    )
    for predicate in tiers:
        matches = [task for task in available if predicate(task)]
        if matches:
            return sorted(matches, key=lambda task: (task.duration, task.budget, task.id))[0]
    return None


def normalize_replacement_history(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(task_id) for task_id in value if task_id]
    return []


def build_replaced_item(current: dict[str, Any], replacement: Task) -> dict[str, Any]:
    updated = dict(current)
    replacement_history = normalize_replacement_history(current.get("replacement_history"))
    for task_id in (current.get("task_id"), replacement.id):
        if task_id and task_id not in replacement_history:
            replacement_history.append(task_id)
    updated.update(
        task_id=replacement.id,
        title=replacement.title,
        category=replacement.category,
        status="pending",
        replacement_history=replacement_history,
    )
    return updated


def enrich_plan_item_payload(item: dict[str, Any], task: Task | None = None) -> dict[str, Any]:
    payload = {
        "id": item["id"],
        "task_id": item["task_id"],
        "title": item["title"],
        "category": item["category"],
        "start_at": item["start_at"].isoformat(),
        "end_at": item["end_at"].isoformat(),
        "kind": item["kind"],
        "status": item["status"],
        "locked": bool(item["locked"]),
        "replacement_history": normalize_replacement_history(
            item.get("replacement_history")
        ),
    }
    if item["kind"] != "task":
        payload["reason_tags"] = ["自由调整", "低压力友好"]
        payload["reason_text"] = "这段时间用于休息与自由调整，避免计划过满。"
        return payload

    start_at = item["start_at"]
    end_at = item["end_at"]
    slot_minutes = max(1, int((end_at - start_at).total_seconds() // 60))
    if task is None:
        payload["reason_tags"] = [f"覆盖{item['category']}", "时间已安排"]
        payload["reason_text"] = f"该任务覆盖「{item['category']}」，并已保留当前时间段。"
        return payload

    payload["reason_tags"] = build_reason_tags(task, slot_minutes=slot_minutes)
    payload["reason_text"] = build_reason_text(task, slot_minutes=slot_minutes)
    return payload


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
            connection.execute(
                "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS replacement_history JSONB NOT NULL DEFAULT '[]'::jsonb"
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
                           kind, status, locked, replacement_history
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
        task_lookup = {
            task.id: task
            for task in TaskRepository().public_tasks
        }
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
                enrich_plan_item_payload(item, task_lookup.get(item["task_id"]))
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
                         kind, status, locked, replacement_history)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        Jsonb(normalize_replacement_history(item.get("replacement_history"))),
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
        if current["kind"] != "task":
            raise HTTPException(status_code=400, detail="只能替换任务项")
        session = self.sessions.require_active(session_id)
        budget_limit = {"low": 20, "medium": 40, "high": 80}.get(session.preferences.get("budget"), 40)
        max_duration = {"half": 270, "day": 480}.get(session.preferences.get("duration"), 270)
        used_ids = {
            item["task_id"]
            for item in plan["items"]
            if item["task_id"]
        }
        used_ids.update(normalize_replacement_history(current.get("replacement_history")))
        candidates = self.tasks.public_tasks + self.tasks.custom_tasks.get(session_id, [])
        candidate = select_replacement_task(
            candidates=candidates,
            category=current["category"],
            used_task_ids=used_ids,
            budget_limit=budget_limit,
            max_duration=max_duration,
            outing=session.preferences.get("outing", "any"),
            company=session.preferences.get("company", "both"),
            preferred_task_id=replacement_task_id,
        )
        if candidate is None:
            raise HTTPException(status_code=409, detail="当前约束下没有可替换任务")
        start = self._parse_time(current["start_at"])
        end = self._parse_time(current["end_at"])
        self._ensure_slot(plan, start, end, item_id)
        items = [dict(item) for item in plan["items"]]
        for item in items:
            if item["id"] == item_id:
                item.update(build_replaced_item(item, candidate))
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
                "replacement_history": [],
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
