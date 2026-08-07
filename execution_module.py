"""Synchronous execution state machine for scheduled plan items.

The module is deliberately independent from FastAPI and PostgreSQL. A service
layer can call ``execute_action`` inside one database transaction, update the
plan item, and append the returned event to ``execution_events``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone


class ExecutionError(ValueError):
    """Raised when an execution action is invalid or the item is not runnable."""


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    item_id: str
    event_type: str
    from_status: str
    to_status: str
    occurred_at: datetime


@dataclass(slots=True)
class PlanItem:
    id: str
    title: str
    start_at: datetime
    end_at: datetime
    status: str = "pending"
    events: list[ExecutionEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "status": self.status,
            "needs_adjustment": self.status == "needs_adjustment",
            "events": [
                {
                    **asdict(event),
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in self.events
            ],
        }


ALLOWED_ACTIONS = {
    "pending": {"start", "skip"},
    "active": {"complete", "skip"},
}


def _validate_item(item: PlanItem) -> None:
    if not item.id or not item.title:
        raise ExecutionError("任务 ID 和标题不能为空")
    if item.start_at >= item.end_at:
        raise ExecutionError("任务结束时间必须晚于开始时间")
    if item.status not in {
        "pending",
        "active",
        "completed",
        "skipped",
        "missed",
        "overdue",
        "needs_adjustment",
    }:
        raise ExecutionError(f"不支持的任务状态: {item.status}")


def _validate_time(item: PlanItem, current: datetime) -> None:
    if (item.start_at.tzinfo is None) != (current.tzinfo is None):
        raise ExecutionError("任务时间和当前时间必须使用相同的时区格式")


def _record_event(
    item: PlanItem,
    event_type: str,
    old_status: str,
    new_status: str,
    current: datetime,
) -> None:
    item.events.append(
        ExecutionEvent(
            item_id=item.id,
            event_type=event_type,
            from_status=old_status,
            to_status=new_status,
            occurred_at=current,
        )
    )


def expire_if_needed(item: PlanItem, current: datetime) -> bool:
    """Mark a pending or active item as needing adjustment after its deadline.

    The caller supplies the server/database time. Repeated checks are
    idempotent because terminal adjustment states are not changed again.
    """
    _validate_item(item)
    _validate_time(item, current)

    if current < item.end_at:
        return False

    old_status = item.status
    if item.status == "pending":
        item.status = "needs_adjustment"
        _record_event(item, "missed", old_status, item.status, current)
        return True

    if item.status == "active":
        item.status = "needs_adjustment"
        _record_event(item, "overdue", old_status, item.status, current)
        return True

    return False


def execute_action(
    item: PlanItem,
    action: str,
    current: datetime,
) -> PlanItem:
    """Apply ``start``, ``complete`` or ``skip`` to one plan item.

    Timeout detection runs before explicit action validation. Therefore a late
    request returns ``needs_adjustment`` and does not accidentally complete a
    task after its deadline.
    """
    _validate_item(item)

    if expire_if_needed(item, current):
        return item

    old_status = item.status
    if action not in ALLOWED_ACTIONS.get(old_status, set()):
        raise ExecutionError(f"不允许从 {old_status} 执行 {action}")

    if action == "start":
        if current < item.start_at:
            raise ExecutionError("任务尚未到开始时间")
        item.status = "active"
        event_type = "started"
    elif action == "complete":
        item.status = "completed"
        event_type = "completed"
    elif action == "skip":
        item.status = "needs_adjustment"
        event_type = "skipped"
    else:
        raise ExecutionError(f"不支持的操作: {action}")

    _record_event(item, event_type, old_status, item.status, current)
    return item


def demo() -> None:
    tz = timezone.utc
    start = datetime(2026, 8, 7, 14, 0, tzinfo=tz)
    end = start + timedelta(minutes=40)

    completed = PlanItem("item_001", "去公园散步", start, end)
    execute_action(completed, "start", start + timedelta(minutes=5))
    execute_action(completed, "complete", start + timedelta(minutes=30))

    missed = PlanItem("item_002", "阅读 30 分钟", start, start + timedelta(minutes=30))
    execute_action(missed, "start", start + timedelta(minutes=35))

    print(json.dumps({
        "completed_flow": completed.to_dict(),
        "missed_flow": missed.to_dict(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
