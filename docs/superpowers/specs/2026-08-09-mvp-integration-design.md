# MVP Core Integration Design

## Goal

将当前分散的 Session、Questionnaire、Profile、Task、Recommendation、Scheduling 和 Web Delivery 代码整合为一条可在本地 PostgreSQL 环境运行的核心 MVP 闭环。

## Scope

本轮整合覆盖：

```text
创建会话 -> 保存偏好 -> 5/30 题问卷 -> 计算画像 -> 筛选任务
-> 分类覆盖推荐 -> 时间排程 -> PostgreSQL 保存 -> 网页展示
```

本轮不接入外部地图、商户、活动、PDF、邮件、MQ、异步 Worker、日历和 Execution/Feedback 主流程。

## Architecture

- `main.py` 是唯一 FastAPI 入口。
- Session 和 Questionnaire 继续使用 PostgreSQL repository。
- Profile、Plan 和 Delivery 增加 PostgreSQL repository；Task Repository 保持人工审核的静态任务库。
- 新增 `mvp_orchestrator.py`，只负责跨模块编排，不复制画像、推荐和排程规则。
- 前端只调用 `main.py` 暴露的 `/api/v1` 接口，页面状态由后端响应驱动。

## Core API

- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PUT /api/v1/sessions/{session_id}/preferences`
- `POST /api/v1/sessions/{session_id}/questionnaire/start`
- `PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}`
- `POST /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}`
- `GET /api/v1/sessions/{session_id}/questionnaire/progress`
- `POST /api/v1/sessions/{session_id}/questionnaire/submit`
- `POST /api/v1/sessions/{session_id}/plan/generate`
- `GET /api/v1/sessions/{session_id}/plan`
- `GET /api/v1/sessions/{session_id}/plan/delivery`

## Generate Flow

1. 校验 Session 存在且未过期。
2. 读取已提交问卷和偏好。
3. Profile Service 按四级量表、反向题和跳过分计算维度分数。
4. Task Repository 根据分类、预算、出行和同行约束过滤任务。
5. Recommendation Service 按画像分数排序并保证用户选择的分类被覆盖。
6. Scheduling Service 按空闲时间和密度生成无冲突计划，并保留休息块。
7. 将 Profile、Plan、Plan Items 写入 PostgreSQL。
8. 通过 Web Delivery Service 生成并持久化前端 JSON。
9. 返回计划、任务时间线和未安排任务。

## Persistence

- `profiles`: session、维度分数、约束、置信度和规则版本。
- `plans`: plan、session、状态、版本、空闲时间和父计划。
- `plan_items`: 计划中的任务和休息块。
- `delivery_jobs`: 网页交付 JSON，使用 session + plan + channel 幂等。

## Acceptance

- 现有 Session / Questionnaire 测试保持通过。
- 完整核心流程可以从 HTTP 调用走到网页交付 JSON。
- PostgreSQL 重启后通过 Session ID 可以恢复问卷、画像和计划。
- 生成的计划没有时间冲突，且至少包含一个休息块。
- 生成接口重复调用不会破坏已有计划版本。
- Swagger `/docs` 可以看到并调用所有核心接口。

