from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from psycopg.errors import ForeignKeyViolation

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
            user = self.users.setdefault(
                anonymous_id,
                {
                    "anonymous_id": anonymous_id,
                    "cohort": cohort,
                    "last_seen_at": _now,
                },
            )
            if "cohort = EXCLUDED.cohort" in statement:
                user["cohort"] = cohort
            user["last_seen_at"] = _now
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
            if anonymous_id not in self.users:
                raise ForeignKeyViolation("test_events anonymous_id must reference test_users")
            event = self.events.setdefault(
                (anonymous_id, idempotency_key),
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
            if anonymous_id not in self.users:
                raise ForeignKeyViolation(
                    "task_test_feedback anonymous_id must reference test_users"
                )
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
        elif "UPDATE test_users SET last_seen_at" in statement:
            last_seen_at, anonymous_id = params
            if anonymous_id not in self.users:
                raise ForeignKeyViolation("test_users anonymous_id must exist")
            self.users[anonymous_id]["last_seen_at"] = last_seen_at
        elif "DELETE FROM test_users" in statement:
            if "last_seen_at <" in statement:
                cutoff = params[0]
                anonymous_ids = [
                    anonymous_id
                    for anonymous_id, user in self.users.items()
                    if user["last_seen_at"] < cutoff
                ]
            else:
                anonymous_ids = [params[0]]
            for anonymous_id in anonymous_ids:
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
                    self.rowcount += 1
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

    def test_identify_preserves_first_cohort_for_existing_anonymous_id(self) -> None:
        self.service.identify("student_001", "student_2026_09")

        result = self.service.identify("student_001", "student_2026_10")

        self.assertEqual(result, {"anonymous_id": "student_001", "cohort": "student_2026_09"})
        self.assertEqual(self.connection.users["student_001"]["cohort"], "student_2026_09")
        statement = self.connection.executions[-1][0]
        self.assertNotIn("cohort = EXCLUDED.cohort", statement)

    def test_identify_rejects_personal_or_control_character_identifier(self) -> None:
        for anonymous_id in (
            "alice@example.com",
            "student_alice",
            "student_Alice",
            "student_13800138000",
            "student_138-0013-8000",
            "student_+8613800138000",
            "student_001\n",
        ):
            with self.subTest(anonymous_id=anonymous_id):
                with self.assertRaises(ValueError):
                    self.service.identify(anonymous_id, "student_2026_09")

    def test_identify_rejects_all_control_characters_in_identity_fields(self) -> None:
        controls = ("\x00", "\x07", "\x0b", "\x0c", "\x1b", "\x7f", "\x85", "\x9f")
        for control in controls:
            with self.subTest(control=hex(ord(control))):
                with self.assertRaises(ValueError):
                    self.service.identify(f"student_00{control}1", "student_2026_09")
                with self.assertRaises(ValueError):
                    self.service.identify("student_001", f"student_2026_09{control}")

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
        with self.assertRaises(ValueError):
            self.service.record_event(
                anonymous_id="student_001",
                event_type="task_completed",
                session_id=None,
                plan_id=None,
                plan_item_id=None,
                reason_code="low_energy",
                metadata={},
                idempotency_key="event_003",
            )

    def test_record_event_preserves_only_approved_metadata_and_is_idempotent(self) -> None:
        self.service.identify("student_001", "student_2026_09")

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
                "reason_detail": "先做最容易开始的部分",
                "email": "not-stored@example.com",
            },
            idempotency_key="event_003",
        )
        duplicate = self.service.record_event(
            anonymous_id="student_001",
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
            {
                "task_category": "study",
                "energy_level": "medium",
                "available_minutes": 30,
                "reason_detail": "先做最容易开始的部分",
            },
        )
        event_executions = [
            execution
            for execution in self.connection.executions
            if "INSERT INTO test_events" in execution[0]
        ]
        statement, params = event_executions[0]
        self.assertNotIn("not-stored@example.com", statement)
        self.assertNotIn("not-stored@example.com", repr(params))
        self.assertIn("ON CONFLICT (anonymous_id, idempotency_key)", statement)
        self.assertEqual(
            sum("UPDATE test_users SET last_seen_at" in statement for statement, _ in self.connection.executions),
            2,
        )

    def test_idempotency_key_reuse_is_isolated_between_anonymous_users(self) -> None:
        self.service.identify("student_001", "student_2026_09")
        self.service.identify("student_002", "student_2026_09")

        first = self.service.record_event(
            anonymous_id="student_001",
            event_type="task_completed",
            session_id="session_001",
            plan_id=None,
            plan_item_id=None,
            reason_code=None,
            metadata={},
            idempotency_key="shared-key",
        )
        second = self.service.record_event(
            anonymous_id="student_002",
            event_type="task_completed",
            session_id="session_002",
            plan_id=None,
            plan_item_id=None,
            reason_code=None,
            metadata={},
            idempotency_key="shared-key",
        )

        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["anonymous_id"], "student_001")
        self.assertEqual(second["anonymous_id"], "student_002")
        self.assertEqual(len(self.connection.events), 2)

    def test_all_control_characters_are_rejected_from_free_text(self) -> None:
        self.service.identify("student_001", "student_2026_09")
        controls = ("\x00", "\x07", "\x0b", "\x0c", "\x1b", "\x7f", "\x85", "\x9f")

        for control in controls:
            with self.subTest(control=hex(ord(control))):
                with self.assertRaises(ValueError):
                    self.service.save_feedback(
                        anonymous_id="student_001",
                        session_id="session_001",
                        plan_item_id=f"item_{ord(control)}",
                        rating=5,
                        comment=f"note{control}",
                    )
                with self.assertRaises(ValueError):
                    self.service.record_event(
                        anonymous_id="student_001",
                        event_type="flow_error",
                        session_id=None,
                        plan_id=None,
                        plan_item_id=None,
                        reason_code=None,
                        metadata={"error_code": f"timeout{control}"},
                        idempotency_key=f"event{control}",
                    )
                with self.assertRaises(ValueError):
                    self.service.record_event(
                        anonymous_id="student_001",
                        event_type="task_skipped",
                        session_id=None,
                        plan_id=None,
                        plan_item_id=None,
                        reason_code="other",
                        metadata={"reason_detail": f"detail{control}"},
                        idempotency_key=f"detail_{ord(control)}",
                    )
                with self.assertRaises(ValueError):
                    self.service.record_event(
                        anonymous_id="student_001",
                        event_type="task_skipped",
                        session_id=None,
                        plan_id=None,
                        plan_item_id=None,
                        reason_code=f"other{control}",
                        metadata={},
                        idempotency_key=f"reason_{ord(control)}",
                    )

    def test_record_event_rejects_unidentified_user(self) -> None:
        with self.assertRaises(ForeignKeyViolation):
            self.service.record_event(
                anonymous_id="student_001",
                event_type="task_completed",
                session_id=None,
                plan_id=None,
                plan_item_id=None,
                reason_code=None,
                metadata={},
                idempotency_key="event_004",
            )

        self.assertEqual(self.connection.events, {})

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
        self.service.identify("student_001", "student_2026_09")

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
        self.assertIn("ON CONFLICT (plan_item_id)", self.connection.executions[-2][0])
        self.assertIn("UPDATE test_users SET last_seen_at", self.connection.executions[-1][0])

    def test_save_feedback_rejects_unidentified_user(self) -> None:
        with self.assertRaises(ForeignKeyViolation):
            self.service.save_feedback(
                anonymous_id="student_001",
                session_id="session_001",
                plan_item_id="item_001",
                rating=5,
                comment=None,
            )

        self.assertEqual(self.connection.feedback, {})

    def test_delete_anonymous_data_removes_only_observability_records(self) -> None:
        self.service.identify("student_001", "student_2026_09")

        deleted = self.service.delete_anonymous_data("student_001")

        self.assertEqual(deleted, 1)
        self.assertNotIn("student_001", self.connection.users)
        self.assertIn("DELETE FROM test_users", self.connection.executions[-1][0])

    def test_delete_expired_data_uses_ninety_day_cutoff_and_cascades_observation_rows(self) -> None:
        now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.service.identify("student_001", "student_2026_09")
        self.service.record_event(
            anonymous_id="student_001",
            event_type="session_created",
            session_id="session_001",
            plan_id=None,
            plan_item_id=None,
            reason_code=None,
            metadata={},
            idempotency_key="old-event",
        )
        self.connection.users["student_001"]["last_seen_at"] = now - timedelta(days=91)
        self.service.identify("student_002", "student_2026_09")

        deleted = self.service.delete_expired_data(now=now)

        self.assertEqual(deleted, 1)
        self.assertNotIn("student_001", self.connection.users)
        self.assertNotIn(("student_001", "old-event"), self.connection.events)
        self.assertIn("student_002", self.connection.users)
        statement, params = self.connection.executions[-1]
        self.assertIn("last_seen_at < %s", statement)
        self.assertEqual(params, (now - timedelta(days=90),))


if __name__ == "__main__":
    unittest.main()
