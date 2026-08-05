from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from main import create_app
from questionnaire_module import (
    PostgresQuestionnaireRepository,
    QuestionnaireService,
)
from session_module import PostgresSessionRepository, SessionService


class ApiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.session_repository = PostgresSessionRepository(database_url)
        session_service = SessionService(self.session_repository)
        questionnaire_service = QuestionnaireService(
            session_service,
            PostgresQuestionnaireRepository(database_url),
        )
        self.client = TestClient(
            create_app(session_service, questionnaire_service),
        )
        self.session_ids: list[str] = []

    def tearDown(self) -> None:
        for session_id in self.session_ids:
            self.session_repository.delete(session_id)
        self.client.close()

    def create_session(self) -> tuple[str, dict[str, object]]:
        response = self.client.post("/api/v1/sessions")
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIsNone(payload["error"])
        self.assertNotIn("token", payload["data"])
        session_id = payload["data"]["session_id"]
        self.session_ids.append(session_id)
        return session_id, payload["data"]

    @staticmethod
    def preferences() -> dict[str, object]:
        return {
            "categories": ["energy", "recovery"],
            "duration": "half",
            "budget": "low",
            "outing": "home",
            "company": "solo",
            "city_or_campus": "",
            "rest_only": False,
        }

    def start_questionnaire(self, session_id: str, mode: str) -> dict:
        response = self.client.post(
            f"/api/v1/sessions/{session_id}/questionnaire/start",
            json={"mode": mode},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_complete_quick_flow_without_authorization_header(self) -> None:
        session_id, _ = self.create_session()
        saved = self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json=self.preferences(),
        )
        self.assertEqual(saved.status_code, 200)

        started = self.start_questionnaire(session_id, "quick")
        self.assertEqual(started["total"], 5)
        for index, question in enumerate(started["questions"]):
            if index == 4:
                response = self.client.post(
                    f"/api/v1/sessions/{session_id}/questionnaire/skip/{question['id']}"
                )
            else:
                response = self.client.patch(
                    f"/api/v1/sessions/{session_id}/questionnaire/answers/{question['id']}",
                    json={"value": 3},
                )
            self.assertEqual(response.status_code, 200)

        progress = self.client.get(
            f"/api/v1/sessions/{session_id}/questionnaire/progress"
        ).json()["data"]
        self.assertEqual(progress["answered_count"], 4)
        self.assertEqual(progress["skipped_count"], 1)

        submitted = self.client.post(
            f"/api/v1/sessions/{session_id}/questionnaire/submit"
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertTrue(submitted.json()["data"]["submitted"])

    def test_deep_flow_returns_thirty_questions(self) -> None:
        session_id, _ = self.create_session()
        self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json=self.preferences(),
        )

        started = self.start_questionnaire(session_id, "deep")

        self.assertEqual(started["total"], 30)

    def test_restore_and_clear_remove_questionnaire_progress(self) -> None:
        session_id, created = self.create_session()
        restored = self.client.get(f"/api/v1/sessions/{session_id}")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["data"]["session_id"], session_id)
        self.assertEqual(restored.json()["data"]["version"], created["version"])

        self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json=self.preferences(),
        )
        self.start_questionnaire(session_id, "quick")

        cleared = self.client.delete(f"/api/v1/sessions/{session_id}/data")
        self.assertEqual(cleared.status_code, 200)
        progress = self.client.get(
            f"/api/v1/sessions/{session_id}/questionnaire/progress"
        )
        self.assertEqual(progress.status_code, 409)

    def test_http_errors_use_unified_shape(self) -> None:
        response = self.client.get("/api/v1/sessions/sess_missing")

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(response.json()["data"])
        self.assertEqual(response.json()["error"]["code"], "session_not_found")
        self.assertEqual(response.json()["error"]["message"], "会话不存在")

    def test_cors_allows_only_local_frontend_origins(self) -> None:
        headers = {
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        }
        allowed = self.client.options("/api/v1/sessions", headers=headers)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )

        blocked = self.client.options(
            "/api/v1/sessions",
            headers={**headers, "Origin": "https://example.com"},
        )
        self.assertNotIn("access-control-allow-origin", blocked.headers)


if __name__ == "__main__":
    unittest.main()
