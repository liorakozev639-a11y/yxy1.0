# 空闲时间规划 Agent 演示页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个无需后端或大模型的静态网页原型，演示方向选择、30 题问卷、10 个候选任务和可调整计划的完整流程。

**Architecture:** 使用静态 HTML、CSS 和原生 JavaScript。`logic.js` 提供可单测的题目分配、候选任务和计划生成函数；`app.js` 负责界面状态、渲染和用户交互；所有数据保存在内存中。

**Tech Stack:** HTML5、CSS3、原生 JavaScript、Node.js 内置 `node:test`。

## Global Constraints

- 不接入大模型、数据库、邮件服务或 PDF 生成服务。
- 问卷固定为 30 道单选题，四项选择严格使用 `8/8/7/7` 的优先级分配。
- 推荐固定返回 10 个候选任务并覆盖所有已选方向。
- 页面须展示学生和“长期工作繁忙、突然获得空闲时间的职场人”两类用户语境。
- 结果页只模拟 PDF 下载与邮件发送反馈，不产生外部副作用。

---

### Task 1: 建立演示数据与确定性业务逻辑

**Files:**
- Create: `logic.js`
- Create: `tests/logic.test.js`

**Interfaces:**
- Produces: `window.FreeTimeLogic` and CommonJS exports with `allocateQuestionCounts(categories)`, `buildQuestions(categories)`, `buildCandidates(categories, preferences)`, and `buildSchedule(tasks, timeMode)`.
- Consumes: an ordered string array of category ids and a `timeMode` string of `half` or `full`.

- [ ] **Step 1: Write the failing test**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { allocateQuestionCounts } = require('../logic.js');

test('allocates four ordered categories as 8/8/7/7', () => {
  assert.deepEqual(
    allocateQuestionCounts(['energy', 'calm', 'social', 'explore']),
    { energy: 8, calm: 8, social: 7, explore: 7 },
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/logic.test.js`

Expected: FAIL because `logic.js` does not exist.

- [ ] **Step 3: Write minimal implementation**

```js
function allocateQuestionCounts(categories) {
  const base = Math.floor(30 / categories.length);
  const remainder = 30 % categories.length;
  return Object.fromEntries(categories.map((id, index) => [id, base + (index < remainder ? 1 : 0)]));
}
```

`buildQuestions` must create exactly 30 deterministic multiple-choice items. `buildCandidates` must return 10 tasks, with at least one task per selected category. `buildSchedule` must return non-overlapping blocks within 4.5 hours for `half` and 8 hours for `full`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/logic.test.js`

Expected: PASS for allocation, 30-question, task-coverage, and non-overlap tests.

- [ ] **Step 5: Commit**

```bash
git add logic.js tests/logic.test.js
git commit -m "feat: add demo planning logic"
```

### Task 2: 构建移动优先的多步骤展示界面

**Files:**
- Create: `index.html`
- Create: `styles.css`
- Create: `app.js`
- Modify: `logic.js`

**Interfaces:**
- Consumes: `window.FreeTimeLogic` exposed by `logic.js`.
- Produces: a navigable browser UI with steps `welcome`, `profile`, `quiz`, `candidates`, and `plan`.

- [ ] **Step 1: Define a browser acceptance checklist**

```text
1. Select one or more direction cards and reorder selected directions with priority buttons.
2. Select user context, time mode, budget, outing and company preferences.
3. Answer 30 generated questions with a visible count.
4. View exactly 10 candidates that cover every selected direction.
5. Toggle tasks and regenerate a schedule; show web, PDF-demo and email-demo actions.
```

- [ ] **Step 2: Implement the HTML structure**

Create a single `main` application shell with a slim progress header, five step sections, a toast region, and buttons using `data-action` attributes. Load `logic.js` before `app.js` and load Lucide from a CDN for familiar button icons.

- [ ] **Step 3: Implement styles and responsive layout**

Use a light neutral page background, deep ink text, coral and teal accents, a max-width content column, square-to-soft 8px cards, clear focus states, and a mobile breakpoint below 720px. Avoid decorative gradients and nested cards.

- [ ] **Step 4: Implement interaction state**

Store selections in a `state` object. Render each step from state, disable progression until required choices are made, and use `FreeTimeLogic` for question counts, candidates and schedules. PDF and email buttons must show an honest “演示模式” toast rather than performing a download or send.

- [ ] **Step 5: Run the logic tests**

Run: `node --test tests/logic.test.js`

Expected: PASS with all tests green.

- [ ] **Step 6: Commit**

```bash
git add index.html styles.css app.js logic.js
git commit -m "feat: add free time planner demo"
```

### Task 3: 验证静态交付

**Files:**
- Modify: `index.html` only if verification exposes a semantic or accessibility defect.

**Interfaces:**
- Consumes: all static application files from Tasks 1 and 2.
- Produces: a browser-ready static prototype that can be opened directly.

- [ ] **Step 1: Verify source-level requirements**

Run: `node --test tests/logic.test.js`

Expected: PASS.

- [ ] **Step 2: Verify static file references**

Run: `rg -n 'logic.js|app.js|styles.css|FreeTimeLogic' index.html app.js`

Expected: `index.html` loads all assets and `app.js` accesses `FreeTimeLogic`.

- [ ] **Step 3: Manually verify browser checklist**

Open `index.html`, complete each of the five acceptance-checklist items, and confirm that no external request is required for question generation, recommendations or plan rendering.

- [ ] **Step 4: Commit**

```bash
git add index.html styles.css app.js logic.js tests/logic.test.js
git commit -m "test: verify planner demo"
```
