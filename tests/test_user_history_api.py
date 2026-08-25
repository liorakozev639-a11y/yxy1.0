from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import create_app


class UserHistoryApiTest(unittest.TestCase):
    def setUp(self) -> None:
        if not os.getenv("SESSION_DATABASE_URL"):
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.client = TestClient(create_app())

    def _create_plan(self) -> tuple[str, str, str]:
        session_id = self.client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json={
                "categories": ["活力充电", "松弛疗愈"],
                "budget": "medium",
                "outing": "nearby",
                "company": "both",
                "duration": "half",
            },
        )
        questions = self.client.post(
            f"/api/v1/sessions/{session_id}/questionnaire/start", json={"mode": "quick"}
        ).json()["data"]["questions"]
        for question in questions:
            self.client.patch(
                f"/api/v1/sessions/{session_id}/questionnaire/answers/{question['id']}",
                json={"value": 3},
            )
        self.client.post(f"/api/v1/sessions/{session_id}/questionnaire/submit")
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        plan = self.client.post(
            f"/api/v1/sessions/{session_id}/plan/generate",
            json={
                "free_start": start.isoformat(),
                "free_end": (start + timedelta(hours=4)).isoformat(),
                "density": "balanced",
            },
        ).json()["data"]["plan"]
        item = next(entry for entry in plan["items"] if entry["kind"] == "task")
        return session_id, plan["plan_id"], item["id"]

    def test_anonymous_user_completed_action_updates_history_summary(self) -> None:
        user = self.client.post("/api/v1/users/anonymous", json={}).json()["data"]
        _, plan_id, item_id = self._create_plan()
        now = datetime.now(timezone.utc)
        self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/execution/start",
            json={"user_id": user["user_id"], "now": now.isoformat()},
        )
        completed = self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/execution/complete",
            json={"user_id": user["user_id"], "now": (now + timedelta(minutes=1)).isoformat()},
        )

        self.assertEqual(completed.status_code, 200)
        summary = self.client.get(f"/api/v1/users/{user['user_id']}/history/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["data"]["completed_count"], 1)

    def test_low_energy_preparation_recommends_easier_replacement(self) -> None:
        _, plan_id, item_id = self._create_plan()

        response = self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/execution/prepare",
            json={"energy": "low"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["recommended_action"], "replace_easier")
        self.assertFalse(response.json()["data"]["can_start"])

    def test_replace_easier_keeps_category_and_records_history(self) -> None:
        user = self.client.post("/api/v1/users/anonymous", json={}).json()["data"]
        session_id, plan_id, item_id = self._create_plan()
        original_plan = self.client.get(
            f"/api/v1/sessions/{session_id}/plan"
        ).json()["data"]
        original_item = next(item for item in original_plan["items"] if item["id"] == item_id)

        response = self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/replace-easier",
            json={"expected_version": 1, "user_id": user["user_id"]},
        )

        self.assertEqual(response.status_code, 200)
        replaced_plan = response.json()["data"]
        replacement = next(
            item for item in replaced_plan["items"] if item["replacement_history"]
        )
        self.assertEqual(replacement["category"], original_item["category"])
        self.assertNotEqual(replacement["task_id"], original_item["task_id"])
        self.assertIn(original_item["task_id"], replacement["replacement_history"])
        self.assertIn(replacement["task_id"], replacement["replacement_history"])
        self.assertEqual(
            self.client.get(f"/api/v1/users/{user['user_id']}/history/summary").json()["data"]["replaced_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
