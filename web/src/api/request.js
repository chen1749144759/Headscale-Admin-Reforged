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
  const endpoint = error.config?.url || '未知接口'
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return { code: 'request_timeout', message: `请求超时：${endpoint}` }
    }
    return { code: 'network_error', message: `无法连接管理服务：${endpoint}` }
  }
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'object') {
    return {
      code: detail.code || '',
      message: detail.message || detail.error || `请求失败：${endpoint}`,
    }
  }
  return {
    code: error.response?.data?.code || '',
    message: detail || error.response?.data?.msg || (
      error.response?.status === 404
        ? `接口不存在：${endpoint}`
        : error.response?.status >= 500
          ? `服务处理失败：${endpoint}`
          : `请求失败：${endpoint}`
    ),
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
