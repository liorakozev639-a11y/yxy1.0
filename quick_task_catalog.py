"""Manually reviewed task-bank entries that need no preparation to start."""

from task_repository import Task


QUICK_FIRST_ACTIONS: dict[str, str] = {
    "task_recovery_01": "坐稳，把双脚放在地上，缓慢呼吸一次。",
    "task_recovery_02": "找个安全舒适的位置坐下或躺下。",
    "task_recovery_08": "坐稳，注意到自己当下的一次呼吸。",
    "task_recovery_11": "放松肩膀，尝试缓慢地用腹部呼吸。",
    "task_recovery_18": "坐稳，先觉察双脚与地面的接触。",
    "task_recovery_32": "闭上眼睛，先让视线离开屏幕。",
    "task_recovery_100": "走到窗边，看看此刻的天空。",
    "task_recovery_126": "播放一首熟悉的歌，先注意一次呼吸。",
    "task_energy_01": "站稳，先轻轻活动肩膀和颈部。",
    "task_energy_06": "站稳，缓慢转动肩膀一次。",
    "task_energy_11": "起身站稳，先做一次温和伸展。",
    "task_energy_16": "轻轻转动手腕与脚踝各一次。",
    "task_energy_22": "站在原地，缓慢伸展上肢一次。",
    "task_energy_27": "放松肩膀，轻轻打开胸口。",
}


def quick_metadata(task: Task) -> str | None:
    return QUICK_FIRST_ACTIONS.get(task.id)
