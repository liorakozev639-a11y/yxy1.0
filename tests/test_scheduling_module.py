import unittest
from datetime import datetime, timedelta, timezone

from scheduling_module import (
    PlanDraft,
    PlanItem,
    ScheduleError,
    Task,
    build_schedule,
    replan,
    validate_time_change,
)


UTC = timezone.utc


class SchedulingModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.free_start = datetime(2026, 8, 6, 14, 0, tzinfo=UTC)
        self.free_end = datetime(2026, 8, 6, 18, 0, tzinfo=UTC)
        self.tasks = [
            Task("walk", "去公园散步", "活力充电", 40, 0.95),
            Task("coffee", "喝咖啡放松", "松弛疗愈", 30, 0.90),
            Task("read", "安静阅读", "自我成长", 45, 0.85),
            Task("stretch", "居家拉伸", "活力充电", 20, 0.80),
            Task("music", "听一张专辑", "乐享探索", 30, 0.75),
            Task("call", "和朋友通话", "社交连接", 30, 0.70),
        ]

    def test_balanced_schedule_has_four_tasks_rest_and_no_overlap(self) -> None:
        draft = build_schedule(
            session_id="sess_001",
            tasks=self.tasks,
            free_start=self.free_start,
            free_end=self.free_end,
            density="balanced",
        )

        task_items = [item for item in draft.items if item.kind == "task"]
        rest_items = [item for item in draft.items if item.kind == "rest"]
        self.assertEqual(len(task_items), 4)
        self.assertEqual(len(rest_items), 1)
        self.assertEqual(draft.unscheduled_task_ids, ("music", "call"))
        self.assertEqual(draft.version, 1)

        ordered = sorted(draft.items, key=lambda item: item.start_at)
        self.assertTrue(all(item.start_at >= self.free_start for item in ordered))
        self.assertTrue(all(item.end_at <= self.free_end for item in ordered))
        self.assertTrue(all(left.end_at <= right.start_at for left, right in zip(ordered, ordered[1:])))

    def test_density_limits_are_two_four_and_six_tasks(self) -> None:
        long_end = self.free_start + timedelta(hours=8)
        expected = {"light": 2, "balanced": 4, "full": 6}

        for density, expected_count in expected.items():
            with self.subTest(density=density):
                draft = build_schedule(
                    "sess_density",
                    self.tasks,
                    self.free_start,
                    long_end,
                    density,
                )
                actual = sum(item.kind == "task" for item in draft.items)
                self.assertEqual(actual, expected_count)
                self.assertTrue(any(item.kind == "rest" for item in draft.items))

    def test_short_window_keeps_rest_and_reports_unscheduled_tasks(self) -> None:
        draft = build_schedule(
            "sess_short",
            self.tasks[:2],
            self.free_start,
            self.free_start + timedelta(minutes=70),
            "balanced",
        )

        self.assertTrue(any(item.kind == "rest" for item in draft.items))
        self.assertGreaterEqual(len(draft.unscheduled_task_ids), 1)

    def test_validate_time_change_rejects_bounds_and_overlap(self) -> None:
        existing = PlanItem(
            id="item_existing",
            task_id="existing",
            title="已有任务",
            category="自我成长",
            start_at=self.free_start + timedelta(hours=1),
            end_at=self.free_start + timedelta(hours=2),
        )

        with self.assertRaisesRegex(ScheduleError, "超出可用时间"):
            validate_time_change(
                self.free_start - timedelta(minutes=1),
                30,
                self.free_start,
                self.free_end,
                [existing],
            )
        with self.assertRaisesRegex(ScheduleError, "时间发生冲突"):
            validate_time_change(
                self.free_start + timedelta(minutes=90),
                30,
                self.free_start,
                self.free_end,
                [existing],
            )

        start_at, end_at = validate_time_change(
            existing.end_at,
            30,
            self.free_start,
            self.free_end,
            [existing],
        )
        self.assertEqual(start_at, existing.end_at)
        self.assertEqual(end_at, existing.end_at + timedelta(minutes=30))

    def test_replan_preserves_completed_item_and_creates_new_version(self) -> None:
        completed = PlanItem(
            id="item_completed",
            task_id="walk",
            title="去公园散步",
            category="活力充电",
            start_at=self.free_start,
            end_at=self.free_start + timedelta(minutes=40),
            status="completed",
            locked=True,
        )
        old = PlanDraft(
            plan_id="plan_old",
            session_id="sess_replan",
            density="balanced",
            free_start=self.free_start,
            free_end=self.free_end,
            items=(completed,),
            unscheduled_task_ids=(),
            version=1,
        )

        updated = replan(old, self.tasks)

        preserved = next(item for item in updated.items if item.id == completed.id)
        self.assertEqual(preserved, completed)
        self.assertEqual(updated.parent_plan_id, old.plan_id)
        self.assertEqual(updated.version, 2)
        self.assertEqual(
            sum(item.task_id == completed.task_id for item in updated.items),
            1,
        )

    def test_replan_also_preserves_explicitly_locked_pending_item(self) -> None:
        pending = PlanItem(
            id="item_fixed",
            task_id="coffee",
            title="喝咖啡放松",
            category="松弛疗愈",
            start_at=self.free_start + timedelta(hours=2),
            end_at=self.free_start + timedelta(hours=2, minutes=30),
            locked=True,
        )
        old = PlanDraft(
            plan_id="plan_fixed",
            session_id="sess_fixed",
            density="light",
            free_start=self.free_start,
            free_end=self.free_end,
            items=(pending,),
            unscheduled_task_ids=(),
        )

        updated = replan(old, self.tasks)

        self.assertIn(pending, updated.items)
        self.assertEqual(sum(item.task_id == "coffee" for item in updated.items), 1)


if __name__ == "__main__":
    unittest.main()
