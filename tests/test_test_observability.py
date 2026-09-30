from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from test_observability import TestObservabilityService


class ControlledConnection:
    """Small psycopg boundary replacement; it deliberately is not PostgreSQL."""

    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...] | None]] = []
        self.users: dict[str, dict[str, object]] = {}
        self.events: dict[str, dict[str, object]] = {}
        self.feedback: dict[str, dict[str, object]] = {}
        self._row: dict[str, object] | None = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params=None):
        statement = str(statement)
        self.executions.append((statement, params))
        self._row = None
        self.rowcount = 0
        if "INSERT INTO test_users" in statement:
            _user_id, anonymous_id, cohort, _now = params
            self.users[anonymous_id] = {
                "anonymous_id": anonymous_id,
                "cohort": cohort,
            }
            self._row = self.users[anonymous_id]
        elif "INSERT INTO test_events" in statement:
            (
                event_id,
                anonymous_id,
                session_id,
                plan_id,
                plan_item_id,
                event_type,
                reason_code,
                metadata,
                occurred_at,
                idempotency_key,
            ) = params
            event = self.events.setdefault(
                idempotency_key,
                {
                    "id": event_id,
                    "anonymous_id": anonymous_id,
                    "session_id": session_id,
                    "plan_id": plan_id,
                    "plan_item_id": plan_item_id,
                    "event_type": event_type,
                    "reason_code": reason_code,
                    "metadata_json": metadata.obj,
                    "occurred_at": occurred_at,
                    "idempotency_key": idempotency_key,
                },
            )
            self._row = event
        elif "INSERT INTO task_test_feedback" in statement:
            feedback_id, anonymous_id, session_id, plan_item_id, rating, comment, now = params
            feedback = self.feedback.setdefault(
                plan_item_id,
                {
                    "id": feedback_id,
                    "anonymous_id": anonymous_id,
                    "session_id": session_id,
                    "plan_item_id": plan_item_id,
                    "created_at": now,
                },
            )
            feedback.update({"rating": rating, "comment": comment})
            self._row = feedback
        elif "DELETE FROM test_users" in statement:
            anonymous_id = params[0]
            if anonymous_id in self.users:
                del self.users[anonymous_id]
                self.events = {
                    key: value
                    for key, value in self.events.items()
                    if value["anonymous_id"] != anonymous_id
                }
                self.feedback = {
                    key: value
                    for key, value in self.feedback.items()
                    if value["anonymous_id"] != anonymous_id
                }
                self.rowcount = 1
        return self

    def fetchone(self):
        return self._row


class TestObservabilityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = ControlledConnection()
        self.connect = patch(
            "test_observability.psycopg.connect",
            return_value=self.connection,
        )
        self.connect.start()
        self.addCleanup(self.connect.stop)
        self.service = TestObservabilityService("postgresql://controlled-test")

    def test_identify_accepts_anonymous_student_identifier(self) -> None:
        result = self.service.identify("student_001", "student_2026_09")

        self.assertEqual(result, {"anonymous_id": "student_001", "cohort": "student_2026_09"})
        statement, params = self.connection.executions[-1]
        self.assertIn("INSERT INTO test_users", statement)
        self.assertEqual(params[1:3], ("student_001", "student_2026_09"))

    def test_identify_rejects_personal_or_control_character_identifier(self) -> None:
        for anonymous_id in ("alice@example.com", "student_13800138000", "student_001\n"):
            with self.subTest(anonymous_id=anonymous_id):
                with self.assertRaises(ValueError):
                    self.service.identify(anonymous_id, "student_2026_09")

    def test_record_event_rejects_unknown_event_or_reason(self) -> None:
        with self.assertRaises(ValueError):
            self.service.record_event(
                anonymous_id="student_001",
                event_type="anything",
                session_id=None,
                plan_id=None,
                plan_item_id=None,
                reason_code=None,
                metadata={},
                idempotency_key="event_001",
            )
        with self.assertRaises(ValueError):
            self.service.record_event(
                anonymous_id="student_001",
                event_type="task_skipped",
                session_id=None,
                plan_id=None,
                plan_item_id=None,
                reason_code="because_i_said_so",
                metadata={},
                idempotency_key="event_002",
            )

    def test_record_event_preserves_only_approved_metadata_and_is_idempotent(self) -> None:
        first = self.service.record_event(
            anonymous_id="student_001",
            event_type="task_completed",
            session_id="session_001",
            plan_id="plan_001",
            plan_item_id="item_001",
            reason_code=None,
            metadata={
                "task_category": "study",
                "energy_level": "medium",
                "available_minutes": 30,
                "email": "not-stored@example.com",
            },
            idempotency_key="event_003",
        )
        duplicate = self.service.record_event(
            anonymous_id="student_999",
            event_type="task_skipped",
            session_id=None,
            plan_id=None,
            plan_item_id=None,
            reason_code="low_energy",
            metadata={},
            idempotency_key="event_003",
        )

        self.assertEqual(first, duplicate)
        self.assertEqual(len(self.connection.events), 1)
        self.assertEqual(
            first["metadata"],
            {"task_category": "study", "energy_level": "medium", "available_minutes": 30},
        )
        statement, params = self.connection.executions[-2]
        self.assertNotIn("not-stored@example.com", statement)
        self.assertNotIn("not-stored@example.com", repr(params))
        self.assertIn("ON CONFLICT (idempotency_key)", statement)

    def test_save_feedback_rejects_out_of_range_rating_and_long_comment(self) -> None:
        for rating in (0, 6, True):
            with self.subTest(rating=rating):
                with self.assertRaises(ValueError):
                    self.service.save_feedback(
                        anonymous_id="student_001",
                        session_id="session_001",
                        plan_item_id="item_001",
                        rating=rating,
                        comment=None,
                    )
        with self.assertRaises(ValueError):
            self.service.save_feedback(
                anonymous_id="student_001",
                session_id="session_001",
                plan_item_id="item_001",
                rating=5,
                comment="x" * 501,
            )

    def test_save_feedback_updates_duplicate_plan_item(self) -> None:
        self.service.save_feedback(
            anonymous_id="student_001",
            session_id="session_001",
            plan_item_id="item_001",
            rating=3,
            comment="first",
        )
        updated = self.service.save_feedback(
            anonymous_id="student_001",
            session_id="session_001",
            plan_item_id="item_001",
            rating=5,
            comment="updated",
        )

        self.assertEqual(len(self.connection.feedback), 1)
        self.assertEqual(updated["rating"], 5)
        self.assertEqual(updated["comment"], "updated")
        self.assertIn("ON CONFLICT (plan_item_id)", self.connection.executions[-1][0])

    def test_delete_anonymous_data_removes_only_observability_records(self) -> None:
        self.service.identify("student_001", "student_2026_09")

        deleted = self.service.delete_anonymous_data("student_001")

        self.assertEqual(deleted, 1)
        self.assertNotIn("student_001", self.connection.users)
        self.assertIn("DELETE FROM test_users", self.connection.executions[-1][0])


if __name__ == "__main__":
    unittest.main()
