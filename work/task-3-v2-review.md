# Demo V2 Task 3 Independent Review

## Spec Compliance

### Pass

- `quick` / `deep` 题数与四级量表符合规格。`createQuestionnaire('quick')` 返回 5 题，`createQuestionnaire('deep')` 返回 30 题，且题目都带固定四级量表，见 `outputs/free-time-agent-demo-v2/logic.js:164-177`。
- 默认模式是 `quick`，见 `outputs/free-time-agent-demo-v2/logic.js:383-391` 与 `outputs/free-time-agent-demo-v2/app.js:66-74`。
- 单题问卷、上一题、跳过都已实现，且切换 quick/deep 时会保留重叠题目的答案，见 `outputs/free-time-agent-demo-v2/app.js:89-107`、`208-245`、`409-419`、`421-433`。
- 前置条件中的 `city` / `campus` / `workStatus` 为可选输入，不阻塞进入问卷，见 `outputs/free-time-agent-demo-v2/app.js:195-203`、`527-535`。
- `localStorage` 恢复带版本字段，损坏 JSON 时只清理 Demo V2 自己的 key，并保留无关 key，见 `outputs/free-time-agent-demo-v2/app.js:313-353`。
- 当前代码路径与测试目标都指向 `outputs/free-time-agent-demo-v2/`，旧 `tests/logic.test.js` 通过；从当前工作区状态看，没有发现 V2 直接覆盖旧原型的证据。

### Findings

- **[P1] 推荐补足在 UI 流程里放宽了硬约束，违背了计划/规格要求。**  
  `logic.recommendActivities()` 的 fallback 只放宽 `selectedCategories`，仍保留 outing/company/budget/duration 等硬约束，符合 Task 2 计划；但 `app.js` 里的 `buildTenCandidates()` 又额外构造了 5 组变体，依次把 `outing`、`company`、`budget`、`duration` 置空，最终会把不满足用户前置条件的活动补进结果里。见 `outputs/free-time-agent-demo-v2/app.js:469-489`。这和设计规格“活动不足时从低压力通用活动补足到 10 个”以及本次审查重点“推荐补足是否放宽硬约束”不一致。

- **[P2] 问卷界面缺少规格明确要求的 submit 动作。**  
  Task 3 Step 4 要求渲染 “previous / skip / submit” 操作；当前问卷 UI 只有上一题和跳过两个按钮，最后一题通过 `advanceQuestionnaire()` 自动提交，没有显式 submit 控件。见 `outputs/free-time-agent-demo-v2/app.js:240-243`、`492-503`。这不影响基本流程跑通，但不满足规格文字要求。

- **[P2] 恢复逻辑对“结构损坏但 JSON 合法”的草稿校验过浅，会静默归一化而不是清理。**  
  `validateStoredPayload()` 只检查 `version`、`state` 和 `stage`，没有校验 `preferences.selectedCategories`、`questionnaire.answers`、`preferences.mode` 等关键字段结构。结果是某些损坏草稿不会触发清理，而是被 `createRuntimeState()` 部分吞掉并继续使用，见 `outputs/free-time-agent-demo-v2/app.js:324-329`、`63-86`、`347-352`。这和“on malformed state, clear only the Demo V2 key”相比仍有缺口。

## Code Quality

- `logic.js` 的问卷生成、活动库过滤和 fallback 分层比较清晰，尤其 `recommendActivities()` 本身对硬约束处理是对的，见 `outputs/free-time-agent-demo-v2/logic.js:351-377`。
- Task 3 的主要偏差集中在 `app.js`：UI 层重新实现了候选补足策略，绕开了逻辑层已经定义好的约束边界，导致行为与规格脱节，见 `outputs/free-time-agent-demo-v2/app.js:469-489`。
- 旧原型隔离性从目录结构上是好的：V2 产物都在 `outputs/free-time-agent-demo-v2/`，旧 bundle 仍在 `outputs/free-time-agent-demo/`。当前环境不是 git 仓库，无法用版本历史进一步证明“从未触碰”，只能基于现有文件布局、时间戳和测试结果给出结论。

## Tests

### Ran

- `node tests/demo-v2-smoke.test.js` ✅
- `node tests/demo-v2-logic.test.js` ✅
- `node tests/demo-v2-questionnaire.test.js` ✅
- `node tests/logic.test.js` ✅
- `node --check outputs/free-time-agent-demo-v2/app.js` ✅
- `node --check outputs/free-time-agent-demo-v2/logic.js` ✅

### Coverage Notes

- 现有 `tests/demo-v2-questionnaire.test.js` 覆盖了 quick/deep 题数、量表、基本问卷流、版本字段恢复、坏 JSON 清理。
- 但它没有覆盖：
  - 推荐补足是否仍保留 outing/company/budget/duration 等硬约束；
  - 问卷 UI 是否存在显式 submit 控件；
  - “结构损坏但 JSON 合法”的 localStorage 草稿是否会被清理；
  - “旧原型未被触碰”的仓库级约束。

## Verdict

**Changes required before Task 3 can be considered spec-complete.**

主要原因有二：

1. 推荐补足在实际 UI 流程中放宽了硬约束，这是本次审查重点里的核心违例，优先级最高。  
2. 问卷缺少显式 submit 动作，且 localStorage 损坏校验对合法 JSON 的坏结构覆盖不足。

如果只看“测试是否通过”，当前状态是绿的；如果按 Task 3 计划和设计规格做独立验收，我的结论是 **未完全通过**。
