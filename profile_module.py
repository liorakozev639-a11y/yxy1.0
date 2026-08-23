"""Runnable Profile Module example.

Run:
    python -m pip install fastapi uvicorn
    python examples/profile_module.py

Open:
    http://127.0.0.1:8002/docs

This example is synchronous and in-memory. It receives the submitted
questionnaire result and turns it into a deterministic user profile.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


RULE_VERSION = "profile-rule-v1"
SKIPPED_SCORE = 2.5


@dataclass(frozen=True)
class Question:
    """定义题目，返回用户维度"""

    id: str
    dimension: str
    reverse_scored: bool = False


@dataclass(frozen=True)
class Answer:
    """Questionnaire Module 提交给 Profile Module 的答案。"""

    question_id: str
    value: Optional[int]
    skipped: bool = False


@dataclass(frozen=True)
class Profile:
    session_id: str
    profile_version: int
    scores: dict[str, float]
    constraints: dict[str, Any]
    confidence: float
    rule_version: str


DIMENSION_LABELS = {
    "energy": "活力充电",
    "recovery": "松弛疗愈",
    "calm": "松弛疗愈",
    "social": "社交连接",
    "exploration": "乐享探索",
    "explore": "乐享探索",
    "growth": "自我成长",
    "活力充电": "活力充电",
    "松弛疗愈": "松弛疗愈",
    "社交连接": "社交连接",
    "乐享探索": "乐享探索",
    "自我成长": "自我成长",
}

DIMENSION_EXPLANATIONS = {
    "活力充电": "你更容易被能让身体动起来、恢复精神的活动带动。",
    "松弛疗愈": "你当前更需要降低压力、放慢节奏和恢复情绪余量。",
    "社交连接": "你会从熟人陪伴、轻量互动或共同完成任务里获得动力。",
    "乐享探索": "你适合给空闲时间加入一点新鲜体验，让这段时间更有记忆点。",
    "自我成长": "你愿意用可控的小目标，让休息时间也保留一点成就感。",
}

CONSTRAINT_LABELS = {
    "duration": {"half": "半天", "day": "全天"},
    "budget": {"low": "20 元以内", "medium": "40 元以内", "high": "80 元以内"},
    "outing": {
        "home": "居家完成",
        "nearby": "附近出门",
        "city": "全城范围",
        "any": "都可以",
    },
    "company": {"solo": "独处", "group": "结伴", "both": "都可以"},
}


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "强偏好"
    if score >= 0.5:
        return "中等偏好"
    if score >= 0.25:
        return "轻度偏好"
    return "低偏好"


def _constraint_card(key: str, label: str, raw_value: Any, text: str) -> dict[str, Any]:
    value = CONSTRAINT_LABELS.get(key, {}).get(raw_value, raw_value)
    return {
        "key": key,
        "label": label,
        "value": str(value) if value is not None else "未填写",
        "text": text,
    }


def build_profile_insight(profile: Profile) -> dict[str, Any]:
    top_dimensions = [
        {
            "dimension": dimension,
            "label": DIMENSION_LABELS.get(dimension, dimension),
            "score": score,
            "level": _score_level(score),
            "text": DIMENSION_EXPLANATIONS.get(
                DIMENSION_LABELS.get(dimension, dimension),
                "这个方向会作为任务推荐的重要参考。",
            ),
        }
        for dimension, score in sorted(
            profile.scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    primary = top_dimensions[0] if top_dimensions else {
        "label": "自由安排",
        "score": 0,
    }
    constraints = profile.constraints
    selected_categories = list(constraints.get("categories") or [])
    constraint_cards = [
        _constraint_card(
            "duration",
            "可用时间",
            constraints.get("duration"),
            "用于控制计划总时长和任务数量。",
        ),
        _constraint_card(
            "budget",
            "预算区间",
            constraints.get("budget"),
            "用于筛掉明显超出预算的活动。",
        ),
        _constraint_card(
            "outing",
            "活动方式",
            constraints.get("outing"),
            "用于决定任务偏向居家、附近或全城范围。",
        ),
        _constraint_card(
            "company",
            "同行偏好",
            constraints.get("company"),
            "用于决定任务偏向独处、结伴或两者都可。",
        ),
    ]
    if constraints.get("city_or_campus"):
        constraint_cards.append(
            _constraint_card(
                "city_or_campus",
                "所在城市或校园",
                constraints.get("city_or_campus"),
                "后续接入本地数据后，可用于推荐更具体的地点。",
            )
        )

    suggestions = [
        f"优先保留{primary['label']}相关任务，再用其他方向补齐计划。",
        "单个任务建议控制在当前可用时间内，先保证能开始。",
    ]
    if constraints.get("rest_only"):
        suggestions.insert(1, "当前状态偏恢复，计划会降低任务强度和连续任务密度。")

    category_text = "、".join(selected_categories) if selected_categories else "未选择固定方向"
    return {
        "session_id": profile.session_id,
        "profile_version": profile.profile_version,
        "rule_version": profile.rule_version,
        "confidence": profile.confidence,
        "summary": (
            f"你的主要倾向是{primary['label']}，本次计划会在"
            f"{category_text}中优先匹配更容易执行的任务。"
        ),
        "top_dimensions": top_dimensions,
        "constraint_cards": constraint_cards,
        "suggestions": suggestions,
    }


class QuestionInput(BaseModel):
    id: str
    dimension: str
    reverse_scored: bool = False


class AnswerInput(BaseModel):
    question_id: str
    # 未跳过时 value 必须是 1～4；跳过题允许 value 为 None。
    value: Optional[int] = Field(default=None, ge=1, le=4)
    skipped: bool = False


class BuildProfileRequest(BaseModel):
    questions: list[QuestionInput]
    answers: list[AnswerInput]
    preferences: dict[str, Any] = Field(default_factory=dict)


class ProfileRepository:
    """MVP 内存仓库；生产环境替换为 profiles 表。"""

    def __init__(self) -> None:
        self.profiles: dict[str, list[Profile]] = {}

    def save(self, profile: Profile) -> None:
        self.profiles.setdefault(profile.session_id, []).append(profile)

    def get(self, session_id: str) -> Optional[Profile]:
        versions = self.profiles.get(session_id, [])
        return versions[-1] if versions else None

    def next_version(self, session_id: str) -> int:
        versions = self.profiles.get(session_id, [])
        return len(versions) + 1


class ProfileService:
    def __init__(self, repository: ProfileRepository) -> None:
        self.repository = repository

    def build(
        self,
        session_id: str,
        questions: list[Question],
        answers: list[Answer],
        preferences: dict[str, Any],
    ) -> Profile:
        question_map = {
        question.id: question 
        for question in questions
        }
        answer_map = {
        answer.question_id: answer 
        for answer in answers
        }

        
        

        unknown_question_ids = sorted(set(answer_map) - set(question_map))
        """将答案字典和问题字典的键(id)转换成集合，相减可知道答案中有没有包含不属于当前问卷的题目"""
        if unknown_question_ids:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "答案中包含不属于当前问卷的题目",
                    "question_ids": unknown_question_ids,
                },
            )

        dimensions: dict[str, list[float]] = {}

        for question in questions:
            answer = answer_map.get(question.id)
            if answer is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"题目 {question.id} 缺少答案或跳过记录",
                )

            value = SKIPPED_SCORE if answer.skipped else answer.value
            if value is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"题目 {question.id} 必须提供 value 或 skipped=true",
                )

            if question.reverse_scored:
                value = 5 - value

            dimensions.setdefault(question.dimension, []).append(float(value))
            """识别题目的维度，创建或get列表，将得分加入列表，为后续计算平均分做准备"""

        scores = {
            dimension: round((sum(values) / len(values) - 1) / 3, 2)
            for dimension, values in dimensions.items()
        }
        """计算每个画像维度的标准化得分scores"""
        
        profile = Profile(
            session_id=session_id,
            profile_version=self.repository.next_version(session_id),
            scores=scores,
            constraints=dict(preferences),
            confidence=round(len(answers) / len(questions), 2)
            if questions
            else 0.0,
            rule_version=RULE_VERSION,
        )
        self.repository.save(profile)
        return profile


app = FastAPI(title="Free Time Agent - Profile Module")
repository = ProfileRepository()
service = ProfileService(repository)


def model_to_dict(model: BaseModel) -> dict[str, Any]:

    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
    """判断model是否存在model_dump方法"""


@app.post("/api/v1/sessions/{session_id}/profile/build")
def build_profile(
    session_id: str,
    body: BuildProfileRequest,
) -> dict[str, Any]:
    questions = [Question(**model_to_dict(question)) for question in body.questions]
    answers = [Answer(**model_to_dict(answer)) for answer in body.answers]
    profile = service.build(
        session_id=session_id,
        questions=questions,
        answers=answers,
        preferences=body.preferences,
    )
    return {"data": asdict(profile), "error": None}


@app.get("/api/v1/sessions/{session_id}/profile")
def get_profile(session_id: str) -> dict[str, Any]:
    profile = repository.get(session_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="画像尚未生成")
    return {"data": asdict(profile), "error": None}


def demo() -> None:
    """展示普通题、反向题、跳过题和标准化计算"""

    questions = [
        Question(id="q_energy_1", dimension="energy"),
        Question(id="q_energy_2", dimension="energy"),
        Question(id="q_recovery_1", dimension="recovery", reverse_scored=True),
        Question(id="q_social_1", dimension="social"),
    ]
    answers = [
        Answer(question_id="q_energy_1", value=4),
        Answer(question_id="q_energy_2", value=3),
        Answer(question_id="q_recovery_1", value=4),
        Answer(question_id="q_social_1", value=None, skipped=True),
    ]

    profile = service.build(
        session_id="sess_demo",
        questions=questions,
        answers=answers,
        preferences={
            "budget_max": 100,
            "duration_minutes": 180,
            "outing": "home",
            "company": "solo",
        },
    )
    print(asdict(profile))


if __name__ == "__main__":
    demo()
    uvicorn.run("profile_module:app", host="127.0.0.1", port=8002)
