# 历史计划与偏好学习可视化设计

## 已确认范围

- 统计范围：当前本地匿名用户的全部历史。
- 入口位置：计划结果页顶部新增「我的历史」按钮。
- 展示方式：在当前单页应用内切换成历史视图，不新开页面。
- 第一版内容：摘要统计 + 最近 5 个历史计划。
- 学习来源：完成任务、跳过任务、替换任务、1-2 分低分反馈。
- 展示粒度：大分类为主，细任务组作为解释。
- 后端接口：`GET /api/v1/users/{user_id}/history/insight`。
- 空状态：没有历史数据时展示真实空状态，引导先完成或跳过任务。

## 产品目标

用户不只看到“系统推荐了什么”，还要看到“系统从我的历史行为里学到了什么”。历史页用更透明的方式说明：本周完成了哪些任务、经常跳过哪些类型、最喜欢哪些分类，以及下次推荐会如何避开不喜欢的任务。

## 后端设计

新增 `history_insight_service.py`，负责从 PostgreSQL 聚合用户历史，不把统计逻辑塞进 `main.py`。它读取：

- `user_task_history`：完成、跳过、替换来源和替换去向。
- `plans`、`plan_items`：最近计划和任务标题。
- `task_feedback`：1-2 分反馈；第一版通过同一计划/任务与用户历史行为关联到匿名用户。

接口返回结构：

```json
{
  "has_history": true,
  "summary": {
    "completed_count": 3,
    "this_week_completed_count": 2,
    "skipped_count": 1,
    "replaced_count": 2,
    "low_rating_count": 1
  },
  "this_week_completed_tasks": [
    {"title": "居家拉伸", "category": "活力充电", "completed_at": "2026-09-07T10:00:00+08:00"}
  ],
  "recent_plans": [
    {
      "plan_id": "plan_xxx",
      "created_at": "2026-09-07T09:30:00+08:00",
      "status": "confirmed",
      "completed_count": 1,
      "skipped_count": 0,
      "replaced_count": 1
    }
  ],
  "favorite_categories": [
    {"category": "活力充电", "completed_count": 2}
  ],
  "avoided_groups": [
    {"feedback_group": "energy_mobility_home", "category": "活力充电", "negative_count": 2}
  ],
  "learning_notes": [
    "你更常完成活力充电类任务，后续会提高这类任务的排序。"
  ],
  "next_recommendation_strategy": [
    "经常跳过或低分的细任务组会被降低排序。"
  ]
}
```

没有历史时返回 `has_history=false`，统计为 0，列表为空，并返回空状态文案。

## 前端设计

在计划结果页顶部增加「我的历史」按钮。点击后将 `state.showingHistory = true`，调用 `api.getHistoryInsight(user_id)`，页面主体切换成历史视图。历史视图包含：

- 四个像素风统计卡：本周完成、累计完成、跳过/替换、低分反馈。
- 本周完成任务列表。
- 最近 5 个历史计划列表。
- 最喜欢分类条形图。
- 经常避开的细任务组。
- “系统下次会如何调整”说明。
- 「返回计划」按钮。

空状态展示：`完成或跳过几个任务后，这里会显示系统学到的偏好。`

## 错误处理

- 没有 `user_id`：前端先调用匿名用户创建接口。
- 后端无用户历史服务：返回 `503`。
- 查询失败：统一走现有错误包装，前端保留当前计划页并显示 toast。

## 测试方案

- Python：新增 `tests/test_history_insight_service.py`，验证空状态、完成/跳过/替换/低分反馈聚合。
- API：扩展 `tests/test_user_history_api.py`，验证 `GET /api/v1/users/{user_id}/history/insight`。
- 前端 API：扩展 `tests/frontend-api.test.js`，验证请求地址和方法。
- 前端渲染：扩展 `tests/frontend-visual.test.js`，验证历史按钮、历史视图、空状态和返回计划入口。
