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
    excluded_feedback_groups: set[str] | None = None,
    history_weights: dict[str, Any] | None = None,
    history_excluded_groups: set[str] | None = None,
) -> dict[str, Any]:
    if not selected_categories:
        raise ValueError("至少需要选择一个活动分类")
    if limit <= 0:
        raise ValueError("推荐任务数量必须大于 0")
    if any(category not in CATEGORIES for category in selected_categories):
        raise ValueError("存在不支持的活动分类")

    selected_category_set = set(selected_categories)
    session_excluded = excluded_feedback_groups or set()
    excluded = session_excluded | (history_excluded_groups or set())
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
        and task.feedback_group not in excluded
    ]
    ranked = sorted(
        usable,
        key=lambda task: (
            -preference_map.get(task.category, 0),
            -history_score(task, history_weights),
            -load_fit_score(task, profile.get("constraints", {})),
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
            "match_score": task["match_score"],
            "matched_preferences": task["matched_preferences"],
            "warning_text": task["warning_text"],
            "load_profile": task["load_profile"],
        }
        for task in enriched_tasks
    ]

    return {
        "tasks": enriched_tasks,
        "task_ids": [task.id for task in selected],
        "covered_categories": sorted(covered),
        "missing_categories": missing,
        "reasons": reasons,
        "recommendation_memory": {
            "excluded_group_count": len(session_excluded),
            "excluded_task_count": sum(
                task.feedback_group in session_excluded for task in candidates
            ),
        },
    }


def history_score(task: Task, history_weights: dict[str, Any] | None) -> float:
    if not history_weights:
        return 0.0
    score = 0.0
    score += history_weights.get("category_boosts", {}).get(task.category, 0)
    score += history_weights.get("group_boosts", {}).get(task.feedback_group, 0)
    score -= history_weights.get("group_penalties", {}).get(task.feedback_group, 0)
    preferred = history_weights.get("preferred_duration_minutes")
    if preferred:
        distance = abs(task.duration - preferred)
        score += max(0, 0.12 - min(distance, 60) / 500)
    return round(score, 4)


def load_fit_score(task: Task, constraints: dict[str, Any] | None = None) -> float:
    constraints = constraints or {}
    score = 0.0
    if constraints.get("rest_only"):
        score += task.ease_level * 0.08
        score += (6 - task.physical_load) * 0.08
        score += (6 - task.social_pressure) * 0.04

    company = constraints.get("company")
    if company == "solo":
        score += (6 - task.social_pressure) * 0.04
    elif company == "group":
        score += max(0, task.social_pressure - 2) * 0.03

    outing = constraints.get("outing")
    if outing == "home" and task.location_dependency in {"home", "flexible"}:
        score += 0.08
    elif outing == "nearby" and task.location_dependency in {"home", "nearby", "flexible"}:
        score += 0.06
    elif outing in {"city", "any"}:
        score += 0.03
    return round(score, 4)


def build_load_profile(task: Task) -> dict[str, Any]:
    ease_label = (
        "很轻松" if task.ease_level >= 5
        else "较轻松" if task.ease_level >= 4
        else "适中" if task.ease_level >= 3
        else "有挑战"
    )
    physical_label = (
        "低体力" if task.physical_load <= 2
        else "中体力" if task.physical_load <= 3
        else "高体力"
    )
    social_label = (
        "低社交压力" if task.social_pressure <= 2
        else "中社交压力" if task.social_pressure <= 3
        else "高社交压力"
    )
    location_label = {
        "home": "居家",
        "nearby": "附近",
        "city": "全城",
        "flexible": "地点灵活",
    }.get(task.location_dependency, "地点灵活")
    return {
        "ease_level": task.ease_level,
        "ease_label": ease_label,
        "physical_load": task.physical_load,
        "physical_label": physical_label,
        "social_pressure": task.social_pressure,
        "social_label": social_label,
        "location_dependency": task.location_dependency,
        "location_label": location_label,
    }


def enrich_task_reason(
    task: Task,
    constraints: dict[str, Any] | None = None,
    preference_score: float = 0,
    slot_minutes: int | None = None,
) -> dict[str, Any]:
    payload = asdict(task)
    payload["load_profile"] = build_load_profile(task)
    payload["reason_tags"] = build_reason_tags(task, constraints, slot_minutes)
    payload["matched_preferences"] = build_matched_preferences(
        task,
        constraints,
        preference_score,
        slot_minutes,
    )
    payload["warning_text"] = build_warning_text(task, constraints, slot_minutes)
    payload["match_score"] = calculate_match_score(
        task,
        constraints,
        preference_score,
        slot_minutes,
    )
    payload["reason_text"] = build_reason_text(
        task,
        constraints,
        preference_score,
        slot_minutes,
    )
    return payload


def calculate_match_score(
    task: Task,
    constraints: dict[str, Any] | None = None,
    preference_score: float = 0,
    slot_minutes: int | None = None,
) -> float:
    constraints = constraints or {}
    active_minutes = slot_minutes or task.duration
    score = float(preference_score)
    if task.budget > constraints.get("budget_limit", task.budget):
        score -= 0.1
    if active_minutes > constraints.get("max_duration", active_minutes):
        score -= 0.1
    outing = constraints.get("outing")
    if outing and outing != "any" and task.outing not in {"home", outing}:
        score -= 0.1
    company = constraints.get("company")
    if company and company != "both" and task.company not in {company, "both"}:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 2)


def build_matched_preferences(
    task: Task,
    constraints: dict[str, Any] | None = None,
    preference_score: float = 0,
    slot_minutes: int | None = None,
) -> list[str]:
    constraints = constraints or {}
    active_minutes = slot_minutes or task.duration
    matches: list[str] = []
    if preference_score >= 0.75:
        matches.append("分类偏好强")
    elif preference_score >= 0.5:
        matches.append("分类偏好中等")
    elif preference_score > 0:
        matches.append("分类偏好轻度")

    outing = constraints.get("outing")
    if outing == "home" and task.outing == "home":
        matches.append("居家可做")
    elif outing == "nearby" and task.outing in {"home", "nearby"}:
        matches.append("出行范围匹配")
    elif outing in {"city", "any"}:
        matches.append("出行弹性匹配")

    company = constraints.get("company")
    if company == "solo" and task.company in {"solo", "both"}:
        matches.append("独处友好")
    elif company == "group" and task.company in {"group", "both"}:
        matches.append("结伴友好")
    elif company == "both":
        matches.append("同行方式灵活")

    if task.budget <= constraints.get("budget_limit", task.budget):
        matches.append("预算匹配")
    if active_minutes <= constraints.get("max_duration", active_minutes):
        matches.append("时长匹配")
    if constraints.get("rest_only"):
        matches.append("低压力优先")
        if task.ease_level >= 4:
            matches.append("轻松度较高")
        if task.physical_load <= 2:
            matches.append("体力负担低")
    if company == "solo" and task.social_pressure <= 2:
        matches.append("社交压力低")
    if task.location_dependency == "flexible":
        matches.append("地点灵活")
    return matches


def build_warning_text(
    task: Task,
    constraints: dict[str, Any] | None = None,
    slot_minutes: int | None = None,
) -> str:
    constraints = constraints or {}
    active_minutes = slot_minutes or task.duration
    warnings: list[str] = []
    if task.budget > constraints.get("budget_limit", task.budget):
        warnings.append("预算高于当前档位")
    if active_minutes > constraints.get("max_duration", active_minutes):
        warnings.append("时长超过当前偏好")
    outing = constraints.get("outing")
    if outing and outing != "any" and task.outing not in {"home", outing}:
        warnings.append("出行范围可能偏远")
    company = constraints.get("company")
    if company and company != "both" and task.company not in {company, "both"}:
        warnings.append("同行方式可能不完全匹配")
    if constraints.get("rest_only") and task.physical_load >= 4:
        warnings.append("体力消耗可能偏高")
    if company == "solo" and task.social_pressure >= 4:
        warnings.append("社交压力可能偏高")
    if outing == "home" and task.location_dependency not in {"home", "flexible"}:
        warnings.append("地点依赖不适合居家")
    if not warnings:
        return ""
    return "；".join(warnings) + "，请确认是否接受。"


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
    if task.ease_level >= 4:
        tags.append("轻松度高")
    if task.physical_load <= 2:
        tags.append("体力消耗低")
    elif task.physical_load >= 4:
        tags.append("体力消耗高")
    if task.social_pressure <= 2:
        tags.append("低社交压力")
    elif task.social_pressure >= 4:
        tags.append("社交压力高")
    if task.location_dependency == "flexible":
        tags.append("地点灵活")
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
    load_profile = build_load_profile(task)
    lines.append(
        "任务轻重："
        f"{load_profile['ease_label']}、"
        f"{load_profile['physical_label']}、"
        f"{load_profile['social_label']}、"
        f"{load_profile['location_label']}。"
    )
    if constraints.get("rest_only"):
        lines.append("你当前偏恢复，系统会优先选择轻松度较高、体力消耗较低的任务。")
    return "\n".join(lines)


def build_recommendation(
    session_id: str,
    profile: dict[str, Any],
    selected_categories: list[str],
    repository: TaskRepository,
    limit: int = 10,
    excluded_feedback_groups: set[str] | None = None,
    history_weights: dict[str, Any] | None = None,
    history_excluded_groups: set[str] | None = None,
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
        excluded_feedback_groups=excluded_feedback_groups,
        history_weights=history_weights,
        history_excluded_groups=history_excluded_groups,
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
