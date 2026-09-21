"""Pure eligibility-preserving ranking for the low-friction product mode."""

from __future__ import annotations

from typing import Any

from candidate_provider import CandidateTask, RecommendationContext, is_quick_eligible


def _sort_key(
    item: CandidateTask,
    context: RecommendationContext,
    weights: dict[str, Any],
) -> tuple[float, int, int, str]:
    task = item.task
    target_load = {"low": 1, "medium": 2, "high": 3}[context.energy_level]
    energy_fit = (
        task.ease_level
        - abs(task.physical_load - target_load)
        - (task.social_pressure if context.energy_level == "low" else 0)
    )
    score = (
        energy_fit
        + weights.get("group_boosts", {}).get(task.feedback_group, 0.0)
        - weights.get("group_penalties", {}).get(task.feedback_group, 0.0)
        + weights.get("category_boosts", {}).get(task.category, 0.0)
    )
    return (-score, item.startup_cost, task.duration, task.id)


def _payload(item: CandidateTask, context: RecommendationContext) -> dict[str, Any]:
    task = item.task
    reason = (
        "适合现在的低精力状态，可在家独自开始。"
        if context.energy_level == "low"
        else "无需出门或花钱，现在就能开始。"
    )
    return {
        "id": task.id,
        "title": task.title,
        "category": task.category,
        "duration_minutes": task.duration,
        "budget": task.budget,
        "outing": task.outing,
        "company": task.company,
        "first_action": item.first_action,
        "reason": reason,
        "feedback_group": task.feedback_group,
        "ease_level": task.ease_level,
        "physical_load": task.physical_load,
        "social_pressure": task.social_pressure,
    }


def rank_quick(
    context: RecommendationContext,
    candidates: list[CandidateTask],
    history_weights: dict[str, Any] | None = None,
    excluded_task_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = excluded_task_ids or set()
    unique = {
        item.task.id: item
        for item in candidates
        if item.task.id not in excluded and is_quick_eligible(context, item)
    }
    ranked = sorted(
        unique.values(),
        key=lambda item: _sort_key(item, context, history_weights or {}),
    )
    return [_payload(item, context) for item in ranked[:10]]
