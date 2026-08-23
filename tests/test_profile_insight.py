import unittest

from profile_module import Profile, build_profile_insight


class ProfileInsightTests(unittest.TestCase):
    def test_build_profile_insight_explains_top_dimensions_and_constraints(self):
        profile = Profile(
            session_id="sess_profile",
            profile_version=2,
            scores={
                "energy": 0.83,
                "recovery": 0.5,
                "social": 0.17,
                "exploration": 0.67,
                "growth": 0.33,
            },
            constraints={
                "categories": ["活力充电", "乐享探索"],
                "duration": "half",
                "budget": "medium",
                "outing": "nearby",
                "company": "solo",
                "rest_only": False,
            },
            confidence=1.0,
            rule_version="profile-rule-v1",
        )

        insight = build_profile_insight(profile)

        self.assertEqual(insight["session_id"], "sess_profile")
        self.assertEqual(insight["profile_version"], 2)
        self.assertIn("活力充电", insight["summary"])
        self.assertEqual(insight["top_dimensions"][0]["label"], "活力充电")
        self.assertGreaterEqual(len(insight["constraint_cards"]), 4)
        self.assertIn("附近出门", [card["value"] for card in insight["constraint_cards"]])
        self.assertTrue(insight["suggestions"])


if __name__ == "__main__":
    unittest.main()
