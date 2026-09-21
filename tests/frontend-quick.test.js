const assert = require('node:assert/strict');
const test = require('node:test');

const { selectQuickTask, afterQuickDislike } = require('../frontend/flow.js');
const { STORAGE_KEY, QUICK_STORAGE_KEY, createApi } = require('../frontend/api.js');
const fs = require('node:fs');
const path = require('node:path');

function storage() {
  const items = new Map([[STORAGE_KEY, 'full_1']]);
  return {
    getItem(key) { return items.get(key) || null; },
    setItem(key, value) { items.set(key, String(value)); },
    removeItem(key) { items.delete(key); },
  };
}

test('quick choice moves one candidate to the top without duplication', () => {
  const run = { primary_task: { id: 'a' }, alternatives: [{ id: 'b' }, { id: 'c' }] };
  const selected = selectQuickTask(run, 'b');
  assert.equal(selected.primary_task.id, 'b');
  assert.deepEqual(selected.alternatives.map((item) => item.id), ['a', 'c']);
  const next = afterQuickDislike(selected, 'b');
  assert.equal(next.primary_task.id, 'a');
  assert.deepEqual(next.alternatives.map((item) => item.id), ['c']);
  assert.equal(run.primary_task.id, 'a');
});

test('disliking the last task leaves a real empty state', () => {
  const next = afterQuickDislike({ primary_task: { id: 'a' }, alternatives: [] }, 'a');
  assert.equal(next.primary_task, null);
  assert.deepEqual(next.alternatives, []);
});

test('quick session and API calls do not overwrite full session', async () => {
  const calls = [];
  const local = storage();
  const api = createApi({ storage: local, fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true, status: 200,
      async json() {
        return { data: url.endsWith('/sessions') ? { session_id: 'quick_1' } : { run_id: 'run_1' }, error: null };
      },
    };
  } });
  await api.createQuickSession();
  await api.createQuickRecommendations({ available_minutes: 15, energy_level: 'low', user_id: 'u' });
  await api.getLatestQuickRecommendations();
  await api.sendQuickFeedback('run_1', { action: 'rest_selected' });
  assert.equal(local.getItem(STORAGE_KEY), 'full_1');
  assert.equal(local.getItem(QUICK_STORAGE_KEY), 'quick_1');
  assert.deepEqual(calls.map((call) => call.options.method), ['POST', 'POST', 'GET', 'POST']);
  assert.ok(calls.slice(1).every((call) => call.url.includes('/sessions/quick_1/quick-recommendations')));
});

test('quick alternatives and history name the constraints and feedback distinctly', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  assert.match(app, /quick-alternative[\s\S]*居家[\s\S]*无需花费/);
  assert.match(app, /极简反馈/);
  assert.match(app, /喜欢[\s\S]*不喜欢/);
});
