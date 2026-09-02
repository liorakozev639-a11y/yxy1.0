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

  function taskReasonSummary(item) {
    const category = item && item.category ? item.category : '当前分类';
    const profile = item && item.load_profile;
    const loadProfile = profile ? {
      ease: profile.ease_label || '',
      physical: profile.physical_label || '',
      social: profile.social_label || '',
      location: profile.location_label || '',
    } : null;
    return {
      tags: Array.isArray(item && item.reason_tags) && item.reason_tags.length > 0
        ? item.reason_tags
        : [`覆盖${category}`],
      text: item && item.reason_text
        ? item.reason_text
        : `该任务覆盖「${category}」，并已进入当前计划。`,
      matchScore: Number.isFinite(Number(item && item.match_score))
        ? Number(item.match_score)
        : null,
      matchedPreferences: Array.isArray(item && item.matched_preferences)
        ? item.matched_preferences
        : [],
      loadProfile,
      warningText: item && item.warning_text ? item.warning_text : '',
      replacementReason: item && item.replacement_reason ? item.replacement_reason : '',
    };
  }

  function recommendationMemorySummary(memory) {
    const count = Number(memory && memory.excluded_group_count);
    if (!Number.isInteger(count) || count <= 0) return '';
    return `已为你避开 ${count} 组不喜欢的任务`;
  }

  function mergeRecommendedItems(items, recommendedTasks) {
    const planItems = Array.isArray(items) ? items : [];
    const scheduledByTaskId = new Map(
      planItems
        .filter((item) => item.kind === 'task' && item.task_id)
        .map((item) => [item.task_id, item]),
    );
    const replacementByPreviousTaskId = new Map();
    planItems
      .filter((item) => item.kind === 'task' && item.task_id)
      .forEach((item) => {
        const history = Array.isArray(item.replacement_history)
          ? item.replacement_history
          : [];
        history.forEach((taskId) => {
          if (taskId !== item.task_id) {
            replacementByPreviousTaskId.set(taskId, item);
          }
        });
      });

    return (Array.isArray(recommendedTasks) ? recommendedTasks : []).flatMap((task, index) => {
      const scheduled = scheduledByTaskId.get(task.id);
      const replacement = scheduled || replacementByPreviousTaskId.get(task.id);
      if (replacement) {
        return [{
          ...task,
          ...replacement,
          recommendationIndex: index,
          recommendationOnly: false,
        }];
      }
      return [{
        ...task,
        id: `recommendation-${task.id}`,
        task_id: task.id,
        kind: 'task',
        status: 'recommended',
        start_at: null,
        end_at: null,
        recommendationIndex: index,
        recommendationOnly: true,
      }];
    });
  }

  return {
    firstUnansweredIndex,
    recommendationMemorySummary,
    mergeRecommendedItems,
    recoverInitialization,
    resumeDestination,
    taskReasonSummary,
  };
}));
