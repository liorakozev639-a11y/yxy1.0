# Demo V2 Task 4 Independent Review

## Spec Compliance

### Pass

- `buildSchedule()` 实现了 `light` / `balanced` / `full` 三档密度，并且 `light` 一定带休息块，所有排程都受可用窗口约束，见 `outputs/free-time-agent-demo-v2/logic.js:427-506`。
- 时间单位在逻辑层统一使用“分钟”，`validateTimeWindow()` 以分钟做重叠和越界校验，`parseStartInput()` 也支持把 `HH:MM` 转成分钟，见 `outputs/free-time-agent-demo-v2/logic.js:508-540`、`outputs/free-time-agent-demo-v2/app.js:764-779`。
- 自定义任务允许空原因标签，逻辑层不会因为 `reasonTag === ''` 拒绝保存，见 `outputs/free-time-agent-demo-v2/logic.js:579-592`。
- 执行阶段提供了“开始 / 完成 / 跳过 / 换一个 / 今天先不做”五类动作，且 `missed / overdue / skipped / paused` 会触发“计划需要调整”，见 `outputs/free-time-agent-demo-v2/logic.js:67-72,617-638`、`outputs/free-time-agent-demo-v2/app.js:523-555`。
- `localStorage` 恢复逻辑只操作 Demo V2 自己的 key，损坏时不会误删无关 key，见 `outputs/free-time-agent-demo-v2/app.js:186-220`。

### Findings

- **[P1] 自定义任务 UI 实际不可提交，Task 4 的“custom task modal and validation”没有在界面层闭环。**  
  计划阶段只渲染了表单字段，没有“保存/添加”按钮，也没有任何地方从 DOM 收集 `data-custom-field` 后触发 `add-custom-task`。`renderCustomTaskForm()` 仅输出输入框（`outputs/free-time-agent-demo-v2/app.js:473-497`），`handleAction('add-custom-task')` 虽然存在（`outputs/free-time-agent-demo-v2/app.js:917-919`），但当前 UI 没有对应入口；`input` 监听也只处理 `data-field`，不处理 `data-custom-field`（`outputs/free-time-agent-demo-v2/app.js:967-973`）。这意味着“空原因标签可用”只在逻辑层成立，用户在页面里根本无法完成自定义任务提交流程。

- **[P1] 重排会清空执行状态并重建整条时间线，无法满足“重排不覆盖已完成任务”。**  
  `generatePlan()` 每次都会直接用 `logic.buildSchedule(state.selectedTasks, state.preferences)` 重建 schedule，然后把 `state.executionState = {}` 清空（`outputs/free-time-agent-demo-v2/app.js:736-751`）。`replaceTask()` 也复用了这条路径（`outputs/free-time-agent-demo-v2/app.js:808-826`）。结果是只要用户点击“立即重排”或“换一个”，之前已经 `completed` 的任务状态就会被抹掉，完成项也会被重新纳入排程候选，和审查重点里的要求正面冲突。

- **[P2] 可用窗口在 UI 中不可配置，当前实现只暴露了时长档位，没有真正完成“时间设置”。**  
  逻辑层支持 `startMinute` / `endMinute` 窗口（`outputs/free-time-agent-demo-v2/logic.js:396-411`），但界面没有任何控件让用户设置可用开始时间或结束时间；`syncTimeWindow()` 只是根据 `duration` 把默认窗口同步成 `09:00-10:00`、`09:00-12:00` 或 `09:00-13:00`（`outputs/free-time-agent-demo-v2/app.js:118-122`）。因此“时间单位和可用窗口”在代码内部是自洽的，但规格里的“时间设置”只完成了一半。

- **[P2] localStorage 恢复策略对旧草稿不兼容，结构稍旧就会整体丢弃。**  
  `validateStoredPayload()` 要求 `payload.version === 'demo-v2-2026-08-01'` 且 state 形状严格匹配（`outputs/free-time-agent-demo-v2/app.js:132-183`）。这能防止坏数据，但也意味着哪怕只是早一版 Demo V2 草稿、或缺少后续新增字段的有效旧草稿，也会被当成无效数据直接清掉，而不是做前向兼容迁移。若“恢复兼容”包含跨 Task 演进保留旧会话，这里不满足。

## Code Quality

- 逻辑层边界总体清楚：排程、窗口校验、自定义任务和执行状态都收敛在 `logic.js`，可测性还不错。
- 主要问题出在 `app.js` 的状态编排。计划生成、重排、换一个这三条路径都直接重建 schedule，没有区分“未来待排任务”和“已完成任务”，导致执行态被 UI 层覆盖。
- 自定义任务相关代码呈现出“逻辑先到位，交互没接上”的状态：底层 API 可用，但页面没有完成提交闭环。这类半接线实现很容易让测试只覆盖函数、不覆盖真实用户路径。
- 测试对正向流程覆盖还行，但对“重排保留完成项”和“自定义任务表单可实际提交”没有保护，因此这两个规格偏差能在全绿测试下漏过去。

## Tests

### Ran

- `node tests/demo-v2-smoke.test.js` 通过
- `node tests/demo-v2-logic.test.js` 通过
- `node tests/demo-v2-questionnaire.test.js` 通过
- `node tests/demo-v2-planning.test.js` 通过
- `node tests/logic.test.js` 通过
- `node --check outputs/free-time-agent-demo-v2/app.js` 通过
- `node --check outputs/free-time-agent-demo-v2/logic.js` 通过

### Gaps

- `tests/demo-v2-delivery.test.js` 不存在。既然用户要求“运行全部 V2 tests”，当前仓库里能运行的 V2 tests 只有 `smoke / logic / questionnaire / planning` 四个文件。
- 现有 Task 4 测试没有覆盖：
  - 自定义任务表单是否真的能从 UI 提交
  - 重排后已完成任务是否保留且不被重排覆盖
  - “今天先不做”之后是否应该从后续重排中排除
  - 可用窗口是否支持用户设置而不只是默认值

## Verdict

**未通过，需修改后再验。**

当前实现把大部分 Task 4 的逻辑函数补齐了，自动化测试也全绿，但有两个阻断级规格问题：

1. 自定义任务在页面里无法真正添加。  
2. 重排会抹掉已完成任务的执行状态。

再加上可用窗口 UI 缺失、localStorage 兼容策略偏硬，结论是：**Task 4 还不能算 spec-complete。**
