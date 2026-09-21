"""Coordinate quick-mode candidates, shared learning, and saved choices."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException

from candidate_provider import CandidateProvider, RecommendationContext
from quick_recommendation import rank_quick
from quick_recommendation_store import QuickRecommendationStore
from session_module import SessionService
from user_history_service import UserHistoryService


EnergyLevel = Literal["low", "medium", "high"]


class QuickRecommendationService:
    def __init__(
        self,
        sessions: SessionService,
        provider: CandidateProvider,
        store: QuickRecommendationStore,
        history: UserHistoryService,
    ) -> None:
        self.sessions = sessions
        self.provider = provider
        self.store = store
        self.history = history

    @staticmethod
    def _result(
        run_id: str | None,
        tasks: list[dict[str, Any]],
        feedback: list[dict[str, Any]],
    ) -> dict[str, Any]:
        disliked = {
            item["task_id"] for item in feedback
            if item["action"] == "disliked"
        }
        visible = [task for task in tasks if task["id"] not in disliked]
        return {
            "run_id": run_id,
            "primary_task": visible[0] if visible else None,
            "alternatives": visible[1:],
            "constraints": (
                {"budget_limit": 0, "outing": "home", "company": "solo"}
                if run_id is not None else None
            ),
            "feedback": feedback,
        }

    def generate(
        self,
        session_id: str,
        user_id: str,
        available_minutes: int,
        energy_level: EnergyLevel,
    ) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        self.history.ensure_user(user_id)
        context = RecommendationContext(
            mode="quick",
            session_id=session_id,
            user_id=user_id,
            available_minutes=available_minutes,
            energy_level=energy_level,
        )
        tasks = rank_quick(
            context,
            self.provider.generate(context),
            history_weights=self.history.preference_weights(user_id),
            excluded_task_ids=self.history.excluded_task_ids(user_id),
        )
        run_id = self.store.save_run(
            session_id, user_id, available_minutes, energy_level, tasks,
        )
        return self._result(run_id, tasks, [])

    def latest(self, session_id: str) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        run = self.store.latest_run(session_id)
        if run is None:
            return self._result(None, [], [])
        return self._result(run["run_id"], run["tasks"], run["feedback"])

    def feedback(
        self,
        session_id: str,
        run_id: str,
        action: Literal["liked", "disliked", "rest_selected"],
        task_id: str | None,
    ) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        try:
            return self.store.save_feedback(session_id, run_id, action, task_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
