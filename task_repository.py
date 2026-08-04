"""Task Repository MVP example.

This file contains an in-memory public task bank, user custom tasks, and a
reviewed questionnaire bank. It runs without PostgreSQL, FastAPI, MQ,
asynchronous workers, maps, merchants, or live activity APIs.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Optional


CATEGORIES = (
    "活力充电",
    "松弛疗愈",
    "社交连接",
    "乐享探索",
    "自我成长",
)

SCENARIOS = (
    "突然获得半天休息时间",
    "周末不知道做什么",
    "工作后精力不足",
    "想独处但不想完全躺平",
    "临时改变想法",
)

QUESTION_SCALE = {
    1: "完全不同意",
    2: "不太同意",
    3: "比较同意",
    4: "非常同意",
}


@dataclass(frozen=True)
class Task:
    """A public or user-created activity that can enter recommendation."""

    id: str
    title: str
    category: str
    duration: int
    budget: int
    outing: str
    company: str
    status: str = "approved"
    owner_session_id: Optional[str] = None
    scenarios: tuple[str, ...] = ()


@dataclass(frozen=True)
class Question:
    """A reviewed preference question used by Questionnaire Module."""

    id: str
    category: str
    dimension: str
    prompt: str
    reverse_scored: bool = False
    status: str = "approved"


# Each category contains exactly ten activities. The scenario tags allow the
# MVP to choose useful tasks without querying real-time external services.
_ACTIVITY_ROWS = [
    ("task_energy_01", "居家拉伸", "活力充电", 30, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_02", "小区快走", "活力充电", 40, 0, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_03", "跟练一节低强度瑜伽", "活力充电", 45, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_04", "完成一组自重训练", "活力充电", 35, 0, "home", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_05", "爬楼梯或坡道走三轮", "活力充电", 25, 0, "nearby", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_06", "做一套肩颈活动度练习", "活力充电", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_07", "骑行绕附近街区一圈", "活力充电", 60, 0, "nearby", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_08", "跟音乐自由舞动", "活力充电", 30, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_09", "完成十分钟核心训练", "活力充电", 20, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_10", "使用泡沫轴放松身体", "活力充电", 25, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_01", "做五分钟呼吸练习", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_02", "小睡二十分钟", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_03", "泡脚并听舒缓音乐", "松弛疗愈", 30, 20, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_04", "在家看一部轻松电影", "松弛疗愈", 120, 30, "home", "solo", ("周末不知道做什么", "临时改变想法")),
    ("task_recovery_05", "去公园慢走并观察树木", "松弛疗愈", 50, 0, "nearby", "solo", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_recovery_06", "写一页情绪日记", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_07", "泡一杯茶并完整休息半小时", "松弛疗愈", 30, 10, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_08", "进行十分钟正念冥想", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_09", "整理房间中的一个小区域", "松弛疗愈", 25, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_recovery_10", "两小时手机免打扰休息", "松弛疗愈", 120, 0, "home", "solo", ("周末不知道做什么", "工作后精力不足")),
    ("task_social_01", "约朋友散步聊天", "社交连接", 60, 0, "nearby", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_02", "给家人打一次视频电话", "社交连接", 30, 0, "home", "group", ("工作后精力不足", "临时改变想法")),
    ("task_social_03", "找同学一起自习", "社交连接", 90, 0, "nearby", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_social_04", "和朋友玩一局桌游", "社交连接", 90, 30, "home", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_05", "和家人一起准备晚餐", "社交连接", 90, 80, "home", "group", ("周末不知道做什么", "临时改变想法")),
    ("task_social_06", "和同伴打半小时羽毛球", "社交连接", 60, 20, "nearby", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_07", "和朋友喝咖啡聊近况", "社交连接", 60, 50, "nearby", "group", ("工作后精力不足", "临时改变想法")),
    ("task_social_08", "参加一次校园或社区活动", "社交连接", 120, 0, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_09", "和朋友进行一次主题照片散步", "社交连接", 90, 0, "nearby", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_10", "给一位久未联系的人发消息", "社交连接", 15, 0, "home", "group", ("工作后精力不足", "临时改变想法")),
    ("task_explore_01", "找一家咖啡馆放空", "乐享探索", 90, 40, "nearby", "both", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_explore_02", "买一份喜欢的甜点慢慢品尝", "乐享探索", 45, 35, "nearby", "both", ("工作后精力不足", "临时改变想法")),
    ("task_explore_03", "逛一次附近的菜市场", "乐享探索", 60, 50, "nearby", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_04", "参观一次小型展览", "乐享探索", 120, 60, "city", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_explore_05", "去书店随意浏览并买一本书", "乐享探索", 90, 80, "nearby", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_explore_06", "在家做一道新菜", "乐享探索", 90, 50, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_07", "听一集轻松有趣的播客", "乐享探索", 45, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_08", "玩一款不超过一小时的游戏", "乐享探索", 60, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_explore_09", "拍摄一组街区细节照片", "乐享探索", 75, 0, "nearby", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_explore_10", "做一次低预算零食尝鲜", "乐享探索", 45, 30, "nearby", "both", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_01", "阅读一本书二十页", "自我成长", 45, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_growth_02", "学习一组日常英语表达", "自我成长", 30, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_03", "完成一节线上微课程", "自我成长", 60, 0, "home", "solo", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_growth_04", "整理一份学习笔记", "自我成长", 40, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_growth_05", "练习三十分钟乐器或唱歌", "自我成长", 30, 0, "home", "solo", ("周末不知道做什么", "临时改变想法")),
    ("task_growth_06", "规划下一周的三个重点", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_07", "学习手机摄影的一个技巧", "自我成长", 45, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_growth_08", "写一篇三百字短文", "自我成长", 35, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_09", "完成一个小型编程练习", "自我成长", 60, 0, "home", "solo", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_growth_10", "为一个兴趣项目建立行动清单", "自我成长", 30, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
]

PUBLIC_TASKS = [
    Task(
        id=task_id,
        title=title,
        category=category,
        duration=duration,
        budget=budget,
        outing=outing,
        company=company,
        scenarios=scenarios,
    )
    for task_id, title, category, duration, budget, outing, company, scenarios
    in _ACTIVITY_ROWS
]


_QUESTION_ROWS = [
    ("q_energy_01", "活力充电", "energy", "我愿意用轻度运动开启一段空闲时间。", False),
    ("q_energy_02", "活力充电", "energy", "我在休息时也希望让身体保持活动。", False),
    ("q_energy_03", "活力充电", "energy", "短时间的拉伸会让我感觉更舒服。", False),
    ("q_energy_04", "活力充电", "energy", "我能接受在居家环境完成简单训练。", False),
    ("q_energy_05", "活力充电", "energy", "我喜欢通过走动恢复精神状态。", False),
    ("q_energy_06", "活力充电", "energy", "我有空时愿意尝试骑行或其他有氧活动。", False),
    ("q_energy_07", "活力充电", "energy", "我不希望所有空闲时间都坐着或躺着。", False),
    ("q_energy_08", "活力充电", "energy", "我喜欢有明确完成感的短时运动。", False),
    ("q_energy_09", "活力充电", "energy", "活动身体后，我通常更容易进入放松状态。", False),
    ("q_energy_10", "活力充电", "energy", "我愿意把一部分休息时间用于身体恢复。", False),
    ("q_recovery_01", "松弛疗愈", "recovery", "我需要安静的活动来缓解工作或学习压力。", False),
    ("q_recovery_02", "松弛疗愈", "recovery", "短暂小睡能有效恢复我的精力。", False),
    ("q_recovery_03", "松弛疗愈", "recovery", "我喜欢听音乐、喝茶等低刺激活动。", False),
    ("q_recovery_04", "松弛疗愈", "recovery", "我愿意安排一段不被打扰的休息时间。", False),
    ("q_recovery_05", "松弛疗愈", "recovery", "慢走、呼吸或冥想适合我目前的状态。", False),
    ("q_recovery_06", "松弛疗愈", "recovery", "我希望空闲安排不要带来额外压力。", False),
    ("q_recovery_07", "松弛疗愈", "recovery", "整理小空间会让我感觉更平静。", False),
    ("q_recovery_08", "松弛疗愈", "recovery", "我能接受把一段空闲时间完全用于恢复。", False),
    ("q_recovery_09", "松弛疗愈", "recovery", "我更偏好节奏舒缓、步骤简单的任务。", False),
    ("q_recovery_10", "松弛疗愈", "recovery", "我通常不需要高强度刺激来获得满足感。", False),
    ("q_social_01", "社交连接", "social", "我愿意在空闲时间和熟悉的人见面。", False),
    ("q_social_02", "社交连接", "social", "和朋友聊天能让我恢复心情。", False),
    ("q_social_03", "社交连接", "social", "我喜欢和同学或同事一起完成轻量活动。", False),
    ("q_social_04", "社交连接", "social", "我愿意主动联系一位朋友或家人。", False),
    ("q_social_05", "社交连接", "social", "我可以接受临时加入一次小型聚会。", False),
    ("q_social_06", "社交连接", "social", "结伴运动或散步对我有吸引力。", False),
    ("q_social_07", "社交连接", "social", "我愿意用共同兴趣开启社交。", False),
    ("q_social_08", "社交连接", "social", "我希望计划中保留适度的社交机会。", False),
    ("q_social_09", "社交连接", "social", "低压力的陪伴比大型聚会更适合我。", False),
    ("q_social_10", "社交连接", "social", "独处时我通常不想和任何人联系。", True),
    ("q_explore_01", "乐享探索", "exploration", "我喜欢通过吃喝体验改善心情。", False),
    ("q_explore_02", "乐享探索", "exploration", "我愿意去附近发现一家新店。", False),
    ("q_explore_03", "乐享探索", "exploration", "我对短时间的轻度外出探索感兴趣。", False),
    ("q_explore_04", "乐享探索", "exploration", "逛书店、市场或小型展览对我有吸引力。", False),
    ("q_explore_05", "乐享探索", "exploration", "我愿意尝试以前没有吃过的小食。", False),
    ("q_explore_06", "乐享探索", "exploration", "我能接受为一次休闲体验支付适度预算。", False),
    ("q_explore_07", "乐享探索", "exploration", "我喜欢给周末安排一个小小的新鲜感。", False),
    ("q_explore_08", "乐享探索", "exploration", "拍照或观察街区细节能让我放松。", False),
    ("q_explore_09", "乐享探索", "exploration", "我偏好不需要复杂准备的娱乐活动。", False),
    ("q_explore_10", "乐享探索", "exploration", "空闲时间我只想待在熟悉的地方。", True),
    ("q_growth_01", "自我成长", "growth", "我愿意用空闲时间阅读或学习。", False),
    ("q_growth_02", "自我成长", "growth", "完成一个小型学习目标会让我满足。", False),
    ("q_growth_03", "自我成长", "growth", "我希望兴趣爱好能够持续积累。", False),
    ("q_growth_04", "自我成长", "growth", "我愿意尝试学习一项新技能。", False),
    ("q_growth_05", "自我成长", "growth", "整理知识或笔记对我有帮助。", False),
    ("q_growth_06", "自我成长", "growth", "我喜欢把大目标拆成短时间可以完成的任务。", False),
    ("q_growth_07", "自我成长", "growth", "创作、写作或练习乐器能让我投入。", False),
    ("q_growth_08", "自我成长", "growth", "我希望休息安排兼顾放松和一点成长。", False),
    ("q_growth_09", "自我成长", "growth", "我愿意为个人兴趣留出固定时间。", False),
    ("q_growth_10", "自我成长", "growth", "空闲时间不适合做任何需要思考的事情。", True),
]

QUESTION_BANK = [
    Question(
        id=question_id,
        category=category,
        dimension=dimension,
        prompt=prompt,
        reverse_scored=reverse_scored,
    )
    for question_id, category, dimension, prompt, reverse_scored in _QUESTION_ROWS
]


class TaskRepository:
    """提供用户同意的任务和问题"""
    
    def __init__(self, public_tasks: Optional[list[Task]] = None) -> None:
        self.public_tasks = list(public_tasks or PUBLIC_TASKS)
        self.custom_tasks: dict[str, list[Task]] = {}

    def add_custom_task(self, session_id: str, task: Task) -> Task:
        """从公共任务库中保存用户所需要的任务"""
        if not session_id:
            raise ValueError("session_id 不能为空")
        if not task.id.startswith("custom_"):
            raise ValueError("用户自定义任务 ID 必须以 custom_ 开头")
        if task.duration <= 0:
            raise ValueError("任务时长必须大于 0")
        if task.budget < 0:
            raise ValueError("任务预算不能为负数")
        if task.category not in CATEGORIES:
            raise ValueError("任务分类不在允许范围内")

        custom_task = Task(
            id=task.id,
            title=task.title,
            category=task.category,
            duration=task.duration,
            budget=task.budget,
            outing=task.outing,
            company=task.company,
            status="approved",
            owner_session_id=session_id,
            scenarios=task.scenarios,
        )
        self.custom_tasks.setdefault(session_id, []).append(custom_task)
        return custom_task

    def search_tasks(
        self,
        session_id: str,
        budget_limit: int,
        max_duration: int,
        outing: str,
        company: str,
        categories: Optional[list[str]] = None,
        scenarios: Optional[list[str]] = None,
    ) -> list[Task]:
        """返回在排除所有限制条件之后筛选出来的任务"""
        if budget_limit < 0 or max_duration <= 0:
            raise ValueError("预算上限不能为负，最大时长必须大于 0")
        if categories and any(category not in CATEGORIES for category in categories):
            raise ValueError("存在不支持的任务分类")
        if scenarios and any(scene not in SCENARIOS for scene in scenarios):
            raise ValueError("存在不支持的使用场景")

        candidates = self.public_tasks + self.custom_tasks.get(session_id, [])
        return [
            task
            for task in candidates
            if task.status == "approved"
            and task.budget <= budget_limit
            and task.duration <= max_duration
            and self._matches_outing(task, outing)
            and self._matches_company(task, company)
            and (not categories or task.category in categories)
            and (not scenarios or set(task.scenarios).intersection(scenarios))
        ]

    def get_questions(
        self,
        categories: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[Question]:
        """返回在questionnaire module中筛选出来的问题"""
        if limit <= 0:
            raise ValueError("题目数量必须大于 0")
        if categories and any(category not in CATEGORIES for category in categories):
            raise ValueError("存在不支持的题目分类")
        questions = [
            question
            for question in QUESTION_BANK
            if question.status == "approved"
            and (not categories or question.category in categories)
        ]
        return questions[:limit]

"""判断任务是否符合出行范围和同行方式"""
    @staticmethod
    def _matches_outing(task: Task, user_outing: str) -> bool:
        allowed = {
            "home": {"home"},
            "nearby": {"home", "nearby"},
            "city": {"home", "nearby", "city"},
            "any": {"home", "nearby", "city"},
        }
        if user_outing not in allowed:
            raise ValueError(f"不支持的出行方式: {user_outing}")
        return task.outing in allowed[user_outing]

    @staticmethod
    def _matches_company(task: Task, user_company: str) -> bool:
        if user_company not in {"solo", "group", "both"}:
            raise ValueError(f"不支持的同行方式: {user_company}")
        return user_company == "both" or task.company in {user_company, "both"}


def demo() -> None:

    category_counts = Counter(task.category for task in PUBLIC_TASKS)
    question_counts = Counter(question.category for question in QUESTION_BANK)
    assert len(PUBLIC_TASKS) == 50
    assert len(QUESTION_BANK) == 50
    assert category_counts == {category: 10 for category in CATEGORIES}
    assert question_counts == {category: 10 for category in CATEGORIES}
    assert all(task.status == "approved" for task in PUBLIC_TASKS)
    assert all(question.status == "approved" for question in QUESTION_BANK)

    repository = TaskRepository()
    session_id = "session_001"
    repository.add_custom_task(
        session_id,
        Task(
            id="custom_reading",
            title="阅读一本喜欢的书",
            category="自我成长",
            duration=45,
            budget=0,
            outing="home",
            company="solo",
            scenarios=("想独处但不想完全躺平",),
        ),
    )

    candidates = repository.search_tasks(
        session_id=session_id,
        budget_limit=50,
        max_duration=90,
        outing="nearby",
        company="solo",
        categories=["活力充电", "松弛疗愈", "乐享探索", "自我成长"],
        scenarios=["工作后精力不足", "想独处但不想完全躺平"],
    )
    questions = repository.get_questions(
        categories=["活力充电", "松弛疗愈"],
        limit=20,
    )

    assert any(task.id == "custom_reading" for task in candidates)"""检查用户自定义的任务有没有被查询到"""
    assert all(task.status == "approved" for task in candidates)"""检查所有候选任务都被审核过"""
    assert len(questions) == 20"""检查题目数量""""
    assert all(question.category in {"活力充电", "松弛疗愈"} for question in questions)"""检查题目分类是否正确"""

    print(f"公共活动数量: {len(PUBLIC_TASKS)}")
    print(f"五类活动数量: {dict(category_counts)}")
    print(f"题目数量: {len(QUESTION_BANK)}")
    print("符合当前场景和约束的候选活动:")
    for task in candidates:
        print(f"- {task.id}: {task.title} ({task.duration} 分钟, {task.budget} 元)")
    print(f"筛选出的问卷题目数量: {len(questions)}")


if __name__ == "__main__":
    demo()
