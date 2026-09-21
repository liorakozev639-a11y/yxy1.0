"""Deterministic, key-free stand-in for the planned two-stage AI generator."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from profile_module import DIMENSION_LABELS
from task_repository import LOCATION_DEPENDENCIES


# These are deliberately small test fixtures, not a production fallback task bank.
_ACTIONS: dict[str, tuple[tuple[str, str, int], ...]] = {
    "活力充电": (
        ("做一轮坐姿肩部绕环", "坐稳后缓慢绕动双肩十次。", 10),
        ("站起来伸展手臂", "站稳并把双臂向上伸展。", 10),
        ("在房间里轻步走", "清出一小段通道，按舒适速度走动。", 12),
        ("做一轮手腕舒展", "放松双手，缓慢转动手腕。", 10),
        ("练习坐姿脚踝画圈", "坐好，分别用脚踝缓慢画圈。", 10),
        ("跟着音乐轻轻踏步", "播放一首喜欢的歌，原地轻踏。", 12),
        ("做一次颈肩轻活动", "保持自然呼吸，轻轻活动颈肩。", 10),
        ("在窗边站立伸展", "站到窗边，伸直手臂和背部。", 10),
        ("做一轮缓慢提踵", "扶稳桌边，缓慢抬起再放下脚跟。", 10),
        ("完成一次坐姿侧弯", "坐直，向左右两侧轻轻伸展。", 10),
        ("在家走动并喝水", "起身倒一杯水，再在室内慢走。", 12),
        ("做一次站姿背部舒展", "站稳，轻轻向前伸展背部。", 10),
    ),
    "松弛疗愈": (
        ("听一段舒缓音乐", "选择一首舒缓音乐并坐下来。", 12),
        ("做十分钟安静呼吸", "找个舒服的位置，缓慢呼吸。", 10),
        ("写下三件今天的小事", "拿出纸笔，写下第一件小事。", 12),
        ("整理一个安静角落", "先移开角落里的一件杂物。", 15),
        ("看一页轻松的书", "打开手边的书，从一页开始读。", 10),
        ("听窗外声音并休息", "坐在窗边，留意周围的声音。", 10),
        ("给自己倒杯温水", "倒一杯温水，慢慢喝完。", 10),
        ("做一次桌面清理", "收好桌面上最显眼的三件小物。", 15),
        ("写一张暂停清单", "写下现在不用立刻处理的一件事。", 12),
        ("进行一段闭眼休息", "设好十分钟提醒后闭眼休息。", 10),
        ("整理一份放松歌单", "选一首让你放松的歌曲。", 15),
        ("做一次睡前放空", "放下手机，坐着安静待一会儿。", 10),
    ),
    "社交连接": (
        ("给熟人发一句问候", "选择一位熟人，发一句简单问候。", 10),
        ("向朋友分享今天的小事", "挑一件小事，发给愿意联系的朋友。", 10),
        ("给家人发一张日常照片", "选一张愿意分享的照片。", 10),
        ("给朋友写一句感谢", "想起一位朋友，写下感谢的话。", 10),
        ("约熟人线上聊十分钟", "给熟人发消息，询问是否方便聊聊。", 15),
        ("和朋友互荐一首歌", "先挑一首最近喜欢的歌。", 12),
        ("给同学发一条近况", "挑一位同学，写一句近况。", 10),
        ("邀请熟人互换一张照片", "发消息邀请熟人分享一张近照。", 15),
        ("给家人打个简短电话", "先发消息确认对方是否方便接听。", 15),
        ("和朋友交流一个小发现", "想一个最近的小发现并发给朋友。", 10),
        ("给久未联系的人问好", "选一位愿意联系的人，发句问候。", 10),
        ("邀请同伴分享本周趣事", "发消息问同伴本周有什么趣事。", 12),
    ),
    "乐享探索": (
        ("听一首陌生风格的歌", "选一个平时较少听的音乐类型。", 10),
        ("给身边物件拍三张照片", "找一件常见物品，先拍第一张。", 15),
        ("尝试一种新的饮水搭配", "从手边已有食材中选一种搭配水。", 12),
        ("看一段陌生主题的短片", "选一个不了解的主题并打开短片。", 15),
        ("观察房间里的三种颜色", "先找出房间里最醒目的一种颜色。", 10),
        ("听一期新主题的播客", "搜索一个未听过的主题。", 20),
        ("为普通照片起个新标题", "打开一张自己的照片，写下标题。", 12),
        ("在家做一次盲选阅读", "从书架或收藏中随机打开一篇。", 15),
        ("给桌面换一种摆放", "先移动桌面上的一件小物。", 15),
        ("寻找一种新的拍照角度", "选一个物件，蹲下拍第一张。", 15),
        ("画一张周末灵感小地图", "拿出纸笔，写下一个想探索的主题。", 15),
        ("挑一部未看过的纪录短片", "搜索一个感兴趣的题目并试看开头。", 15),
    ),
    "自我成长": (
        ("写下一条今天的新发现", "打开笔记，写一句今天学到的事。", 10),
        ("学习一个常用快捷键", "挑一个常用软件，查找一个快捷键。", 12),
        ("阅读一页入门文章", "打开一篇感兴趣的入门文章。", 15),
        ("给一个目标写第一步", "写下目标，再写一个十分钟动作。", 10),
        ("整理三个最近学到的词", "先写下第一个新词。", 12),
        ("复盘一次有效沟通", "回想一次沟通，写下有效的一句话。", 12),
        ("做十分钟专注学习", "选一个小知识点并开始计时。", 10),
        ("写出一个问题的两种解法", "选一个手头问题，先写第一种办法。", 15),
        ("整理一页个人笔记", "打开最近一页笔记，圈出重点。", 15),
        ("向自己解释一个概念", "挑一个概念，用一句话解释它。", 12),
        ("写下明天最小的学习任务", "写下明天最容易开始的一件事。", 10),
        ("画出一个简单流程", "选一件熟悉的事，画出第一步。", 15),
    ),
}


def semantic_signature(title: str) -> str:
    return re.sub(r"\W+", "", title.casefold())


def build_generation_context(
    session: Any,
    questionnaire: Any,
    questions: dict[str, Any],
    answers: list[Any],
    profile: Any,
    request: Any,
    excluded_signatures: set[str] | None = None,
) -> dict[str, Any]:
    if not questionnaire.submitted:
        raise ValueError("问卷尚未提交")
    constraints = dict(profile.constraints)
    sources: dict[str, dict[str, Any]] = {}
    for key, value in session.preferences.items():
        if value is not None and value != "":
            sources[f"preference.{key}"] = {"kind": "preference", "value": value}
    answer_map = {answer.question_id: answer for answer in answers}
    unknown_question_ids: list[str] = []
    answered_categories: set[str] = set()
    for question_id in questionnaire.question_ids:
        answer = answer_map.get(question_id)
        if answer is None or answer.skipped or answer.value is None:
            unknown_question_ids.append(question_id)
            continue
        question = questions[question_id]
        sources[f"question:{question_id}"] = {
            "kind": "answer",
            "prompt": question.prompt,
            "value": answer.value,
            "dimension": question.dimension,
        }
        answered_categories.add(DIMENSION_LABELS.get(question.dimension, question.dimension))
    for category, score in profile.scores.items():
        if category in answered_categories:
            sources[f"profile:{category}"] = {"kind": "profile", "value": score}
    return {
        "session_id": session.id,
        "selected_categories": list(constraints["categories"]),
        "hard_constraints": {
            "budget_limit": constraints["budget_limit"],
            "max_duration": constraints["max_duration"],
            "outing": constraints["outing"],
            "company": constraints["company"],
            "energy_level": constraints.get("energy_level"),
        },
        "questionnaire_mode": questionnaire.mode,
        "unknown_question_ids": unknown_question_ids,
        "sources": sources,
        "profile_scores": {
            category: score for category, score in profile.scores.items()
            if category in answered_categories
        },
        "free_start": request.free_start.isoformat(),
        "free_end": request.free_end.isoformat(),
        "density": request.density,
        "excluded_signatures": sorted(excluded_signatures or set()),
    }


def validate_brief(brief: dict[str, Any], context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if brief.get("hard_constraints") != context["hard_constraints"]:
        errors.append("hard_constraints")
    categories = brief.get("selected_categories")
    if not isinstance(categories, list) or categories != context["selected_categories"]:
        errors.append("selected_categories")
    refs = brief.get("evidence_refs")
    if not isinstance(refs, list) or any(
        not isinstance(ref, str) or ref not in context["sources"] for ref in refs
    ):
        errors.append("unknown_evidence")
    excluded = brief.get("excluded_signatures")
    if not isinstance(excluded, list) or any(not isinstance(value, str) for value in excluded) or set(context["excluded_signatures"]) - set(excluded):
        errors.append("excluded_signatures")
    return errors


def validate_candidates(
    candidates: list[dict[str, Any]],
    context: dict[str, Any],
    excluded_signatures: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen = set(excluded_signatures) | set(context["excluded_signatures"])
    limits = context["hard_constraints"]
    start = datetime.fromisoformat(context["free_start"])
    end = datetime.fromisoformat(context["free_end"])
    window_minutes = int((end - start).total_seconds() // 60)
    outing_allowed = {
        "home": {"home"},
        "nearby": {"home", "nearby"},
        "city": {"home", "nearby", "city"},
        "any": {"home", "nearby", "city"},
    }
    for candidate in candidates:
        if not isinstance(candidate, dict):
            rejected.append({"title": None, "reasons": ["invalid_structure"]})
            continue
        errors: list[str] = []
        title = candidate.get("title")
        signature = semantic_signature(title) if isinstance(title, str) else ""
        if not signature or signature != candidate.get("semantic_signature"):
            errors.append("title_or_signature")
        if signature in seen:
            errors.append("duplicate")
        if candidate.get("category") not in context["selected_categories"]:
            errors.append("category")
        duration = candidate.get("duration_minutes")
        if type(duration) is not int or not 1 <= duration <= min(limits["max_duration"], window_minutes):
            errors.append("duration")
        budget = candidate.get("estimated_budget")
        if type(budget) is not int or not 0 <= budget <= limits["budget_limit"]:
            errors.append("budget")
        outing = candidate.get("outing")
        if not isinstance(outing, str) or outing not in outing_allowed.get(limits["outing"], set()):
            errors.append("outing")
        company = candidate.get("company")
        if not isinstance(company, str) or company not in {"solo", "group", "both"} or (limits["company"] != "both" and company not in {limits["company"], "both"}):
            errors.append("company")
        for name in ("ease_level", "physical_load", "social_pressure"):
            value = candidate.get(name)
            if type(value) is not int or not 1 <= value <= 5:
                errors.append(name)
        if limits.get("energy_level") == "low" and type(candidate.get("physical_load")) is int and candidate["physical_load"] > 2:
            errors.append("physical_load")
        location = candidate.get("location_dependency")
        if not isinstance(location, str) or location not in LOCATION_DEPENDENCIES:
            errors.append("location_dependency")
        if not isinstance(candidate.get("first_action"), str) or not candidate["first_action"].strip():
            errors.append("first_action")
        if not isinstance(candidate.get("prerequisites"), list) or any(not isinstance(part, str) for part in candidate["prerequisites"]):
            errors.append("prerequisites")
        if not isinstance(candidate.get("action_steps"), list) or not candidate["action_steps"] or any(not isinstance(step, str) or not step.strip() for step in candidate["action_steps"]):
            errors.append("action_steps")
        for name in ("generation_reason", "recommendation_reason"):
            if not isinstance(candidate.get(name), str) or not candidate[name].strip():
                errors.append(name)
        refs = candidate.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(
            not isinstance(ref, str) or ref not in context["sources"] for ref in refs
        ):
            errors.append("unknown_evidence")
        if errors:
            rejected.append({"title": title, "reasons": sorted(set(errors))})
        else:
            seen.add(signature)
            accepted.append(candidate)
    return accepted, rejected


class MockTaskGenerator:
    """Replaceable model interface; values are fixtures, never an AI claim."""

    def __init__(self, scenario: str = "valid") -> None:
        self.scenario = scenario

    def write_brief(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "hard_constraints": dict(context["hard_constraints"]),
            "selected_categories": list(context["selected_categories"]),
            "excluded_signatures": list(context["excluded_signatures"]),
            "unknown_question_ids": list(context["unknown_question_ids"]),
            "evidence_refs": sorted(context["sources"]),
            "target_count": 10,
        }

    def generate_tasks(
        self,
        context: dict[str, Any],
        brief: dict[str, Any],
        count: int,
        excluded_signatures: set[str],
    ) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        categories = brief["selected_categories"]
        max_rows = max(len(_ACTIONS[category]) for category in categories)
        for index in range(max_rows):
            for category in categories:
                if index >= len(_ACTIONS[category]):
                    continue
                title, first_action, duration = _ACTIONS[category][index]
                signature = semantic_signature(title)
                if signature in excluded_signatures or signature in context["excluded_signatures"]:
                    continue
                refs = ["preference.categories"]
                refs.extend(
                    ref for ref in ("preference.budget", "preference.outing")
                    if ref in context["sources"]
                )
                if f"profile:{category}" in context["sources"]:
                    refs.append(f"profile:{category}")
                constraints = context["hard_constraints"]
                task = {
                    "title": title,
                    "category": category,
                    "action_steps": [first_action],
                    "first_action": first_action,
                    "prerequisites": [],
                    "duration_minutes": duration,
                    "estimated_budget": 0,
                    "outing": "home",
                    "company": "both",
                    "ease_level": 4,
                    "physical_load": 2 if category == "活力充电" else 1,
                    "social_pressure": 2 if category == "社交连接" else 1,
                    "location_dependency": "home",
                    "generation_reason": f"根据你本次选择的「{category}」方向，构造了一件可在家开始的小事。",
                    "recommendation_reason": (
                        f"这项任务可在家完成，不需要额外花费，约需 {duration} 分钟；"
                        f"符合本次 {constraints['budget_limit']} 元预算和出行条件。"
                    ),
                    "evidence_refs": refs,
                    "uncertainty_note": "这是一条模拟生成任务，尚未接入真实 AI。",
                    "semantic_signature": signature,
                }
                tasks.append(task)
                if len(tasks) >= count:
                    if self.scenario == "over_budget":
                        tasks[0]["estimated_budget"] = constraints["budget_limit"] + 1
                    elif self.scenario == "invented_evidence":
                        tasks[0]["evidence_refs"] = ["question:not_answered"]
                    elif self.scenario == "duplicate" and len(tasks) > 1:
                        tasks[-1] = dict(tasks[0])
                    return tasks
        return tasks
