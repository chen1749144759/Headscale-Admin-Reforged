import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截器 - 附加 Token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('hs_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 - 统一错误处理
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.detail || error.response?.data?.msg || '请求失败'

    if (status === 401) {
      localStorage.removeItem('hs_token')
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export default request
