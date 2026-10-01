from __future__ import annotations

from datetime import date
import os
import unittest
from unittest.mock import patch

# Keep importing the route module from attempting a live database bootstrap.
_database_url = os.environ.pop("SESSION_DATABASE_URL", None)

from fastapi.testclient import TestClient

from main import create_app

if _database_url is not None:
    os.environ["SESSION_DATABASE_URL"] = _database_url


class FakeSessionService:
    def create(self) -> dict[str, object]:
        return {"session_id": "session_api", "stage": "created", "version": 1}


class FakeQuestionnaireService:
    pass


class FakeObservabilityService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.feedback: list[dict[str, object]] = []
        self.event_results: dict[str, dict[str, object]] = {}
        self.fail = False

    def identify(self, anonymous_id: str, cohort: str) -> dict[str, str]:
        if self.fail:
            raise RuntimeError("telemetry unavailable")
        return {"anonymous_id": anonymous_id, "cohort": cohort}

    def record_event(self, **payload: object) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("telemetry unavailable")
        idempotency_key = str(payload["idempotency_key"])
        if idempotency_key not in self.event_results:
            self.events.append(payload)
            self.event_results[idempotency_key] = {
                "event_id": "event_001",
                **payload,
            }
        return self.event_results[idempotency_key]

    def save_feedback(self, **payload: object) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("telemetry unavailable")
        self.feedback.append(payload)
        return {"feedback_id": "feedback_001", **payload}


class FakeAdminMetricsService:
    def __init__(self) -> None:
        self.tokens = {"valid-token"}
        self.authenticated_tokens: list[str] = []
        self.logged_out_tokens: list[str] = []
        self.filters = []

    def login(self, username: str, password: str) -> dict[str, str]:
        if username != "admin" or password != "secret":
            raise PermissionError("登录失败")
        return {"token": "valid-token", "expires_at": "2099-01-01T00:00:00+00:00"}

    def authenticate(self, token: str) -> dict[str, str]:
        self.authenticated_tokens.append(token)
        if token not in self.tokens:
            raise PermissionError("未认证")
        return {"id": "admin_001", "username": "admin", "role": "admin"}

    def logout(self, token: str) -> None:
        self.logged_out_tokens.append(token)
        self.tokens.discard(token)

    def summary(self, filters: object) -> dict[str, object]:
        self.filters.append(filters)
        return {"user_count": 1}

    def funnel(self, filters: object) -> dict[str, object]:
        self.filters.append(filters)
        return {"steps": []}

    def recommendations(self, filters: object) -> list[dict[str, object]]:
        self.filters.append(filters)
        return []

    def reasons(self, filters: object) -> list[dict[str, object]]:
        self.filters.append(filters)
        return []

    def errors(self, filters: object) -> list[dict[str, object]]:
        self.filters.append(filters)
        return []


def build_client(
    observability: FakeObservabilityService | None = None,
    admin_metrics: FakeAdminMetricsService | None = None,
) -> tuple[TestClient, FakeObservabilityService, FakeAdminMetricsService]:
    observability = observability or FakeObservabilityService()
    admin_metrics = admin_metrics or FakeAdminMetricsService()
    return (
        TestClient(
            create_app(
                FakeSessionService(),
                FakeQuestionnaireService(),
                object(),
                test_observability_service=observability,
                admin_metrics_service=admin_metrics,
            )
        ),
        observability,
        admin_metrics,
    )


class TestingApiTests(unittest.TestCase):
    def test_database_configuration_builds_observation_and_admin_services(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SESSION_DATABASE_URL": "postgresql://configured",
                "ADMIN_METRICS_USERNAME": "admin",
                "ADMIN_METRICS_PASSWORD": "secret",
            },
            clear=False,
        ), patch("main.TestObservabilityService") as observation_class, patch(
            "main.AdminMetricsService"
        ) as admin_class:
            create_app(
                FakeSessionService(),
                FakeQuestionnaireService(),
                object(),
            )

        observation_class.assert_called_once_with("postgresql://configured")
        admin_class.assert_called_once_with("postgresql://configured")

    def test_identify_event_and_feedback_success(self) -> None:
        client, observability, _ = build_client()

        identified = client.post(
            "/api/v1/test-users/identify",
            json={"anonymous_id": "student_001", "cohort": "student_2026_09"},
        )
        event = client.post(
            "/api/v1/test-events",
            json={
                "anonymous_id": "student_001",
                "event_type": "task_completed",
                "session_id": "session_001",
                "plan_item_id": "item_001",
                "metadata": {"task_category": "study"},
                "idempotency_key": "event_001",
            },
        )
        feedback = client.post(
            "/api/v1/test-feedback",
            json={
                "anonymous_id": "student_001",
                "session_id": "session_001",
                "plan_item_id": "item_001",
                "rating": 5,
                "comment": "很好",
            },
        )

        self.assertEqual(identified.status_code, 200, identified.text)
        self.assertEqual(event.status_code, 200, event.text)
        self.assertEqual(feedback.status_code, 200, feedback.text)
        self.assertEqual(len(observability.events), 1)
        self.assertEqual(len(observability.feedback), 1)
        client.close()

    def test_invalid_rating_and_event_are_rejected_by_body_validation(self) -> None:
        client, _, _ = build_client()

        invalid_rating = client.post(
            "/api/v1/test-feedback",
            json={
                "anonymous_id": "student_001",
                "session_id": "session_001",
                "plan_item_id": "item_001",
                "rating": 6,
            },
        )
        invalid_event = client.post(
            "/api/v1/test-events",
            json={
                "anonymous_id": "student_001",
                "event_type": "not_a_real_event",
                "idempotency_key": "event_001",
            },
        )

        self.assertEqual(invalid_rating.status_code, 422)
        self.assertEqual(invalid_event.status_code, 422)
        client.close()

    def test_duplicate_event_keeps_service_idempotency_result(self) -> None:
        client, observability, _ = build_client()
        payload = {
            "anonymous_id": "student_001",
            "event_type": "task_completed",
            "idempotency_key": "event_001",
        }

        first = client.post("/api/v1/test-events", json=payload)
        second = client.post("/api/v1/test-events", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(observability.events), 1)
        client.close()

    def test_admin_login_failure_is_uniform_and_metrics_require_authentication(self) -> None:
        client, _, admin_metrics = build_client()

        unknown_user = client.post(
            "/api/v1/admin/login",
            json={"username": "unknown", "password": "wrong"},
        )
        wrong_password = client.post(
            "/api/v1/admin/login",
            json={"username": "admin", "password": "wrong"},
        )
        unauthorized = client.get("/api/v1/admin/metrics/summary")

        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_user.json(), wrong_password.json())
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(admin_metrics.authenticated_tokens, [])
        client.close()

    def test_authorized_admin_routes_authenticate_and_apply_filters(self) -> None:
        client, _, admin_metrics = build_client()
        headers = {"Authorization": "Bearer valid-token"}

        me = client.get("/api/v1/admin/me", headers=headers)
        summary = client.get(
            "/api/v1/admin/metrics/summary?from=2026-09-01&to=2026-09-30"
            "&cohort=student_2026_09&anonymous_id=student_001&task_category=study",
            headers=headers,
        )
        for path in (
            "funnel",
            "recommendations",
            "reasons",
            "errors",
        ):
            response = client.get(f"/api/v1/admin/metrics/{path}", headers=headers)
            self.assertEqual(response.status_code, 200, response.text)

        logged_out = client.post("/api/v1/admin/logout", headers=headers)

        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["data"]["role"], "admin")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["data"], {"user_count": 1})
        self.assertEqual(len(admin_metrics.filters), 5)
        self.assertEqual(admin_metrics.filters[0].from_date, date(2026, 9, 1))
        self.assertEqual(admin_metrics.filters[0].anonymous_id, "student_001")
        self.assertEqual(logged_out.status_code, 200, logged_out.text)
        self.assertEqual(admin_metrics.logged_out_tokens, ["valid-token"])
        client.close()

    def test_observation_failure_does_not_change_business_flow_or_crash_observation_route(self) -> None:
        observability = FakeObservabilityService()
        observability.fail = True
        client, _, _ = build_client(observability=observability)

        with patch("main.logger.warning") as warning:
            observation = client.post(
                "/api/v1/test-events",
                json={
                    "anonymous_id": "student_001",
                    "event_type": "task_completed",
                    "idempotency_key": "event_001",
                },
            )
        business = client.post("/api/v1/sessions")

        self.assertEqual(observation.status_code, 200, observation.text)
        self.assertEqual(observation.json()["data"], {"recorded": False})
        warning.assert_called_once_with("test observation write failed")
        self.assertEqual(business.status_code, 201, business.text)
        self.assertEqual(
            business.json()["data"],
            {"session_id": "session_api", "stage": "created", "version": 1},
        )
        client.close()


if __name__ == "__main__":
    unittest.main()
