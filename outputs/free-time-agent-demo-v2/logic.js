(function () {
  var stageOrder = [
    'welcome',
    'interests',
    'conditions',
    'questionnaire',
    'recommendations',
    'plan',
    'execution',
    'summary',
  ];

  var stageLabelMap = {
    welcome: '欢迎',
    interests: '兴趣方向',
    conditions: '前置条件',
    questionnaire: '问卷',
    recommendations: '推荐',
    plan: '计划',
    execution: '执行',
    summary: '总结',
  };

  var budgetOrder = {
    free: 0,
    low: 1,
    medium: 2,
    high: 3,
  };

  var durationLimits = {
    short: 90,
    medium: 180,
    'half-day': 360,
  };

  var windowDurations = {
    short: 60,
    medium: 180,
    'half-day': 240,
  };

  var densityConfigs = {
    light: {
      usage: 0.52,
      restMinutes: 30,
      maxTasks: 2,
      gapMinutes: 15,
      restFirst: true,
    },
    balanced: {
      usage: 0.72,
      restMinutes: 20,
      maxTasks: 4,
      gapMinutes: 10,
      restFirst: false,
    },
    full: {
      usage: 0.9,
      restMinutes: 10,
      maxTasks: 5,
      gapMinutes: 5,
      restFirst: false,
    },
  };

  var adjustmentStatuses = {
    missed: true,
    overdue: true,
    skipped: true,
    paused: true,
  };

  var allCategories = ['energy', 'calm', 'social', 'explore', 'growth'];
  var questionnaireScale = ['非常同意', '比较同意', '不太同意', '完全不同意'];

  var questionBank = {
    energy: [
      { id: 'energy-core', category: 'energy', prompt: '我现在更需要一点身体上的启动感。', reverse: false },
      { id: 'energy-momentum', category: 'energy', prompt: '只要开始动起来，我通常会越来越有精神。', reverse: false },
      { id: 'energy-outdoor', category: 'energy', prompt: '去户外活动会让我很快进入状态。', reverse: false },
      { id: 'energy-delay', category: 'energy', prompt: '想到要动起来，我会下意识往后拖。', reverse: true },
      { id: 'energy-social-boost', category: 'energy', prompt: '和别人一起行动会让我更愿意出门。', reverse: false },
      { id: 'energy-low-threshold', category: 'energy', prompt: '如果动作门槛太高，我今天宁愿不开始。', reverse: true },
    ],
    calm: [
      { id: 'calm-core', category: 'calm', prompt: '我现在更想先把自己安顿下来。', reverse: false },
      { id: 'calm-silence', category: 'calm', prompt: '安静一点的环境会让我恢复得更快。', reverse: false },
      { id: 'calm-sensory', category: 'calm', prompt: '音乐、阅读或电影这类沉浸式活动更适合我。', reverse: false },
      { id: 'calm-restless', category: 'calm', prompt: '如果只是安静待着，我反而会更烦躁。', reverse: true },
      { id: 'calm-solo', category: 'calm', prompt: '今天我更能接受独处的节奏。', reverse: false },
      { id: 'calm-overload', category: 'calm', prompt: '我现在不想处理太多临场决定。', reverse: false },
    ],
    social: [
      { id: 'social-core', category: 'social', prompt: '和人连接一下会让我感觉更好。', reverse: false },
      { id: 'social-light', category: 'social', prompt: '我更想要轻松聊天，而不是正式安排。', reverse: false },
      { id: 'social-company', category: 'social', prompt: '如果有人陪着，我会更容易开始今天的活动。', reverse: false },
      { id: 'social-drain', category: 'social', prompt: '想到社交，我会先担心自己被耗尽。', reverse: true },
      { id: 'social-spontaneous', category: 'social', prompt: '临时约人对我来说是可以接受的。', reverse: false },
      { id: 'social-small-dose', category: 'social', prompt: '一点点陪伴就足够，不必把时间排满。', reverse: false },
    ],
    explore: [
      { id: 'explore-core', category: 'explore', prompt: '我想换个画面，看看不一样的地方。', reverse: false },
      { id: 'explore-wander', category: 'explore', prompt: '没有明确目标地走走逛逛也很可以。', reverse: false },
      { id: 'explore-curiosity', category: 'explore', prompt: '新鲜感会明显提高我今天的兴趣。', reverse: false },
      { id: 'explore-friction', category: 'explore', prompt: '一想到路线和来回折腾，我就没劲了。', reverse: true },
      { id: 'explore-observe', category: 'explore', prompt: '带着一个小主题去观察环境会很有趣。', reverse: false },
      { id: 'explore-gentle', category: 'explore', prompt: '我希望探索感是轻量的，不要太用力。', reverse: false },
    ],
    growth: [
      { id: 'growth-core', category: 'growth', prompt: '我想把这段时间用在让自己更有收获的事情上。', reverse: false },
      { id: 'growth-focus', category: 'growth', prompt: '哪怕只有一点进展，也会让我感觉今天没白过。', reverse: false },
      { id: 'growth-reset', category: 'growth', prompt: '整理环境或复盘思路也算是有价值的成长。', reverse: false },
      { id: 'growth-pressure', category: 'growth', prompt: '如果一件事看起来像任务，我今天就会抗拒。', reverse: true },
      { id: 'growth-learn', category: 'growth', prompt: '学一点新东西会让我更有满足感。', reverse: false },
      { id: 'growth-soft', category: 'growth', prompt: '我更适合低压力但有方向感的小进展。', reverse: false },
    ],
  };

  var activityLibrary = [
    { id: 'stretch-reset', title: '居家拉伸和放松', category: 'energy', duration: 25, budget: 'free', mode: 'home', company: 'solo', energy: 'low', restFirst: true, reason: '先把身体活动开，适合从低门槛状态慢慢进入节奏。' },
    { id: 'dance-break', title: '跟着节奏跳一段', category: 'energy', duration: 35, budget: 'free', mode: 'home', company: 'solo', energy: 'medium', restFirst: false, reason: '适合想快速提振情绪和行动感的时候。' },
    { id: 'park-jog', title: '去附近开阔空间快走或慢跑', category: 'energy', duration: 50, budget: 'free', mode: 'near', company: 'either', energy: 'high', restFirst: false, reason: '适合需要透气和唤醒状态的半主动活动。' },
    { id: 'city-sports', title: '去公共运动场活动一下', category: 'energy', duration: 80, budget: 'low', mode: 'city', company: 'pair', energy: 'high', restFirst: false, reason: '更适合结伴出门，把运动变成轻社交。' },
    { id: 'music-reset', title: '听一张完整专辑', category: 'calm', duration: 40, budget: 'free', mode: 'home', company: 'solo', energy: 'low', restFirst: true, reason: '适合先休息一下，让注意力慢慢回到自己身上。' },
    { id: 'reading-hour', title: '安静读一会儿书', category: 'calm', duration: 60, budget: 'free', mode: 'home', company: 'solo', energy: 'low', restFirst: true, reason: '比刷信息流更稳，适合恢复专注和情绪。' },
    { id: 'tea-window', title: '找个安静角落喝点热饮', category: 'calm', duration: 45, budget: 'low', mode: 'near', company: 'either', energy: 'low', restFirst: true, reason: '适合就近切换环境，但不需要复杂安排。' },
    { id: 'park-bench', title: '去绿地坐坐再散步', category: 'calm', duration: 75, budget: 'free', mode: 'near', company: 'either', energy: 'low', restFirst: true, reason: '能保留一点外出感，又不过度消耗。' },
    { id: 'movie-night', title: '看一部完整电影', category: 'calm', duration: 130, budget: 'low', mode: 'home', company: 'either', energy: 'low', restFirst: true, reason: '适合需要完整沉浸、不想频繁做决定的时候。' },
    { id: 'friend-dinner', title: '和朋友认真吃顿饭', category: 'social', duration: 120, budget: 'high', mode: 'city', company: 'pair', energy: 'medium', restFirst: false, reason: '把见面这件事做得从容一点，适合留出完整聊天时间。' },
    { id: 'board-game', title: '约人玩桌游或轻松小游戏', category: 'social', duration: 140, budget: 'medium', mode: 'city', company: 'pair', energy: 'medium', restFirst: false, reason: '适合想互动但不想把行程排得太正式。' },
    { id: 'walk-and-talk', title: '边散步边聊天', category: 'social', duration: 70, budget: 'free', mode: 'near', company: 'pair', energy: 'low', restFirst: true, reason: '社交压力比正襟危坐更小，也更容易开始。' },
    { id: 'cook-together', title: '一起做顿简单的饭', category: 'social', duration: 90, budget: 'medium', mode: 'home', company: 'pair', energy: 'medium', restFirst: false, reason: '适合把陪伴和具体的小事结合起来。' },
    { id: 'city-walk', title: '换个片区随意走走', category: 'explore', duration: 110, budget: 'low', mode: 'city', company: 'either', energy: 'medium', restFirst: false, reason: '适合想换画面、看看不同街景的时候。' },
    { id: 'photo-theme', title: '带着一个主题去拍照', category: 'explore', duration: 100, budget: 'free', mode: 'near', company: 'either', energy: 'medium', restFirst: false, reason: '给散步增加一点观察任务，会更有新鲜感。' },
    { id: 'market-stroll', title: '逛逛公共市集或书摊', category: 'explore', duration: 95, budget: 'medium', mode: 'city', company: 'either', energy: 'medium', restFirst: false, reason: '适合不设结果地浏览，靠现场刺激找灵感。' },
    { id: 'micro-exhibit', title: '看一个小型公共展览', category: 'explore', duration: 90, budget: 'low', mode: 'city', company: 'either', energy: 'low', restFirst: true, reason: '有外出和新鲜感，但节奏仍然比较温和。' },
    { id: 'room-reset', title: '整理一下房间和桌面', category: 'growth', duration: 45, budget: 'free', mode: 'home', company: 'solo', energy: 'medium', restFirst: false, reason: '先把环境变顺手，后面的行动阻力会低很多。' },
    { id: 'skill-sprint', title: '学一个新技能的小节', category: 'growth', duration: 75, budget: 'free', mode: 'home', company: 'solo', energy: 'medium', restFirst: false, reason: '适合留一段完整时间，获得一点明确进展。' },
    { id: 'long-note', title: '写一页复盘或随想', category: 'growth', duration: 50, budget: 'free', mode: 'home', company: 'solo', energy: 'low', restFirst: true, reason: '更像整理思路，不需要马上产出结果。' },
    { id: 'library-study', title: '换个公共学习环境做事', category: 'growth', duration: 120, budget: 'low', mode: 'city', company: 'solo', energy: 'medium', restFirst: false, reason: '适合需要一点环境切换来重启专注。' },
  ];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function cloneActivity(activity) {
    return {
      id: activity.id,
      title: activity.title,
      category: activity.category,
      duration: activity.duration,
      budget: activity.budget,
      mode: activity.mode,
      company: activity.company,
      energy: activity.energy,
      restFirst: activity.restFirst,
      reason: activity.reason,
    };
  }

  function getActivityLibrary() {
    return activityLibrary.map(cloneActivity);
  }

  function getSelectedCategories(preferences) {
    if (!preferences || !Array.isArray(preferences.selectedCategories)) {
      return [];
    }
    return preferences.selectedCategories.filter(function (category) {
      return allCategories.indexOf(category) >= 0;
    });
  }

  function normalizeCategories(selectedCategories) {
    var source = Array.isArray(selectedCategories) ? selectedCategories : [];
    var seen = {};
    var ordered = [];

    source.forEach(function (category) {
      if (allCategories.indexOf(category) >= 0 && !seen[category]) {
        seen[category] = true;
        ordered.push(category);
      }
    });

    allCategories.forEach(function (category) {
      if (!seen[category]) {
        ordered.push(category);
      }
    });

    return ordered;
  }

  function cloneQuestion(question) {
    return {
      id: question.id,
      category: question.category,
      prompt: question.prompt,
      options: questionnaireScale.slice(),
      reverse: question.reverse === true,
    };
  }

  function createQuestionnaire(mode, selectedCategories) {
    var normalizedMode = mode === 'deep' ? 'deep' : 'quick';
    var orderedCategories = normalizeCategories(selectedCategories);

    if (normalizedMode === 'quick') {
      return allCategories.map(function (category) {
        return cloneQuestion(questionBank[category][0]);
      });
    }

    return orderedCategories.reduce(function (questions, category) {
      return questions.concat(questionBank[category].map(cloneQuestion));
    }, []).slice(0, 30);
  }

  function includesCategory(activity, preferences) {
    var categories = getSelectedCategories(preferences);
    return categories.length === 0 || categories.indexOf(activity.category) >= 0;
  }

  function matchesOuting(activity, outing) {
    if (!outing) {
      return true;
    }
    return outing === 'city' ? activity.mode === 'city' : activity.mode === outing;
  }

  function matchesCompany(activity, company) {
    if (!company || company === 'either') {
      return true;
    }
    return activity.company === 'either' || activity.company === company;
  }

  function matchesBudget(activity, budget) {
    if (!budget || !Object.prototype.hasOwnProperty.call(budgetOrder, budget)) {
      return true;
    }
    return budgetOrder[activity.budget] <= budgetOrder[budget];
  }

  function matchesDuration(activity, duration) {
    if (!duration || !Object.prototype.hasOwnProperty.call(durationLimits, duration)) {
      return true;
    }
    return activity.duration <= durationLimits[duration];
  }

  function matchesHardConstraints(activity, preferences) {
    return matchesOuting(activity, preferences && preferences.outing) &&
      matchesCompany(activity, preferences && preferences.company) &&
      matchesBudget(activity, preferences && preferences.budget) &&
      matchesDuration(activity, preferences && preferences.duration);
  }

  function filterActivities(preferences) {
    return getActivityLibrary().filter(function (activity) {
      return includesCategory(activity, preferences) && matchesHardConstraints(activity, preferences);
    });
  }

  function filterActivitiesForFallback(preferences) {
    return getActivityLibrary().filter(function (activity) {
      return matchesHardConstraints(activity, preferences);
    });
  }

  function buildMatchReason(activity, preferences, answers, usedCategoryFallback) {
    var parts = [];
    var selectedCategories = getSelectedCategories(preferences);

    if (selectedCategories.indexOf(activity.category) >= 0) {
      parts.push('符合你现在想要的方向');
    } else if (usedCategoryFallback) {
      parts.push('先保留现实条件，再用相近的通用活动补位');
    }

    if (preferences && preferences.restFirst && activity.restFirst) {
      parts.push('优先照顾休息感，不需要太高的启动成本');
    }

    if (answers && typeof answers[activity.category] === 'number' && answers[activity.category] >= 3) {
      parts.push('和问卷里较高的倾向一致');
    }

    parts.push(activity.reason);
    return parts.join('；');
  }

  function scoreActivity(activity, preferences, answers, index) {
    var score = 0;
    var selectedCategories = getSelectedCategories(preferences);

    if (selectedCategories.indexOf(activity.category) >= 0) {
      score += 120;
      score += Math.max(0, 20 - selectedCategories.indexOf(activity.category) * 4);
    }

    if (preferences && preferences.outing === activity.mode) {
      score += 25;
    }

    if (preferences && preferences.company && preferences.company !== 'either') {
      if (activity.company === preferences.company) {
        score += 18;
      } else if (activity.company === 'either') {
        score += 9;
      }
    }

    if (preferences && preferences.budget && matchesBudget(activity, preferences.budget)) {
      score += 12;
    }

    if (preferences && preferences.duration && matchesDuration(activity, preferences.duration)) {
      score += 12;
    }

    if (preferences && preferences.restFirst) {
      score += activity.restFirst ? 40 : -10;
      if (activity.energy === 'low') {
        score += 12;
      }
    }

    if (answers && typeof answers[activity.category] === 'number') {
      score += answers[activity.category] * 5;
    }

    score -= index * 0.01;
    return score;
  }

  function scoreAndSortActivities(activities, preferences, answers) {
    return activities
      .map(function (activity, index) {
        return {
          activity: activity,
          score: scoreActivity(activity, preferences, answers, index),
        };
      })
      .sort(function (left, right) {
        return right.score - left.score;
      });
  }

  function materializeTasks(entries, preferences, answers, seen, usedCategoryFallback) {
    return entries.reduce(function (tasks, entry) {
      if (seen[entry.activity.id]) {
        return tasks;
      }

      var task = cloneActivity(entry.activity);
      task.matchReason = buildMatchReason(task, preferences, answers, usedCategoryFallback);
      seen[task.id] = true;
      tasks.push(task);
      return tasks;
    }, []);
  }

  function recommendActivities(preferences, answers, count) {
    var desiredCount = typeof count === 'number' && count > 0 ? count : 10;
    var filtered = filterActivities(preferences);
    var seen = {};
    var tasks = materializeTasks(
      scoreAndSortActivities(filtered, preferences, answers),
      preferences,
      answers,
      seen,
      false,
    );

    if (tasks.length < desiredCount) {
      tasks = tasks.concat(materializeTasks(
        scoreAndSortActivities(filterActivitiesForFallback(preferences), preferences, answers),
        preferences,
        answers,
        seen,
        true,
      ));
    }

    return {
      tasks: tasks.slice(0, desiredCount),
      totalMatches: filtered.length,
      fallbackUsed: filtered.length < desiredCount,
    };
  }

  function getWindow(preferences) {
    var startMinute = preferences && Number.isFinite(preferences.startMinute) ? preferences.startMinute : 9 * 60;
    var endMinute = preferences && Number.isFinite(preferences.endMinute)
      ? preferences.endMinute
      : startMinute + (windowDurations[(preferences && preferences.duration) || 'half-day'] || 240);

    if (endMinute <= startMinute) {
      endMinute = startMinute + 60;
    }

    return {
      startMinute: startMinute,
      endMinute: endMinute,
      totalMinutes: endMinute - startMinute,
    };
  }

  function normalizeTaskForSchedule(task, index) {
    return {
      id: task.id || ('task-' + index),
      title: task.title || '未命名任务',
      category: task.category || 'calm',
      duration: Number.isFinite(task.duration) ? task.duration : 30,
      budget: task.budget || 'free',
      reasonTag: task.reasonTag || '',
      type: task.type || 'task',
      mode: task.mode || 'custom',
      source: task.source || 'candidate',
    };
  }

  function buildSchedule(tasks, preferences) {
    var normalizedTasks = Array.isArray(tasks) ? tasks.map(normalizeTaskForSchedule) : [];
    var density = preferences && preferences.density && densityConfigs[preferences.density]
      ? preferences.density
      : 'balanced';
    var config = densityConfigs[density];
    var window = getWindow(preferences);
    var available = Math.floor(window.totalMinutes * config.usage);
    var current = window.startMinute;
    var usedMinutes = 0;
    var schedule = [];
    var remaining = normalizedTasks.slice();

    function addRestBlock(minutes, label) {
      if (minutes <= 0 || current + minutes > window.endMinute) {
        return false;
      }
      schedule.push({
        id: 'rest-' + schedule.length,
        type: 'rest',
        title: label || '留白休息',
        start: current,
        end: current + minutes,
        status: 'planned',
      });
      current += minutes;
      return true;
    }

    if (config.restFirst || (preferences && preferences.restFirst)) {
      addRestBlock(Math.min(config.restMinutes, window.endMinute - current), '先缓一缓');
    }

    while (remaining.length && schedule.filter(function (item) { return item.type === 'task'; }).length < config.maxTasks) {
      var next = remaining.shift();
      var gap = schedule.length ? config.gapMinutes : 0;
      var projectedEnd = current + gap + next.duration;

      if (usedMinutes + next.duration > available || projectedEnd > window.endMinute) {
        continue;
      }

      if (gap > 0 && current + gap <= window.endMinute) {
        schedule.push({
          id: 'buffer-' + schedule.length,
          type: 'rest',
          title: '切换一下',
          start: current,
          end: current + gap,
          status: 'planned',
        });
        current += gap;
      }

      schedule.push({
        id: 'slot-' + schedule.length,
        taskId: next.id,
        type: 'task',
        title: next.title,
        category: next.category,
        start: current,
        end: current + next.duration,
        duration: next.duration,
        budget: next.budget,
        reasonTag: next.reasonTag || '',
        status: 'pending',
        source: next.source,
      });
      current += next.duration;
      usedMinutes += next.duration;
    }

    if (density === 'light' && !schedule.some(function (item) { return item.type === 'rest'; })) {
      addRestBlock(Math.min(20, window.endMinute - current), '留一点空白');
    }

    return schedule.filter(function (item) {
      return item.end > item.start;
    });
  }

  function validateTimeWindow(task, schedule, preferences) {
    var window = getWindow(preferences || {});
    var start = Number(task && task.start);
    var duration = Number(task && task.duration);
    var end = start + duration;
    var normalizedSchedule = Array.isArray(schedule) ? schedule : [];

    if (!Number.isFinite(start) || !Number.isFinite(duration) || duration <= 0) {
      return { valid: false, message: '请填写有效的开始时间和持续时间。' };
    }

    if (start < window.startMinute || end > window.endMinute) {
      return {
        valid: false,
        message: '这个时间超出了可用时段，请换一个开始时间。',
      };
    }

    for (var index = 0; index < normalizedSchedule.length; index += 1) {
      var item = normalizedSchedule[index];
      if (item.type === 'rest') {
        continue;
      }
      if (start < item.end && end > item.start) {
        return {
          valid: false,
          message: '这个时间和现有安排重叠了，请换一个空档。',
        };
      }
    }

    return { valid: true };
  }

  function makeCustomTaskId(state) {
    var existing = []
      .concat(Array.isArray(state.customTasks) ? state.customTasks : [])
      .concat(Array.isArray(state.selectedTasks) ? state.selectedTasks : [])
      .map(function (task) { return task.id; });
    var index = existing.length + 1;
    var candidate = 'custom-' + index;

    while (existing.indexOf(candidate) >= 0) {
      index += 1;
      candidate = 'custom-' + index;
    }

    return candidate;
  }

  function addCustomTask(state, input) {
    var nextState = clone(state || createInitialState());
    var budget = input && input.budget ? input.budget : 'free';
    var category = input && input.category ? input.category : 'growth';
    var title = input && typeof input.title === 'string' ? input.title.trim() : '';

    if (!title) {
      throw new Error('请先填写任务名称。');
    }
    if (allCategories.indexOf(category) < 0) {
      throw new Error('请选择任务方向。');
    }
    if (!Object.prototype.hasOwnProperty.call(budgetOrder, budget)) {
      throw new Error('请选择可用的预算档位。');
    }

    var validation = validateTimeWindow(input, nextState.schedule, nextState.preferences);
    if (!validation.valid) {
      throw new Error(validation.message);
    }

    var task = {
      id: makeCustomTaskId(nextState),
      title: title,
      category: category,
      start: Number(input.start),
      duration: Number(input.duration),
      budget: budget,
      reasonTag: input && typeof input.reasonTag === 'string' ? input.reasonTag : '',
      source: 'custom',
      type: 'task',
      matchReason: input && input.reasonTag
        ? '自定义加入：' + input.reasonTag
        : '自定义加入',
    };

    nextState.customTasks = (nextState.customTasks || []).concat([task]);
    nextState.selectedTasks = (nextState.selectedTasks || []).concat([task]);
    nextState.schedule = (nextState.schedule || []).concat([{
      id: 'slot-' + task.id,
      taskId: task.id,
      type: 'task',
      title: task.title,
      category: task.category,
      start: task.start,
      end: task.start + task.duration,
      duration: task.duration,
      budget: task.budget,
      reasonTag: task.reasonTag,
      status: 'pending',
      source: 'custom',
    }]).sort(function (left, right) {
      return left.start - right.start;
    });
    nextState.ui = nextState.ui || {};
    nextState.ui.message = '已加入自定义任务。';
    return nextState;
  }

  function updateTaskStatus(state, taskId, status) {
    var nextState = clone(state || createInitialState());
    var normalizedStatus = status || 'pending';
    var needsAdjustment = adjustmentStatuses[normalizedStatus] === true;

    nextState.executionState = nextState.executionState || {};
    nextState.executionState[taskId] = {
      status: normalizedStatus,
      needsAdjustment: needsAdjustment,
    };

    nextState.schedule = (nextState.schedule || []).map(function (item) {
      if (item.taskId !== taskId) {
        return item;
      }
      item.status = normalizedStatus;
      return item;
    });

    nextState.ui = nextState.ui || {};
    nextState.ui.message = needsAdjustment ? '计划需要调整' : '任务状态已更新。';
    return nextState;
  }

  function createInitialState() {
    return {
      stage: 'welcome',
      preferences: {
        selectedCategories: [],
        mode: 'quick',
        outing: 'near',
        company: 'either',
        budget: 'medium',
        duration: 'half-day',
        density: 'balanced',
        restFirst: false,
        startMinute: 9 * 60,
        endMinute: 13 * 60,
      },
      questionnaire: {
        answers: {},
      },
      candidates: [],
      selectedTasks: [],
      customTasks: [],
      schedule: [],
      executionState: {},
      ui: {
        message: '就绪',
      },
    };
  }

  function renderStage(state) {
    var current = state && stageOrder.indexOf(state.stage) >= 0 ? state.stage : 'welcome';
    var index = stageOrder.indexOf(current);
    var copy = '这是 Demo V2 的页面骨架，后续任务会在这里填充内容。';

    if (current === 'recommendations' && state && Array.isArray(state.candidates) && state.candidates.length > 0) {
      copy = '已准备好本地推荐结果，当前可展示 ' + state.candidates.length + ' 个通用活动候选。';
    }

    return {
      stage: current,
      index: index,
      label: stageLabelMap[current],
      progress: (index + 1) / stageOrder.length,
      copy: copy,
    };
  }

  function resetDemo() {
    return createInitialState();
  }

  var api = {
    stageOrder: stageOrder,
    createInitialState: createInitialState,
    renderStage: renderStage,
    resetDemo: resetDemo,
    createQuestionnaire: createQuestionnaire,
    getActivityLibrary: getActivityLibrary,
    filterActivities: filterActivities,
    recommendActivities: recommendActivities,
    buildSchedule: buildSchedule,
    validateTimeWindow: validateTimeWindow,
    addCustomTask: addCustomTask,
    updateTaskStatus: updateTaskStatus,
    getWindow: getWindow,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  if (typeof window !== 'undefined') {
    window.FreeTimeDemoV2 = api;
  }
}());
