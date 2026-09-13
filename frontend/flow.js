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

  function formatShareTime(value) {
    if (!value) return '--:--';
    const text = String(value);
    const match = text.match(/T(\d{2}):(\d{2})/);
    if (match) return `${match[1]}:${match[2]}`;
    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return '--:--';
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }

  function shareStatusLabel(status) {
    return {
      active: '进行中',
      completed: '已完成',
      missed: '已错过',
      needs_adjustment: '待调整',
      overdue: '已超时',
      pending: '待开始',
      recommended: '待安排',
      skipped: '已跳过',
    }[status || 'pending'] || '待开始';
  }

  function buildPlanShareText({ sessionId, categories, plan }) {
    const items = Array.isArray(plan && plan.items) ? plan.items : [];
    const lines = [
      '留白计划执行清单',
      `Session：${sessionId || '未创建'}`,
    ];
    if (Array.isArray(categories) && categories.length > 0) {
      lines.push(`方向：${categories.join('、')}`);
    }
    lines.push('');
    if (items.length === 0) {
      lines.push('当前还没有可分享的任务。');
    } else {
      items.forEach((item, index) => {
        const start = formatShareTime(item.start_at);
        const end = formatShareTime(item.end_at);
        const title = item.title || '未命名任务';
        const category = item.category ? `｜${item.category}` : '';
        lines.push(`${String(index + 1).padStart(2, '0')}. ${start}-${end} ${title}${category}｜状态：${shareStatusLabel(item.status)}`);
      });
    }
    lines.push('');
    lines.push('来自「留白计划」：把空闲时间变成可以开始的小安排。');
    return lines.join('\n');
  }

  function feedbackReasonOptions(rating) {
    const score = Number(rating);
    if (Number.isFinite(score) && score <= 2) {
      return ['太累', '太贵', '不想出门', '时间太长', '不感兴趣', '社交压力大'];
    }
    if (Number.isFinite(score) && score === 3) {
      return ['还可以', '时间一般', '有点费力', '可以偶尔做'];
    }
    return ['容易开始', '符合当前状态', '下次还想做', '时间刚好', '推荐准确'];
  }

  function planFailureRecoveryOptions(details) {
    const rawOptions = Array.isArray(details && details.recovery_options)
      ? details.recovery_options
      : [];
    const missing = Array.isArray(details && details.missing_categories)
      ? details.missing_categories
      : [];
    return rawOptions.map((option) => ({
      id: option.id || 'recovery',
      label: option.label || '调整后重试',
      description: option.description || '',
      profilePatch: option.profile_patch || {},
      removeMissingCategories: Boolean(option.remove_missing_categories),
      missingCategoriesText: missing.join('、'),
    }));
  }

  function lifeContextSummary(profile) {
    const weatherLabels = {
      clear: '天气适合外出',
      rainy: '下雨或天气不稳定',
      hot: '天气偏热',
      cold: '天气偏冷',
      indoor: '今天想待在室内',
    };
    const dayPartLabels = {
      morning: '上午',
      afternoon: '下午',
      evening: '晚上',
      late: '睡前',
    };
    const energyLabels = {
      low: '低精力',
      medium: '中等精力',
      high: '高精力',
    };
    const moodLabels = {
      empty: '想放空',
      anxious: '有点焦虑',
      bored: '有点无聊',
      recharge: '想充电',
    };
    return [
      weatherLabels[profile && profile.weather],
      dayPartLabels[profile && profile.day_part],
      energyLabels[profile && profile.energy_level],
      moodLabels[profile && profile.mood],
    ].filter(Boolean);
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
    buildPlanShareText,
    feedbackReasonOptions,
    firstUnansweredIndex,
    lifeContextSummary,
    recommendationMemorySummary,
    mergeRecommendedItems,
    planFailureRecoveryOptions,
    recoverInitialization,
    resumeDestination,
    taskReasonSummary,
  };
}));
