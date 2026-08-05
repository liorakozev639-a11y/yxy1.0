from dataclasses import asdict
from typing import Any

try:
    from task_repository import CATEGORIES, Task, TaskRepository
except ModuleNotFoundError:
    from examples.task_repository import CATEGORIES, Task, TaskRepository


def recommend_tasks(
    profile: dict[str, Any],
    selected_categories: list[str],
    candidates: list[Task],
    limit: int = 10,
) -> dict[str, Any]:
    if not selected_categories:
        raise ValueError("至少需要选择一个活动分类")
    if limit <= 0:
        raise ValueError("推荐任务数量必须大于 0")
    if any(category not in CATEGORIES for category in selected_categories):
        raise ValueError("存在不支持的活动分类")

    selected_category_set = set(selected_categories)
    scores = profile.get("scores", {})
    preference_map = {
        category: float(scores.get(category, 0))
        for category in selected_category_set
    }

   
    usable = [
        task
        for task in candidates
        if task.status == "approved"
        and task.category in selected_category_set
    ]
    ranked = sorted(
        usable,
        key=lambda task: (
            -preference_map.get(task.category, 0),
            task.duration,
            task.budget,
            task.id,
        ),
    )

    selected: list[Task] = []
    selected_ids: set[str] = set()
    covered: set[str] = set()

    # First pass: take the highest-ranked task from each requested category.
    for task in ranked:
        if task.category in covered:
            continue
        selected.append(task)
        selected_ids.add(task.id)
        covered.add(task.category)
        if len(selected) >= limit:
            break

    # Second pass: use remaining slots for the highest-ranked tasks.
    if len(selected) < limit:
        for task in ranked:
            if task.id in selected_ids:
                continue
            selected.append(task)
            selected_ids.add(task.id)
            if len(selected) >= limit:
                break

    missing = sorted(selected_category_set - covered)
    reasons = [
        {
            "task_id": task.id,
            "text": (
                f"任务属于{task.category}，当前分类偏好分数为"
                f"{preference_map.get(task.category, 0):.2f}，"
                f"预计需要{task.duration}分钟，预算约为{task.budget}元。"
            ),
        }
        for task in selected
    ]

    return {
        "tasks": [asdict(task) for task in selected],
        "task_ids": [task.id for task in selected],
        "covered_categories": sorted(covered),
        "missing_categories": missing,
        "reasons": reasons,
    }


def build_recommendation(
    session_id: str,
    profile: dict[str, Any],
    selected_categories: list[str],
    repository: TaskRepository,
    limit: int = 10,
) -> dict[str, Any]:
    """Run the complete Profile -> Task Repository -> Recommendation flow."""
    constraints = profile.get("constraints", {})
    candidates = repository.search_tasks(
        session_id=session_id,
        budget_limit=constraints["budget_limit"],
        max_duration=constraints["max_duration"],
        outing=constraints["outing"],
        company=constraints["company"],
        categories=selected_categories,
        scenarios=constraints.get("scenarios"),
    )

    result = recommend_tasks(
        profile=profile,
        selected_categories=selected_categories,
        candidates=candidates,
        limit=limit,
    )
    result["candidate_count"] = len(candidates)
    result["constraints"] = constraints
    return result


def demo() -> None:
    repository = TaskRepository()
    profile = {
        "scores": {
            "活力充电": 0.65,
            "松弛疗愈": 0.90,
            "社交连接": 0.30,
            "乐享探索": 0.55,
            "自我成长": 0.70,
        },
        "constraints": {
            "budget_limit": 50,
            "max_duration": 90,
            "outing": "nearby",
            "company": "solo",
            "scenarios": ["工作后精力不足"],
        },
    }
    selected_categories = ["松弛疗愈", "活力充电", "自我成长"]

    result = build_recommendation(
        session_id="session_001",
        profile=profile,
        selected_categories=selected_categories,
        repository=repository,
        limit=6,
    )

    assert result["candidate_count"] > 0
    assert set(result["covered_categories"]) == set(selected_categories)
    assert result["missing_categories"] == []
    assert len(result["tasks"]) <= 6
    assert all(task["status"] == "approved" for task in result["tasks"])

    print(f"候选任务数量: {result['candidate_count']}")
    print(f"已覆盖分类: {result['covered_categories']}")
    print("推荐任务:")
    for task in result["tasks"]:
        print(f"- {task['id']}: {task['title']}")
    print("匹配理由:")
    for reason in result["reasons"]:
        print(f"- {reason['text']}")


if __name__ == "__main__":
    demo()
