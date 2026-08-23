from __future__ import annotations

import unittest

from plan_module import build_replaced_item, select_replacement_task
from task_repository import Task


class PlanReplacementRuleTests(unittest.TestCase):
    def test_select_replacement_keeps_category_and_relaxes_budget(self) -> None:
        tasks = [
            Task("used_strict", "已在计划内的严格匹配", "松弛疗愈", 20, 0, "home", "solo"),
            Task("expensive", "泡脚放松", "松弛疗愈", 30, 50, "home", "solo"),
            Task("wrong_category", "居家拉伸", "活力充电", 20, 0, "home", "solo"),
        ]

        replacement = select_replacement_task(
            candidates=tasks,
            category="松弛疗愈",
            used_task_ids={"used_strict"},
            budget_limit=20,
            max_duration=30,
            outing="home",
            company="solo",
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.id, "expensive")
        self.assertEqual(replacement.category, "松弛疗愈")

    def test_build_replaced_item_preserves_original_time_slot(self) -> None:
        current = {
            "id": "item_old",
            "task_id": "old",
            "title": "旧任务",
            "category": "乐享探索",
            "start_at": "2026-08-23T10:00:00+00:00",
            "end_at": "2026-08-23T10:30:00+00:00",
            "kind": "task",
            "status": "active",
            "locked": False,
        }
        replacement = Task(
            "new_task",
            "找一家咖啡馆放空",
            "乐享探索",
            90,
            40,
            "nearby",
            "both",
        )

        updated = build_replaced_item(current, replacement)

        self.assertEqual(updated["task_id"], "new_task")
        self.assertEqual(updated["title"], "找一家咖啡馆放空")
        self.assertEqual(updated["category"], "乐享探索")
        self.assertEqual(updated["start_at"], current["start_at"])
        self.assertEqual(updated["end_at"], current["end_at"])
        self.assertEqual(updated["status"], "pending")


if __name__ == "__main__":
    unittest.main()
