from __future__ import annotations

import unittest

from questionnaire_module import QUESTION_BANK, QuestionnaireService
from task_repository import CATEGORIES


class QuestionnaireSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = QuestionnaireService.__new__(QuestionnaireService)

    def test_question_bank_contains_fifty_approved_questions(self) -> None:
        self.assertEqual(len(QUESTION_BANK), 50)
        self.assertEqual(
            {category: sum(question.category == category for question in QUESTION_BANK) for category in CATEGORIES},
            {category: 10 for category in CATEGORIES},
        )
        self.assertTrue(all(question.status == "approved" for question in QUESTION_BANK))

    def test_quick_questions_change_with_frontloaded_preferences(self) -> None:
        home_recovery = self.service.select_questions(
            "quick",
            {
                "categories": ["松弛疗愈", "自我成长"],
                "outing": "home",
                "company": "solo",
                "duration": "half",
                "budget": "low",
                "rest_only": True,
            },
        )[:5]
        city_social = self.service.select_questions(
            "quick",
            {
                "categories": ["社交连接", "乐享探索"],
                "outing": "city",
                "company": "group",
                "duration": "day",
                "budget": "high",
                "rest_only": False,
            },
        )[:5]

        self.assertEqual(len(home_recovery), 5)
        self.assertEqual(len(city_social), 5)
        self.assertNotEqual(
            [question.id for question in home_recovery],
            [question.id for question in city_social],
        )
        self.assertTrue(
            {"松弛疗愈", "自我成长"}.issubset(
                {question.category for question in home_recovery}
            )
        )
        self.assertTrue(
            {"社交连接", "乐享探索"}.issubset(
                {question.category for question in city_social}
            )
        )

    def test_deep_questions_return_thirty_without_duplicates(self) -> None:
        selected = self.service.select_questions(
            "deep",
            {
                "categories": ["活力充电", "松弛疗愈", "乐享探索"],
                "outing": "nearby",
                "company": "both",
                "duration": "day",
                "budget": "medium",
            },
        )[:30]

        self.assertEqual(len(selected), 30)
        self.assertEqual(len({question.id for question in selected}), 30)
        self.assertTrue(
            {"活力充电", "松弛疗愈", "乐享探索"}.issubset(
                {question.category for question in selected}
            )
        )


if __name__ == "__main__":
    unittest.main()
