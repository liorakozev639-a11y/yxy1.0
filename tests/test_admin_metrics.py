from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from admin_metrics_service import AdminMetricsService, MetricsFilters


class ControlledConnection:
    """A small psycopg boundary replacement, not a PostgreSQL substitute."""

    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...] | None]] = []
        self.users: dict[str, dict[str, object]] = {}
        self.sessions: dict[str, dict[str, object]] = {}
        self._row: dict[str, object] | None = None
        self._rows: list[dict[str, object]] = []
        self.rowcount = 0
        self.metric_rows = {
            "summary": [{
                "user_count": 2,
                "session_count": 4,
                "completed_sessions": 3,
                "average_rating": 4.5,
                "replacement_count": 1,
                "skip_count": 2,
                "recommendation_count": 5,
            }],
            "funnel": [
                {"event_type": "session_created", "count": 4},
                {"event_type": "feedback_submitted", "count": 3},
            ],
            "recommendations": [{
                "task_category": "study",
                "recommendation_count": 5,
                "average_rating": 4.5,
                "replacement_count": 1,
                "skip_count": 2,
            }],
            "reasons": [{"reason_code": "low_energy", "count": 2}],
            "errors": [{"error_code": "timeout", "count": 1}],
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params=None):
        statement = str(statement)
        self.executions.append((statement, params))
        self._row = None
        self._rows = []
        self.rowcount = 0

        if "WHERE role = 'admin'" in statement and "FROM admin_users" in statement:
            self._row = next((dict(user) for user in self.users.values()), None)
        elif "INSERT INTO admin_users" in statement:
            admin_id, username, password_hash = params
            self.users.setdefault(username, {
                "id": admin_id,
                "username": username,
                "password_hash": password_hash,
                "role": "admin",
            })
        elif "FROM admin_users" in statement:
            user = self.users.get(params[0])
            self._row = dict(user) if user else None
        elif "INSERT INTO admin_sessions" in statement:
            session_id, admin_user_id, token_hash, expires_at = params
            self.sessions[token_hash] = {
                "id": session_id,
                "admin_user_id": admin_user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "revoked_at": None,
            }
        elif "UPDATE admin_sessions SET revoked_at" in statement:
            token_hash = params[1]
            session = self.sessions.get(token_hash)
            if session and session["revoked_at"] is None:
                session["revoked_at"] = params[0]
                self.rowcount = 1
        elif "FROM admin_sessions" in statement:
            token_hash, now = params
            session = self.sessions.get(token_hash)
            if session and session["revoked_at"] is None and session["expires_at"] > now:
                user = next(
                    user for user in self.users.values()
                    if user["id"] == session["admin_user_id"]
                )
                self._row = {"id": user["id"], "username": user["username"], "role": "admin"}
        else:
            for name, rows in self.metric_rows.items():
                if f"admin_metrics:{name}" in statement:
                    self._rows = [dict(row) for row in rows]
                    if name == "summary" and self._rows:
                        self._row = self._rows[0]
                    break
        return self

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class AdminMetricsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = ControlledConnection()
        self.connect = patch(
            "admin_metrics_service.psycopg.connect", return_value=self.connection
        )
        self.connect.start()
        self.addCleanup(self.connect.stop)
        self.environment = patch.dict(
            os.environ,
            {
                "ADMIN_METRICS_USERNAME": "metrics_admin",
                "ADMIN_METRICS_PASSWORD": "correct horse battery staple",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.service = AdminMetricsService("postgresql://controlled-test")

    def test_login_initializes_single_admin_with_hashed_password_and_token(self) -> None:
        result = self.service.login("metrics_admin", "correct horse battery staple")

        self.assertIn("token", result)
        self.assertGreater(result["expires_at"], datetime.now(timezone.utc))
        admin = self.connection.users["metrics_admin"]
        self.assertNotEqual(admin["password_hash"], "correct horse battery staple")
        self.assertTrue(str(admin["password_hash"]).startswith("scrypt$"))
        self.assertNotIn(result["token"], self.connection.sessions)
        self.assertEqual(len(self.connection.sessions), 1)
        statements = "\n".join(statement for statement, _ in self.connection.executions)
        self.assertNotIn("correct horse battery staple", statements)
        self.assertNotIn(result["token"], statements)

    def test_login_failure_is_uniform_and_limited(self) -> None:
        for username, password in (("metrics_admin", "wrong"), ("unknown", "wrong")):
            with self.subTest(username=username):
                with self.assertRaisesRegex(PermissionError, "登录失败"):
                    self.service.login(username, password)

        for _ in range(3):
            with self.assertRaisesRegex(PermissionError, "登录失败"):
                self.service.login("metrics_admin", "wrong")
        with self.assertRaisesRegex(PermissionError, "登录失败"):
            self.service.login("metrics_admin", "correct horse battery staple")

    def test_initialization_refuses_a_second_admin_when_environment_changes(self) -> None:
        self.service.login("metrics_admin", "correct horse battery staple")
        with patch.dict(
            os.environ,
            {
                "ADMIN_METRICS_USERNAME": "replacement_admin",
                "ADMIN_METRICS_PASSWORD": "another secret",
            },
            clear=False,
        ):
            replacement = AdminMetricsService("postgresql://controlled-test")
            with self.assertRaisesRegex(RuntimeError, "单一管理员"):
                replacement.login("replacement_admin", "another secret")
        self.assertEqual(set(self.connection.users), {"metrics_admin"})

    def test_expired_and_logged_out_tokens_are_rejected(self) -> None:
        token = self.service.login("metrics_admin", "correct horse battery staple")["token"]
        self.assertEqual(self.service.authenticate(token)["username"], "metrics_admin")

        self.service.logout(token)
        with self.assertRaisesRegex(PermissionError, "未认证"):
            self.service.authenticate(token)

        expired_token = self.service.login("metrics_admin", "correct horse battery staple")["token"]
        token_hash = self.service._token_hash(expired_token)
        self.connection.sessions[token_hash]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaisesRegex(PermissionError, "未认证"):
            self.service.authenticate(expired_token)

    def test_metrics_use_all_filters_as_bound_parameters_and_return_stable_aggregates(self) -> None:
        filters = MetricsFilters(
            from_date=date(2026, 9, 1),
            to_date=date(2026, 9, 30),
            cohort="student_2026_09",
            anonymous_id="student_001",
            task_category="study",
        )

        self.assertEqual(
            self.service.summary(filters),
            {
                "user_count": 2,
                "session_count": 4,
                "full_flow_success_rate": 75.0,
                "average_rating": 4.5,
                "replacement_rate": 20.0,
                "skip_rate": 40.0,
            },
        )
        self.assertEqual(
            self.service.funnel(filters),
            [
                {"event_type": "session_created", "count": 4},
                {"event_type": "questionnaire_completed", "count": 0},
                {"event_type": "recommendations_viewed", "count": 0},
                {"event_type": "task_started", "count": 0},
                {"event_type": "task_completed", "count": 0},
                {"event_type": "feedback_submitted", "count": 3},
            ],
        )
        self.assertEqual(
            self.service.recommendations(filters),
            [{
                "task_category": "study",
                "recommendation_count": 5,
                "average_rating": 4.5,
                "replacement_rate": 20.0,
                "skip_rate": 40.0,
            }],
        )
        self.assertEqual(self.service.reasons(filters), [{"reason_code": "low_energy", "count": 2}])
        self.assertEqual(self.service.errors(filters), [{"error_code": "timeout", "count": 1}])

        metric_executions = [
            (statement, params)
            for statement, params in self.connection.executions
            if "admin_metrics:" in statement
        ]
        self.assertEqual(len(metric_executions), 5)
        for statement, params in metric_executions:
            self.assertIsNotNone(params)
            self.assertNotIn("student_2026_09", statement)
            self.assertNotIn("student_001", statement)
            self.assertNotIn("study", statement)
            self.assertIn("student_2026_09", params)
            self.assertIn("student_001", params)
            self.assertIn("study", params)

    def test_empty_metrics_are_zero_or_empty(self) -> None:
        self.connection.metric_rows = {
            "summary": [{
                "user_count": 0,
                "session_count": 0,
                "completed_sessions": 0,
                "average_rating": None,
                "replacement_count": 0,
                "skip_count": 0,
                "recommendation_count": 0,
            }],
            "funnel": [],
            "recommendations": [],
            "reasons": [],
            "errors": [],
        }
        filters = MetricsFilters()

        self.assertEqual(self.service.summary(filters)["full_flow_success_rate"], 0.0)
        self.assertEqual(self.service.summary(filters)["average_rating"], 0.0)
        self.assertEqual(self.service.recommendations(filters), [])
        self.assertEqual(self.service.reasons(filters), [])
        self.assertEqual(self.service.errors(filters), [])


if __name__ == "__main__":
    unittest.main()
