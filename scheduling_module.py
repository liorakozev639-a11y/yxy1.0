from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


class ScheduleError(ValueError):
    """Raised when a valid schedule cannot be produced."""


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    title: str
    category: str
    duration: int
    score: float


@dataclass(frozen=True, slots=True)
class PlanItem:
    id: str
    task_id: str | None
    title: str
    category: str | None
    start_at: datetime
    end_at: datetime
    kind: str = "task"
    status: str = "pending"
    locked: bool = False


@dataclass(frozen=True, slots=True)
class DensityConfig:
    max_tasks: int
    buffer_minutes: int
    rest_after_tasks: int
    rest_minutes: int


@dataclass(frozen=True, slots=True)
class PlanDraft:
    plan_id: str
    session_id: str
    density: str
    free_start: datetime
    free_end: datetime
    items: tuple[PlanItem, ...]
    unscheduled_task_ids: tuple[str, ...]
    version: int = 1
    parent_plan_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "density": self.density,
            "free_start": self.free_start.isoformat(),
            "free_end": self.free_end.isoformat(),
            "version": self.version,
            "parent_plan_id": self.parent_plan_id,
            "unscheduled_task_ids": list(self.unscheduled_task_ids),
            "items": [
                {
                    "id": item.id,
                    "task_id": item.task_id,
                    "title": item.title,
                    "category": item.category,
                    "kind": item.kind,
                    "status": item.status,
                    "locked": item.locked,
                    "start_at": item.start_at.isoformat(),
                    "end_at": item.end_at.isoformat(),
                }
                for item in self.items
            ],
        }


DENSITY_CONFIGS = {
    "light": DensityConfig(2, 20, 1, 30),
    "balanced": DensityConfig(4, 15, 2, 20),
    "full": DensityConfig(6, 10, 3, 15),
}


@dataclass(slots=True)
class _FreeSlot:
    cursor: datetime
    end_at: datetime


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _validate_window(free_start: datetime, free_end: datetime) -> None:
    if free_start >= free_end:
        raise ScheduleError("空闲结束时间必须晚于开始时间")
    if (free_start.tzinfo is None) != (free_end.tzinfo is None):
        raise ScheduleError("开始时间和结束时间必须使用相同的时区格式")


def _validate_tasks(tasks: list[Task]) -> None:
    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ScheduleError("推荐任务中存在重复的任务 ID")
    for task in tasks:
        if not task.id or not task.title or not task.category:
            raise ScheduleError("任务 ID、标题和分类不能为空")
        if task.duration <= 0:
            raise ScheduleError("任务持续时间必须大于 0")
        if not 0 <= task.score <= 1:
            raise ScheduleError("任务匹配分数必须在 0 到 1 之间")


def _validate_locked_items(
    items: list[PlanItem],
    free_start: datetime,
    free_end: datetime,
) -> list[PlanItem]:
    ordered = sorted(items, key=lambda item: (item.start_at, item.end_at, item.id))
    for item in ordered:
        if item.start_at >= item.end_at:
            raise ScheduleError("锁定任务的结束时间必须晚于开始时间")
        if item.start_at < free_start or item.end_at > free_end:
            raise ScheduleError("锁定任务超出可用时间")
    for left, right in zip(ordered, ordered[1:]):
        if left.end_at > right.start_at:
            raise ScheduleError("锁定任务之间存在时间冲突")
    return ordered


def _build_free_slots(
    free_start: datetime,
    free_end: datetime,
    locked_items: list[PlanItem],
    buffer_minutes: int,
) -> list[_FreeSlot]:
    buffer = timedelta(minutes=buffer_minutes)
    cursor = free_start
    slots: list[_FreeSlot] = []
    for item in locked_items:
        gap_end = item.start_at - buffer
        if cursor < gap_end:
            slots.append(_FreeSlot(cursor, gap_end))
        cursor = max(cursor, item.end_at + buffer)
    if cursor < free_end:
        slots.append(_FreeSlot(cursor, free_end))
    return slots


def _copy_slots(slots: list[_FreeSlot]) -> list[_FreeSlot]:
    return [_FreeSlot(slot.cursor, slot.end_at) for slot in slots]


def _place(
    slots: list[_FreeSlot],
    duration_minutes: int,
    following_buffer_minutes: int,
) -> tuple[datetime, datetime] | None:
    duration = timedelta(minutes=duration_minutes)
    following_buffer = timedelta(minutes=following_buffer_minutes)
    for slot in slots:
        start_at = slot.cursor
        end_at = start_at + duration
        if end_at + following_buffer <= slot.end_at:
            slot.cursor = end_at + following_buffer
            return start_at, end_at
    return None


def _make_rest_item(start_at: datetime, end_at: datetime) -> PlanItem:
    return PlanItem(
        id=make_id("rest"),
        task_id=None,
        title="休息与自由调整",
        category="松弛疗愈",
        start_at=start_at,
        end_at=end_at,
        kind="rest",
    )


def _attempt_schedule(
    tasks: list[Task],
    base_slots: list[_FreeSlot],
    config: DensityConfig,
    task_limit: int,
    rest_already_present: bool,
    rest_first: bool,
) -> list[PlanItem] | None:
    slots = _copy_slots(base_slots)
    created: list[PlanItem] = []
    rest_added = rest_already_present

    if rest_first and not rest_added:
        position = _place(slots, config.rest_minutes, 0)
        if position is None:
            return None
        created.append(_make_rest_item(*position))
        rest_added = True

    scheduled_count = 0
    for task in tasks:
        if scheduled_count >= task_limit:
            break
        position = _place(slots, task.duration, config.buffer_minutes)
        if position is None:
            continue
        created.append(
            PlanItem(
                id=make_id("item"),
                task_id=task.id,
                title=task.title,
                category=task.category,
                start_at=position[0],
                end_at=position[1],
            )
        )
        scheduled_count += 1

        if not rest_added and scheduled_count == config.rest_after_tasks:
            rest_position = _place(slots, config.rest_minutes, 0)
            if rest_position is not None:
                created.append(_make_rest_item(*rest_position))
                rest_added = True

    if not rest_added:
        rest_position = _place(slots, config.rest_minutes, 0)
        if rest_position is None:
            return None
        created.append(_make_rest_item(*rest_position))

    return created


def build_schedule(
    session_id: str,
    tasks: Iterable[Task],
    free_start: datetime,
    free_end: datetime,
    density: str = "balanced",
    *,
    locked_items: Iterable[PlanItem] = (),
    version: int = 1,
    parent_plan_id: str | None = None,
) -> PlanDraft:
    if not session_id:
        raise ScheduleError("session_id 不能为空")
    if density not in DENSITY_CONFIGS:
        raise ScheduleError("不支持的计划密度")
    if version <= 0:
        raise ScheduleError("计划版本必须大于 0")
    _validate_window(free_start, free_end)

    task_list = list(tasks)
    _validate_tasks(task_list)
    config = DENSITY_CONFIGS[density]
    locked = _validate_locked_items(list(locked_items), free_start, free_end)
    locked_task_ids = {
        item.task_id for item in locked if item.kind == "task" and item.task_id
    }
    ranked = sorted(
        (task for task in task_list if task.id not in locked_task_ids),
        key=lambda task: (-task.score, task.duration, task.id),
    )

    base_slots = _build_free_slots(
        free_start,
        free_end,
        locked,
        config.buffer_minutes,
    )
    locked_task_count = sum(item.kind == "task" for item in locked)
    maximum_new_tasks = max(0, config.max_tasks - locked_task_count)
    rest_present = any(item.kind == "rest" for item in locked)

    created: list[PlanItem] | None = None
    for task_limit in range(maximum_new_tasks, -1, -1):
        attempts = [
            _attempt_schedule(
                ranked,
                base_slots,
                config,
                task_limit,
                rest_present,
                rest_first,
            )
            for rest_first in (False, True)
        ]
        valid_attempts = [attempt for attempt in attempts if attempt is not None]
        if valid_attempts:
            created = max(
                valid_attempts,
                key=lambda attempt: sum(item.kind == "task" for item in attempt),
            )
            break

    if created is None:
        raise ScheduleError("可用时间不足，无法保留休息块")

    items = sorted(
        [*locked, *created],
        key=lambda item: (item.start_at, item.end_at, item.id),
    )
    for left, right in zip(items, items[1:]):
        if left.end_at > right.start_at:
            raise ScheduleError("生成的计划存在时间冲突")
    if not any(item.kind == "rest" for item in items):
        raise ScheduleError("计划必须包含至少一个休息块")

    scheduled_task_ids = {
        item.task_id for item in items if item.kind == "task" and item.task_id
    }
    unscheduled = tuple(
        task.id
        for task in task_list
        if task.id not in scheduled_task_ids and task.id not in locked_task_ids
    )
    return PlanDraft(
        plan_id=make_id("plan"),
        session_id=session_id,
        density=density,
        free_start=free_start,
        free_end=free_end,
        items=tuple(items),
        unscheduled_task_ids=unscheduled,
        version=version,
        parent_plan_id=parent_plan_id,
    )


def validate_time_change(
    start_at: datetime,
    duration_minutes: int,
    free_start: datetime,
    free_end: datetime,
    existing_items: Iterable[PlanItem],
    *,
    ignore_item_id: str | None = None,
) -> tuple[datetime, datetime]:
    _validate_window(free_start, free_end)
    if duration_minutes <= 0:
        raise ScheduleError("任务持续时间必须大于 0")
    end_at = start_at + timedelta(minutes=duration_minutes)
    if start_at < free_start or end_at > free_end:
        raise ScheduleError("任务超出可用时间")
    for item in existing_items:
        if item.id == ignore_item_id:
            continue
        if start_at < item.end_at and end_at > item.start_at:
            raise ScheduleError(f"任务时间发生冲突: {item.id}")
    return start_at, end_at


def replan(
    previous: PlanDraft,
    tasks: Iterable[Task],
    density: str | None = None,
) -> PlanDraft:
    locked = tuple(
        item
        for item in previous.items
        if item.locked or item.status == "completed"
    )
    return build_schedule(
        session_id=previous.session_id,
        tasks=tasks,
        free_start=previous.free_start,
        free_end=previous.free_end,
        density=density or previous.density,
        locked_items=locked,
        version=previous.version + 1,
        parent_plan_id=previous.plan_id,
    )


def demo() -> None:
    free_start = datetime(2026, 8, 6, 14, 0, tzinfo=timezone.utc)
    tasks = [
        Task("walk", "去公园散步", "活力充电", 40, 0.95),
        Task("coffee", "喝咖啡放松", "松弛疗愈", 30, 0.90),
        Task("read", "安静阅读", "自我成长", 45, 0.85),
        Task("stretch", "居家拉伸", "活力充电", 20, 0.80),
        Task("music", "听一张专辑", "乐享探索", 30, 0.75),
    ]
    draft = build_schedule(
        session_id="sess_demo",
        tasks=tasks,
        free_start=free_start,
        free_end=free_start + timedelta(hours=4),
        density="balanced",
    )
    print(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
