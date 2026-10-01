const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
  ADMIN_TOKEN_STORAGE_KEY,
  TEST_ANONYMOUS_ID_KEY,
  createTestTelemetry,
  createApi,
  dedupeRecommendationTelemetryItems,
} = require('../frontend/api.js');

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return { data, error: null }; },
  };
}

test('testing API persists anonymous identity and posts observation feedback', async () => {
  const calls = [];
  const store = storage({ [TEST_ANONYMOUS_ID_KEY]: 'student_001' });
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response({ token: 'admin-token', recorded: true });
    },
  });

  assert.equal(api.getTestAnonymousId(), 'student_001');

  await api.identifyTestUser('student_001', 'student_2026_09');
  await api.recordTestEvent({
    anonymous_id: 'student_001',
    event_type: 'task_completed',
    session_id: 'sess_1',
    idempotency_key: 'task_completed:sess_1:item_1',
  });
  await api.saveTestFeedback({
    anonymous_id: 'student_001',
    session_id: 'sess_1',
    plan_item_id: 'item_1',
    rating: 5,
    comment: '很好开始',
  });

  assert.deepEqual(calls.map(({ url, options }) => [url, options.method]), [
    ['http://127.0.0.1:8000/api/v1/test-users/identify', 'POST'],
    ['http://127.0.0.1:8000/api/v1/test-events', 'POST'],
    ['http://127.0.0.1:8000/api/v1/test-feedback', 'POST'],
  ]);
  assert.equal(JSON.parse(calls[2].options.body).comment, '很好开始');
});

test('testing identity is generated once and reused from localStorage', () => {
  const store = storage();
  const api = createApi({ storage: store, fetchImpl: async () => response({}) });
  const first = api.getTestAnonymousId();
  const second = api.getTestAnonymousId();

  assert.match(first, /^student_\d{6}$/);
  assert.equal(second, first);
  assert.equal(store.getItem(TEST_ANONYMOUS_ID_KEY), first);
});

test('admin login stores token and metric requests send filters without user state', async () => {
  const calls = [];
  const store = storage({ [TEST_ANONYMOUS_ID_KEY]: 'student_002' });
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(url.endsWith('/login')
        ? { token: 'admin-token', expires_at: '2026-10-01T12:00:00Z' }
        : { user_count: 2 });
    },
  });

  await api.adminLogin('admin', 'secret');
  await api.adminMetrics('summary', {
    from: '2026-09-01',
    to: '2026-09-30',
    cohort: 'student_2026_09',
    anonymous_id: 'student_002',
  });

  assert.equal(store.getItem(ADMIN_TOKEN_STORAGE_KEY), 'admin-token');
  assert.match(calls[1].url, /\/api\/v1\/admin\/metrics\/summary\?/);
  assert.match(calls[1].url, /anonymous_id=student_002/);
  assert.equal(calls[1].options.headers.Authorization, 'Bearer admin-token');
  assert.equal(store.getItem(TEST_ANONYMOUS_ID_KEY), 'student_002');
});

test('frontend wires success-only telemetry and swallows telemetry failures', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  assert.match(app, /mvp_test_anonymous_id/);
  assert.match(app, /function reportTestEvent\(/);
  assert.match(app, /console\.debug\(/);
  for (const eventType of [
    'session_created',
    'questionnaire_started',
    'questionnaire_completed',
    'recommendations_viewed',
    'task_started',
    'task_completed',
    'task_skipped',
    'task_replaced',
    'feedback_submitted',
  ]) {
    assert.match(app, new RegExp(eventType));
  }
  assert.match(app, /saveTestFeedback/);
  assert.match(app, /reason_code/);
});

test('telemetry payloads get unique action keys while retries can reuse an explicit key', async () => {
  const payloads = [];
  const telemetry = createTestTelemetry({
    getAnonymousId: () => 'student_003',
    getSessionId: () => 'sess_3',
    recordEvent: async (payload) => {
      payloads.push(payload);
      return { recorded: true };
    },
  });

  await telemetry.report({
    event_type: 'task_replaced',
    plan_id: 'plan_3',
    plan_item_id: 'item_3',
    metadata: { task_category: '自我成长' },
  });
  await telemetry.report({
    event_type: 'task_replaced',
    plan_id: 'plan_3',
    plan_item_id: 'item_3',
    metadata: { task_category: '自我成长' },
  });
  await telemetry.report({
    event_type: 'task_skipped',
    action_id: 'user-action-7',
    reason_code: 'not_enough_time',
  });
  await telemetry.report({
    event_type: 'task_skipped',
    action_id: 'user-action-7',
    reason_code: 'not_enough_time',
  });

  assert.notEqual(payloads[0].idempotency_key, payloads[1].idempotency_key);
  assert.equal(payloads[0].metadata.task_category, '自我成长');
  assert.equal(payloads[2].idempotency_key, payloads[3].idempotency_key);
  assert.equal('action_id' in payloads[2], false);
});

test('telemetry idempotency keys are scoped by anonymous user while same-user retries stay stable', async () => {
  const payloads = [];
  const createReporter = (anonymousId) => createTestTelemetry({
    getAnonymousId: () => anonymousId,
    getSessionId: () => 'sess_shared',
    recordEvent: async (payload) => {
      payloads.push(payload);
      return { recorded: true };
    },
  });
  const firstUser = createReporter('student_004');
  const secondUser = createReporter('student_005');
  const event = { event_type: 'task_skipped', action_id: 'same-action' };

  await firstUser.report(event);
  await firstUser.report(event);
  await secondUser.report(event);

  assert.equal(payloads[0].idempotency_key, payloads[1].idempotency_key);
  assert.notEqual(payloads[0].idempotency_key, payloads[2].idempotency_key);
  assert.match(payloads[0].idempotency_key, /student_004/);
  assert.match(payloads[2].idempotency_key, /student_005/);
});

test('recommendation telemetry dedupe uses the visible card task identity', () => {
  const items = dedupeRecommendationTelemetryItems([
    { id: 'recommendation-task-1', category: '自我成长' },
    { id: 'plan-item-1', task_id: 'recommendation-task-1', category: '自我成长' },
    { id: 'recommendation-task-2', category: '健康生活' },
  ]);

  assert.deepEqual(items.map((item) => item.id), [
    'recommendation-task-1',
    'recommendation-task-2',
  ]);
});

test('recommendation hooks include category metadata and quick mode reports flow errors safely', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  assert.match(app, /function reportRecommendationsViewed\(/);
  assert.match(app, /task_category: item\.category/);
  assert.match(app, /mode: 'quick',[\s\S]*?task_category: item\.category/);
  assert.match(app, /async function runQuickTask\([\s\S]*?event_type: 'flow_error'/);
  assert.match(app, /runQuickTask\([\s\S]*?reportTestEvent\([\s\S]*?flow_error/);
});

test('all recommendation adjustment actions map to allowed reason codes', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  for (const [adjustment, reason] of [
    ['easier', 'low_energy'],
    ['shorter', 'not_enough_time'],
    ['cheaper', 'over_budget'],
    ['nearer', 'location_inconvenient'],
    ['less_social', 'not_matching_current_state'],
    ['more_growth', 'not_matching_current_state'],
  ]) {
    assert.match(app, new RegExp(`${adjustment}: '${reason}'`));
  }
});

test('admin dashboard is isolated and requests all required metric views', () => {
  const frontendDir = path.join(__dirname, '..', 'frontend');
  const html = fs.readFileSync(path.join(frontendDir, 'admin.html'), 'utf8');
  const js = fs.readFileSync(path.join(frontendDir, 'admin.js'), 'utf8');
  const css = fs.readFileSync(path.join(frontendDir, 'admin.css'), 'utf8');

  assert.match(html, /admin\.js/);
  assert.match(html, /admin\.css/);
  assert.match(html, /admin-login/);
  assert.match(html, /anonymous_id/);
  assert.match(js, /adminLogin/);
  for (const view of ['summary', 'funnel', 'recommendations', 'reasons', 'errors']) {
    assert.match(js, new RegExp(`adminMetrics\\(['"]${view}['"]`));
  }
  for (const filter of ['from', 'cohort', 'anonymous_id', 'task_category']) {
    assert.match(html, new RegExp(filter));
  }
  assert.match(js, /FormData\(filterForm\)/);
  assert.match(html, /个人|identity|姓名/);
  assert.match(css, /@media/);
});

test('admin dashboard exposes authenticated retention controls', async () => {
  const calls = [];
  const store = storage({ [ADMIN_TOKEN_STORAGE_KEY]: 'admin-token' });
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(url.includes('/cleanup') ? { deleted_users: 3, retention_days: 90 } : { deleted: 1 });
    },
  });

  await api.deleteAdminTestUser('student_001');
  await api.cleanupAdminTestObservations();

  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/admin/test-users/student_001');
  assert.equal(calls[0].options.method, 'DELETE');
  assert.equal(calls[1].url, 'http://127.0.0.1:8000/api/v1/admin/test-observations/cleanup');
  assert.equal(calls[1].options.method, 'POST');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer admin-token');

  const html = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'admin.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'admin.js'), 'utf8');
  assert.match(html, /admin-delete-user-form/);
  assert.match(html, /admin-cleanup/);
  assert.match(html, /90 天/);
  assert.match(js, /window\.confirm/);
  assert.match(js, /deleteAdminTestUser/);
  assert.match(js, /cleanupAdminTestObservations/);
});
