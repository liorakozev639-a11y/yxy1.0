# Task Repository Module Implementation Plan

> **For agentic workers:** This plan is executed inline in the current session.

**Goal:** 完善 MVP 后端技术方案中的 Task Repository 章节，并提供可独立运行的 Python 示例。

**Architecture:** 使用模块化单体中的独立任务库类，区分公共任务和用户自定义任务。Task Repository 只做审核状态和预算、时长、出行、同行方式等硬过滤，偏好排序交给 Recommendation Module。

**Tech Stack:** Python 3.10+ 标准库，`dataclasses`，不依赖数据库、FastAPI、大模型或异步组件。

## Global Constraints

- MVP 任务来源为人工录入或初始化脚本导入，不直接爬取互联网。
- 公共任务必须为 `approved` 才能参与推荐。
- 用户自定义任务独立保存，不修改公共任务库。
- 无城市数据时仍可返回通用居家任务。

### Task 1: 完整任务库示例

**Files:**
- Create: `examples/task_repository.py`

- [ ] 定义任务数据结构、公共任务、自定义任务存储和硬约束查询。
- [ ] 增加出行方式、同行方式和兴趣分类过滤。
- [ ] 增加 `demo()`，演示公共任务、自定义任务和排除原因。

### Task 2: 更新后端技术方案

**Files:**
- Modify: `outputs/空闲时间规划Agent-MVP-后端技术方案-工作流与示例.md:584-657`

- [ ] 补充模块职责、输入输出、数据来源、工作流、边界和验收点。
- [ ] 说明 Task Repository 与 Profile、Recommendation Module 的职责边界。
- [ ] 链接完整 Python 示例文件。

### Task 3: 验证

- [ ] 使用文本检查确认文档包含完整章节和示例文件路径。
- [ ] 使用可用的 Python 解释器运行 `examples/task_repository.py`；若本机解释器不可用，至少进行静态语法检查并明确说明。
