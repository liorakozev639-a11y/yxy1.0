"""Offline, reproducible evaluation of the rule-based recommendation paths."""

from __future__ import annotations

from collections import Counter
import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any

from candidate_provider import (
    CandidateTask, RecommendationContext, TaskBankProvider,
    is_full_eligible, is_quick_eligible,
)
from quick_recommendation import rank_quick
from recommendation_module import recommend_tasks
from task_repository import CATEGORIES, SCENARIOS, TaskRepository


DEFAULT_CASES = Path(__file__).resolve().parent / "data" / "recommendation_evaluation_cases.json"
_COMMON_FIELDS = {"id", "mode", "available_minutes", "energy_level", "expect_empty", "repeat_rounds"}
_FULL_FIELDS = {
    "budget_limit", "outing", "company", "categories", "scenarios", "weather", "day_part", "mood"
}


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _validate_case(case: object) -> None:
    if not isinstance(case, dict):
        raise ValueError("case must be a JSON object")
    case_id = case.get("id", "<missing id>")
    try:
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("id must be nonempty")
        mode = case.get("mode")
        if mode not in {"full", "quick"}:
            raise ValueError("mode must be full or quick")
        allowed = _COMMON_FIELDS | (_FULL_FIELDS if mode == "full" else set())
        unknown = set(case) - allowed
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        if not _positive_int(case.get("available_minutes")):
            raise ValueError("available_minutes must be a positive integer")
        if case.get("energy_level") not in {"low", "medium", "high"}:
            raise ValueError("energy_level must be low, medium or high")
        if "expect_empty" in case and type(case["expect_empty"]) is not bool:
            raise ValueError("expect_empty must be boolean")
        if "repeat_rounds" in case and (
            not _positive_int(case["repeat_rounds"]) or case["repeat_rounds"] > 3
        ):
            raise ValueError("repeat_rounds must be an integer from 1 to 3")
        if mode == "full":
            if type(case.get("budget_limit")) is not int or case["budget_limit"] < 0:
                raise ValueError("budget_limit must be a nonnegative integer")
            if case.get("outing") not in {"home", "nearby", "city", "any"}:
                raise ValueError("outing is invalid")
            if case.get("company") not in {"solo", "group", "both"}:
                raise ValueError("company is invalid")
            categories = case.get("categories")
            if not isinstance(categories, list) or not categories or (
                any(category not in CATEGORIES for category in categories)
                or len(set(categories)) != len(categories)
            ):
                raise ValueError("categories must be a nonempty, unique list of supported values")
            scenarios = case.get("scenarios", [])
            if not isinstance(scenarios, list) or any(scene not in SCENARIOS for scene in scenarios):
                raise ValueError("scenarios contains an unsupported value")
            for key, options in (
                ("weather", {"clear", "rainy", "hot", "cold", "indoor"}),
                ("day_part", {"morning", "afternoon", "evening", "late"}),
                ("mood", {"empty", "anxious", "bored", "recharge"}),
            ):
                if key in case and case[key] not in options:
                    raise ValueError(f"{key} is invalid")
    except (TypeError, KeyError) as error:
        raise ValueError(f"{case_id}: malformed case") from error
    except ValueError as error:
        raise ValueError(f"{case_id}: {error}") from error


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("case file must contain a JSON list")
    for case in cases:
        _validate_case(case)
    ids = [case["id"] for case in cases]
    duplicate = next((case_id for case_id, count in Counter(ids).items() if count > 1), None)
    if duplicate:
        raise ValueError(f"{duplicate}: duplicate case id")
    modes = Counter(case["mode"] for case in cases)
    if modes != {"full": 30, "quick": 20}:
        raise ValueError(f"expected 30 full and 20 quick cases, got {dict(modes)}")
    return cases


def check_constraints(
    case: dict[str, Any], task: dict[str, Any], candidate: CandidateTask | None = None,
) -> list[str]:
    """Check returned fields independently of the provider's eligibility filter."""
    issues: list[str] = []
    duration = task.get("duration", task.get("duration_minutes"))
    if not isinstance(duration, int) or not 0 < duration <= case["available_minutes"]:
        issues.append("duration exceeds available time or is invalid")
    budget = task.get("budget")
    budget_limit = case.get("budget_limit", 0)
    if not isinstance(budget, int) or not 0 <= budget <= budget_limit:
        issues.append("budget exceeds limit or is invalid")
    allowed_outings = {
        "home": {"home"}, "nearby": {"home", "nearby"},
        "city": {"home", "nearby", "city"},
        "any": {"home", "nearby", "city"},
    }
    if task.get("outing") not in allowed_outings[case.get("outing", "home")]:
        issues.append("outing does not match")
    company = case.get("company", "solo")
    if company != "both" and task.get("company") not in {company, "both"}:
        issues.append("company does not match")
    if candidate is not None and candidate.task.status != "approved":
        issues.append("candidate is not approved")
    if case["mode"] == "full":
        if task.get("status") != "approved":
            issues.append("task is not approved")
        if task.get("category") not in case["categories"]:
            issues.append("category does not match")
        if case.get("scenarios") and not set(task.get("scenarios", [])).intersection(case["scenarios"]):
            issues.append("scenario does not match")
    else:
        if not task.get("first_action", "").strip():
            issues.append("first_action is missing")
        if candidate is not None and not candidate.immediate_start:
            issues.append("not immediately startable")
        if candidate is not None and candidate.startup_cost < 0:
            issues.append("startup_cost is invalid")
    return issues


def check_reasons(case: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    reason = task.get("reason_text") if case["mode"] == "full" else task.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return {"passed": 0, "total": 1, "issues": ["missing reason"]}
    checks: list[tuple[bool, str]] = []
    if case["mode"] == "full":
        checks.append((f"「{task.get('category')}」" in reason, "category claim mismatch"))
        duration_claim = re.search(r"当前时间段约\s*(\d+)\s*分钟", reason)
        checks.append((duration_claim is not None and int(duration_claim[1]) == task.get("duration"),
                       "duration claim mismatch"))
        budget_claim = re.search(r"预计预算约为\s*(\d+)\s*元", reason)
        checks.append((budget_claim is not None and int(budget_claim[1]) == task.get("budget"),
                       "budget claim mismatch"))
        tag_checks = {
            "居家可做": task.get("outing") == "home",
            "低预算": isinstance(task.get("budget"), int) and task["budget"] <= 20,
            "短时间可完成": isinstance(task.get("duration"), int) and task["duration"] <= 30,
            "适合独处": task.get("company") == "solo",
            "适合结伴": task.get("company") == "group",
            "低精力友好": task.get("ease_level", 0) >= 4 and task.get("physical_load", 9) <= 2
                             and case.get("energy_level") == "low",
        }
        for tag in task.get("reason_tags", []):
            if tag in tag_checks:
                checks.append((tag_checks[tag], f"reason tag mismatch: {tag}"))
        for claim, field, expected in (
            ("无需外出完成", "outing", "home"),
            ("适合独处完成", "company", "solo"),
            ("更适合结伴完成", "company", "group"),
        ):
            if claim in reason:
                checks.append((task.get(field) == expected, f"{field} claim mismatch"))
    else:
        if "低精力" in reason:
            checks.append((case.get("energy_level") == "low", "energy claim mismatch"))
        if "无需出门" in reason or "可在家" in reason:
            checks.append((task.get("outing") == "home", "outing claim mismatch"))
        if "无需" in reason and "花钱" in reason:
            checks.append((task.get("budget") == 0, "budget claim mismatch"))
        if "独自开始" in reason:
            checks.append((task.get("company") in {"solo", "both"}, "company claim mismatch"))
    if not checks:
        return {"passed": 0, "total": 1, "issues": ["no checkable reason claim"]}
    issues = [message for passed, message in checks if not passed]
    return {"passed": len(checks) - len(issues), "total": len(checks), "issues": issues}


def evaluate_case(case: dict[str, Any], provider: TaskBankProvider) -> dict[str, Any]:
    context = RecommendationContext(
        mode=case["mode"], session_id=f"evaluation_{case['id']}", user_id=None,
        available_minutes=case["available_minutes"], energy_level=case["energy_level"],
        categories=tuple(case.get("categories", [])), budget_limit=case.get("budget_limit", 0),
        outing=case.get("outing", "home"), company=case.get("company", "solo"),
        scenarios=tuple(case.get("scenarios", [])),
    )
    eligible = is_full_eligible if case["mode"] == "full" else is_quick_eligible
    candidates = [item for item in provider.generate(context) if eligible(context, item)]
    by_id = {item.task.id: item for item in candidates}
    excluded: set[str] = set()
    rounds: list[list[str]] = []
    displayed: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    constraint_passed = constraint_total = repetition_violations = repetition_total = 0
    reason_passed = reason_total = 0
    issues: list[str] = []
    for round_number in range(case.get("repeat_rounds", 1)):
        if case["mode"] == "full":
            constraints = {
                "budget_limit": context.budget_limit, "max_duration": context.available_minutes,
                "outing": context.outing, "company": context.company,
                "energy_level": context.energy_level, "scenarios": list(context.scenarios),
                **{key: case[key] for key in ("weather", "day_part", "mood") if key in case},
            }
            profile = {"scores": {category: 0.8 for category in context.categories},
                       "constraints": constraints}
            tasks = recommend_tasks(
                profile, list(context.categories), [item.task for item in candidates],
                excluded_task_ids=excluded,
            )["tasks"]
        else:
            tasks = rank_quick(context, candidates, excluded_task_ids=excluded)
        ids = [task["id"] for task in tasks]
        rounds.append(ids)
        if round_number == 0:
            review_candidates = [
                {"id": task["id"], "title": task["title"], "category": task["category"],
                 "reason": task.get("reason_text", task.get("reason", ""))}
                for task in tasks
            ]
        if round_number == 0 and not tasks:
            constraint_total += 1
            if case.get("expect_empty", False):
                constraint_passed += 1
            else:
                issues.append("unexpected empty recommendation")
        if round_number == 0 and tasks and case.get("expect_empty", False):
            issues.append("expected empty recommendation")
        current_ids: set[str] = set()
        for task in tasks:
            task_id = task["id"]
            displayed.append(task)
            constraint_total += 1
            task_issues = check_constraints(case, task, by_id.get(task_id))
            if round_number == 0 and case.get("expect_empty", False):
                task_issues.append("expected empty recommendation")
            if task_issues:
                issues.extend(f"round {round_number + 1} {task_id}: {issue}" for issue in task_issues)
            else:
                constraint_passed += 1
            repetition_total += 1
            if task_id in current_ids or task_id in excluded:
                repetition_violations += 1
                issues.append(f"round {round_number + 1} {task_id}: repeated task")
            current_ids.add(task_id)
            reason_check = check_reasons(case, task)
            reason_passed += reason_check["passed"]
            reason_total += reason_check["total"]
            issues.extend(f"round {round_number + 1} {task_id}: {issue}"
                          for issue in reason_check["issues"])
        if ids:
            excluded.add(ids[0])
    return {
        "id": case["id"], "mode": case["mode"], "candidate_count": len(candidates),
        "round_task_ids": rounds, "first_task": displayed[0] if displayed else None,
        "review_candidates": review_candidates,
        "constraints": {"passed": constraint_passed, "total": constraint_total},
        "repetition": {"violations": repetition_violations, "total": repetition_total},
        "reasons": {"passed": reason_passed, "total": reason_total}, "issues": issues,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
        constraints = {key: sum(row["constraints"][key] for row in rows) for key in ("passed", "total")}
        repetition = {key: sum(row["repetition"][key] for row in rows) for key in ("violations", "total")}
        reasons = {key: sum(row["reasons"][key] for row in rows) for key in ("passed", "total")}
        return {
            "case_count": len(rows), "failed_case_count": sum(bool(row["issues"]) for row in rows),
            "empty_case_count": sum(not row["round_task_ids"][0] for row in rows
                                    if row.get("round_task_ids")),
            "constraints": constraints, "repetition": repetition, "reasons": reasons,
            "constraint_rate": constraints["passed"] / constraints["total"] if constraints["total"] else None,
            "repetition_rate": repetition["violations"] / repetition["total"] if repetition["total"] else None,
            "reason_consistency_rate": reasons["passed"] / reasons["total"] if reasons["total"] else None,
        }
    return {
        "overall": metric(results),
        "by_mode": {mode: metric([row for row in results if row["mode"] == mode])
                    for mode in ("full", "quick")},
    }


def build_manual_review(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    review: list[dict[str, str]] = []
    used_task_ids: set[str] = set()
    covered_categories: set[str] = set()
    for mode, count in (("full", 6), ("quick", 4)):
        eligible = [row for row in results if row["mode"] == mode and row.get("first_task")]
        if len(eligible) < count:
            raise ValueError(f"manual review shortage: {mode} has {len(eligible)} of {count} needed")
        positions = [round(index * (len(eligible) - 1) / (count - 1)) for index in range(count)]
        for position in positions:
            row = eligible[position]
            choices = [task for task in row.get("review_candidates", [])
                       if task["id"] not in used_task_ids and task.get("reason")]
            if not choices:
                raise ValueError(f"manual review shortage: no unique task for {row['id']}")
            task = next((task for task in choices
                         if task["category"] not in covered_categories), choices[0])
            used_task_ids.add(task["id"])
            covered_categories.add(task["category"])
            review.append({
                "case_id": row["id"], "mode": mode, "task_id": task["id"],
                "title": task["title"], "category": task["category"],
                "reason": task["reason"],
                "manual_rating": "", "notes": "",
            })
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the offline task-bank recommenders")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.cases)
    provider = TaskBankProvider(TaskRepository())
    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            results.append(evaluate_case(case, provider))
        except Exception as error:
            results.append({
                "id": case["id"], "mode": case["mode"], "round_task_ids": [[]],
                "first_task": None, "constraints": {"passed": 0, "total": 1},
                "repetition": {"violations": 0, "total": 0},
                "reasons": {"passed": 0, "total": 0},
                "issues": [f"evaluation error: {type(error).__name__}: {error}"],
            })
    report: dict[str, Any] = {
        "fixture": str(args.cases), "summary": summarize(results), "results": results,
        "manual_review_status": "pending",
    }
    try:
        review = build_manual_review(results)
    except ValueError as error:
        review = []
        report["manual_review_status"] = str(error)
    report["results"] = [
        {key: value for key, value in result.items()
         if key not in {"first_task", "review_candidates"}}
        for result in results
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if review:
        args.review.parent.mkdir(parents=True, exist_ok=True)
        with args.review.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(review[0]))
            writer.writeheader()
            writer.writerows(review)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["manual_review_status"] != "pending":
        print(report["manual_review_status"])
    return 1 if report["summary"]["overall"]["failed_case_count"] or not review else 0


if __name__ == "__main__":
    raise SystemExit(main())
