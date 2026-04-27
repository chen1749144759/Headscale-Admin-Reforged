// Headscale Admin - SPA 逻辑（纯 Vue3 + Element Plus，无 Jinja2）
const { createApp, ref, reactive, computed, onMounted, watch } = Vue;

const app = createApp({
  setup() {
    // ─── API 工具 ─────────────────────────────
    const API = {
      token: localStorage.getItem('hs_token') || '',
      async request(method, url, data = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (this.token) opts.headers['Authorization'] = 'Bearer ' + this.token;
        if (data) opts.body = JSON.stringify(data);
        const r = await fetch(url, opts);
        if (r.status === 401) { isLoggedIn.value = false; this.token = ''; localStorage.removeItem('hs_token'); throw new Error('登录已过期'); }
        const json = await r.json();
        if (r.status >= 400) throw new Error(json.detail || json.msg || '请求失败');
        return json;
      },
      get(url) { return this.request('GET', url); },
      post(url, d) { return this.request('POST', url, d); },
      put(url, d) { return this.request('PUT', url, d); },
      del(url) { return this.request('DELETE', url); },
    };

    // ─── 状态 ─────────────────────────────────
    const isLoggedIn = ref(!!API.token);
    const currentUser = reactive({ id:0, name:'', role:'', email:'', cellphone:'', node:0, route:0, enable:1, expire:'', created_at:'' });
    const currentPage = ref('nodes');
    const sidebarCollapsed = ref(false);
    const systemStatus = reactive({ headscale_running: false, headscale_healthy: false, headscale_version: '', open_user_reg: 'on' });
    const openReg = computed(() => systemStatus.open_user_reg === 'on');

    // ─── 菜单 ─────────────────────────────────
    const svg = {
      console: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
      nodes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>',
      users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>',
      routes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4 17 10 11 14 15 20 9"/><polyline points="14 9 20 9 20 15"/></svg>',
      acl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
      key: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777z"/><line x1="15" y1="9" x2="19" y2="5"/></svg>',
      settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
      logs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    };
    const menuGroups = computed(() => {
      const groups = [
        { label: '概览', items: [{ key:'console', label:'控制台', icon: svg.console }] },
        { label: '管理', items: [
          { key:'nodes', label:'节点管理', icon: svg.nodes },
          { key:'routes', label:'路由管理', icon: svg.routes },
          { key:'preauthkeys', label:'预认证密钥', icon: svg.key },
        ]},
        { label: '系统', items: [
          { key:'settings', label:'系统设置', icon: svg.settings },
          { key:'logs', label:'操作日志', icon: svg.logs },
        ]},
      ];
      // 管理员才能看到用户管理和 ACL
      if (currentUser.role === 'manager') {
        groups[1].items.splice(1, 0, { key:'users', label:'用户管理', icon: svg.users });
        groups[1].items.splice(3, 0, { key:'acl', label:'ACL 规则', icon: svg.acl });
      }
      return groups;
    });
    const pageTitles = { console:'控制台', nodes:'节点管理', users:'用户管理', routes:'路由管理', acl:'ACL 规则', preauthkeys:'预认证密钥', settings:'系统设置', logs:'操作日志', profile:'基本资料', password:'修改密码', deploy:'部署帮助' };
    const currentPageTitle = computed(() => pageTitles[currentPage.value] || '');

    // ─── 登录 ─────────────────────────────────
    const loginForm = reactive({ username: '', password: '' });
    const loginRules = { username: [{required:true, message:'请输入用户名', trigger:'blur'}], password: [{required:true, message:'请输入密码', trigger:'blur'}] };
    const loginFormRef = ref(null);
    const loginLoading = ref(false);
    const sliderVerified = ref(false);
    const sliderLeft = ref(0);
    let sliderDragging = false, sliderStartX = 0;

    function sliderStart(e) {
      if (sliderVerified.value) return;
      sliderDragging = true;
      sliderStartX = (e.clientX || e.touches[0].clientX) - sliderLeft.value;
      const move = (ev) => { if (!sliderDragging) return; sliderLeft.value = Math.max(0, Math.min((ev.clientX||ev.touches[0].clientX) - sliderStartX, 280)); };
      const end = () => { sliderDragging = false; if (sliderLeft.value > 240) { sliderVerified.value = true; sliderLeft.value = 260; } else { sliderLeft.value = 0; } };
      document.addEventListener('mousemove', move); document.addEventListener('mouseup', end);
      document.addEventListener('touchmove', move, {passive:true}); document.addEventListener('touchend', end);
    }

    async function handleLogin() {
      if (!sliderVerified.value) { ElMessage.warning('请完成滑块验证'); return; }
      try { await loginFormRef.value.validate(); } catch { return; }
      loginLoading.value = true;
      try {
        const r = await API.post('/api/auth/login', loginForm);
        API.token = r.data.token;
        localStorage.setItem('hs_token', API.token);
        Object.assign(currentUser, r.data.user);
        isLoggedIn.value = true;
        // 首个用户且 Headscale 未配置 → 强制设置页
        await loadSystemStatus();
        if (!systemStatus.headscale_healthy) currentPage.value = 'settings';
        else currentPage.value = currentUser.role === 'manager' ? 'console' : 'nodes';
        ElMessage.success('登录成功');
        loadPageData();
      } catch (e) { ElMessage.error(e.message); }
      loginLoading.value = false;
    }

    // ─── 注册 ─────────────────────────────────
    const showRegister = ref(false);
    const regForm = reactive({ username: '', password: '', confirmPassword: '' });
    const regRules = {
      username: [{required:true, message:'请输入用户名', trigger:'blur'}],
      password: [{required:true, message:'请输入密码', trigger:'blur'}],
      confirmPassword: [{required:true, message:'请确认密码', trigger:'blur'}, { validator: (r,v,cb) => { if (v!==regForm.password) cb(new Error('密码不一致')); else cb(); }, trigger:'blur' }],
    };
    const regFormRef = ref(null);
    const regLoading = ref(false);

    async function handleRegister() {
      try { await regFormRef.value.validate(); } catch { return; }
      regLoading.value = true;
      try {
        const r = await API.post('/api/auth/register', regForm);
        ElMessage.success(r.msg + (r.data.role === 'manager' ? '（首个用户自动成为管理员）' : ''));
        showRegister.value = false;
      } catch (e) { ElMessage.error(e.message); }
      regLoading.value = false;
    }

    // ─── 导航 ─────────────────────────────────
    function navigateTo(key) { currentPage.value = key; loadPageData(); }
    function refreshPage() { loadPageData(); }
    function handleUserCommand(cmd) {
      if (cmd === 'profile') navigateTo('profile');
      else if (cmd === 'password') navigateTo('password');
      else if (cmd === 'logout') doLogout();
    }
    async function doLogout() {
      try { await API.post('/api/auth/logout'); } catch {}
      API.token = ''; localStorage.removeItem('hs_token');
      isLoggedIn.value = false;
      sliderVerified.value = false; sliderLeft.value = 0;
    }

    // ─── 系统状态 ─────────────────────────────
    const sysInfo = reactive({ cpu_usage: 0, memory_percent: 0 });
    async function loadSystemStatus() {
      try {
        const r = await API.get('/api/system/status');
        Object.assign(systemStatus, r.data);
      } catch {}
    }
    async function loadSysInfo() {
      try { const r = await API.get('/api/system/info'); Object.assign(sysInfo, r.data); } catch {}
    }

    // ─── 节点 ─────────────────────────────────
    const nodesList = ref([]);
    const nodesLoading = ref(false);
    async function loadNodes() {
      nodesLoading.value = true;
      try {
        const r = await API.get('/api/nodes');
        // headscale 返回的格式可能是 {nodes:[...]} 或直接数组
        nodesList.value = r.data?.nodes || (Array.isArray(r.data) ? r.data : []);
      } catch (e) { ElMessage.error('加载节点失败: ' + e.message); }
      nodesLoading.value = false;
    }
    async function deleteNode(id) {
      try { await API.del('/api/nodes/' + id); ElMessage.success('已删除'); loadNodes(); } catch (e) { ElMessage.error(e.message); }
    }
    async function expireNode(id) {
      try { await API.post('/api/nodes/' + id + '/expire'); ElMessage.success('已过期'); loadNodes(); } catch (e) { ElMessage.error(e.message); }
    }

    // ─── 用户 ─────────────────────────────────
    const usersList = ref([]);
    const usersLoading = ref(false);
    async function loadUsers() {
      usersLoading.value = true;
      try { const r = await API.get('/api/users'); usersList.value = r.data || []; } catch (e) { ElMessage.error(e.message); }
      usersLoading.value = false;
    }
    async function deleteUser(id) {
      try { await API.del('/api/users/' + id); ElMessage.success('已删除'); loadUsers(); } catch (e) { ElMessage.error(e.message); }
    }
    async function toggleUserRoute(user) {
      try { await API.post('/api/users/' + user.id + '/update', { route_enable: user.route !== 1 }); loadUsers(); } catch (e) { ElMessage.error(e.message); }
    }
    async function toggleUserEnable(user) {
      try { await API.post('/api/users/' + user.id + '/update', { user_enable: user.enable !== 1 }); loadUsers(); } catch (e) { ElMessage.error(e.message); }
    }

    // ─── 路由 ─────────────────────────────────
    const routesList = ref([]);
    const routesLoading = ref(false);
    async function loadRoutes() {
      routesLoading.value = true;
      try {
        const r = await API.get('/api/routes');
        routesList.value = r.data?.routes || (Array.isArray(r.data) ? r.data : []);
      } catch (e) { ElMessage.error(e.message); }
      routesLoading.value = false;
    }
    async function toggleRoute(id, enable) {
      try { await API.post('/api/routes/' + id + '/' + (enable?'enable':'disable')); loadRoutes(); } catch (e) { ElMessage.error(e.message); }
    }

    // ─── ACL ──────────────────────────────────
    const aclContent = ref('');
    const aclSaving = ref(false);
    async function loadAcl() {
      try { const r = await API.get('/api/acl'); aclContent.value = r.data || ''; } catch {}
    }
    async function saveAcl() {
      aclSaving.value = true;
      try { await API.put('/api/acl', { acl: aclContent.value }); ElMessage.success('ACL 已保存'); } catch (e) { ElMessage.error(e.message); }
      aclSaving.value = false;
    }

    // ─── 预认证密钥 ──────────────────────────
    const preauthkeysList = ref([]);
    const keysLoading = ref(false);
    async function loadPreauthkeys() {
      keysLoading.value = true;
      try {
        const r = await API.get('/api/preauthkeys');
        preauthkeysList.value = r.data?.preAuthKeys || (Array.isArray(r.data) ? r.data : []);
      } catch (e) { ElMessage.error(e.message); }
      keysLoading.value = false;
    }
    async function createKey() {
      try { await API.post('/api/preauthkeys', { user: currentUser.name, reusable: false, ephemeral: false }); ElMessage.success('密钥已创建'); loadPreauthkeys(); } catch (e) { ElMessage.error(e.message); }
    }

    // ─── 设置 ─────────────────────────────────
    const settingsForm = reactive({ server_url:'', server_net:'', bearer_token_display:'', default_reg_days:7, default_node_count:2, open_user_reg_bool:'on', network_interfaces:[] });
    const settingsSaving = ref(false);
    async function loadSettings() {
      try {
        const r = await API.get('/api/settings');
        Object.assign(settingsForm, { server_url: r.data.server_url, server_net: r.data.server_net, bearer_token_display: r.data.bearer_token, default_reg_days: r.data.default_reg_days, default_node_count: r.data.default_node_count, open_user_reg_bool: r.data.open_user_reg, network_interfaces: r.data.network_interfaces || [] });
      } catch {}
    }
    async function saveSettings() {
      settingsSaving.value = true;
      try {
        await API.put('/api/settings', { server_url: settingsForm.server_url, server_net: settingsForm.server_net, default_reg_days: settingsForm.default_reg_days, default_node_count: settingsForm.default_node_count, open_user_reg: settingsForm.open_user_reg_bool });
        ElMessage.success('设置已保存');
        loadSystemStatus();
      } catch (e) { ElMessage.error(e.message); }
      settingsSaving.value = false;
    }
    async function refreshApiKey() {
      try { const r = await API.post('/api/settings/refresh-apikey'); settingsForm.bearer_token_display = r.data.substring(0,8)+'...'; ElMessage.success('API Key 已刷新'); } catch (e) { ElMessage.error(e.message); }
    }
    async function switchHeadscale(action) {
      try { await API.put('/api/settings', { headscale_action: action }); ElMessage.success(action==='start'?'正在启动':'正在停止'); setTimeout(loadSystemStatus, 3000); } catch (e) { ElMessage.error(e.message); }
    }

    // ─── 日志 ─────────────────────────────────
    const logsList = ref([]);
    const logsLoading = ref(false);
    const logsPage = ref(1);
    const logsTotal = ref(0);
    async function loadLogs() {
      logsLoading.value = true;
      try { const r = await API.get('/api/logs?page=' + logsPage.value); logsList.value = r.data || []; logsTotal.value = r.total || 0; } catch {}
      logsLoading.value = false;
    }

    // ─── 个人资料/密码 ───────────────────────
    const profileForm = reactive({ email: '', cellphone: '' });
    const pwdForm = reactive({ old_password: '', new_password: '' });
    const pwdRules = { old_password:[{required:true,message:'请输入原密码',trigger:'blur'}], new_password:[{required:true,message:'请输入新密码',trigger:'blur'}] };
    const pwdFormRef = ref(null);
    const pwdLoading = ref(false);
    async function loadProfile() { profileForm.email = currentUser.email||''; profileForm.cellphone = currentUser.cellphone||''; }
    async function saveProfile() {
      try { await API.post('/api/auth/profile', profileForm); ElMessage.success('已保存'); loadMe(); } catch (e) { ElMessage.error(e.message); }
    }
    async function changePassword() {
      try { await pwdFormRef.value.validate(); } catch { return; }
      pwdLoading.value = true;
      try { await API.post('/api/auth/password', pwdForm); ElMessage.success('密码已修改，请重新登录'); doLogout(); } catch (e) { ElMessage.error(e.message); }
      pwdLoading.value = false;
    }

    // ─── 部署 ─────────────────────────────────
    const deployCmd = computed(() => `tailscale up --login-server ${settingsForm.server_url || 'http://YOUR_SERVER:8080'} --authkey YOUR_KEY`);

    // ─── 工具 ─────────────────────────────────
    function copyText(text) { navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制')); }

    // ─── 加载当前用户 ─────────────────────────
    async function loadMe() {
      try { const r = await API.get('/api/auth/me'); Object.assign(currentUser, r.data); } catch { isLoggedIn.value = false; }
    }

    // ─── 页面数据加载 ────────────────────────
    function loadPageData() {
      const page = currentPage.value;
      if (page === 'console') { loadSysInfo(); loadSystemStatus(); }
      else if (page === 'nodes') loadNodes();
      else if (page === 'users') loadUsers();
      else if (page === 'routes') loadRoutes();
      else if (page === 'acl') loadAcl();
      else if (page === 'preauthkeys') loadPreauthkeys();
      else if (page === 'settings') loadSettings();
      else if (page === 'logs') loadLogs();
      else if (page === 'profile') loadProfile();
    }

    // ─── 初始化 ───────────────────────────────
    onMounted(async () => {
      if (isLoggedIn.value) {
        await loadMe();
        await loadSystemStatus();
        if (!systemStatus.headscale_healthy) currentPage.value = 'settings';
        else currentPage.value = currentUser.role === 'manager' ? 'console' : 'nodes';
        loadPageData();
      } else {
        // 加载开放注册状态
        try {
          const r = await fetch('/api/public/status');
          if (r.ok) { const d = await r.json(); systemStatus.open_user_reg = d.data?.open_user_reg || 'off'; }
        } catch {}
      }
    });

    return {
      isLoggedIn, currentUser, currentPage, currentPageTitle, sidebarCollapsed, systemStatus, openReg,
      menuGroups, navigateTo, refreshPage, handleUserCommand,
      loginForm, loginRules, loginFormRef, loginLoading, sliderVerified, sliderLeft, sliderStart, handleLogin,
      showRegister, regForm, regRules, regFormRef, regLoading, handleRegister,
      sysInfo, nodesList, nodesLoading, loadNodes, deleteNode, expireNode,
      usersList, usersLoading, loadUsers, deleteUser, toggleUserRoute, toggleUserEnable,
      routesList, routesLoading, loadRoutes, toggleRoute,
      aclContent, aclSaving, loadAcl, saveAcl,
      preauthkeysList, keysLoading, loadPreauthkeys, createKey,
      settingsForm, settingsSaving, loadSettings, saveSettings, refreshApiKey, switchHeadscale,
      logsList, logsLoading, logsPage, logsTotal, loadLogs,
      profileForm, loadProfile, saveProfile,
      pwdForm, pwdRules, pwdFormRef, pwdLoading, changePassword,
      deployCmd, copyText,
    };
  }
});

app.use(ElementPlus);
app.mount('#app');
