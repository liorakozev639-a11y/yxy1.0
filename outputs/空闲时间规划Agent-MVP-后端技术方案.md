# 空闲时间规划 Agent MVP 后端技术方案

**版本：** v1.0  
**依据：**《空闲时间规划 Agent MVP 产品需求文档》  
**目标：** 用最少的后端组件完成“问卷 → 推荐 → 排程 → 执行 → 调整”的同步闭环。

## 1. 技术范围

### 1.1 MVP 负责的能力

- 匿名会话和草稿恢复。
- 兴趣方向和前置条件保存。
- 5 题快速问卷和 30 题深度问卷。
- 规则计算用户画像。
- 从人工审核任务库筛选任务。
- 规则版 Agent 组合任务并生成理由。
- 生成三种计划密度。
- 自定义任务和时间调整。
- 任务执行状态记录。
- 计划重新排程。
- 网页接口返回计划和状态。

### 1.2 明确移除的能力

- MQ、Worker 和异步任务。
- 邮件、PDF 和日历交付。
- 实时地图、商户和活动 API。
- 浏览器推送通知。
- 登录、账号和跨设备历史数据。
- Agent 自主联网搜索。

## 2. 总体架构

采用“模块化单体 + 同步 HTTP API”：

```text
网页前端
   ↓ 同步 HTTP/JSON
API 服务
   ├── Session
   ├── Questionnaire
   ├── Profile
   ├── Task Repository
   ├── Recommendation
   ├── Scheduling
   ├── Execution
   └── Feedback
   ↓
PostgreSQL
```

所有请求在一次 HTTP 调用内完成。MVP 不引入 MQ、定时 Worker 或独立 Agent 服务。

## 3. 推荐技术栈

| 层 | 选择 | 用途 |
|---|---|---|
| API | Node.js + TypeScript + Fastify | 同步接口和参数校验 |
| 数据库 | PostgreSQL | 会话、题库、任务、计划和事件 |
| ORM | Prisma 或 Drizzle | 数据访问和迁移 |
| 校验 | Zod 或框架 DTO | 请求和返回值校验 |
| 身份 | 匿名 session token | MVP 无需注册 |
| 日志 | 结构化 JSON 日志 | 错误定位和行为追踪 |
| 部署 | 单个 API 服务 + PostgreSQL | 降低部署复杂度 |

Redis、MQ、缓存层和异步 Worker 暂不使用。

## 4. 后端模块

### 4.1 Session Module

**职责：** 创建匿名会话、保存当前流程、恢复草稿和删除本次数据。

**核心数据：** `sessionId`、token 哈希、当前阶段、有效期、版本号。

**实现要求：**

- 服务端只保存 token 哈希，不保存明文 token。
- 每个接口通过 session token 校验访问权限。
- 会话状态直接写入数据库。
- 前端可额外使用版本化本地存储进行断网恢复。

### 4.2 Questionnaire Module

**职责：** 生成问卷、保存答案、处理跳过和提交。

**实现要求：**

- 根据 `quick` 返回 5 题，根据 `deep` 返回 30 题。
- 题目必须来自审核题库。
- 统一使用四级量表，服务端校验选项值。
- 保存每次答案和最终提交状态。
- 根据前置条件筛选适用题目。

### 4.3 Profile Module

**职责：** 将问卷答案转换为结构化偏好画像。

**实现要求：**

- 使用确定性规则计算画像。
- 支持反向题计分。
- 生成活力、恢复、社交、探索和成长等偏好分数。
- 将预算、出行、同行和空闲时长作为约束保存。
- 保存规则版本，保证同一答案可复现。

### 4.4 Task Repository

**职责：** 提供人工审核的通用任务和用户自定义任务。

**实现要求：**

- 公共任务由管理员或初始化脚本写入数据库。
- 只有 `approved` 状态的任务可参与推荐。
- 任务记录时长、预算、方向、出行方式、同行方式和精力要求。
- 用户自定义任务单独存储，仅属于当前 session。
- 不抓取互联网，不保存未经验证的商户和活动事实。

### 4.5 Recommendation Module

**职责：** 根据画像和硬约束筛选、排序并组合候选任务。

**实现顺序：**

```text
预算/时长/出行/同行硬约束过滤
→ 方向覆盖检查
→ 偏好分数排序
→ 任务多样性处理
→ 生成匹配理由
```

**Agent 边界：**

- MVP 使用规则编排器实现 Agent 接口。
- 只能使用已筛选的任务 ID。
- 不能创建任务库之外的真实地点、价格或活动。
- 输出必须经过服务端约束校验。
- 失败时直接返回规则结果，不进行异步重试。

### 4.6 Scheduling Module

**职责：** 将候选任务放入空闲时间，生成可执行计划。

**实现要求：**

- 支持 `light`、`balanced`、`full` 三种密度。
- 不允许任务重叠或超出空闲时间。
- 至少保留一个低压力休息块。
- 计算任务总预算并校验上限。
- 支持修改开始时间和持续时间。
- 保存计划版本，不覆盖已确认或已完成内容。

### 4.7 Execution Module

**职责：** 记录任务执行状态并处理超时。

**状态：**

```text
pending → active → completed
pending → skipped
pending → missed
active  → overdue
missed / overdue / skipped → needs_adjustment
```

**同步超时判断：**

- 用户打开计划页时检查当前时间。
- 用户点击开始、完成、跳过时检查当前时间。
- 不使用后台定时任务。
- 数据库保存真实状态，页面统一展示“计划需要调整”。

### 4.8 Feedback Module

**职责：** 保存满意度和可选原因标签。

**实现要求：**

- 满意度范围为 1-5。
- 原因标签可以为空。
- 反馈关联 `planItemId` 和 session。
- MVP 只保存反馈，不实时改变当前计划。

## 5. 核心数据表

### 5.1 `sessions`

```text
id
token_hash
stage
expires_at
created_at
updated_at
version
```

### 5.2 `preferences`

```text
session_id
categories_json
duration
budget
location_scope
city_or_campus
outing
company
density
rest_only
```

### 5.3 `question_bank`

```text
id
mode
category
prompt
dimension
options_json
reverse_scored
eligibility_json
version
status
```

### 5.4 `questionnaire_answers`

```text
session_id
question_id
value
skipped
answered_at
```

### 5.5 `profiles`

```text
session_id
scores_json
constraints_json
confidence
rule_version
created_at
```

### 5.6 `tasks`

```text
id
category
title
description
duration_minutes
budget_level
outing_mode
company_mode
energy_level
rest_first
review_status
version
```

### 5.7 `plans`

```text
id
session_id
parent_plan_id
version
status
density
confirmed_at
created_at
```

### 5.8 `plan_items`

```text
id
plan_id
task_id
custom_task_id
item_type
title
start_at
end_at
status
reason
```

### 5.9 `execution_events`

```text
id
plan_item_id
event_type
occurred_at
metadata_json
```

### 5.10 `feedback`

```text
id
session_id
plan_item_id
rating
reason_tags_json
created_at
```

## 6. 同步 API

统一响应格式：

```json
{
  "requestId": "req_xxx",
  "data": {},
  "error": null
}
```

### 6.1 会话和前置条件

```text
POST   /api/v1/sessions
GET    /api/v1/sessions/{sessionId}
DELETE /api/v1/sessions/{sessionId}/data
PUT    /api/v1/sessions/{sessionId}/preferences
```

### 6.2 问卷

```text
POST  /api/v1/sessions/{sessionId}/questionnaire/start
PATCH /api/v1/sessions/{sessionId}/questionnaire/answers/{questionId}
POST  /api/v1/sessions/{sessionId}/questionnaire/skip/{questionId}
POST  /api/v1/sessions/{sessionId}/questionnaire/submit
POST  /api/v1/sessions/{sessionId}/questionnaire/switch-mode
```

### 6.3 推荐和计划

```text
POST  /api/v1/sessions/{sessionId}/recommendations
POST  /api/v1/sessions/{sessionId}/plans/draft
GET   /api/v1/plans/{planId}
PATCH /api/v1/plans/{planId}/items/{itemId}
POST  /api/v1/plans/{planId}/replan
POST  /api/v1/plans/{planId}/confirm
POST  /api/v1/plans/{planId}/custom-tasks
```

### 6.4 执行和反馈

```text
POST /api/v1/plans/{planId}/items/{itemId}/start
POST /api/v1/plans/{planId}/items/{itemId}/complete
POST /api/v1/plans/{planId}/items/{itemId}/skip
POST /api/v1/plans/{planId}/items/{itemId}/replace
POST /api/v1/plans/{planId}/items/{itemId}/feedback
```

## 7. 关键同步流程

### 7.1 生成推荐

```text
校验 session
→ 读取 preferences
→ 读取 questionnaire_answers
→ 计算 profile
→ 查询 approved tasks
→ 硬约束过滤
→ 规则排序和组合
→ 服务端校验输出
→ 返回候选任务
```

### 7.2 生成计划

```text
读取候选任务
→ 读取空闲时间和不可用时间
→ 保留已完成任务
→ 根据密度选择任务
→ 插入休息块
→ 检查冲突、预算和总时长
→ 保存 plan 和 plan_items
→ 返回计划草稿
```

### 7.3 任务执行

```text
请求进入
→ 校验 session 和计划归属
→ 读取当前状态
→ 校验允许的状态转换
→ 根据当前时间判断是否超时
→ 更新 plan_item
→ 写入 execution_event
→ 返回最新状态
```

所有状态更新和事件写入必须在同一个数据库事务中完成。

## 8. 事务与一致性要求

- 计划创建使用数据库事务，确保 `plans` 和 `plan_items` 同时成功。
- 任务状态更新与执行事件写入使用同一事务。
- 计划确认时检查草稿版本，避免覆盖其他版本。
- 计划编辑使用 `version` 或更新时间做乐观锁校验。
- 同一 session 不允许同时存在两个未确认的主计划草稿。
- 重排创建新计划版本，不删除旧计划。

## 9. 错误处理

| 错误 | HTTP 状态 | 处理 |
|---|---:|---|
| session 不存在 | 404 | 提示重新创建会话 |
| 参数无效 | 400 | 返回字段级错误 |
| 无权限访问计划 | 403 | 不返回计划内容 |
| 问卷未完成 | 409 | 提示完成问卷或切换快速版 |
| 没有匹配任务 | 200 | 返回限制原因和通用低压力任务 |
| 时间冲突 | 409 | 返回可用时间范围 |
| 状态转换非法 | 409 | 返回当前状态和可用操作 |
| 版本冲突 | 409 | 要求刷新后重新编辑 |
| 数据库异常 | 500 | 记录 requestId，页面显示可重试 |

## 10. 隐私和安全

- 匿名 token 使用随机值，服务端只保存哈希。
- 所有接口校验 session 与资源归属。
- 日志不记录原始 token、完整问卷答案和精确位置。
- 城市或校园只作为普通文本保存，不进行精确定位。
- 用户可以删除当前 session 的全部数据。
- 写接口需要校验请求体，限制标题长度、时长范围和标签数量。
- 对创建会话、提交答案和执行操作设置基础频率限制。

## 11. 日志和指标

### 11.1 技术日志

- `requestId`
- 接口路径
- HTTP 状态码
- 响应耗时
- session 脱敏标识
- 错误类型

### 11.2 产品事件

```text
session_created
questionnaire_started
question_answered
questionnaire_completed
recommendation_generated
plan_confirmed
task_started
task_completed
task_skipped
plan_adjusted
custom_task_created
feedback_submitted
draft_restored
```

## 12. 精简实施顺序

### 第一步：基础工程

- 创建 API 项目。
- 配置 PostgreSQL 和 ORM。
- 建立统一响应、错误处理和 session 校验。
- 完成数据库迁移。

### 第二步：输入闭环

- 实现 Session Module。
- 实现兴趣方向和前置条件接口。
- 实现快速版和深度版问卷。
- 实现答案保存和恢复。

### 第三步：推荐闭环

- 导入人工审核任务库。
- 实现画像计算规则。
- 实现任务硬约束过滤。
- 实现规则推荐和匹配理由。

### 第四步：计划闭环

- 实现三种计划密度。
- 实现时间冲突检查。
- 实现自定义任务。
- 实现计划版本和确认。

### 第五步：执行闭环

- 实现开始、完成、跳过接口。
- 实现请求时超时判断。
- 实现执行事件记录。
- 实现重新排程和反馈。

### 第六步：验证上线

- 完成接口测试和核心流程测试。
- 使用单城市或单校园数据进行内部测试。
- 验证推荐约束、排程冲突和状态转换。
- 小范围灰度发布。

## 13. MVP 验收重点

- 用户无需注册即可完成完整规划。
- 5 题快速问卷可以生成计划。
- 30 题深度问卷可以生成更细画像。
- 推荐任务符合时间、预算、出行和同行条件。
- 推荐结果覆盖用户选择的方向，或明确说明缺口。
- 计划不存在时间冲突。
- 用户可以修改时间和添加自定义任务。
- 任务状态可以正确流转。
- 超时判断不依赖异步任务。
- 已完成任务不会在重排时丢失。
- 全部核心能力由同步 API 完成。
