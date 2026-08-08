import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
  withCredentials: true,
  headers: { Accept: 'application/json' },
})

function errorDetail(error) {
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'object') {
    return {
      code: detail.code || '',
      message: detail.message || detail.error || '请求失败',
    }
  }
  return {
    code: error.response?.data?.code || '',
    message: detail || error.response?.data?.msg || '请求失败',
  }
}

request.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const status = error.response?.status
    const { code, message } = errorDetail(error)

    if (status === 401) {
      const { useUserStore } = await import('@/stores/user')
      useUserStore().clearSession()
      if (router.currentRoute.value.name !== 'Login') await router.replace('/login')
      if (error.config?.url !== '/auth/me') ElMessage.error('登录已过期，请重新登录')
    } else if (status === 403 && code === 'password_change_required') {
      if (router.currentRoute.value.name !== 'Password') router.replace('/password')
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }
    throw error
  },
)

export default request
