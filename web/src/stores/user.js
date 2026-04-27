import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, getSystemStatus, getPublicStatus } from '@/api'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('hs_token') || '')
  const userInfo = ref({})
  const systemStatus = ref({
    headscale_running: false,
    headscale_healthy: false,
    headscale_version: '',
    open_user_reg: 'off',
  })

  const isLoggedIn = computed(() => !!token.value)
  const isManager = computed(() => userInfo.value.role === 'manager')
  const openReg = computed(() => systemStatus.value.open_user_reg === 'on')

  function setToken(t) {
    token.value = t
    if (t) {
      localStorage.setItem('hs_token', t)
    } else {
      localStorage.removeItem('hs_token')
    }
  }

  async function fetchUserInfo() {
    try {
      const res = await getMe()
      userInfo.value = res.data
    } catch {
      logout()
    }
  }

  async function fetchSystemStatus() {
    try {
      const res = token.value ? await getSystemStatus() : await getPublicStatus()
      systemStatus.value = res.data
    } catch {}
  }

  function logout() {
    setToken('')
    userInfo.value = {}
    router.push('/login')
  }

  return {
    token, userInfo, systemStatus,
    isLoggedIn, isManager, openReg,
    setToken, fetchUserInfo, fetchSystemStatus, logout,
  }
})
