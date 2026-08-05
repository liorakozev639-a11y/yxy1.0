from __future__ import annotations

import os
import unittest
from datetime import timedelta

from fastapi import HTTPException

from session_module import (
    PostgresSessionRepository,
    SessionService,
    SessionStage,
    utc_now,
)


class SessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.repository = PostgresSessionRepository(database_url)
        self.service = SessionService(self.repository)

    def create_session(self) -> dict[str, object]:
        created = self.service.create()
        self.addCleanup(self.repository.delete, str(created["session_id"]))
        return created

    def test_create_returns_no_token_and_restore_uses_session_id(self) -> None:
        created = self.create_session()

        self.assertEqual(
            set(created),
            {"session_id", "stage", "version", "expires_at"},
        )
        restored = self.service.restore(created["session_id"])
        self.assertEqual(restored["session_id"], created["session_id"])

    def test_preferences_are_persisted_and_versioned(self) -> None:
        created = self.create_session()

        saved = self.service.save_preferences(
            created["session_id"],
            {"categories": ["energy"], "outing": "home"},
        )
        restored = self.service.restore(created["session_id"])

        self.assertEqual(saved.stage, SessionStage.QUESTIONNAIRE)
        self.assertEqual(restored["version"], 2)
        self.assertEqual(restored["preferences"]["categories"], ["energy"])

    def test_expired_session_is_rejected(self) -> None:
        created = self.create_session()
        session = self.repository.get(created["session_id"])
        assert session is not None
        session.expires_at = utc_now() - timedelta(seconds=1)
        self.repository.save(session)

        with self.assertRaises(HTTPException) as context:
            self.service.restore(created["session_id"])

        self.assertEqual(context.exception.status_code, 410)

    def test_clear_data_resets_session(self) -> None:
        created = self.create_session()
        session_id = created["session_id"]
        self.service.save_preferences(session_id, {"categories": ["growth"]})

        self.service.clear_data(session_id)
        restored = self.service.restore(session_id)

        self.assertEqual(restored["stage"], SessionStage.INTERESTS)
        self.assertEqual(restored["preferences"], {})
        self.assertEqual(restored["version"], 3)

class PostgresSessionRepositoryTests(unittest.TestCase):
    def test_preferences_survive_repository_reload(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        first = SessionService(PostgresSessionRepository(database_url))
        created = first.create()
        session_id = created["session_id"]
        self.addCleanup(first.repository.delete, session_id)

        first.save_preferences(session_id, {"categories": ["energy"]})
        second = SessionService(PostgresSessionRepository(database_url))

        self.assertEqual(
            second.restore(session_id)["preferences"]["categories"],
            ["energy"],
        )


if __name__ == "__main__":
    unittest.main()
