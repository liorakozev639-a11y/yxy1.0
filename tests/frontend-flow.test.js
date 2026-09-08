const assert = require('node:assert/strict');
const test = require('node:test');

const {
  firstUnansweredIndex,
  mergeRecommendedItems,
  recoverInitialization,
  recommendationMemorySummary,
  taskReasonSummary,
  resumeDestination,
  feedbackReasonOptions,
  planFailureRecoveryOptions,
} = require('../frontend/flow.js');

test('resumeDestination distinguishes welcome, mode, quiz, and result', () => {
  assert.equal(resumeDestination({ preferences: {}, progress: null }), 'welcome');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: null,
  }), 'mode');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: { submitted: false },
  }), 'quiz');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: { submitted: true },
  }), 'result');
});

test('firstUnansweredIndex resumes at the first missing answer', () => {
  const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }];
  assert.equal(firstUnansweredIndex(questions, { q1: { value: 4 } }), 1);
  assert.equal(firstUnansweredIndex(questions, {
    q1: { value: 4 },
    q2: { skipped: true },
    q3: { value: 2 },
  }), 2);
});

test('recoverInitialization exposes replacement-session failures for retry', async () => {
  let forgot = false;
  const replacementError = new Error('数据库离线');
  const result = await recoverInitialization({
    forgetSession() { forgot = true; },
    async createSession() { throw replacementError; },
  }, { status: 410 });

  assert.equal(forgot, true);
  assert.equal(result.recovered, false);
  assert.equal(result.retry, true);
  assert.equal(result.message, '数据库离线');
});

test('recoverInitialization returns the replacement session on success', async () => {
  const result = await recoverInitialization({
    forgetSession() {},
    async createSession() { return { session_id: 'sess_new' }; },
  }, { status: 404 });

  assert.equal(result.recovered, true);
  assert.equal(result.session.session_id, 'sess_new');
});

test('taskReasonSummary normalizes card tags and detail text', () => {
  const item = {
    title: '居家拉伸',
    category: '活力充电',
    reason_tags: ['居家可做', '低预算', '短时间可完成', '适合独处'],
    reason_text: '你选择了「活力充电」，这个任务可以覆盖该方向。',
    match_score: 0.86,
    matched_preferences: ['分类偏好强', '居家可做'],
    warning_text: '预算略高，请确认是否接受。',
    replacement_reason: '已避开你之前看过的任务。',
    load_profile: {
      ease_label: '很轻松',
      physical_label: '低体力',
      social_label: '低社交压力',
      location_label: '居家',
    },
  };

  const summary = taskReasonSummary(item);

  assert.deepEqual(summary.tags, ['居家可做', '低预算', '短时间可完成', '适合独处']);
  assert.equal(summary.text, '你选择了「活力充电」，这个任务可以覆盖该方向。');
  assert.equal(summary.matchScore, 0.86);
  assert.deepEqual(summary.matchedPreferences, ['分类偏好强', '居家可做']);
  assert.equal(summary.warningText, '预算略高，请确认是否接受。');
  assert.equal(summary.replacementReason, '已避开你之前看过的任务。');
  assert.deepEqual(summary.loadProfile, {
    ease: '很轻松',
    physical: '低体力',
    social: '低社交压力',
    location: '居家',
  });
});

test('taskReasonSummary falls back when backend reason fields are missing', () => {
  const summary = taskReasonSummary({ category: '松弛疗愈' });

  assert.deepEqual(summary.tags, ['覆盖松弛疗愈']);
  assert.equal(summary.text, '该任务覆盖「松弛疗愈」，并已进入当前计划。');
  assert.deepEqual(summary.loadProfile, null);
});

test('recommendationMemorySummary gives users a readable exclusion count', () => {
  assert.equal(recommendationMemorySummary({ excluded_group_count: 2 }), '已为你避开 2 组不喜欢的任务');
  assert.equal(recommendationMemorySummary({ excluded_group_count: 0 }), '');
  assert.equal(recommendationMemorySummary(null), '');
});

test('mergeRecommendedItems replaces stale recommendation cards after a task replacement', () => {
  const items = [{
    id: 'item_new',
    task_id: 'task_new',
    title: '新的任务',
    category: '活力充电',
    kind: 'task',
    status: 'pending',
    replacement_history: ['task_old', 'task_new'],
  }];
  const recommendations = [
    { id: 'task_old', title: '旧任务', category: '活力充电' },
    { id: 'task_other', title: '其他任务', category: '活力充电' },
  ];

  const merged = mergeRecommendedItems(items, recommendations);

  assert.equal(merged[0].task_id, 'task_new');
  assert.equal(merged[0].recommendationOnly, false);
  assert.equal(merged.some((item) => item.task_id === 'task_old'), false);
});

test('feedbackReasonOptions switches to dislike reasons for low ratings', () => {
  assert.deepEqual(feedbackReasonOptions(2), [
    '太累',
    '太贵',
    '不想出门',
    '时间太长',
    '不感兴趣',
    '社交压力大',
  ]);
  assert.deepEqual(feedbackReasonOptions(5), [
    '容易开始',
    '符合当前状态',
    '下次还想做',
    '时间刚好',
    '推荐准确',
  ]);
});

test('planFailureRecoveryOptions converts backend 409 details into actionable fixes', () => {
  const options = planFailureRecoveryOptions({
    missing_categories: ['社交连接'],
    recovery_options: [
      {
        id: 'relax_constraints',
        label: '放宽条件重新生成',
        description: '扩大出行和同行范围。',
        profile_patch: { outing: 'any', company: 'both', budget: 'high' },
      },
    ],
  });

  assert.equal(options.length, 1);
  assert.equal(options[0].id, 'relax_constraints');
  assert.equal(options[0].missingCategoriesText, '社交连接');
  assert.deepEqual(options[0].profilePatch, {
    outing: 'any',
    company: 'both',
    budget: 'high',
  });
});
