import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/console',
    children: [
      { path: 'console', name: 'Console', component: () => import('@/views/Console.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/Accounts.vue'), meta: { requiresManager: true } },
      { path: 'groups', name: 'Groups', component: () => import('@/views/Group.vue'), meta: { requiresManager: true } },
      { path: 'accounts', redirect: '/users' },
      { path: 'routes', name: 'Routes', component: () => import('@/views/Routes.vue') },
      { path: 'traffic', name: 'Traffic', component: () => import('@/views/Traffic.vue') },
      { path: 'client-policies', name: 'ClientPolicies', component: () => import('@/views/ClientPolicies.vue'), meta: { requiresManager: true } },
      { path: 'client-releases', name: 'ClientReleases', component: () => import('@/views/ClientReleases.vue'), meta: { requiresManager: true } },
      { path: 'security', name: 'Security', component: () => import('@/views/Security.vue'), meta: { requiresManager: true } },
      { path: 'acl', name: 'ACL', component: () => import('@/views/Acl.vue'), meta: { requiresManager: true } },
      { path: 'settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { requiresManager: true } },
      { path: 'settings/dns', name: 'DnsSettings', component: () => import('@/views/Settings.vue'), meta: { requiresManager: true } },
      { path: 'logs', name: 'Logs', component: () => import('@/views/Logs.vue'), meta: { requiresManager: true } },
      { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
      { path: 'password', name: 'Password', component: () => import('@/views/Password.vue') },
      { path: 'deploy', name: 'Deploy', component: () => import('@/views/Deploy.vue'), meta: { requiresManager: true } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const { useUserStore } = await import('@/stores/user')
  const userStore = useUserStore()
  const loggedIn = await userStore.ensureSession()

  if (to.meta.requiresAuth === false) {
    if (loggedIn && to.name === 'Login') return next(userStore.mustChangePassword ? '/password' : '/console')
    return next()
  }

  if (!loggedIn) return next('/login')
  if (userStore.mustChangePassword && to.name !== 'Password') return next('/password')

  if (to.meta.requiresManager) {
    if (!userStore.isManager) return next('/console')
  }

  next()
})

export default router
