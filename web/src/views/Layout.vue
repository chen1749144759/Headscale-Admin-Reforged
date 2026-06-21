<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-logo" @click="router.push('/console')">
        <img src="/img/logo.ico" alt="Logo" class="logo-icon" />
        <transition name="fade"><span v-show="!sidebarCollapsed" class="logo-text">ScaleForge</span></transition>
      </div>

      <nav class="sidebar-nav">
        <template v-for="group in visibleGroups" :key="group.label">
          <div v-if="!sidebarCollapsed" class="nav-group-label">{{ group.label }}</div>
          <router-link v-for="item in group.items" :key="item.path" :to="item.path"
            class="nav-item" :class="{ active: currentPath === item.path }">
            <component :is="item.icon" class="nav-icon-el" />
            <transition name="fade"><span v-show="!sidebarCollapsed" class="nav-label">{{ item.name }}</span></transition>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-footer">
        <div class="footer-avatar">{{ userStore.userInfo?.name?.[0]?.toUpperCase() || 'U' }}</div>
        <transition name="fade">
          <div v-show="!sidebarCollapsed" class="footer-info">
            <div class="footer-name">{{ userStore.userInfo?.name || '用户' }}</div>
            <div class="footer-role">{{ userStore.isManager ? '管理员' : '用户' }}</div>
          </div>
        </transition>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="main-area" :class="{ collapsed: sidebarCollapsed }">
      <!-- 顶栏 -->
      <header class="main-header">
        <div class="header-left">
          <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
            <el-icon :size="18"><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/console' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentName">{{ currentName }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag v-if="userStore.systemStatus.headscale_healthy" type="success" size="small" effect="plain" round>
            <span class="status-dot online"></span>Headscale 运行中
          </el-tag>
          <el-tag v-else type="danger" size="small" effect="plain" round>
            <span class="status-dot offline"></span>Headscale 未连接
          </el-tag>
          <el-dropdown @command="handleCommand">
            <span class="user-dropdown-trigger">
              <el-avatar :size="28" style="background:var(--v3s-primary)">{{ userStore.userInfo?.name?.[0]?.toUpperCase() || 'U' }}</el-avatar>
              <span class="dropdown-name">{{ userStore.userInfo?.name }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile"><el-icon><User /></el-icon>个人资料</el-dropdown-item>
                <el-dropdown-item command="password"><el-icon><Key /></el-icon>修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Headscale 未连接提示 -->
      <div v-if="!userStore.systemStatus.headscale_healthy && currentPath !== '/settings'" class="hs-alert-wrap">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>
            Headscale 未连接 — 服务未运行或未正确配置，部分功能不可用。
            <el-button v-if="userStore.isManager" type="primary" link size="small" @click="router.push('/settings')">前往设置</el-button>
          </template>
        </el-alert>
      </div>

      <!-- 页面内容 -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, markRaw } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessageBox } from 'element-plus'
import {
  Monitor, Connection, User, Guide, SetUp, Key, Document, Setting,
  DataAnalysis, Tickets, UserFilled, HelpFilled
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const sidebarCollapsed = ref(false)

const currentPath = computed(() => route.path)
const currentName = computed(() => {
  const map = {
    '/traffic': '流量统计',
    '/client-policies': '限速策略',
    '/client-releases': '客户端版本',
    '/security': '安全中心',
    '/console': '控制台', '/users': '用户管理', '/groups': '分组管理',
    '/routes': '路由管理', '/acl': 'ACL 规则', '/preauthkeys': '预认证密钥',
    '/settings': '系统设置', '/logs': '操作日志', '/profile': '个人资料',
    '/password': '修改密码', '/deploy': '部署帮助',
  }
  return map[route.path] || ''
})

const menuGroups = [
  {
    label: '安全运维',
    items: [
      { name: '流量统计', path: '/traffic', icon: markRaw(DataAnalysis) },
      { name: '限速策略', path: '/client-policies', icon: markRaw(Setting), managerOnly: true },
      { name: '客户端版本', path: '/client-releases', icon: markRaw(Document), managerOnly: true },
      { name: '安全中心', path: '/security', icon: markRaw(Tickets) },
    ],
  },
  {
    label: '概览',
    items: [
      { name: '控制台', path: '/console', icon: markRaw(Monitor) },
    ],
  },
  {
    label: '网络管理',
    items: [
      { name: '用户管理', path: '/users', icon: markRaw(Connection) },
      { name: '路由管理', path: '/routes', icon: markRaw(Guide) },
      { name: '预认证密钥', path: '/preauthkeys', icon: markRaw(Key) },
    ],
  },
  {
    label: '系统管理',
    managerOnly: true,
    items: [
      { name: '分组管理', path: '/groups', icon: markRaw(UserFilled), managerOnly: true },
      { name: 'ACL 规则', path: '/acl', icon: markRaw(SetUp), managerOnly: true },
      { name: '系统设置', path: '/settings', icon: markRaw(Setting), managerOnly: true },
      { name: '操作日志', path: '/logs', icon: markRaw(Tickets), managerOnly: true },
    ],
  },
  {
    label: '帮助',
    items: [
      { name: '部署帮助', path: '/deploy', icon: markRaw(HelpFilled) },
    ],
  },
]

const visibleGroups = computed(() => {
  return menuGroups.map(group => ({
    ...group,
    items: group.items.filter(item => !item.managerOnly || userStore.isManager),
  })).filter(group => {
    if (group.managerOnly && !userStore.isManager) return false
    return group.items.length > 0
  })
})

function handleCommand(cmd) {
  if (cmd === 'profile') router.push('/profile')
  else if (cmd === 'password') router.push('/password')
  else if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '退出登录', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
      .then(() => userStore.logout())
      .catch(() => {})
  }
}

onMounted(async () => {
  await userStore.fetchUserInfo()
  await userStore.fetchSystemStatus()
})
</script>

<style scoped>
.admin-layout { display: flex; min-height: 100vh; }

/* ─── 侧边栏 ─── */
.sidebar {
  width: var(--v3s-sidebar-width);
  background: var(--v3s-sidebar-bg);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0; height: 100vh;
  z-index: 100;
  transition: width 0.25s cubic-bezier(.4,0,.2,1);
  border-right: 1px solid rgba(255,255,255,0.04);
}
.sidebar.collapsed { width: var(--v3s-sidebar-collapsed); }

.sidebar-logo {
  display: flex; align-items: center; gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--v3s-sidebar-border);
  cursor: pointer;
  min-height: 60px;
}
.logo-icon { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0; }
.logo-text { font-size: 16px; font-weight: 700; color: #fff; white-space: nowrap; }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 0; }
.nav-group-label {
  padding: 16px 20px 6px;
  font-size: 11px; color: #484f58;
  text-transform: uppercase; letter-spacing: 0.5px;
  font-weight: 600;
}
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px;
  margin: 2px 8px;
  border-radius: 8px;
  color: var(--v3s-sidebar-text);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  font-size: 14px;
}
.nav-item:hover { background: var(--v3s-sidebar-hover); color: #c9d1d9; }
.nav-item.active { background: var(--v3s-primary); color: #fff; }
.nav-icon-el { width: 18px; height: 18px; flex-shrink: 0; }

.sidebar-footer {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--v3s-sidebar-border);
}
.footer-avatar {
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--v3s-primary);
  color: #fff; font-weight: 600; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.footer-name { color: #e6edf3; font-size: 13px; font-weight: 500; }
.footer-role { color: #484f58; font-size: 11px; }

/* ─── 主区域 ─── */
.main-area {
  flex: 1;
  margin-left: var(--v3s-sidebar-width);
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left 0.25s cubic-bezier(.4,0,.2,1);
  background: var(--v3s-content-bg);
}
.main-area.collapsed { margin-left: var(--v3s-sidebar-collapsed); }

/* ─── 顶栏 (毛玻璃) ─── */
.main-header {
  height: var(--v3s-header-height);
  background: var(--v3s-header-bg);
  backdrop-filter: var(--v3s-header-blur);
  -webkit-backdrop-filter: var(--v3s-header-blur);
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky; top: 0; z-index: 50;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.collapse-btn {
  background: none; border: none; cursor: pointer;
  padding: 6px; border-radius: 6px; color: #606266;
  display: flex; align-items: center;
}
.collapse-btn:hover { background: #f0f2f5; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-dropdown-trigger {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; font-size: 14px; color: #606266;
}
.dropdown-name { font-weight: 500; }

.hs-alert-wrap { padding: 16px 24px 0; }
.main-content { flex: 1; padding: 20px 24px; overflow-y: auto; }

/* ─── 过渡动画 ─── */
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .sidebar { width: 0; }
  .sidebar.collapsed { width: 0; }
  .main-area, .main-area.collapsed { margin-left: 0; }
}
</style>
