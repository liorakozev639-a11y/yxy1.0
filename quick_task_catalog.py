"""Low-friction task-bank entries for the quick recommendation mode."""

from task_repository import Task


QUICK_FIRST_ACTIONS: dict[str, str] = {
    "task_recovery_01": "坐稳，把双脚放在地上，缓慢呼吸一次。",
    "task_recovery_02": "找个安全舒适的位置坐下或躺下。",
    "task_recovery_08": "坐稳，注意到自己当下的一次呼吸。",
    "task_recovery_11": "放松肩膀，尝试缓慢地用腹部呼吸。",
    "task_recovery_18": "坐稳，先觉察双脚与地面的接触。",
    "task_recovery_32": "闭上眼睛，先让视线离开屏幕。",
    "task_energy_01": "站稳，先轻轻活动肩膀和颈部。",
    "task_energy_06": "站稳，缓慢转动肩膀一次。",
    "task_energy_11": "起身站稳，先做一次温和伸展。",
    "task_energy_16": "轻轻转动手腕与脚踝各一次。",
    "task_energy_22": "站在原地，缓慢伸展上肢一次。",
    "task_energy_27": "放松肩膀，轻轻打开胸口。",
    "task_energy_31": "站稳，活动一下手腕和脚踝。",
    "task_energy_32": "在原地慢慢踏步十次。",
    "task_energy_38": "站稳，缓慢抬起并放下双臂一次。",
    "task_energy_43": "放松肩膀，做一次轻柔的颈部伸展。",
    "task_energy_53": "坐稳，先伸展一下双臂和背部。",
    "task_energy_60": "找一个舒服的位置，放慢呼吸一次。",
    "task_energy_66": "站稳，把双脚踩实地面。",
    "task_energy_72": "站稳，缓慢伸展一下上肢。",
    "task_energy_78": "先站起来，做一次不费力的原地活动。",
    "task_energy_82": "站稳，轻轻活动一下肩颈。",
    "task_energy_87": "站稳，缓慢拉伸一下手臂。",
    "task_energy_91": "站稳，做一次短暂的舒展。",
    "task_energy_113": "站稳，先感受双脚与地面的接触。",
    "task_energy_132": "放松肩膀，缓慢呼吸一次。",
    "task_energy_140": "站稳，做一次轻柔的全身伸展。",
    "task_recovery_42": "坐稳，把注意力放在一次缓慢呼吸上。",
    "task_recovery_43": "坐稳，先让肩膀自然放下。",
    "task_recovery_44": "先把手机放在一旁，做一次深呼吸。",
    "task_recovery_46": "找一个舒服的位置坐下，放慢呼吸。",
    "task_recovery_47": "走到窗边，停下来感受一下光线。",
    "task_recovery_48": "坐稳，轻轻闭上眼睛三秒钟。",
    "task_recovery_49": "拿起纸笔或打开备忘录，写下第一个词。",
    "task_recovery_50": "坐稳，先听一小段自然声音。",
    "task_recovery_52": "先关闭一条不重要的通知。",
    "task_recovery_53": "打开备忘录，写下此刻的一句话。",
    "task_recovery_54": "找个舒服的位置，缓慢呼吸一次。",
    "task_recovery_56": "坐稳，打开一段让人放松的声音。",
    "task_recovery_58": "坐稳，注意一次完整的呼吸。",
    "task_recovery_59": "从眼前最小的一件物品开始整理。",
    "task_recovery_60": "打开一首喜欢的歌，先听十秒。",
    "task_recovery_61": "先停下手边的事，缓慢呼吸一次。",
    "task_recovery_62": "拿起水杯，先喝一小口水。",
    "task_recovery_63": "坐稳，闭上眼睛三秒钟。",
    "task_recovery_64": "打开纸笔或备忘录，写下第一个感受。",
    "task_recovery_66": "走到窗边，停下来做一次深呼吸。",
    "task_recovery_67": "放松肩膀，留意身体最紧绷的地方。",
    "task_recovery_69": "坐稳，先读第一句话。",
    "task_recovery_70": "给自己留十秒钟，什么也不用做。",
    "task_recovery_72": "坐稳，观察一下此刻的呼吸节奏。",
    "task_recovery_76": "把手机放远一点，先看向房间里的一个物体。",
    "task_recovery_81": "把灯光调暗一点，缓慢呼吸一次。",
    "task_recovery_84": "坐稳，用指腹轻轻按一下太阳穴。",
    "task_recovery_86": "坐稳，先从头到脚放松一次。",
    "task_recovery_91": "坐稳，把一只手轻放在胸前。",
    "task_recovery_93": "给自己倒一杯水，先喝一小口。",
    "task_recovery_94": "打开备忘录，写下一个想感谢的人或事。",
    "task_recovery_95": "坐稳，先觉察一下身体的紧绷感。",
    "task_recovery_100": "坐到窗边，先安静看向远处十秒。",
    "task_recovery_101": "打开纸笔或备忘录，写下一句不评判自己的话。",
    "task_recovery_103": "找一个舒服的位置，闭眼休息十秒。",
    "task_recovery_110": "坐稳，把注意力放在缓慢的呼气上。",
    "task_recovery_112": "打开一段舒缓音频，先听十秒。",
    "task_recovery_121": "给自己留十秒空白，什么也不用完成。",
    "task_recovery_126": "选一首歌，先只听前十秒。",
    "task_recovery_131": "停下来，给自己一个短暂的暂停。",
    "task_recovery_140": "把手机放远一点，慢慢呼吸一次。",
}


def quick_metadata(task: Task) -> str | None:
    return QUICK_FIRST_ACTIONS.get(task.id)


def quick_fallback_metadata(task: Task) -> str | None:
    """Return a low-preparation starter for safe, unseen similar candidates."""
    if task.id in QUICK_FIRST_ACTIONS:
        return None
    if (
        task.duration > 30
        or task.ease_level < 4
        or task.physical_load > 2
        or task.social_pressure > 2
    ):
        return None
    starters = {
        "活力充电": "先站稳，做一次轻柔舒展，再开始最小的一步。",
        "松弛疗愈": "先坐稳，缓慢呼吸一次，再开始最小的一步。",
        "乐享探索": "先打开手机或拿出纸笔，只做最小的一步。",
        "自我成长": "先打开计时器，只投入十分钟开始最小的一步。",
    }
    return starters.get(task.category)
