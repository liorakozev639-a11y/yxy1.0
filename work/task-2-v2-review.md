# Demo V2 Task 2 Review

## Spec Compliance

- `outputs/free-time-agent-demo-v2/logic.js` 已经提供了本地活动库、`filterActivities` 和 `recommendActivities`，活动库也确实覆盖了五类方向：`energy`、`calm`、`social`、`explore`、`growth`。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:37) [logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:128) [logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:215)
- 推荐结果也默认返回 10 条，并且每条都有 `matchReason`，这部分和 Task 2 计划一致。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:261)
- 但“硬筛选”没有真正收住：当首轮过滤后的候选不足 10 条时，`recommendActivities` 会直接从整库里补位，不再重新限制 `outing`、`company`、`budget` 和 `duration`。比如 `selectedCategories: ['calm'], outing: 'home', company: 'solo', budget: 'low', duration: 'short'` 这类条件下，后补的结果会混进不满足条件的项。这个行为和设计里“过滤前置条件后再补足 10 条”的意图不一致。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:217) [logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:238)
- 没有看到实时地图、商户、天气或交通数据接入，也没有伪造具体地点或营业时间，这点符合规格要求。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:37)

## Code Quality

- `scoreActivity` 的排序是可重复的，既有固定库顺序，又有非常小的索引微调，所以在当前 Node/V8 下结果是稳定的。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:171)
- 但“先过滤、再用整库补位”的实现让排序和过滤语义混在一起了。结果是看起来像在做硬筛选，实际上只对前半段成立，边界场景会违背前置条件。
- `app.js` 直接把 `window.FreeTimeDemoV2` 重新赋值成 `Object.assign({}, logic, ...)`，这会把逻辑模块的导出面扩大到 Task 1 之外；对后续维护来说，模块契约会比较脆。[app.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/app.js:62)

## Tests

- `node tests/demo-v2-logic.test.js` 通过。
- `node tests/logic.test.js` 通过，说明旧版根逻辑没有被误伤。
- `node --check outputs/free-time-agent-demo-v2/app.js` 通过。
- `node --check outputs/free-time-agent-demo-v2/logic.js` 通过。
- `node tests/demo-v2-smoke.test.js` 失败，原因是 `logic.js` 的导出键不再只包含 Task 1 smoke test 期望的四个项，而是额外暴露了 `getActivityLibrary`、`filterActivities` 和 `recommendActivities`。[tests/demo-v2-smoke.test.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/tests/demo-v2-smoke.test.js:30) [logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:316)

## Verdict

Task 2 的核心功能基本到位，活动库和推荐逻辑也跑通了，但现在还不能算通过审查。一个问题是硬筛选在补位阶段失效，另一个问题是公开导出面扩大，已经把 Task 1 的 smoke contract 顶坏了。我的结论是：**Needs revision**，先把过滤语义和兼容性收紧，再合并更稳。

## Problems

### High

1. `recommendActivities` 在候选不足 10 条时会从整库补位，绕过 `outing`、`company`、`budget` 和 `duration` 的硬条件，导致返回结果可能不满足用户前置条件。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:238)

### Medium

1. `logic.js` 和 `app.js` 现在把 `getActivityLibrary`、`filterActivities`、`recommendActivities` 也暴露到了模块/全局导出里，打破了 Task 1 smoke test 依赖的既有契约，并让 `tests/demo-v2-smoke.test.js` 直接失败。[logic.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/logic.js:316) [app.js](C:/Users/杨星宇/Documents/Codex/2026-08-01/an-zhu/outputs/free-time-agent-demo-v2/app.js:62)
