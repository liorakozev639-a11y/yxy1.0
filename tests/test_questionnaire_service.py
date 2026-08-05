from __future__ import annotations

import os
import unittest

from fastapi import HTTPException

from questionnaire_module import (
    PostgresQuestionnaireRepository,
    QuestionnaireService,
)
from session_module import PostgresSessionRepository, SessionService


class QuestionnaireServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            self.fail("运行测试前必须设置 SESSION_DATABASE_URL")
        self.database_url = database_url
        self.session_repository = PostgresSessionRepository(database_url)
        self.session_service = SessionService(self.session_repository)
        self.repository = PostgresQuestionnaireRepository(database_url)
        self.service = QuestionnaireService(self.session_service, self.repository)

    def create_session(self, preferences: dict[str, object] | None = None) -> str:
        created = self.session_service.create()
        session_id = str(created["session_id"])
        self.addCleanup(self.session_repository.delete, session_id)
        self.session_service.save_preferences(
            session_id,
            preferences
            or {
                "categories": ["energy", "recovery"],
                "outing": "home",
                "company": "solo",
            },
        )
        return session_id

    def test_quick_and_deep_counts(self) -> None:
        quick_session_id = self.create_session()
        deep_session_id = self.create_session()

        quick = self.service.start(quick_session_id, "quick")
        deep = self.service.start(deep_session_id, "deep")

        self.assertEqual(quick["total"], 5)
        self.assertEqual(deep["total"], 30)

    def test_start_restores_same_questionnaire_and_rejects_mode_change(self) -> None:
        session_id = self.create_session()
        first = self.service.start(session_id, "quick")

        restored = self.service.start(session_id, "quick")

        self.assertEqual(restored["questions"], first["questions"])
        with self.assertRaises(HTTPException) as context:
            self.service.start(session_id, "deep")
        self.assertEqual(context.exception.status_code, 409)

    def test_answer_update_skip_and_progress_survive_repository_reload(self) -> None:
        session_id = self.create_session()
        started = self.service.start(session_id, "quick")
        first_id = started["questions"][0]["id"]
        second_id = started["questions"][1]["id"]

        self.service.save_answer(session_id, first_id, 2)
        self.service.save_answer(session_id, first_id, 4)
        self.service.skip_question(session_id, second_id)
        restored_service = QuestionnaireService(
            SessionService(PostgresSessionRepository(self.database_url)),
            PostgresQuestionnaireRepository(self.database_url),
        )
        progress = restored_service.progress(session_id)

        self.assertEqual(progress["answered_count"], 1)
        self.assertEqual(progress["skipped_count"], 1)
        self.assertEqual(progress["unanswered_count"], 3)
        self.assertEqual(progress["answers"][first_id]["value"], 4)

    def test_submit_requires_every_question_and_locks_answers(self) -> None:
        session_id = self.create_session()
        started = self.service.start(session_id, "quick")

        with self.assertRaises(HTTPException) as context:
            self.service.submit(session_id)
        self.assertEqual(context.exception.status_code, 409)

        for index, question in enumerate(started["questions"]):
            if index == len(started["questions"]) - 1:
                self.service.skip_question(session_id, question["id"])
            else:
                self.service.save_answer(session_id, question["id"], 3)

        result = self.service.submit(session_id)

        self.assertEqual(result["answered_count"], 4)
        self.assertEqual(result["skipped_count"], 1)
        self.assertNotIn("profile_input", result)
        with self.assertRaises(HTTPException) as locked:
            self.service.save_answer(
                session_id,
                started["questions"][0]["id"],
                4,
            )
        self.assertEqual(locked.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
