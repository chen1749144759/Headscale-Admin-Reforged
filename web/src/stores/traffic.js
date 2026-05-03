/**
 * 全局流量历史 store（模块级单例）
 *
 * 采样逻辑独立于组件生命周期：
 *   - 首次调用 startSampling() 后，每 5 秒轮询一次 /system/traffic
 *   - 计算速率并推入环形缓冲区（最多 MAX_SAMPLES 个点）
 *   - 页面切走再回来，历史数据仍然保留，图表立即完整显示
 */
import { reactive } from 'vue'
import { getSystemTraffic } from '@/api'

const MAX_SAMPLES = 60

// ─── 全局状态（模块级变量，SPA 生命周期内持续存在） ─────
const state = reactive({
  upload: [],       // 上传速率历史 (bytes/s)
  download: [],     // 下载速率历史 (bytes/s)
  upRate: 0,        // 当前上传速率
  downRate: 0,      // 当前下载速率
  netSent: 0,       // 累计上传字节
  netRecv: 0,       // 累计下载字节
})

let _prev = { sent: 0, recv: 0, time: 0 }
let _timer = null

async function _tick() {
  try {
    const res = await getSystemTraffic()
    const d = res.data || {}
    const nowSent = d.bytes_sent ?? d.net_sent ?? 0
    const nowRecv = d.bytes_recv ?? d.net_recv ?? 0
    const now = Date.now()

    if (_prev.time > 0) {
      const elapsed = (now - _prev.time) / 1000
      if (elapsed > 0) {
        const up = Math.max(0, (nowSent - _prev.sent) / elapsed)
        const down = Math.max(0, (nowRecv - _prev.recv) / elapsed)
        state.upRate = up
        state.downRate = down
        state.upload.push(up)
        state.download.push(down)
        if (state.upload.length > MAX_SAMPLES) state.upload.shift()
        if (state.download.length > MAX_SAMPLES) state.download.shift()
      }
    }

    state.netSent = nowSent
    state.netRecv = nowRecv
    _prev = { sent: nowSent, recv: nowRecv, time: now }
  } catch {
    // 接口不可用时静默跳过
  }
}

/**
 * 启动全局流量采样（幂等，多次调用只启动一次）
 */
export function startTrafficSampling() {
  if (_timer) return
  // 立刻执行一次初始化基准值
  _tick()
  _timer = setInterval(_tick, 5000)
}

export const MAX_TRAFFIC_SAMPLES = MAX_SAMPLES

export function useTrafficStore() {
  return state
}
