const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const { STORAGE_KEY, createApi } = require('../frontend/api.js');

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

function response(data) {
  return { ok: true, status: 200, async json() { return { data, error: null }; } };
}

test('execution API methods use phase two routes', async () => {
  const calls = [];
  const store = storage();
  store.setItem(STORAGE_KEY, 'sess_frontend');
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response({ status: 'active' });
    },
  });

  await api.startExecution('plan_1', 'item_1');
  await api.completeExecution('plan_1', 'item_1');
  await api.skipExecution('plan_1', 'item_1');
  await api.checkExecutionDeadline('plan_1', 'item_1');
  await api.saveFeedback('plan_1', 'item_1', { rating: 5, reasons: ['容易开始'] });
  await api.refreshExecution('plan_1');
  await api.saveReflection('plan_1', 'item_1', { sentiment: 'neutral' });
  await api.getReview('plan_1');

  assert.deepEqual(calls.map(({ url, options }) => [url, options.method]), [
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/start', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/complete', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/skip', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/check-deadline', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/feedback', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/execution/refresh', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/reflection', 'POST'],
    ['http://127.0.0.1:8000/api/v1/plans/plan_1/review', 'GET'],
  ]);
});

test('result view presents recommended times and execution controls', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  assert.match(app, /推荐时间/);
  assert.match(app, /按此流程执行/);
  assert.match(app, /已按流程执行/);
  assert.match(app, /data-action="start-execution"/);
  assert.match(app, /data-action="complete-execution"/);
  assert.match(app, /data-action="skip-execution"/);
  assert.match(app, /data-action="save-feedback"/);
  assert.match(app, /needs_adjustment/);
  assert.match(app, /recommendationMemorySummary/);
  assert.match(app, /replacementReason/);
  assert.match(app, /api\.refreshExecution/);
  assert.match(app, /setInterval\(/);
  assert.match(app, /clearInterval\(/);
  assert.match(app, /async function initialize\(\)[\s\S]*?state\.busy = false;\s*render\(\);\s*syncExecutionRefresh\(\);/);
  assert.match(app, /data-action="view-review"/);
  assert.match(app, /data-action="save-reflection"/);
  assert.match(app, /satisfied/);
  assert.match(app, /neutral/);
  assert.match(app, /dissatisfied/);
});
