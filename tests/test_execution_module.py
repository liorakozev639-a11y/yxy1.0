import unittest
from datetime import datetime, timedelta, timezone

from execution_module import (
    ExecutionError,
    PlanItem,
    execute_action,
    expire_if_needed,
)


class ExecutionModuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tz = timezone.utc
        self.start = datetime(2026, 8, 7, 14, 0, tzinfo=self.tz)
        self.end = self.start + timedelta(minutes=40)

    def make_item(self) -> PlanItem:
        return PlanItem("item_001", "去公园散步", self.start, self.end)

    def at(self, minutes: int) -> datetime:
        return self.start + timedelta(minutes=minutes)

    def test_start_and_complete_record_events(self) -> None:
        item = self.make_item()

        execute_action(item, "start", self.at(5))
        execute_action(item, "complete", self.at(30))

        self.assertEqual(item.status, "completed")
        self.assertEqual(
            [event.event_type for event in item.events],
            ["started", "completed"],
        )
        self.assertEqual(item.events[0].from_status, "pending")
        self.assertEqual(item.events[1].to_status, "completed")

    def test_start_before_scheduled_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExecutionError, "尚未到开始时间"):
            execute_action(self.make_item(), "start", self.at(-1))

    def test_pending_item_becomes_missed_after_deadline(self) -> None:
        item = self.make_item()

        execute_action(item, "start", self.at(41))

        self.assertEqual(item.status, "needs_adjustment")
        self.assertEqual(item.events[-1].event_type, "missed")

    def test_active_item_becomes_overdue_after_deadline(self) -> None:
        item = self.make_item()
        execute_action(item, "start", self.at(5))

        execute_action(item, "complete", self.at(41))

        self.assertEqual(item.status, "needs_adjustment")
        self.assertEqual(item.events[-1].event_type, "overdue")

    def test_skip_needs_adjustment(self) -> None:
        item = self.make_item()

        execute_action(item, "skip", self.at(5))

        self.assertEqual(item.status, "needs_adjustment")
        self.assertEqual(item.events[-1].event_type, "skipped")

    def test_invalid_transition_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExecutionError, "不允许"):
            execute_action(self.make_item(), "complete", self.at(5))

    def test_completed_item_cannot_be_started_again(self) -> None:
        item = self.make_item()
        execute_action(item, "start", self.at(5))
        execute_action(item, "complete", self.at(30))

        with self.assertRaisesRegex(ExecutionError, "不允许"):
            execute_action(item, "start", self.at(31))

    def test_timeout_check_is_idempotent(self) -> None:
        item = self.make_item()
        execute_action(item, "start", self.at(41))
        first_event_count = len(item.events)

        self.assertFalse(expire_if_needed(item, self.at(42)))

        self.assertEqual(item.status, "needs_adjustment")
        self.assertEqual(len(item.events), first_event_count)


if __name__ == "__main__":
    unittest.main()
