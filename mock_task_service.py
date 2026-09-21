"""Validate and persist deterministic mock tasks behind the future AI boundary."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import HTTPException

from mock_task_generation import (
    MockTaskGenerator,
    semantic_signature,
    validate_brief,
    validate_candidates,
)
from recommendation_module import build_load_profile
from task_repository import Task


def payload_to_task(payload: dict[str, Any]) -> Task:
    return Task(
        id=payload["id"],
        title=payload["title"],
        category=payload["category"],
        duration=payload["duration"],
        budget=payload["budget"],
        outing=payload["outing"],
        company=payload["company"],
        owner_session_id=payload["session_id"],
        feedback_group=f"mock:{payload['semantic_signature']}",
        ease_level=payload["ease_level"],
        physical_load=payload["physical_load"],
        social_pressure=payload["social_pressure"],
        location_dependency=payload["location_dependency"],
    )


def _public_payload(candidate: dict[str, Any], session_id: str) -> dict[str, Any]:
    payload = {
        **candidate,
        "id": f"mock_{uuid.uuid4().hex}",
        "session_id": session_id,
        "duration": candidate["duration_minutes"],
        "budget": candidate["estimated_budget"],
        "status": "approved",
        "generation_mode": "mock",
        "reason_text": candidate["recommendation_reason"],
        "reason_tags": ["模拟生成", candidate["category"]],
        "matched_preferences": [candidate["category"]],
        "warning_text": candidate.get("uncertainty_note", ""),
        "match_score": None,
    }
    payload["load_profile"] = build_load_profile(payload_to_task(payload))
    return payload


class MockTaskGenerationService:
    def __init__(self, repository: Any, generator: MockTaskGenerator | None = None) -> None:
        self.repository = repository
        self.generator = generator or MockTaskGenerator()

    @staticmethod
    def _key(context: dict[str, Any]) -> str:
        serialized = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _validated_candidates(
        self,
        context: dict[str, Any],
        count: int,
        excluded_signatures: set[str],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        brief = self.generator.write_brief(context)
        errors = validate_brief(brief, context)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"code": "ai_invalid_output", "reasons": errors},
            )
        raw = self.generator.generate_tasks(context, brief, count, excluded_signatures)
        accepted, rejected = validate_candidates(raw, context, excluded_signatures)
        # One targeted retry, excluding every task already seen, valid or invalid.
        if len(accepted) < count:
            seen = set(excluded_signatures)
            seen.update(
                semantic_signature(item.get("title", ""))
                for item in raw if isinstance(item, dict) and isinstance(item.get("title"), str)
            )
            follow_up = self.generator.generate_tasks(context, brief, count - len(accepted), seen)
            more, more_rejected = validate_candidates(
                follow_up,
                context,
                seen,
            )
            accepted.extend(more)
            rejected.extend(more_rejected)
        return brief, accepted[:count], rejected

    @staticmethod
    def _recommendation(tasks: list[dict[str, Any]], rejected: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        covered = {task["category"] for task in tasks}
        return {
            "tasks": tasks,
            "task_ids": [task["id"] for task in tasks],
            "covered_categories": sorted(covered),
            "missing_categories": sorted(set(context["selected_categories"]) - covered),
            "reasons": [
                {"task_id": task["id"], "text": task["reason_text"], "evidence_refs": task["evidence_refs"]}
                for task in tasks
            ],
            "recommendation_memory": {
                "excluded_group_count": 0,
                "excluded_task_count": len(context["excluded_signatures"]),
                "adjustment_excluded_task_count": 0,
            },
            "candidate_count": len(tasks) + len(rejected),
            "recommended_task_count": len(tasks),
            "rejected_count": len(rejected),
            "rejection_reasons": [item["reasons"] for item in rejected],
            "constraints": context["hard_constraints"],
            "generation_mode": "mock",
        }

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]:
        session_id = context["session_id"]
        key = self._key(context)
        existing = self.repository.get_run(session_id, key)
        if existing is not None:
            return self._recommendation(existing["tasks"], existing["rejected"], context)
        previous_signatures = {
            task["semantic_signature"] for task in self.repository.list_tasks(session_id)
        }
        effective_context = {
            **context,
            "excluded_signatures": sorted(
                set(context["excluded_signatures"]) | previous_signatures
            ),
        }
        brief, accepted, rejected = self._validated_candidates(effective_context, 10, set())
        if not accepted:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "insufficient_valid_tasks",
                    "message": "当前限制下没有合格的模拟任务，请调整条件后重试",
                    "rejection_reasons": [item["reasons"] for item in rejected],
                },
            )
        tasks = [_public_payload(task, session_id) for task in accepted]
        saved = self.repository.save_run(session_id, key, effective_context, brief, tasks, rejected)
        return self._recommendation(saved["tasks"], saved["rejected"], effective_context)

    def generate_one(
        self,
        context: dict[str, Any],
        category: str,
        excluded_ids: set[str],
        current: dict[str, Any] | None = None,
        adjustment: str | None = None,
    ) -> dict[str, Any]:
        scoped = {**context, "selected_categories": [category]}
        previous = self.repository.list_tasks(context["session_id"])
        excluded = {task["semantic_signature"] for task in previous}
        excluded.update(
            task["semantic_signature"] for task in previous if task["id"] in excluded_ids
        )
        brief, accepted, _ = self._validated_candidates(scoped, 20, excluded)
        for candidate in accepted:
            if current is not None and adjustment is not None and not self._improves(candidate, current, adjustment):
                continue
            task = _public_payload(candidate, context["session_id"])
            self.repository.save_task(context["session_id"], task)
            return task
        raise HTTPException(
            status_code=409,
            detail={
                "code": "insufficient_valid_tasks",
                "message": "当前条件下没有新的合格任务；可以调整限制后重试",
            },
        )

    @staticmethod
    def _improves(candidate: dict[str, Any], current: dict[str, Any], adjustment: str) -> bool:
        if adjustment == "easier":
            return (
                candidate["ease_level"] > current["ease_level"]
                or candidate["physical_load"] < current["physical_load"]
                or candidate["duration_minutes"] < current["duration_minutes"]
            )
        if adjustment == "shorter":
            return candidate["duration_minutes"] < current["duration_minutes"]
        if adjustment == "cheaper":
            return candidate["estimated_budget"] < current["estimated_budget"]
        if adjustment == "nearer":
            rank = {"home": 0, "nearby": 1, "city": 2}
            return rank[candidate["outing"]] < rank[current["outing"]]
        if adjustment == "less_social":
            return candidate["social_pressure"] < current["social_pressure"]
        if adjustment == "more_growth":
            return candidate["category"] == "自我成长" and current["category"] != "自我成长"
        return False
