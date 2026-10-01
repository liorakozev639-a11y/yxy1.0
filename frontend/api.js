(function (root, factory) {
  const exported = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  if (root) {
    const client = exported.createApi({
      fetchImpl: root.fetch.bind(root),
      storage: root.localStorage,
      baseUrl: root.FREE_TIME_API_BASE_URL,
    });
    root.FreeTimeApi = { ...exported, ...client };
  }
}(typeof window !== 'undefined' ? window : null, function () {
  const STORAGE_KEY = 'free_time_agent_session_id';
  const USER_STORAGE_KEY = 'free_time_agent_user_id';
  const QUICK_STORAGE_KEY = 'free_time_agent_quick_session_id';
  const TEST_ANONYMOUS_ID_KEY = 'mvp_test_anonymous_id';
  const ADMIN_TOKEN_STORAGE_KEY = 'mvp_admin_metrics_token';
  let anonymousIdSequence = 0;
  const generatedAnonymousIds = new Set();

  function randomUint32() {
    try {
      if (typeof globalThis !== 'undefined' && globalThis.crypto && typeof globalThis.crypto.getRandomValues === 'function') {
        const values = new Uint32Array(1);
        globalThis.crypto.getRandomValues(values);
        return values[0];
      }
    } catch (_) {
      // Fall through to the session-local entropy source.
    }
    anonymousIdSequence += 1;
    const time = Date.now() >>> 0;
    const random = Math.floor(Math.random() * 0x100000000) >>> 0;
    return (time ^ random ^ anonymousIdSequence) >>> 0;
  }

  function generateTestAnonymousId() {
    for (let attempt = 0; attempt < 32; attempt += 1) {
      const number = 100000 + (randomUint32() % 900000);
      const candidate = `student_${number}`;
      if (!generatedAnonymousIds.has(candidate)) {
        generatedAnonymousIds.add(candidate);
        return candidate;
      }
    }
    anonymousIdSequence += 1;
    const number = 100000 + (anonymousIdSequence % 900000);
    const candidate = `student_${number}`;
    generatedAnonymousIds.add(candidate);
    return candidate;
  }

  function isLocalHostname(hostname) {
    return hostname === 'localhost'
      || hostname === '127.0.0.1'
      || hostname.startsWith('192.168.')
      || hostname.startsWith('10.')
      || /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname);
  }

  function defaultBaseUrl() {
    if (typeof window !== 'undefined' && window.location?.hostname) {
      const hostname = window.location.hostname;
      if (isLocalHostname(hostname)) {
        return `${window.location.protocol}//${hostname}:8000`;
      }
      return window.location.origin;
    }
    return 'http://127.0.0.1:8000';
  }

  const DEFAULT_BASE_URL = defaultBaseUrl();

  class ApiError extends Error {
    constructor(message, status, code, details) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.code = code;
      this.details = details;
    }
  }

  function createTestTelemetry({
    getAnonymousId,
    getSessionId,
    recordEvent,
    logger = typeof console !== 'undefined' ? console : null,
  } = {}) {
    if (typeof getAnonymousId !== 'function') throw new Error('getAnonymousId 必须是函数');
    if (typeof recordEvent !== 'function') throw new Error('recordEvent 必须是函数');
    let sequence = 0;

    function logFailure(error) {
      if (logger && typeof logger.debug === 'function') {
        logger.debug('test telemetry event failed', error?.code || error?.message || error);
      }
    }

    function idempotencyKey(event, anonymousId) {
      const scope = String(anonymousId || 'anonymous');
      if (event.idempotency_key) {
        const explicitKey = String(event.idempotency_key);
        return explicitKey.startsWith(`telemetry:${scope}:`)
          ? explicitKey
          : `telemetry:${scope}:${explicitKey}`;
      }
      if (event.action_id) return `telemetry:${scope}:${event.event_type}:${event.action_id}`;
      sequence += 1;
      return `telemetry:${scope}:${event.event_type}:${Date.now().toString(36)}:${sequence}:${Math.random().toString(36).slice(2, 10)}`;
    }

    function report(event) {
      try {
        const { action_id: _actionId, ...rest } = event;
        const anonymousId = getAnonymousId();
        const payload = {
          ...rest,
          anonymous_id: anonymousId,
          session_id: event.session_id ?? (typeof getSessionId === 'function' ? getSessionId() : null),
          metadata: event.metadata || {},
          idempotency_key: idempotencyKey(event, anonymousId),
        };
        return Promise.resolve(recordEvent(payload)).catch((error) => {
          logFailure(error);
          return { recorded: false };
        });
      } catch (error) {
        logFailure(error);
        return Promise.resolve({ recorded: false });
      }
    }

    return { report };
  }

  function dedupeRecommendationTelemetryItems(items) {
    const seen = new Set();
    return (Array.isArray(items) ? items : []).filter((item) => {
      const identity = item && (item.task_id || item.id || item.item_id);
      if (!identity || seen.has(identity)) return false;
      seen.add(identity);
      return true;
    });
  }

  function createApi({ fetchImpl, storage, baseUrl = DEFAULT_BASE_URL } = {}) {
    if (typeof fetchImpl !== 'function') throw new Error('fetchImpl 必须是函数');
    if (!storage) throw new Error('storage 不能为空');
    const apiBase = String(baseUrl || DEFAULT_BASE_URL).replace(/\/$/, '');
    let inMemoryTestAnonymousId = null;

    async function request(path, { method = 'GET', body, headers: extraHeaders = {} } = {}) {
      const headers = { ...extraHeaders };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      let response;
      try {
        response = await fetchImpl(`${apiBase}${path}`, {
          method,
          headers,
          ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        });
      } catch (_) {
        throw new ApiError('本地后端服务未启动，请先启动后端', 0, 'service_unreachable');
      }
      let payload;
      try {
        payload = await response.json();
      } catch (_) {
        throw new ApiError('服务返回了无法解析的数据', response.status, 'invalid_response');
      }
      if (!response.ok || payload.error) {
        const error = payload.error || {};
        const messages = {
          database_unavailable: 'PostgreSQL 数据库未连接，请检查数据库服务',
        };
        throw new ApiError(
          messages[error.code] || error.message || `请求失败（${response.status}）`,
          response.status,
          error.code || 'request_failed',
          error.details,
        );
      }
      return payload.data;
    }

    function getHealth() {
      return request('/health');
    }

    function getDatabaseHealth() {
      return request('/api/v1/health/database');
    }

    function getSessionId() {
      return storage.getItem(STORAGE_KEY);
    }

    function getQuickSessionId() {
      return storage.getItem(QUICK_STORAGE_KEY);
    }

    function currentUserId() {
      return storage.getItem(USER_STORAGE_KEY);
    }

    function getTestAnonymousId() {
      let existing = null;
      try {
        existing = storage.getItem(TEST_ANONYMOUS_ID_KEY);
      } catch (_) {
        // Private browsing and blocked storage still need a distinct session id.
      }
      if (existing) return existing;
      if (inMemoryTestAnonymousId) return inMemoryTestAnonymousId;
      const generated = generateTestAnonymousId();
      inMemoryTestAnonymousId = generated;
      try {
        storage.setItem(TEST_ANONYMOUS_ID_KEY, generated);
      } catch (_) {
        // Keep the id in the module/session memory when storage is unavailable.
      }
      return generated;
    }

    async function ensureAnonymousUser() {
      const existing = currentUserId();
      const data = await request('/api/v1/users/anonymous', {
        method: 'POST',
        body: existing ? { user_id: existing } : {},
      });
      if (data.user_id) storage.setItem(USER_STORAGE_KEY, data.user_id);
      return data;
    }

    function requireSessionId(sessionId) {
      const current = sessionId || getSessionId();
      if (!current) throw new ApiError('当前没有可用会话', 0, 'session_missing');
      return current;
    }

    async function createSession() {
      const data = await request('/api/v1/sessions', { method: 'POST' });
      storage.setItem(STORAGE_KEY, data.session_id);
      return data;
    }

    async function createQuickSession() {
      const data = await request('/api/v1/sessions', { method: 'POST' });
      storage.setItem(QUICK_STORAGE_KEY, data.session_id);
      return data;
    }

    function requireQuickSessionId(sessionId) {
      const current = sessionId || getQuickSessionId();
      if (!current) throw new ApiError('当前没有可用的极简会话', 0, 'session_missing');
      return current;
    }

    function forgetQuickSession() {
      storage.removeItem(QUICK_STORAGE_KEY);
    }

    function createQuickRecommendations(input, sessionId) {
      const current = requireQuickSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/quick-recommendations`, {
        method: 'POST', body: input,
      });
    }

    function getLatestQuickRecommendations(sessionId) {
      const current = requireQuickSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/quick-recommendations/latest`);
    }

    function sendQuickFeedback(runId, input, sessionId) {
      const current = requireQuickSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/quick-recommendations/${runId}/feedback`, {
        method: 'POST', body: input,
      });
    }

    function restoreSession(sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}`);
    }

    function savePreferences(preferences, sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/preferences`, {
        method: 'PUT',
        body: preferences,
      });
    }

    function startQuestionnaire(mode, sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/questionnaire/start`, {
        method: 'POST',
        body: { mode },
      });
    }

    function saveAnswer(questionId, value, sessionId) {
      const current = requireSessionId(sessionId);
      return request(
        `/api/v1/sessions/${current}/questionnaire/answers/${questionId}`,
        { method: 'PATCH', body: { value } },
      );
    }

    function skipQuestion(questionId, sessionId) {
      const current = requireSessionId(sessionId);
      return request(
        `/api/v1/sessions/${current}/questionnaire/skip/${questionId}`,
        { method: 'POST' },
      );
    }

    function getProgress(sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/questionnaire/progress`);
    }

    function submitQuestionnaire(sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/questionnaire/submit`, {
        method: 'POST',
      });
    }

    function getProfileInsight(sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/profile/insight`);
    }

    function getHistoryInsight(userId) {
      if (!userId) throw new ApiError('当前没有可用用户', 0, 'user_missing');
      return request(`/api/v1/users/${userId}/history/insight`);
    }

    function generatePlan(input, sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/plan/generate`, {
        method: 'POST',
        body: input,
      });
    }

    function getPlan(sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/plan`);
    }

    function updatePlanItem(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}`, {
        method: 'PATCH',
        body: input,
      });
    }

    function replacePlanItem(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/replace`, {
        method: 'POST',
        body: input,
      });
    }

    function adjustPlanItem(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/adjust`, {
        method: 'POST',
        body: input,
      });
    }

    function adjustRecommendationTask(taskId, input, sessionId) {
      const current = requireSessionId(sessionId);
      return request(`/api/v1/sessions/${current}/recommendations/${taskId}/adjust`, {
        method: 'POST',
        body: input,
      });
    }

    function skipPlanItem(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/skip`, {
        method: 'POST',
        body: input,
      });
    }

    function addCustomTask(planId, input) {
      return request(`/api/v1/plans/${planId}/custom-tasks`, {
        method: 'POST',
        body: input,
      });
    }

    function addRecommendedTask(planId, taskId, input) {
      return request(`/api/v1/plans/${planId}/recommended-tasks/${taskId}`, {
        method: 'POST',
        body: input,
      });
    }

    function confirmPlan(planId, input) {
      return request(`/api/v1/plans/${planId}/confirm`, {
        method: 'POST',
        body: input,
      });
    }

    function replan(planId, input) {
      return request(`/api/v1/plans/${planId}/replan`, {
        method: 'POST',
        body: input,
      });
    }

    function executionRequest(planId, itemId, action, input = {}) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/execution/${action}`, {
        method: 'POST',
        body: input,
      });
    }

    function startExecution(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'start', input);
    }

    function prepareExecution(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/execution/prepare`, {
        method: 'POST',
        body: input,
      });
    }

    function completeExecution(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'complete', input);
    }

    function skipExecution(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'skip', input);
    }

    function replacePlanItemEasier(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/replace-easier`, {
        method: 'POST',
        body: input,
      });
    }

    function checkExecutionDeadline(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'check-deadline', input);
    }

    function refreshExecution(planId) {
      return request(`/api/v1/plans/${planId}/execution/refresh`, {
        method: 'POST',
      });
    }

    function saveReflection(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/reflection`, {
        method: 'POST',
        body: input,
      });
    }

    function getReview(planId) {
      return request(`/api/v1/plans/${planId}/review`);
    }

    function saveFeedback(planId, itemId, input) {
      return request(`/api/v1/plans/${planId}/items/${itemId}/feedback`, {
        method: 'POST',
        body: input,
      });
    }

    function getFeedback(planId) {
      return request(`/api/v1/plans/${planId}/feedback`);
    }

    function identifyTestUser(anonymousId, cohort) {
      return request('/api/v1/test-users/identify', {
        method: 'POST',
        body: { anonymous_id: anonymousId, cohort },
      });
    }

    function recordTestEvent(event) {
      return request('/api/v1/test-events', {
        method: 'POST',
        body: event,
      });
    }

    function saveTestFeedback(feedback) {
      return request('/api/v1/test-feedback', {
        method: 'POST',
        body: feedback,
      });
    }

    function getAdminToken() {
      return storage.getItem(ADMIN_TOKEN_STORAGE_KEY);
    }

    async function adminLogin(username, password) {
      const data = await request('/api/v1/admin/login', {
        method: 'POST',
        body: { username, password },
      });
      if (data && data.token) storage.setItem(ADMIN_TOKEN_STORAGE_KEY, data.token);
      return data;
    }

    async function adminLogout() {
      const token = getAdminToken();
      if (!token) return { logged_out: false };
      try {
        return await request('/api/v1/admin/logout', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } finally {
        storage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      }
    }

    function adminMetrics(path, filters = {}) {
      const endpoint = String(path || '').replace(/^\/+/, '');
      const query = new URLSearchParams();
      Object.entries(filters || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') query.set(key, value);
      });
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const token = getAdminToken();
      return request(`/api/v1/admin/metrics/${endpoint}${suffix}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    }

    function deleteAdminTestUser(anonymousId) {
      const encodedId = encodeURIComponent(String(anonymousId || ''));
      const token = getAdminToken();
      return request(`/api/v1/admin/test-users/${encodedId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    }

    function cleanupAdminTestObservations() {
      const token = getAdminToken();
      return request('/api/v1/admin/test-observations/cleanup', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    }

    async function clearSession(sessionId) {
      const current = requireSessionId(sessionId);
      const data = await request(`/api/v1/sessions/${current}/data`, {
        method: 'DELETE',
      });
      storage.removeItem(STORAGE_KEY);
      return data;
    }

    function forgetSession() {
      storage.removeItem(STORAGE_KEY);
    }

    return {
      adjustPlanItem,
      adjustRecommendationTask,
      clearSession,
      addCustomTask,
      addRecommendedTask,
      checkExecutionDeadline,
      completeExecution,
      confirmPlan,
      createSession,
      createQuickSession,
      createQuickRecommendations,
      currentUserId,
      ensureAnonymousUser,
      forgetSession,
      forgetQuickSession,
      getFeedback,
      getHealth,
      getDatabaseHealth,
      getHistoryInsight,
      getReview,
      getProgress,
      getPlan,
      getProfileInsight,
      getSessionId,
      getQuickSessionId,
      getLatestQuickRecommendations,
      getAdminToken,
      getTestAnonymousId,
      generatePlan,
      identifyTestUser,
      recordTestEvent,
      saveTestFeedback,
      adminLogin,
      adminLogout,
      adminMetrics,
      cleanupAdminTestObservations,
      deleteAdminTestUser,
      restoreSession,
      replacePlanItem,
      replacePlanItemEasier,
      replan,
      refreshExecution,
      saveFeedback,
      saveAnswer,
      savePreferences,
      saveReflection,
      sendQuickFeedback,
      skipExecution,
      skipQuestion,
      skipPlanItem,
      startExecution,
      prepareExecution,
      startQuestionnaire,
      submitQuestionnaire,
      updatePlanItem,
    };
  }

  return {
    ADMIN_TOKEN_STORAGE_KEY,
    ApiError,
    DEFAULT_BASE_URL,
    STORAGE_KEY,
    TEST_ANONYMOUS_ID_KEY,
    USER_STORAGE_KEY,
    QUICK_STORAGE_KEY,
    createTestTelemetry,
    dedupeRecommendationTelemetryItems,
    createApi,
  };
}));
