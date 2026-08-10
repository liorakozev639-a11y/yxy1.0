# MVP 前端主流程断点调试清单设计

## 目标

为正在学习 Python、FastAPI 和 PyCharm 调试的用户生成一份可逐步执行的中文清单，用断点验证当前前端已经接通的产品主流程是否正常。

清单不修改业务代码，不在源文件中添加调试注释，只提供稳定的函数定位、当前行号参考、触发操作、观察变量和验收标准。

## 验证范围

包含：

1. 创建和恢复 Session。
2. 保存活动分类与前置条件。
3. 启动快速版 5 题或深度版 30 题问卷。
4. 保存、修改、跳过答案与恢复进度。
5. 提交问卷。
6. 构建 Profile。
7. Task Repository 约束筛选。
8. Recommendation 分类覆盖与排序。
9. Scheduling 时间排程。
10. PostgreSQL 保存画像、计划和计划项。
11. Delivery 生成网页展示数据。
12. 前端展示、刷新恢复和重新开始。

不包含：

- 尚未接入 `main.py` 的 Execution Module。
- 尚未接入主流程的 Feedback Module。
- PDF、邮件、日历和实时地图/商户接口。

## 文档结构

正式清单保存为 `docs/MVP前端主流程断点调试清单.md`，由以下部分组成：

1. 调试前准备：PostgreSQL、后端、前端和 PyCharm Debug Configuration。
2. 断点使用规则：按阶段启用，F7/F8/F9 的使用边界，Variables 与 Evaluate Expression。
3. 十二个产品阶段：每阶段包含触发动作、接口、断点顺序、变量、前端反馈、后端反馈、数据库验证和通过标准。
4. 异常分支：400、404、409、410、422、503 的触发和观察点。
5. 最终验收表：逐项勾选并记录 Session ID、Question ID 和 Plan ID。

## 断点设计原则

- 先在 `main.py` 路由入口暂停，确认 HTTP 数据已经被 Pydantic 转换。
- 再使用 F7 进入 Service 或 Orchestrator，观察业务规则。
- 在 Repository 写入前后分别观察 Python 对象和 PostgreSQL 返回值。
- 一个阶段调试完成后禁用该组断点，再启用下一组，避免一次请求暂停过多。
- 函数名是主要定位依据；行号只作为当前提交版本的参考。
- 不在 Evaluate Expression 中调用写数据库的方法，避免重复写入。

## 每个阶段的固定模板

每个阶段统一记录：

| 项目 | 内容 |
| --- | --- |
| 前端操作 | 用户在页面上执行的动作 |
| HTTP 接口 | 前端实际请求的接口 |
| 断点顺序 | 路由、服务、仓储或算法函数 |
| 关键变量 | Variables 中应检查的值 |
| 单步操作 | 应使用 F7、F8 还是 F9 |
| 前端预期 | 页面、进度或错误提示 |
| 后端预期 | HTTP 状态和 JSON 关键字段 |
| 数据库预期 | 对应表中的新增或更新记录 |
| 通过标准 | 判断该阶段成功的明确条件 |

## 数据与错误处理

- 调试过程中记录并复用同一个 `session_id`。
- 问卷阶段记录当前 `question_id`。
- 计划阶段记录 `plan_id` 并确认 GET 恢复结果一致。
- 业务错误必须同时核对 HTTP 状态码、统一 `error` 对象和后端异常处理断点。
- PostgreSQL 查询只使用当前测试 Session，避免混入历史数据。

## 验收标准

- 清单覆盖 `main.py` 当前全部 Session、Questionnaire 和 Plan 路由。
- Profile、Task、Recommendation、Scheduling 和 Web Delivery 均有断点路径。
- 每个阶段至少包含一个明确变量和一个明确通过标准。
- 文档明确区分前端反馈、后端反馈和数据库结果。
- 所有路径和函数均来自当前 `D:\yxy1.0`。
- 不包含真实数据库密码、Token 或个人数据。
- Existing `session_module.py` 与 `questionnaire_module.py` 未提交改动不进入本次提交。
