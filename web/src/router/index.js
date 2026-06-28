import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/console',
    children: [
      { path: 'console', name: 'Console', component: () => import('@/views/Console.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/User.vue') },
      { path: 'groups', name: 'Groups', component: () => import('@/views/Group.vue'), meta: { requiresManager: true } },
      { path: 'routes', name: 'Routes', component: () => import('@/views/Routes.vue') },
      { path: 'traffic', name: 'Traffic', component: () => import('@/views/Traffic.vue') },
      { path: 'client-policies', name: 'ClientPolicies', component: () => import('@/views/ClientPolicies.vue'), meta: { requiresManager: true } },
      { path: 'client-releases', name: 'ClientReleases', component: () => import('@/views/ClientReleases.vue'), meta: { requiresManager: true } },
      { path: 'security', name: 'Security', component: () => import('@/views/Security.vue') },
      { path: 'acl', name: 'ACL', component: () => import('@/views/Acl.vue'), meta: { requiresManager: true } },
      { path: 'preauthkeys', name: 'Preauthkeys', component: () => import('@/views/Preauthkeys.vue') },
      { path: 'settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { requiresManager: true } },
      { path: 'settings/dns', name: 'DnsSettings', component: () => import('@/views/Settings.vue'), meta: { requiresManager: true } },
      { path: 'logs', name: 'Logs', component: () => import('@/views/Logs.vue'), meta: { requiresManager: true } },
      { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
      { path: 'password', name: 'Password', component: () => import('@/views/Password.vue') },
      { path: 'deploy', name: 'Deploy', component: () => import('@/views/Deploy.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('hs_token')

  // 不需要认证的页面
  if (to.meta.requiresAuth === false) {
    if (token && (to.name === 'Login' || to.name === 'Register')) {
      return next('/console')
    }
    return next()
  }

  // 未登录
  if (!token) {
    return next('/login')
  }

  // 管理员页面权限检查
  if (to.meta.requiresManager) {
    const { useUserStore } = await import('@/stores/user')
    const userStore = useUserStore()
    if (!userStore.userInfo?.role) {
      await userStore.fetchUserInfo()
    }
    if (userStore.userInfo?.role !== 'manager') {
      return next('/console')
    }
  }

  next()
})

export default router
