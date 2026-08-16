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
  const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

  class ApiError extends Error {
    constructor(message, status, code, details) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.code = code;
      this.details = details;
    }
  }

  function createApi({ fetchImpl, storage, baseUrl = DEFAULT_BASE_URL } = {}) {
    if (typeof fetchImpl !== 'function') throw new Error('fetchImpl 必须是函数');
    if (!storage) throw new Error('storage 不能为空');
    const apiBase = String(baseUrl || DEFAULT_BASE_URL).replace(/\/$/, '');

    async function request(path, { method = 'GET', body } = {}) {
      const headers = {};
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const response = await fetchImpl(`${apiBase}${path}`, {
        method,
        headers,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
      let payload;
      try {
        payload = await response.json();
      } catch (_) {
        throw new ApiError('服务返回了无法解析的数据', response.status, 'invalid_response');
      }
      if (!response.ok || payload.error) {
        const error = payload.error || {};
        throw new ApiError(
          error.message || `请求失败（${response.status}）`,
          response.status,
          error.code || 'request_failed',
          error.details,
        );
      }
      return payload.data;
    }

    function getSessionId() {
      return storage.getItem(STORAGE_KEY);
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

    function completeExecution(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'complete', input);
    }

    function skipExecution(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'skip', input);
    }

    function checkExecutionDeadline(planId, itemId, input = {}) {
      return executionRequest(planId, itemId, 'check-deadline', input);
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
      clearSession,
      addCustomTask,
      checkExecutionDeadline,
      completeExecution,
      confirmPlan,
      createSession,
      forgetSession,
      getFeedback,
      getProgress,
      getPlan,
      getSessionId,
      generatePlan,
      restoreSession,
      replacePlanItem,
      replan,
      saveFeedback,
      saveAnswer,
      savePreferences,
      skipExecution,
      skipQuestion,
      skipPlanItem,
      startExecution,
      startQuestionnaire,
      submitQuestionnaire,
      updatePlanItem,
    };
  }

  return { ApiError, DEFAULT_BASE_URL, STORAGE_KEY, createApi };
}));
