from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO


CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "recommendation_evaluation_cases.json"


class RecommendationEvaluationFixtureTests(unittest.TestCase):
    def test_fixture_has_fifty_distinct_cases_in_both_modes(self) -> None:
        self.assertTrue(CASES_PATH.is_file())
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case["id"] for case in cases}), 50)
        self.assertEqual(sum(case["mode"] == "full" for case in cases), 30)
        self.assertEqual(sum(case["mode"] == "quick" for case in cases), 20)

    def test_loader_accepts_the_fixed_fixture(self) -> None:
        from recommendation_evaluation import load_cases

        cases = load_cases(CASES_PATH)
        self.assertEqual(len(cases), 50)
        self.assertEqual(cases[0]["id"], "full-01-low-energy-home-15m")

    def test_loader_names_a_duplicate_case(self) -> None:
        from recommendation_evaluation import load_cases

        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        cases[-1]["id"] = cases[0]["id"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "full-01-low-energy-home-15m"):
                load_cases(path)

    def test_loader_names_invalid_case_field(self) -> None:
        from recommendation_evaluation import load_cases

        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        cases[0]["energy_level"] = "unknown"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "full-01-low-energy-home-15m"):
                load_cases(path)


class RecommendationEvaluationScoringTests(unittest.TestCase):
    def test_full_and_quick_paths_use_real_offline_recommenders(self) -> None:
        from candidate_provider import TaskBankProvider
        from recommendation_evaluation import evaluate_case, load_cases
        from task_repository import TaskRepository

        cases = {case["id"]: case for case in load_cases(CASES_PATH)}
        provider = TaskBankProvider(TaskRepository())
        for case_id in ("full-01-low-energy-home-15m", "quick-06-low-15m"):
            result = evaluate_case(cases[case_id], provider)
            self.assertTrue(result["round_task_ids"][0], case_id)
            self.assertEqual(result["constraints"]["passed"], result["constraints"]["total"])

    def test_expected_empty_passes_and_unexpected_empty_fails(self) -> None:
        from candidate_provider import TaskBankProvider
        from recommendation_evaluation import evaluate_case, load_cases
        from task_repository import TaskRepository

        cases = {case["id"]: case for case in load_cases(CASES_PATH)}
        provider = TaskBankProvider(TaskRepository())
        expected = evaluate_case(cases["quick-01-empty-1m"], provider)
        self.assertEqual(expected["constraints"], {"passed": 1, "total": 1})
        unexpected_case = {**cases["quick-01-empty-1m"], "expect_empty": False}
        unexpected = evaluate_case(unexpected_case, provider)
        self.assertEqual(unexpected["constraints"], {"passed": 0, "total": 1})
        self.assertIn("unexpected empty", " ".join(unexpected["issues"]))

    def test_constraint_checker_detects_budget_duration_and_outing(self) -> None:
        from recommendation_evaluation import check_constraints

        case = {
            "mode": "full", "available_minutes": 15, "budget_limit": 0,
            "outing": "home", "company": "solo", "categories": ["松弛疗愈"],
        }
        task = {
            "id": "bad", "category": "松弛疗愈", "duration": 30,
            "budget": 20, "outing": "city", "company": "solo", "status": "approved",
        }
        issues = check_constraints(case, task)
        self.assertTrue(any("budget" in issue for issue in issues))
        self.assertTrue(any("duration" in issue for issue in issues))
        self.assertTrue(any("outing" in issue for issue in issues))

    def test_reason_checker_detects_missing_and_false_numeric_claims(self) -> None:
        from recommendation_evaluation import check_reasons

        case = {"mode": "full", "categories": ["松弛疗愈"], "energy_level": "low"}
        task = {
            "id": "bad", "category": "松弛疗愈", "duration": 10,
            "budget": 0, "outing": "home", "company": "solo",
            "reason_text": "你选择了「松弛疗愈」。当前时间段约 30 分钟。预计预算约为 20 元。",
            "reason_tags": [],
        }
        scored = check_reasons(case, task)
        self.assertGreaterEqual(scored["total"], 3)
        self.assertTrue(any("duration" in issue for issue in scored["issues"]))
        self.assertTrue(any("budget" in issue for issue in scored["issues"]))
        task["reason_text"] = ""
        missing = check_reasons(case, task)
        self.assertEqual(missing, {"passed": 0, "total": 1, "issues": ["missing reason"]})

    def test_quick_reason_only_scores_claims_actually_present(self) -> None:
        from recommendation_evaluation import check_reasons

        case = {"mode": "quick", "energy_level": "medium"}
        task = {"id": "example", "outing": "home", "budget": 0, "company": "solo",
                "reason": "无需出门或花钱，现在就能开始。"}
        self.assertEqual(check_reasons(case, task)["total"], 2)
        task["reason"] = "推荐给你。"
        self.assertEqual(check_reasons(case, task), {
            "passed": 0, "total": 1, "issues": ["no checkable reason claim"]
        })

    def test_replacement_rounds_do_not_reuse_a_previous_task(self) -> None:
        from candidate_provider import TaskBankProvider
        from recommendation_evaluation import evaluate_case, load_cases
        from task_repository import TaskRepository

        cases = {case["id"]: case for case in load_cases(CASES_PATH)}
        provider = TaskBankProvider(TaskRepository())
        for case_id in ("full-21-repeat-home-recovery", "quick-18-repeat-low-20m"):
            result = evaluate_case(cases[case_id], provider)
            first_ids = [round_ids[0] for round_ids in result["round_task_ids"] if round_ids]
            self.assertEqual(len(first_ids), len(set(first_ids)), case_id)
            self.assertEqual(result["repetition"]["violations"], 0, case_id)

    def test_summary_preserves_denominators_and_null_for_unchecked(self) -> None:
        from recommendation_evaluation import summarize

        result = summarize([{
            "id": "sample", "mode": "quick", "constraints": {"passed": 1, "total": 2},
            "repetition": {"violations": 1, "total": 2},
            "reasons": {"passed": 0, "total": 0}, "issues": ["bad"],
        }])
        self.assertEqual(result["overall"]["constraint_rate"], 0.5)
        self.assertEqual(result["overall"]["repetition_rate"], 0.5)
        self.assertIsNone(result["overall"]["reason_consistency_rate"])
        self.assertEqual(result["by_mode"]["quick"]["case_count"], 1)

    def test_manual_review_has_ten_unlabeled_stratified_examples(self) -> None:
        from candidate_provider import TaskBankProvider
        from recommendation_evaluation import build_manual_review, evaluate_case, load_cases
        from task_repository import TaskRepository

        provider = TaskBankProvider(TaskRepository())
        results = [evaluate_case(case, provider) for case in load_cases(CASES_PATH)]
        review = build_manual_review(results)
        self.assertEqual(len(review), 10)
        self.assertEqual(sum(row["mode"] == "full" for row in review), 6)
        self.assertEqual(sum(row["mode"] == "quick" for row in review), 4)
        self.assertEqual(len({row["task_id"] for row in review}), 10)
        self.assertEqual(len({row["case_id"] for row in review}), 10)
        self.assertTrue(all(row["reason"] and row["task_id"] for row in review))
        self.assertTrue(all(row["manual_rating"] == "" for row in review))

    def test_manual_review_reports_shortage(self) -> None:
        from recommendation_evaluation import build_manual_review

        with self.assertRaisesRegex(ValueError, "manual review shortage"):
            build_manual_review([])

    def test_cli_writes_failed_case_and_returns_nonzero(self) -> None:
        from recommendation_evaluation import main

        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        cases[0]["expect_empty"] = True
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "cases.json"
            output = root / "report.json"
            review = root / "review.csv"
            fixture.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
            with patch("sys.argv", ["recommendation_evaluation", "--cases", str(fixture),
                                    "--output", str(output), "--review", str(review)]), \
                 redirect_stdout(StringIO()):
                exit_code = main()
            self.assertEqual(exit_code, 1)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["overall"]["failed_case_count"], 1)
            self.assertIn("expected empty", " ".join(report["results"][0]["issues"]))


if __name__ == "__main__":
    unittest.main()
