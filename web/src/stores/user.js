import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getMe, getPublicStatus, getSystemStatus, logout as logoutRequest } from '@/api'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({})
  const authenticated = ref(false)
  const sessionChecked = ref(false)
  const systemStatus = ref({
    headscale_running: false,
    headscale_healthy: false,
    headscale_version: '',
  })

  const isLoggedIn = computed(() => authenticated.value)
  const isManager = computed(() => userInfo.value.role === 'manager')
  const mustChangePassword = computed(() => Boolean(userInfo.value.mustChangePassword))

  function acceptSession(user) {
    userInfo.value = user || {}
    authenticated.value = Boolean(user?.id)
    sessionChecked.value = true
  }

  function clearSession() {
    userInfo.value = {}
    authenticated.value = false
    sessionChecked.value = true
  }

  async function fetchUserInfo() {
    try {
      const res = await getMe()
      acceptSession(res.data)
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function ensureSession() {
    if (!sessionChecked.value) return fetchUserInfo()
    return authenticated.value
  }

  async function fetchSystemStatus() {
    try {
      const res = authenticated.value ? await getSystemStatus() : await getPublicStatus()
      systemStatus.value = res.data || systemStatus.value
    } catch {}
  }

  async function logout() {
    // Only clear local state after Headscale confirms that the opaque session
    // was revoked. Otherwise the UI would claim logout while the HttpOnly
    // cookie remains valid on the server.
    await logoutRequest()
    clearSession()
    await router.replace('/login')
  }

  return {
    userInfo,
    authenticated,
    sessionChecked,
    systemStatus,
    isLoggedIn,
    isManager,
    mustChangePassword,
    acceptSession,
    clearSession,
    fetchUserInfo,
    ensureSession,
    fetchSystemStatus,
    logout,
  }
})
