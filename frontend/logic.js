(function () {
  const categoryNames = {
    energy: '活力充电',
    calm: '松弛疗愈',
    social: '社交连接',
    explore: '乐享探索',
    growth: '自我成长',
  };

  const questionPrompts = {
    energy: ['空闲时间里，你希望身体状态更接近哪种感受？', '你对户外活动的接受程度是？', '完成活动后，你期待获得什么？'],
    calm: ['这段休闲时间里，你最需要恢复什么？', '你偏好的放松环境是？', '你希望安排节奏是？'],
    social: ['这次空闲时间里，你更想和谁相处？', '你希望社交活动的规模是？', '你对临时邀约的态度是？'],
    explore: ['你最想尝试哪类新体验？', '这次休闲时间的消费倾向是？', '你愿意为体验走多远？'],
    growth: ['这段时间最想推进哪件事？', '你更喜欢哪种成长方式？', '完成后最希望留下什么成果？'],
  };

  const taskTemplates = {
    energy: ['校园或社区慢跑', '拉伸与轻力量训练', '公园骑行', '羽毛球约练', '晨间散步', '游泳体验', '球场投篮', '居家舒展训练', '城市绿道漫步', '跳操体验'],
    calm: ['安静阅读时段', '咖啡馆放空', '公园慢走', '音乐与拉伸', '午后小憩', '手账整理', '冥想练习', '桌前断舍离', '泡一杯热饮', '晚间低刺激观影'],
    social: ['约一位朋友喝咖啡', '三人轻食聚会', '桌游小局', '社团活动体验', '给家人打电话', '一起逛校园', '同学学习互助', '傍晚散步聊天', '朋友间交换近况', '参加线下兴趣活动'],
    explore: ['看一部电影', '探一家小店', '逛一次展览', '城市街区漫游', '游戏体验时段', '拍一组生活照片', '尝试新餐厅', '逛书店与文创店', '看一场演出回放', '主题市集闲逛'],
    growth: ['整理本周笔记', '学习一个小技能', '完成短篇阅读', '写一页复盘', '规划下周重点', '制作灵感板', '练习一项创作', '清理数字文件', '完成在线课程章节', '写给未来自己的信'],
  };

  const options = ['更接近选项 A', '更接近选项 B', '两者都可以', '暂时不确定'];

  function allocateQuestionCounts(categories) {
    if (!Array.isArray(categories) || categories.length < 1 || categories.length > 5) {
      throw new Error('请选择 1 到 5 个方向');
    }

    const base = Math.floor(30 / categories.length);
    const remainder = 30 % categories.length;
    return Object.fromEntries(categories.map((id, index) => [id, base + (index < remainder ? 1 : 0)]));
  }

  function buildQuestions(categories) {
    const counts = allocateQuestionCounts(categories);
    return categories.flatMap((category) => Array.from({ length: counts[category] }, (_, index) => ({
      id: `${category}-${index + 1}`,
      category,
      categoryName: categoryNames[category],
      prompt: questionPrompts[category][index % questionPrompts[category].length],
      options,
    })));
  }

  function buildCandidates(categories, preferences) {
    if (!categories.length) return [];
    const candidates = [];
    const offset = preferences && preferences.budget === 'low' ? 1 : 0;
    const isHome = preferences && preferences.outing === false;
    const location = preferences && preferences.location ? preferences.location : '你所在区域';
    const company = preferences && preferences.company === 'solo' ? '适合独处' : preferences && preferences.company === 'friends' ? '适合结伴' : '独处或结伴皆可';

    for (let index = 0; index < 10; index += 1) {
      const category = categories[index % categories.length];
      const title = taskTemplates[category][(Math.floor(index / categories.length) + offset) % taskTemplates[category].length];
      candidates.push({
        id: `${category}-${index}`,
        category,
        categoryName: categoryNames[category],
        title,
        duration: 45,
        budget: preferences && preferences.budget === 'high' ? '80 元以内' : preferences && preferences.budget === 'medium' ? '40 元以内' : '20 元以内',
        mode: isHome ? '居家完成' : '可按出行意愿调整',
        location,
        company,
      });
    }

    return candidates;
  }

  function buildSchedule(tasks, timeMode) {
    const limit = timeMode === 'full' ? 480 : 270;
    const buffer = 15;
    let cursor = 0;

    return tasks.reduce((schedule, task) => {
      const end = cursor + task.duration;
      if (end > limit) return schedule;
      schedule.push({ ...task, start: cursor, end });
      cursor = end + buffer;
      return schedule;
    }, []);
  }

  const api = { allocateQuestionCounts, buildQuestions, buildCandidates, buildSchedule, categoryNames };
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof window !== 'undefined') window.FreeTimeLogic = api;
}());
