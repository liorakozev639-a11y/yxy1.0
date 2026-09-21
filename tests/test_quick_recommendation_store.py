from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from main import create_app
from quick_test_support import delete_test_user, require_test_database
from quick_recommendation_store import QuickRecommendationStore
from session_module import PostgresSessionRepository
from task_repository import TaskRepository
from user_history_service import UserHistoryService


def task_payload(task_id: str) -> dict:
    task = next(task for task in TaskRepository().public_tasks if task.id == task_id)
    return {
        "id": task.id,
        "title": task.title,
        "category": task.category,
        "feedback_group": task.feedback_group,
        "duration_minutes": task.duration,
        "first_action": "现在坐下。",
    }


class QuickStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database_url = require_test_database()
        self.client = TestClient(create_app())
        self.session_id = self.client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.user_id = self.client.post("/api/v1/users/anonymous", json={}).json()["data"]["user_id"]
        self.store = QuickRecommendationStore(self.database_url)
        self.history = UserHistoryService(self.database_url)

    def tearDown(self) -> None:
        PostgresSessionRepository(self.database_url).delete(self.session_id)
        delete_test_user(self.database_url, self.user_id)
        self.client.close()

    def save_run(self, task_ids: list[str]) -> str:
        return self.store.save_run(
            self.session_id, self.user_id, 15, "low",
            [task_payload(task_id) for task_id in task_ids],
        )

    def test_feedback_is_idempotent_and_run_bound(self) -> None:
        run_id = self.save_run(["task_recovery_01"])
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        self.assertEqual(len(self.store.latest_run(self.session_id)["feedback"]), 1)
        with self.assertRaises(LookupError):
            self.store.save_feedback("another_session", run_id, "liked", "task_recovery_01")
        with self.assertRaises(LookupError):
            self.store.save_feedback(self.session_id, run_id, "liked", "not_in_run")

    def test_new_feedback_replaces_previous_choice_for_one_task(self) -> None:
        run_id = self.save_run(["task_recovery_01"])
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        self.store.save_feedback(self.session_id, run_id, "disliked", "task_recovery_01")
        self.assertEqual(
            self.store.latest_run(self.session_id)["feedback"],
            [{"action": "disliked", "task_id": "task_recovery_01"}],
        )

    def test_rest_is_neutral_and_creates_no_plan_action(self) -> None:
        run_id = self.save_run([])
        self.store.save_feedback(self.session_id, run_id, "rest_selected", None)
        self.store.save_feedback(self.session_id, run_id, "rest_selected", None)
        self.assertEqual(
            self.store.latest_run(self.session_id)["feedback"],
            [{"action": "rest_selected", "task_id": None}],
        )
        self.assertEqual(self.history.summary(self.user_id)["completed_count"], 0)
        self.assertEqual(self.history.preference_weights(self.user_id)["group_penalties"], {})

    def test_likes_feed_shared_weights_without_claiming_completion(self) -> None:
        run_id = self.save_run(["task_recovery_01"])
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        weights = self.history.preference_weights(self.user_id)
        self.assertGreater(weights["group_boosts"].get("recovery_quiet_home", 0), 0)
        self.assertIsNone(weights["preferred_duration_minutes"])
        self.assertEqual(self.history.summary(self.user_id)["completed_count"], 0)

    def test_one_dislike_excludes_task_but_two_distinct_dislikes_exclude_group(self) -> None:
        run_id = self.save_run(["task_recovery_08", "task_recovery_32"])
        self.store.save_feedback(self.session_id, run_id, "disliked", "task_recovery_08")
        self.assertIn("task_recovery_08", self.history.excluded_task_ids(self.user_id))
        self.assertNotIn("recovery_pressure_release", self.history.excluded_groups(self.user_id))
        self.store.save_feedback(self.session_id, run_id, "disliked", "task_recovery_32")
        self.assertIn("recovery_pressure_release", self.history.excluded_groups(self.user_id))


if __name__ == "__main__":
    unittest.main()
