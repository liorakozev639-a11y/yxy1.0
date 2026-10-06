(function (root) {
  if (!root || !root.document || !root.FreeTimeApi) return;

  const api = root.FreeTimeApi;
  const document = root.document;
  const loginPanel = document.querySelector('#admin-login');
  const dashboard = document.querySelector('#admin-dashboard');
  const loginForm = document.querySelector('#admin-login-form');
  const filterForm = document.querySelector('#admin-filters');
  const deleteUserForm = document.querySelector('#admin-delete-user-form');
  const cleanupButton = document.querySelector('#admin-cleanup');
  const retentionStatus = document.querySelector('#admin-retention-status');
  const loginError = document.querySelector('#admin-login-error');
  const dashboardError = document.querySelector('#admin-error');
  const logout = document.querySelector('#admin-logout');

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function filters() {
    const values = new FormData(filterForm);
    return Object.fromEntries([...values.entries()].filter(([, value]) => value));
  }

  function renderTable(target, columns, rows, empty = '暂无数据') {
    const element = document.querySelector(target);
    if (!rows || rows.length === 0) {
      element.innerHTML = `<p class="muted">${empty}</p>`;
      return;
    }
    element.innerHTML = `<div class="table-scroll"><table><thead><tr>${columns.map(([, label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([key]) => `<td>${escapeHtml(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderSummary(summary) {
    const labels = [
      ['user_count', '匿名用户'],
      ['session_count', '会话数'],
      ['full_flow_success_rate', '完整流程成功率', '%'],
      ['average_rating', '平均评分'],
      ['replacement_rate', '替换率', '%'],
      ['skip_rate', '跳过率', '%'],
    ];
    document.querySelector('#summary').innerHTML = labels.map(([key, label, suffix = '']) => `<article class="metric"><span>${label}</span><strong>${escapeHtml(summary?.[key] ?? 0)}${suffix}</strong></article>`).join('');
  }

  async function loadDashboard() {
    dashboardError.textContent = '';
    const selected = filters();
    try {
      const [summary, funnel, recommendations, energyRecommendations, reasons, reasonDetails, errors, userDetail] = await Promise.all([
        api.adminMetrics('summary', selected),
        api.adminMetrics('funnel', selected),
        api.adminMetrics('recommendations', selected),
        api.adminMetrics('energy-recommendations', selected),
        api.adminMetrics('reasons', selected),
        api.adminMetrics('reason-details', selected),
        api.adminMetrics('errors', selected),
        api.adminMetrics('user-detail', selected),
      ]);
      renderSummary(summary);
      renderTable('#funnel', [['event_type', '事件'], ['count', '次数']], funnel?.steps);
      renderTable('#recommendations', [
        ['task_category', '任务分类'], ['recommendation_count', '推荐次数'],
        ['average_rating', '平均评分'], ['replacement_rate', '替换率'], ['skip_rate', '跳过率'],
      ], recommendations);
      renderTable('#energy-recommendations', [
        ['energy_level', '当前精力'], ['task_category', '推荐分类'],
        ['recommendation_count', '推荐次数'], ['average_rating', '平均评分'],
        ['replacement_rate', '替换率'], ['skip_rate', '跳过率'],
      ], energyRecommendations);
      renderTable('#reasons', [['reason_code', '原因'], ['count', '次数']], reasons);
      renderTable('#reason-details', [
        ['anonymous_id', '匿名编号'], ['reason_code', '原因'],
        ['detail', '补充说明'], ['occurred_at', '时间'],
      ], reasonDetails);
      renderTable('#errors', [['error_code', '错误代码'], ['count', '次数']], errors);
      renderTable('#user-detail', [
        ['anonymous_id', '匿名编号'], ['cohort', '测试批次'],
        ['event_count', '事件数'], ['session_count', '会话数'],
        ['completed_count', '完成数'], ['skipped_count', '跳过数'],
        ['replaced_count', '替换数'], ['average_rating', '平均评分'],
      ], userDetail);
    } catch (error) {
      dashboardError.textContent = error.message || '指标暂时无法加载';
      if (error.status === 401) showLogin();
    }
  }

  function showDashboard() {
    loginPanel.hidden = true;
    dashboard.hidden = false;
    logout.hidden = false;
    void loadDashboard();
  }

  function showLogin() {
    loginPanel.hidden = false;
    dashboard.hidden = true;
    logout.hidden = true;
  }

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginError.textContent = '';
    const values = new FormData(loginForm);
    try {
      await api.adminLogin(values.get('username'), values.get('password'));
      loginForm.reset();
      showDashboard();
    } catch (error) {
      loginError.textContent = '登录失败';
    }
  });

  filterForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void loadDashboard();
  });

  deleteUserForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = new FormData(deleteUserForm);
    const anonymousId = String(values.get('anonymous_id') || '');
    if (!window.confirm(`确认删除 ${anonymousId} 的匿名观测数据？业务会话和任务不会删除。`)) return;
    retentionStatus.textContent = '';
    try {
      const result = await api.deleteAdminTestUser(anonymousId);
      retentionStatus.textContent = `已删除 ${result.deleted} 条匿名用户观测数据。`;
      deleteUserForm.reset();
      void loadDashboard();
    } catch (error) {
      retentionStatus.textContent = error.message || '删除失败';
    }
  });

  cleanupButton.addEventListener('click', async () => {
    if (!window.confirm('确认清理最近 90 天以前的匿名观测数据？业务数据不会删除。')) return;
    retentionStatus.textContent = '';
    try {
      const result = await api.cleanupAdminTestObservations();
      retentionStatus.textContent = `已清理 ${result.deleted_users} 个匿名用户的观测数据。`;
      void loadDashboard();
    } catch (error) {
      retentionStatus.textContent = error.message || '清理失败';
    }
  });


  logout.addEventListener('click', async () => {
    try { await api.adminLogout(); } finally { showLogin(); }
  });

  if (api.getAdminToken()) showDashboard();
}(typeof window !== 'undefined' ? window : null));
