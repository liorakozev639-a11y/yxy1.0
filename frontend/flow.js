(function (root, factory) {
  const exported = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  if (root) root.FreeTimeFlow = exported;
}(typeof window !== 'undefined' ? window : null, function () {
  function resumeDestination({ preferences, progress }) {
    const categories = preferences && preferences.categories;
    if (!Array.isArray(categories) || categories.length === 0) return 'welcome';
    if (!progress) return 'mode';
    return progress.submitted ? 'result' : 'quiz';
  }

  function firstUnansweredIndex(questions, answers) {
    const index = questions.findIndex((question) => !answers[question.id]);
    return index >= 0 ? index : Math.max(0, questions.length - 1);
  }

  async function recoverInitialization(api, error) {
    if (!error || ![404, 410].includes(error.status)) {
      return {
        recovered: false,
        retry: true,
        message: error && error.message ? error.message : '无法连接本地服务',
      };
    }
    api.forgetSession();
    try {
      return {
        recovered: true,
        retry: false,
        session: await api.createSession(),
      };
    } catch (recoveryError) {
      return {
        recovered: false,
        retry: true,
        message: recoveryError.message || '无法创建新会话',
      };
    }
  }

  return { firstUnansweredIndex, recoverInitialization, resumeDestination };
}));
