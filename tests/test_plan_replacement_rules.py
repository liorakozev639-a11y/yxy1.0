from __future__ import annotations

import unittest

from recommendation_module import select_adjusted_task
from plan_module import build_replaced_item, select_replacement_task
from task_repository import Task


class PlanReplacementRuleTests(unittest.TestCase):
    def test_select_adjusted_task_excludes_current_history_and_session_pool(self) -> None:
        tasks = [
            Task(
                "task_a", "原任务", "松弛疗愈", 45, 20, "home", "solo",
                ease_level=3, physical_load=3, social_pressure=2,
            ),
            Task(
                "task_b", "第一次换出的任务", "松弛疗愈", 30, 10, "home", "solo",
                ease_level=4, physical_load=2, social_pressure=1,
            ),
            Task(
                "task_c", "真正的新任务", "松弛疗愈", 20, 0, "home", "solo",
                ease_level=5, physical_load=1, social_pressure=1,
            ),
        ]

        replacement = select_adjusted_task(
            candidates=tasks,
            current_task=tasks[0],
            adjustment="easier",
            used_task_ids={"task_a", "task_b"},
            constraints={
                "budget_limit": 20,
                "max_duration": 60,
                "outing": "home",
                "company": "solo",
            },
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.id, "task_c")

    def test_select_adjusted_task_returns_none_when_only_seen_tasks_match(self) -> None:
        tasks = [
            Task("task_a", "原任务", "活力充电", 45, 20, "home", "solo"),
            Task("task_b", "旧替换", "活力充电", 25, 0, "home", "solo"),
        ]

        replacement = select_adjusted_task(
            candidates=tasks,
            current_task=tasks[0],
            adjustment="shorter",
            used_task_ids={"task_a", "task_b"},
            constraints={
                "budget_limit": 20,
                "max_duration": 60,
                "outing": "home",
                "company": "solo",
            },
        )

        self.assertIsNone(replacement)

    def test_select_replacement_excludes_history_and_feedback_group(self) -> None:
        tasks = [
            Task(
                "seen", "已替换过", "乐享探索", 20, 0, "home", "solo",
                feedback_group="explore_game_relax",
            ),
            Task(
                "disliked", "不喜欢的同组", "乐享探索", 20, 0, "home", "solo",
                feedback_group="explore_food_drink",
            ),
            Task(
                "fresh", "新的任务", "乐享探索", 20, 0, "home", "solo",
                feedback_group="explore_local_browse",
            ),
        ]

        replacement = select_replacement_task(
            candidates=tasks,
            category="乐享探索",
            used_task_ids={"seen"},
            budget_limit=20,
            max_duration=30,
            outing="home",
            company="solo",
            excluded_feedback_groups={"explore_food_drink"},
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.id, "fresh")

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
        self.assertIn("replacement_reason", updated)
        self.assertIn("已避开旧任务", updated["replacement_reason"])
        self.assertIn("同属乐享探索", updated["replacement_reason"])

    def test_build_replaced_item_tracks_replacement_history(self) -> None:
        current = {
            "id": "item_old",
            "task_id": "task_a",
            "title": "旧任务",
            "category": "乐享探索",
            "start_at": "2026-08-23T10:00:00+00:00",
            "end_at": "2026-08-23T10:30:00+00:00",
            "kind": "task",
            "status": "pending",
            "locked": False,
            "replacement_history": ["task_a"],
        }
        first_replacement = Task(
            "task_b",
            "找一家咖啡馆放空",
            "乐享探索",
            90,
            40,
            "nearby",
            "both",
        )
        second_replacement = Task(
            "task_c",
            "在家制作一份简单甜品",
            "乐享探索",
            70,
            40,
            "home",
            "solo",
        )

        replaced_once = build_replaced_item(current, first_replacement)
        replaced_twice = build_replaced_item(replaced_once, second_replacement)

        self.assertEqual(replaced_once["replacement_history"], ["task_a", "task_b"])
        self.assertEqual(
            replaced_twice["replacement_history"],
            ["task_a", "task_b", "task_c"],
        )


if __name__ == "__main__":
    unittest.main()
