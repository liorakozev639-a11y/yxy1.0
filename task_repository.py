"""Task Repository MVP example.

This file contains an in-memory public task bank, user custom tasks, and a
reviewed questionnaire bank. It runs without PostgreSQL, FastAPI, MQ,
asynchronous workers, maps, merchants, or live activity APIs.
"""

"""当前任务库以人工审核的通用任务为主，暂不依赖实时商户、地点或营业时间搜索。
五个类别各维护 60 个任务，共 300 个任务；任务会按预算、时长、出行、同行方式和使用场景过滤，
再交给 Recommendation Module 按问卷画像排序。问卷题目由 Questionnaire Module 独立维护，
用于 quick 和 deep 模式的偏好画像与推荐。"""

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

LOCATION_DEPENDENCIES = {"home", "nearby", "city", "flexible"}


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
    feedback_group: str = ""
    ease_level: int = 3
    physical_load: int = 3
    social_pressure: int = 3
    location_dependency: str = "flexible"

    def __post_init__(self) -> None:
        if not 1 <= self.ease_level <= 5:
            raise ValueError("任务轻松度必须在 1-5 之间")
        if not 1 <= self.physical_load <= 5:
            raise ValueError("任务体力消耗必须在 1-5 之间")
        if not 1 <= self.social_pressure <= 5:
            raise ValueError("任务社交压力必须在 1-5 之间")
        if self.location_dependency not in LOCATION_DEPENDENCIES:
            raise ValueError("任务地点依赖不在允许范围内")


# Each category contains exactly thirty activities. The scenario tags allow the
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
    ("task_energy_11", "晨间舒展唤醒身体", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_12", "跟着节拍做低冲击有氧", "活力充电", 25, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_13", "楼下绕行轻松散步", "活力充电", 30, 0, "nearby", "both", ("突然获得半天休息时间", "临时改变想法")),
    ("task_energy_14", "完成一组深蹲和俯身划船替代练习", "活力充电", 30, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_energy_15", "去开阔处晒太阳走动", "活力充电", 35, 0, "nearby", "both", ("工作后精力不足", "突然获得半天休息时间")),
    ("task_energy_16", "做一轮手腕脚踝灵活训练", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_17", "跟练一套站姿燃脂操", "活力充电", 35, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_energy_18", "去操场或步道慢跑", "活力充电", 45, 0, "nearby", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_19", "完成一次舒缓普拉提", "活力充电", 40, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_20", "做十分钟靠墙静蹲挑战", "活力充电", 15, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_21", "沿固定路线快走听歌", "活力充电", 45, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_energy_22", "进行一轮全身拉伸放松", "活力充电", 25, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_23", "和同伴打一场轻量球类运动", "活力充电", 60, 20, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_energy_24", "做台阶上下来回训练", "活力充电", 20, 0, "nearby", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_25", "在室内完成跳绳替代步伐", "活力充电", 20, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_26", "安排一次轻松骑行", "活力充电", 75, 0, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_27", "做肩背打开和胸椎伸展", "活力充电", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_28", "用计步目标完成一次散步", "活力充电", 50, 0, "nearby", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_energy_29", "跟练一套睡前舒缓瑜伽", "活力充电", 30, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_30", "做一次低强度循环训练", "活力充电", 40, 0, "home", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_recovery_01", "做五分钟呼吸练习", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_02", "小睡二十分钟", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_03", "泡脚并听舒缓音乐", "松弛疗愈", 30, 20, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_04", "在家看一部轻松电影", "松弛疗愈", 120, 30, "home", "solo", ("周末不知道做什么", "临时改变想法")),
    ("task_recovery_05", "去公园慢走并观察树木", "松弛疗愈", 50, 0, "nearby", "both", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_recovery_06", "写一页情绪日记", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_07", "泡一杯茶并完整休息半小时", "松弛疗愈", 30, 10, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_08", "进行十分钟正念冥想", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_09", "整理房间中的一个小区域", "松弛疗愈", 25, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_recovery_10", "两小时手机免打扰休息", "松弛疗愈", 120, 0, "home", "solo", ("周末不知道做什么", "工作后精力不足")),
    ("task_recovery_11", "做一轮腹式呼吸放松", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_12", "听白噪音闭眼休息", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_13", "给自己做一次热敷护理", "松弛疗愈", 25, 10, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_14", "在安静角落阅读轻松散文", "松弛疗愈", 45, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_recovery_15", "去公园坐着观察云和行人", "松弛疗愈", 45, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_recovery_16", "整理一天的待办并删减压力项", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_17", "泡一杯无咖啡因饮品慢慢喝", "松弛疗愈", 25, 15, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_18", "做一次身体扫描冥想", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_19", "清理桌面并点亮一盏暖光灯", "松弛疗愈", 20, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_recovery_20", "写下三件今天还不错的小事", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_21", "泡澡或温水淋浴放松", "松弛疗愈", 35, 10, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_22", "在窗边晒太阳不看手机", "松弛疗愈", 25, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_23", "做一次轻量香氛或空间整理", "松弛疗愈", 30, 20, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_recovery_24", "听一张完整的舒缓专辑", "松弛疗愈", 50, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_25", "沿安静路线散步不设目标", "松弛疗愈", 40, 0, "nearby", "solo", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_recovery_26", "给植物浇水并整理阳台", "松弛疗愈", 25, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_recovery_27", "做一次眼部休息和远眺", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_28", "给自己安排一段安静午茶", "松弛疗愈", 40, 20, "home", "solo", ("周末不知道做什么", "工作后精力不足")),
    ("task_recovery_29", "用纸笔写下当前压力来源", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_30", "在公园长椅完成十分钟放空", "松弛疗愈", 30, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
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
    ("task_social_11", "和朋友一起做晚间散步", "社交连接", 45, 0, "nearby", "group", ("工作后精力不足", "临时改变想法")),
    ("task_social_12", "邀请同伴一起整理房间", "社交连接", 60, 0, "home", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_social_13", "和家人一起看一集轻松节目", "社交连接", 50, 0, "home", "group", ("工作后精力不足", "临时改变想法")),
    ("task_social_14", "约一位朋友喝热饮聊天", "社交连接", 60, 40, "nearby", "group", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_social_15", "和同学交换一本推荐读物", "社交连接", 45, 0, "nearby", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_social_16", "组一次线上语音近况局", "社交连接", 45, 0, "home", "group", ("临时改变想法", "工作后精力不足")),
    ("task_social_17", "和朋友一起完成低强度运动", "社交连接", 60, 0, "nearby", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_18", "给朋友寄出一段感谢文字", "社交连接", 20, 0, "home", "group", ("工作后精力不足", "临时改变想法")),
    ("task_social_19", "和同伴一起逛书店", "社交连接", 75, 30, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_20", "安排一次家庭小茶话", "社交连接", 60, 30, "home", "group", ("周末不知道做什么", "工作后精力不足")),
    ("task_social_21", "和朋友互相推荐三首歌", "社交连接", 30, 0, "home", "group", ("临时改变想法", "工作后精力不足")),
    ("task_social_22", "一起准备一顿简单轻食", "社交连接", 80, 60, "home", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_23", "约同伴完成一次拍照散步", "社交连接", 80, 0, "nearby", "group", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_social_24", "和朋友玩一次轻量协作游戏", "社交连接", 60, 0, "home", "group", ("临时改变想法", "周末不知道做什么")),
    ("task_social_25", "向家人请教一道拿手菜", "社交连接", 60, 40, "home", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_social_26", "和同学互相复盘一周收获", "社交连接", 45, 0, "nearby", "group", ("工作后精力不足", "周末不知道做什么")),
    ("task_social_27", "找朋友一起完成咖啡散步", "社交连接", 75, 40, "nearby", "group", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_social_28", "参加一次小范围兴趣交流", "社交连接", 90, 20, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_29", "和朋友互相整理愿望清单", "社交连接", 45, 0, "home", "group", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_social_30", "约同伴去公园坐坐聊天", "社交连接", 60, 0, "nearby", "group", ("工作后精力不足", "突然获得半天休息时间")),
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
    ("task_explore_11", "尝试一款新的自制饮品", "乐享探索", 35, 20, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_explore_12", "去附近面包房买一份早餐", "乐享探索", 45, 35, "nearby", "both", ("突然获得半天休息时间", "临时改变想法")),
    ("task_explore_13", "沿街区寻找有趣橱窗", "乐享探索", 50, 0, "nearby", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_explore_14", "在家办一次主题观影小场", "乐享探索", 110, 30, "home", "both", ("周末不知道做什么", "工作后精力不足")),
    ("task_explore_15", "去公园完成一次自然观察", "乐享探索", 60, 0, "nearby", "solo", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_explore_16", "给自己安排一顿慢速午餐", "乐享探索", 75, 60, "nearby", "both", ("周末不知道做什么", "工作后精力不足")),
    ("task_explore_17", "尝试一种没喝过的茶饮", "乐享探索", 40, 30, "nearby", "both", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_explore_18", "用半小时整理喜欢的歌单", "乐享探索", 30, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_19", "做一次随机主题拍照练习", "乐享探索", 50, 0, "nearby", "solo", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_explore_20", "在家制作一份简单甜品", "乐享探索", 70, 40, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_21", "去附近便利点买一份小惊喜", "乐享探索", 30, 25, "nearby", "both", ("临时改变想法", "工作后精力不足")),
    ("task_explore_22", "参观公共文化空间", "乐享探索", 100, 20, "city", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_explore_23", "选择一条没走过的近路散步", "乐享探索", 55, 0, "nearby", "solo", ("想独处但不想完全躺平", "突然获得半天休息时间")),
    ("task_explore_24", "做一次三十分钟手账拼贴", "乐享探索", 45, 20, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_explore_25", "去书架前随机挑一本翻读", "乐享探索", 40, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_26", "在附近买一份季节水果", "乐享探索", 45, 35, "nearby", "both", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_explore_27", "安排一次轻量桌面游戏", "乐享探索", 60, 0, "home", "both", ("周末不知道做什么", "临时改变想法")),
    ("task_explore_28", "听一集城市故事类节目", "乐享探索", 45, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_29", "去附近绿地完成一次野餐替代", "乐享探索", 80, 50, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_explore_30", "给今天设计一个微型主题路线", "乐享探索", 60, 20, "nearby", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
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
    ("task_growth_11", "阅读一篇长文章并摘录三句", "自我成长", 35, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_growth_12", "学习一个办公软件小技巧", "自我成长", 30, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_13", "整理一个课程或项目文件夹", "自我成长", 30, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_14", "完成一次二十分钟专注阅读", "自我成长", 25, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_growth_15", "练习一页字帖或手写笔记", "自我成长", 30, 10, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_16", "看一节公开课并写三点收获", "自我成长", 60, 0, "home", "solo", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_growth_17", "复盘一个最近遇到的小问题", "自我成长", 25, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_18", "为兴趣技能制定七天练习表", "自我成长", 35, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_growth_19", "学习一种简单拍照构图方法", "自我成长", 40, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_growth_20", "做一次十五分钟口语跟读", "自我成长", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_21", "整理三条个人经验卡片", "自我成长", 30, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_growth_22", "完成一个算法或逻辑小题", "自我成长", 45, 0, "home", "solo", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_growth_23", "学习一道简单菜谱的步骤", "自我成长", 35, 30, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_24", "制作一页个人灵感板", "自我成长", 45, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_growth_25", "为未来一个月列三件想尝试的事", "自我成长", 25, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_26", "完成一次轻量知识复习", "自我成长", 40, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_growth_27", "写一段给未来自己的备忘", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_28", "练习三十分钟绘画或手工", "自我成长", 45, 20, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_growth_29", "整理个人简历或作品集一小段", "自我成长", 50, 0, "home", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_growth_30", "学习一个生活管理方法并试用", "自我成长", 35, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_energy_31", "晨间八分钟关节唤醒", "活力充电", 10, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_energy_32", "室内踏步听播客", "活力充电", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_33", "在公园做一轮拉伸", "活力充电", 30, 0, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_34", "练习平衡与核心动作", "活力充电", 20, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_energy_35", "骑共享单车短途绕行", "活力充电", 35, 5, "nearby", "both", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_energy_36", "做十分钟拳击操", "活力充电", 15, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_37", "在楼下走一段上坡路", "活力充电", 20, 0, "nearby", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_38", "跟练坐姿拉伸", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_39", "尝试一轮轻器械训练", "活力充电", 30, 0, "home", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_40", "完成一次散步打卡", "活力充电", 30, 0, "nearby", "both", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_recovery_31", "做一杯热可可慢慢喝", "松弛疗愈", 20, 15, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_32", "给眼睛做十分钟闭目休息", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_33", "听一张完整的轻音乐专辑", "松弛疗愈", 40, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_recovery_34", "做一次香氛或护手护理", "松弛疗愈", 20, 20, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_35", "看窗外发呆十分钟", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_36", "整理床铺后休息", "松弛疗愈", 15, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_recovery_37", "去附近长椅坐一会", "松弛疗愈", 25, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_recovery_38", "完成一段渐进式肌肉放松", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_39", "泡一次温水澡", "松弛疗愈", 30, 15, "home", "solo", ("周末不知道做什么", "工作后精力不足")),
    ("task_recovery_40", "写下三件今天不必完成的事", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_social_31", "给老朋友发一条近况消息", "社交连接", 10, 0, "home", "both", ("临时改变想法", "工作后精力不足")),
    ("task_social_32", "和同学约一次校园散步", "社交连接", 40, 0, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_33", "与家人视频通话十五分钟", "社交连接", 15, 0, "home", "both", ("工作后精力不足", "临时改变想法")),
    ("task_social_34", "和朋友分享一首歌", "社交连接", 10, 0, "home", "both", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_social_35", "约人一起吃简单早餐", "社交连接", 45, 30, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_36", "参加一次两三人的桌游", "社交连接", 60, 0, "home", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_37", "向朋友表达一次感谢", "社交连接", 10, 0, "home", "both", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_social_38", "和室友做一顿简单晚饭", "社交连接", 60, 40, "home", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_39", "约熟人一起逛校园或街区", "社交连接", 45, 0, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_40", "和家人聊一件开心的小事", "社交连接", 15, 0, "home", "both", ("工作后精力不足", "临时改变想法")),
    ("task_explore_31", "去附近买一份喜欢的小点心", "乐享探索", 25, 20, "nearby", "both", ("临时改变想法", "周末不知道做什么")),
    ("task_explore_32", "尝试一款新口味茶饮", "乐享探索", 30, 20, "nearby", "both", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_explore_33", "看一集轻松综艺", "乐享探索", 45, 0, "home", "both", ("工作后精力不足", "临时改变想法")),
    ("task_explore_34", "逛一次书店或文创店", "乐享探索", 50, 30, "nearby", "both", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_explore_35", "玩二十分钟休闲游戏", "乐享探索", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_36", "在街区拍三张有趣照片", "乐享探索", 30, 0, "nearby", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_explore_37", "尝试做一份水果酸奶碗", "乐享探索", 25, 25, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_explore_38", "看一场线上直播回放", "乐享探索", 50, 0, "home", "both", ("周末不知道做什么", "工作后精力不足")),
    ("task_explore_39", "去便利店选一件没买过的小零食", "乐享探索", 20, 15, "nearby", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_explore_40", "参观一个免费的校园展览或公共空间", "乐享探索", 45, 0, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_growth_31", "抄写一段喜欢的文字", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_growth_32", "整理十个常用电脑文件", "自我成长", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_33", "练习十分钟速写", "自我成长", 15, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_growth_34", "学一个常用快捷键", "自我成长", 10, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_35", "写一页旅行或生活计划", "自我成长", 25, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_growth_36", "听一节短知识播客并记笔记", "自我成长", 30, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_growth_37", "完成一轮单词复习", "自我成长", 20, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_38", "为正在学的课程列三个问题", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_39", "练习一首简单乐器片段", "自我成长", 25, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_growth_40", "整理一本待读书单", "自我成长", 20, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_41", "做一组五分钟唤醒操", "活力充电", 10, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_42", "沿小区慢走一圈", "活力充电", 20, 0, "nearby", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_43", "练习一轮肩颈舒展", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_44", "做一次轻量瑜伽流动", "活力充电", 30, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_energy_45", "去楼下晒太阳并散步", "活力充电", 25, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_energy_46", "完成一轮低强度深蹲", "活力充电", 15, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_energy_47", "在公园慢走并听音乐", "活力充电", 35, 0, "nearby", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_energy_48", "尝试十分钟节奏操", "活力充电", 15, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_energy_49", "做一组手腕和手臂放松", "活力充电", 10, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_50", "骑车去附近买饮品", "活力充电", 35, 20, "nearby", "solo", ("突然获得半天休息时间", "临时改变想法")),
    ("task_energy_51", "完成一次楼梯慢走练习", "活力充电", 15, 0, "nearby", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_52", "做一轮站立平衡练习", "活力充电", 15, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_energy_53", "在窗边做呼吸与伸展", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_energy_54", "和同伴进行轻松投篮", "活力充电", 45, 0, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_energy_55", "完成一次短时跳舞练习", "活力充电", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_energy_56", "沿河边或绿道散步", "活力充电", 45, 0, "nearby", "both", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_energy_57", "做一组温和核心激活", "活力充电", 20, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_energy_58", "跟着音乐做手臂操", "活力充电", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_energy_59", "去附近广场慢走观察", "活力充电", 30, 0, "nearby", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_energy_60", "完成一次睡前舒缓拉伸", "活力充电", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_41", "泡一杯温热花草茶", "松弛疗愈", 15, 20, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_42", "做一段五分钟呼吸练习", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_43", "听窗外声音放空一会", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_44", "换上舒适衣服休息", "松弛疗愈", 15, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_recovery_45", "做一次简单足部放松", "松弛疗愈", 20, 10, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_46", "整理一个舒适的休息角落", "松弛疗愈", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_recovery_47", "在阳台安静晒太阳", "松弛疗愈", 20, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_recovery_48", "做一次三分钟眼部放松", "松弛疗愈", 10, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_49", "读几页轻松散文", "松弛疗愈", 20, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_recovery_50", "听一段自然环境音", "松弛疗愈", 15, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_51", "做一次温和肩颈热敷", "松弛疗愈", 20, 15, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_52", "关掉通知安静休息一会", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_53", "写下此刻最想放下的事", "松弛疗愈", 15, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_recovery_54", "做一套舒缓睡前动作", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_recovery_55", "去安静街角坐一坐", "松弛疗愈", 25, 0, "nearby", "solo", ("突然获得半天休息时间", "工作后精力不足")),
    ("task_recovery_56", "看一段低刺激风景视频", "松弛疗愈", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_recovery_57", "给自己准备一份水果", "松弛疗愈", 15, 20, "nearby", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_recovery_58", "完成一次身体扫描冥想", "松弛疗愈", 15, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_recovery_59", "慢慢收拾并擦拭书桌", "松弛疗愈", 25, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_recovery_60", "听喜欢的歌曲并闭目休息", "松弛疗愈", 20, 0, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_social_41", "给朋友发一张近况照片", "社交连接", 10, 0, "home", "both", ("临时改变想法", "工作后精力不足")),
    ("task_social_42", "和同学互相分享午餐灵感", "社交连接", 15, 0, "home", "both", ("临时改变想法", "周末不知道做什么")),
    ("task_social_43", "和家人一起看一集节目", "社交连接", 45, 0, "home", "group", ("工作后精力不足", "周末不知道做什么")),
    ("task_social_44", "约朋友线上玩一局小游戏", "社交连接", 30, 0, "home", "both", ("临时改变想法", "周末不知道做什么")),
    ("task_social_45", "和室友一起买饮品散步", "社交连接", 30, 20, "nearby", "group", ("工作后精力不足", "周末不知道做什么")),
    ("task_social_46", "参加一次轻松线上分享", "社交连接", 45, 0, "home", "group", ("周末不知道做什么", "临时改变想法")),
    ("task_social_47", "和朋友交换一条歌单", "社交连接", 15, 0, "home", "both", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_social_48", "和同伴一起做简单拉伸", "社交连接", 20, 0, "home", "group", ("工作后精力不足", "周末不知道做什么")),
    ("task_social_49", "给久未联系的人留言", "社交连接", 10, 0, "home", "both", ("临时改变想法", "工作后精力不足")),
    ("task_social_50", "和家人聊聊最近的小发现", "社交连接", 20, 0, "home", "both", ("工作后精力不足", "周末不知道做什么")),
    ("task_social_51", "和朋友进行一次轻松问答", "社交连接", 25, 0, "home", "both", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_social_52", "约同学在校园坐坐", "社交连接", 40, 0, "nearby", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_53", "一起完成一份简单拼图", "社交连接", 45, 30, "home", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_social_54", "和朋友互相推荐一部电影", "社交连接", 15, 0, "home", "both", ("临时改变想法", "工作后精力不足")),
    ("task_social_55", "和室友一起整理公共区域", "社交连接", 30, 0, "home", "group", ("临时改变想法", "周末不知道做什么")),
    ("task_social_56", "与同伴进行一次短途散步", "社交连接", 35, 0, "nearby", "group", ("工作后精力不足", "突然获得半天休息时间")),
    ("task_social_57", "给家人发一段语音问候", "社交连接", 10, 0, "home", "both", ("临时改变想法", "工作后精力不足")),
    ("task_social_58", "和朋友一起做一杯饮品", "社交连接", 30, 20, "home", "group", ("周末不知道做什么", "临时改变想法")),
    ("task_social_59", "参加一次小组兴趣练习", "社交连接", 50, 0, "home", "group", ("周末不知道做什么", "突然获得半天休息时间")),
    ("task_social_60", "和熟人分享本周一件开心事", "社交连接", 15, 0, "home", "both", ("工作后精力不足", "临时改变想法")),
    ("task_explore_41", "尝试一种新的早餐搭配", "乐享探索", 30, 30, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_explore_42", "去附近寻找一面有趣的墙", "乐享探索", 35, 0, "nearby", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_43", "做一份随机水果拼盘", "乐享探索", 25, 25, "home", "both", ("临时改变想法", "周末不知道做什么")),
    ("task_explore_44", "听一集新主题播客", "乐享探索", 45, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_explore_45", "逛一圈附近文具店", "乐享探索", 40, 30, "nearby", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_explore_46", "在家尝试一种新调味", "乐享探索", 30, 15, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_explore_47", "拍摄五张身边的几何图案", "乐享探索", 40, 0, "nearby", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_explore_48", "随机选择一部短纪录片", "乐享探索", 50, 0, "home", "both", ("工作后精力不足", "周末不知道做什么")),
    ("task_explore_49", "去附近公园寻找一处新角落", "乐享探索", 45, 0, "nearby", "solo", ("突然获得半天休息时间", "想独处但不想完全躺平")),
    ("task_explore_50", "制作一份主题零食组合", "乐享探索", 35, 40, "home", "both", ("周末不知道做什么", "临时改变想法")),
    ("task_explore_51", "找一条新路线回家", "乐享探索", 35, 0, "nearby", "solo", ("临时改变想法", "突然获得半天休息时间")),
    ("task_explore_52", "体验一次线上虚拟展览", "乐享探索", 60, 0, "home", "both", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_53", "为房间拍一组主题照片", "乐享探索", 30, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_explore_54", "尝试一种新的无酒精饮品", "乐享探索", 30, 25, "nearby", "both", ("工作后精力不足", "临时改变想法")),
    ("task_explore_55", "去附近观察季节变化", "乐享探索", 40, 0, "nearby", "solo", ("突然获得半天休息时间", "周末不知道做什么")),
    ("task_explore_56", "给熟悉的歌单换个主题", "乐享探索", 25, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_explore_57", "安排一次小型家庭观影", "乐享探索", 90, 30, "home", "group", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_explore_58", "买一份没尝试过的水果", "乐享探索", 30, 30, "nearby", "both", ("临时改变想法", "工作后精力不足")),
    ("task_explore_59", "做一次五分钟创意涂鸦", "乐享探索", 20, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_explore_60", "为今天设计一个小主题", "乐享探索", 20, 0, "home", "solo", ("临时改变想法", "周末不知道做什么")),
    ("task_growth_41", "整理一页近期想法", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_42", "学习一个键盘快捷操作", "自我成长", 10, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_43", "阅读一篇短科普文章", "自我成长", 25, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_growth_44", "复盘一次最近的沟通", "自我成长", 20, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_45", "练习一段英文听力", "自我成长", 30, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_growth_46", "整理一份个人灵感清单", "自我成长", 25, 0, "home", "solo", ("周末不知道做什么", "想独处但不想完全躺平")),
    ("task_growth_47", "完成一个十分钟逻辑练习", "自我成长", 15, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_48", "写下三个想继续保持的习惯", "自我成长", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_49", "学习一个简单构图技巧", "自我成长", 25, 0, "home", "solo", ("想独处但不想完全躺平", "周末不知道做什么")),
    ("task_growth_50", "整理一份数字资料收藏", "自我成长", 30, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_51", "为一个小目标写行动第一步", "自我成长", 15, 0, "home", "solo", ("临时改变想法", "想独处但不想完全躺平")),
    ("task_growth_52", "完成一页轻量练字", "自我成长", 25, 10, "home", "solo", ("工作后精力不足", "想独处但不想完全躺平")),
    ("task_growth_53", "学习一道简单菜的原理", "自我成长", 30, 20, "home", "solo", ("临时改变想法", "周末不知道做什么")),
    ("task_growth_54", "把一个大任务拆成三步", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_55", "听一段知识音频并记一句话", "自我成长", 20, 0, "home", "solo", ("想独处但不想完全躺平", "工作后精力不足")),
    ("task_growth_56", "写一段给自己的鼓励", "自我成长", 15, 0, "home", "solo", ("工作后精力不足", "临时改变想法")),
    ("task_growth_57", "整理一次电脑桌面", "自我成长", 25, 0, "home", "solo", ("临时改变想法", "工作后精力不足")),
    ("task_growth_58", "练习一小段绘画线条", "自我成长", 20, 10, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
    ("task_growth_59", "为下周准备一个提醒清单", "自我成长", 20, 0, "home", "solo", ("工作后精力不足", "周末不知道做什么")),
    ("task_growth_60", "阅读并摘录一段喜欢的话", "自我成长", 25, 0, "home", "solo", ("想独处但不想完全躺平", "临时改变想法")),
]


FEEDBACK_GROUPS = {
    "活力充电": (
        "energy_mobility_home", "energy_low_impact_home", "energy_mobility_outdoor",
        "energy_core_balance", "energy_light_cycling", "energy_rhythm_cardio",
        "energy_brisk_walk", "energy_strength_light",
    ),
    "松弛疗愈": (
        "recovery_quiet_home", "recovery_warm_drink", "recovery_music_rest",
        "recovery_self_care", "recovery_light_tidy", "recovery_quiet_outdoor",
        "recovery_body_relax", "recovery_pressure_release",
    ),
    "社交连接": (
        "social_light_contact", "social_small_group", "social_family_contact",
        "social_meal_together", "social_walk_together", "social_game_together",
    ),
    "乐享探索": (
        "explore_food_drink", "explore_screen_entertainment", "explore_local_browse",
        "explore_game_relax", "explore_photo_walk", "explore_food_make",
    ),
    "自我成长": (
        "growth_reading_writing", "growth_digital_organize", "growth_creative_practice",
        "growth_skill_micro", "growth_planning", "growth_learning_audio",
        "growth_language_practice", "growth_learning_review",
    ),
}


def feedback_group_for(task_id: str, category: str) -> str:
    groups = FEEDBACK_GROUPS[category]
    return groups[(int(task_id.rsplit("_", 1)[1]) - 1) % len(groups)]


def _clamp_level(value: int) -> int:
    return max(1, min(5, value))


def infer_task_load(
    title: str,
    category: str,
    duration: int,
    budget: int,
    outing: str,
    company: str,
) -> dict[str, int | str]:
    """Infer task intensity metadata from the existing curated task bank."""
    high_physical_keywords = (
        "训练", "慢跑", "快走", "骑行", "球", "燃脂", "跳绳", "台阶", "爬楼梯",
        "拳击操", "静蹲", "有氧", "核心", "坡道",
    )
    low_physical_keywords = (
        "拉伸", "舒展", "舒缓", "冥想", "呼吸", "小睡", "放空", "听", "阅读",
        "热敷", "泡脚", "晒太阳", "写下", "闭眼", "闭目", "发呆",
    )

    physical = 2
    if category == "活力充电":
        physical = 3
    if any(keyword in title for keyword in high_physical_keywords):
        physical += 1
    if any(keyword in title for keyword in low_physical_keywords):
        physical -= 1
    if duration >= 60 and category in {"活力充电", "社交连接", "乐享探索"}:
        physical += 1
    physical_load = _clamp_level(physical)

    if duration <= 15:
        ease = 5
    elif duration <= 30:
        ease = 4
    elif duration <= 60:
        ease = 3
    elif duration <= 90:
        ease = 2
    else:
        ease = 1
    if category == "松弛疗愈":
        ease += 1
    if outing == "home":
        ease += 1
    if outing == "city":
        ease -= 1
    if company == "group":
        ease -= 1
    if budget > 60:
        ease -= 1
    if physical_load >= 4:
        ease -= 1
    ease_level = _clamp_level(ease)

    if company == "solo":
        social = 1
    elif company == "both":
        social = 2
    else:
        social = 4
    if category == "社交连接" and company == "group":
        social += 1
    social_pressure = _clamp_level(social)

    location_dependency = outing if outing in {"home", "nearby", "city"} else "flexible"
    return {
        "ease_level": ease_level,
        "physical_load": physical_load,
        "social_pressure": social_pressure,
        "location_dependency": location_dependency,
    }


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
        feedback_group=feedback_group_for(task_id, category),
        **infer_task_load(title, category, duration, budget, outing, company),
    )
    for task_id, title, category, duration, budget, outing, company, scenarios
    in _ACTIVITY_ROWS
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
            feedback_group=task.feedback_group or f"custom:{task.id}",
            ease_level=task.ease_level,
            physical_load=task.physical_load,
            social_pressure=task.social_pressure,
            location_dependency=task.location_dependency,
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
    assert len(PUBLIC_TASKS) == 300
    assert category_counts == {category: 60 for category in CATEGORIES}
    assert all(task.status == "approved" for task in PUBLIC_TASKS)

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
    assert any(task.id == "custom_reading" for task in candidates)
    assert all(task.status == "approved" for task in candidates)

    print(f"公共活动数量: {len(PUBLIC_TASKS)}")
    print(f"五类活动数量: {dict(category_counts)}")
    print("符合当前场景和约束的候选活动:")
    for task in candidates:
        print(f"- {task.id}: {task.title} ({task.duration} 分钟, {task.budget} 元)")


if __name__ == "__main__":
    demo()
