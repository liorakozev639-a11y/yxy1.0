"""Candidate source shared by rule-based recommendations and future adapters."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Literal, Protocol

from quick_task_catalog import quick_metadata
from task_repository import Task, TaskRepository


@dataclass(frozen=True)
class RecommendationContext:
    mode: Literal["quick", "full"]
    session_id: str
    user_id: str | None
    available_minutes: int
    energy_level: Literal["low", "medium", "high"]
    categories: tuple[str, ...] = ()
    budget_limit: int = 0
    outing: str = "home"
    company: str = "solo"
    scenarios: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateTask:
    task: Task
    first_action: str
    source: str
    immediate_start: bool = False
    startup_cost: int = 0


class CandidateProvider(Protocol):
    def generate(self, context: RecommendationContext) -> list[CandidateTask]: ...


def is_quick_eligible(context: RecommendationContext, item: CandidateTask) -> bool:
    task = item.task
    return (
        context.mode == "quick"
        and task.status == "approved"
        and 0 < task.duration <= context.available_minutes
        and task.budget == 0
        and task.outing == "home"
        and task.company in {"solo", "both"}
        and item.immediate_start
        and bool(item.first_action.strip())
        and item.startup_cost >= 0
    )


class TaskBankProvider:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def generate(self, context: RecommendationContext) -> list[CandidateTask]:
        tasks = self.repository.search_tasks(
            session_id=context.session_id,
            budget_limit=context.budget_limit,
            max_duration=context.available_minutes,
            outing=context.outing,
            company=context.company,
            categories=list(context.categories) if context.categories else None,
            scenarios=list(context.scenarios) if context.scenarios else None,
        )
        if context.mode == "quick":
            return [
                CandidateTask(task, action, "task_bank", True)
                for task in tasks
                if (action := quick_metadata(task)) is not None
            ]
        return [CandidateTask(task, "", "task_bank") for task in tasks]


class FallbackCandidateProvider:
    def __init__(
        self,
        primary: CandidateProvider,
        fallback: CandidateProvider,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(self, context: RecommendationContext) -> list[CandidateTask]:
        try:
            primary = self.primary.generate(context)
        except (TimeoutError, ConnectionError):
            logging.getLogger(__name__).warning("Candidate source unavailable; using task bank")
            return self.fallback.generate(context)

        if context.mode == "quick":
            primary = [item for item in primary if is_quick_eligible(context, item)]
        else:
            primary = [item for item in primary if item.task.status == "approved"]
        if primary:
            return primary
        logging.getLogger(__name__).info("Candidate source returned no usable tasks; using task bank")
        return self.fallback.generate(context)
