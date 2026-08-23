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
    enriched_tasks = [
        enrich_task_reason(
            task,
            profile.get("constraints", {}),
            preference_map.get(task.category, 0),
        )
        for task in selected
    ]
    reasons = [
        {
            "task_id": task["id"],
            "tags": task["reason_tags"],
            "text": task["reason_text"],
        }
        for task in enriched_tasks
    ]

    return {
        "tasks": enriched_tasks,
        "task_ids": [task.id for task in selected],
        "covered_categories": sorted(covered),
        "missing_categories": missing,
        "reasons": reasons,
    }


def enrich_task_reason(
    task: Task,
    constraints: dict[str, Any] | None = None,
    preference_score: float = 0,
    slot_minutes: int | None = None,
) -> dict[str, Any]:
    payload = asdict(task)
    payload["reason_tags"] = build_reason_tags(task, constraints, slot_minutes)
    payload["reason_text"] = build_reason_text(
        task,
        constraints,
        preference_score,
        slot_minutes,
    )
    return payload


def build_reason_tags(
    task: Task,
    constraints: dict[str, Any] | None = None,
    slot_minutes: int | None = None,
) -> list[str]:
    constraints = constraints or {}
    active_minutes = slot_minutes or task.duration
    tags: list[str] = []

    if task.outing == "home":
        tags.append("居家可做")
    elif task.outing == "nearby":
        tags.append("附近可做")
    elif task.outing == "city":
        tags.append("适合全城探索")

    if task.budget <= 20:
        tags.append("低预算")
    elif task.budget <= constraints.get("budget_limit", task.budget):
        tags.append("预算匹配")

    if active_minutes <= 30:
        tags.append("短时间可完成")
    elif active_minutes <= 60:
        tags.append("一小时内完成")

    if task.company == "solo":
        tags.append("适合独处")
    elif task.company == "group":
        tags.append("适合结伴")
    elif task.company == "both":
        tags.append("独处结伴皆可")

    if constraints.get("rest_only"):
        tags.append("低压力友好")
    tags.append(f"覆盖{task.category}")
    return tags


def build_reason_text(
    task: Task,
    constraints: dict[str, Any] | None = None,
    preference_score: float = 0,
    slot_minutes: int | None = None,
) -> str:
    constraints = constraints or {}
    active_minutes = slot_minutes or task.duration
    lines = [
        f"你选择了「{task.category}」，这个任务可以覆盖该方向的空闲需求。",
        f"当前分类偏好分数为 {float(preference_score):.2f}，系统会优先保留匹配度更高的分类。",
    ]
    if task.outing == "home":
        lines.append("你的当前安排可以无需外出完成，适合居家或低出行成本场景。")
    elif task.outing == "nearby":
        lines.append("这个任务适合在附近完成，不需要长距离移动。")
    else:
        lines.append("这个任务适合留给出行范围更宽松的时间段。")

    if task.company == "solo":
        lines.append("它适合独处完成，不依赖他人临时配合。")
    elif task.company == "group":
        lines.append("它更适合结伴完成，可以满足社交连接需求。")
    else:
        lines.append("它既可以独处完成，也可以和别人一起完成。")

    lines.append(f"当前时间段约 {active_minutes} 分钟，系统会按这个时间段展示可执行版本。")
    lines.append(f"预计预算约为 {task.budget} 元，便于控制休闲成本。")
    return "\n".join(lines)


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
    # assert 用于检查演示结果是否符合预期。
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
