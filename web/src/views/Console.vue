<template>
  <div>
    <div class="page-header"><h2>控制台</h2><p>{{ userStore.isManager ? '系统运行状态总览' : '我的 ScaleTail 网络概览' }}</p></div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="6" v-for="s in statCards" :key="s.label">
        <div class="glass-card stat-card">
          <div class="stat-icon" :style="{ background: s.color }">
            <el-icon :size="22"><component :is="s.icon" /></el-icon>
          </div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 第二行：Headscale信息 + 快捷操作  (等高) -->
    <el-row :gutter="16" style="margin-top:16px" class="info-row">
      <el-col v-if="userStore.isManager" :xs="24" :sm="14">
        <div class="glass-card content-card equal-card hs-status-card">
          <!-- 标题行 -->
          <div class="hs-header">
            <div class="hs-header-left">
              <div class="hs-logo" :class="{ healthy: hsHealthy }">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                </svg>
              </div>
              <div>
                <div class="hs-title">Headscale 服务状态</div>
                <div class="hs-subtitle">
                  <span class="hs-dot" :class="hsHealthy ? 'on' : 'off'"></span>
                  {{ hsHealthy ? '运行中' : '未连接' }}
                  <span v-if="hsVersion" class="hs-ver">{{ hsVersion }}</span>
                </div>
              </div>
            </div>
            <div class="hs-header-right">
              <span class="hs-server-url" v-if="serverUrl">{{ serverUrl }}</span>
            </div>
          </div>

          <!-- 指标网格 -->
          <div class="hs-metrics">
            <!-- CPU -->
            <div class="metric-item">
              <div class="metric-icon cpu-icon">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg>
              </div>
              <div class="metric-body">
                <div class="metric-label">CPU</div>
                <div class="metric-bar-wrap">
                  <div class="metric-bar" :style="{ width: sysInfo.cpu + '%', background: progressColor(sysInfo.cpu) }"></div>
                </div>
              </div>
              <div class="metric-val">{{ sysInfo.cpu }}%</div>
            </div>
            <!-- 内存 -->
            <div class="metric-item">
              <div class="metric-icon mem-icon">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 6V4a2 2 0 012-2h8a2 2 0 012 2v2"/><line x1="6" y1="10" x2="6" y2="14"/><line x1="10" y1="10" x2="10" y2="14"/><line x1="14" y1="10" x2="14" y2="14"/></svg>
              </div>
              <div class="metric-body">
                <div class="metric-label">内存 <span class="metric-detail">{{ formatBytes(sysInfo.memoryUsed) }} / {{ formatBytes(sysInfo.memoryTotal) }}</span></div>
                <div class="metric-bar-wrap">
                  <div class="metric-bar" :style="{ width: sysInfo.memory + '%', background: progressColor(sysInfo.memory) }"></div>
                </div>
              </div>
              <div class="metric-val">{{ sysInfo.memory }}%</div>
            </div>
          </div>

          <!-- 内网IP (独占一行) -->
          <div class="hs-ip-row">
            <div class="ip-icon">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
            </div>
            <span class="ip-label">内网IP</span>
            <div class="ip-tags" v-if="internalIps.length">
              <span class="ip-tag" v-for="item in internalIps" :key="item.ip">{{ item.ip }}<span class="ip-iface">({{ item.iface }})</span></span>
            </div>
            <span v-else class="ip-loading">获取中...</span>
          </div>

          <!-- 流量：上传左 / 下载右 -->
          <div class="hs-traffic-row">
            <div class="traffic-half upload">
              <div class="traffic-head">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 11 12 6 7 11"/><line x1="12" y1="18" x2="12" y2="6"/></svg>
                <span>上传</span>
              </div>
              <div class="traffic-num">{{ formatBytes(traffic.netSent) }}</div>
              <div class="traffic-rate" v-if="traffic.upRate">{{ formatBytes(traffic.upRate) }}/s</div>
            </div>
            <div class="traffic-divider"></div>
            <div class="traffic-half download">
              <div class="traffic-head">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="7 13 12 18 17 13"/><line x1="12" y1="6" x2="12" y2="18"/></svg>
                <span>下载</span>
              </div>
              <div class="traffic-num">{{ formatBytes(traffic.netRecv) }}</div>
              <div class="traffic-rate" v-if="traffic.downRate">{{ formatBytes(traffic.downRate) }}/s</div>
            </div>
          </div>

          <!-- 迷你流量趋势图 -->
          <div class="hs-chart-area">
            <div class="chart-label">近期流量趋势</div>
            <div class="mini-chart" ref="chartRef">
              <svg :viewBox="`0 0 ${chartW} ${chartH}`" preserveAspectRatio="none" width="100%" :height="chartH">
                <!-- 上传曲线 -->
                <path :d="uploadAreaPoints" fill="rgba(16,185,129,0.08)" stroke="none" />
                <path :d="uploadPoints" fill="none" stroke="#10b981" stroke-width="1" stroke-linecap="round" />
                <!-- 下载曲线 -->
                <path :d="downloadAreaPoints" fill="rgba(79,70,229,0.08)" stroke="none" />
                <path :d="downloadPoints" fill="none" stroke="#4f46e5" stroke-width="1" stroke-linecap="round" />
              </svg>
              <div class="chart-legend">
                <span class="legend-item"><span class="legend-dot" style="background:#10b981"></span>上传</span>
                <span class="legend-item"><span class="legend-dot" style="background:#4f46e5"></span>下载</span>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="userStore.isManager ? 10 : 24">
        <div class="glass-card content-card equal-card">
          <div class="section-title">快捷操作</div>
          <div class="quick-actions">
            <div v-for="a in quickActions" :key="a.label" class="quick-action-item" @click="router.push(a.path)">
              <div class="qa-icon" :style="{ background: a.color }">
                <el-icon :size="18"><component :is="a.icon" /></el-icon>
              </div>
              <div>
                <div class="qa-title">{{ a.label }}</div>
                <div class="qa-desc">{{ a.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 第三行：最近日志 -->
    <div class="glass-card content-card" style="margin-top:16px" v-if="userStore.isManager">
      <div class="section-title">最近操作日志</div>
      <el-table :data="recentLogs" size="default" stripe :show-header="true" style="width:100%">
        <el-table-column prop="user_name" label="用户" width="120" />
        <el-table-column prop="content" label="操作内容" min-width="260" />
        <el-table-column prop="created_at" label="时间" width="200" />
      </el-table>
      <div style="text-align:right;margin-top:12px">
        <el-button type="primary" link size="small" @click="router.push('/logs')">查看全部日志 →</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useTrafficStore, startTrafficSampling, MAX_TRAFFIC_SAMPLES } from '@/stores/traffic'
import { getSystemInfo, getNodes, getHsUsers, getLogs, getTrafficSummary } from '@/api'
import { Monitor, Cpu, Connection, UserFilled, Setting, Guide, SetUp, Download, Upload } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const traffic = useTrafficStore()

// 宿主机网卡采样属于管理员视角，普通账户只读取自身网络的聚合流量。
if (userStore.isManager) startTrafficSampling()

const sysInfo = ref({ cpu: 0, memory: 0, memoryUsed: 0, memoryTotal: 0 })
const internalIps = ref([])
const nodeCount = ref(0)
const onlineCount = ref(0)
const userCount = ref(0)
const recentLogs = ref([])
const trafficSummary = ref({ today_rx_bytes: 0, today_tx_bytes: 0 })

// 迷你流量图配置
const MAX_SAMPLES = MAX_TRAFFIC_SAMPLES
const chartW = 300
const chartH = 60

function buildPoints(arr, w, h) {
  if (arr.length < 2) return ''
  const max = Math.max(...arr, 1)
  const step = w / (MAX_SAMPLES - 1)
  const offset = (MAX_SAMPLES - arr.length) * step
  const pts = arr.map((v, i) => ({
    x: offset + i * step,
    y: h - (v / max) * (h - 4) - 2
  }))
  // 平滑贝塞尔曲线
  let d = `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i - 1], c = pts[i]
    const cpx = (p.x + c.x) / 2
    d += ` C ${cpx.toFixed(1)} ${p.y.toFixed(1)}, ${cpx.toFixed(1)} ${c.y.toFixed(1)}, ${c.x.toFixed(1)} ${c.y.toFixed(1)}`
  }
  return d
}
function buildAreaPoints(arr, w, h) {
  const line = buildPoints(arr, w, h)
  if (!line) return ''
  const step = w / (MAX_SAMPLES - 1)
  const offset = (MAX_SAMPLES - arr.length) * step
  const lastX = offset + (arr.length - 1) * step
  return `${line} L ${lastX.toFixed(1)} ${h} L ${offset.toFixed(1)} ${h} Z`
}
const uploadPoints = computed(() => buildPoints(traffic.upload, chartW, chartH))
const downloadPoints = computed(() => buildPoints(traffic.download, chartW, chartH))
const uploadAreaPoints = computed(() => buildAreaPoints(traffic.upload, chartW, chartH))
const downloadAreaPoints = computed(() => buildAreaPoints(traffic.download, chartW, chartH))

const hsHealthy = computed(() => userStore.systemStatus.headscale_healthy)
const hsVersion = computed(() => {
  const v = userStore.systemStatus.headscale_version || ''
  const m = v.match(/v[\d.]+/)
  return m ? m[0] : v.split('\n')[0]
})
const serverUrl = computed(() => userStore.systemStatus.server_url || '')

const statCards = computed(() => {
  const cards = [
    { label: '在线机器', value: onlineCount.value, icon: markRaw(Connection), color: '#10b981' },
    { label: '总机器数', value: nodeCount.value, icon: markRaw(Monitor), color: '#4f46e5' },
  ]
  if (userStore.isManager) {
    cards.push(
      { label: '分组数', value: userCount.value, icon: markRaw(UserFilled), color: '#f59e0b' },
      { label: 'CPU 使用率', value: sysInfo.value.cpu + '%', icon: markRaw(Cpu), color: '#06b6d4' },
    )
  } else {
    cards.push(
      { label: '今日接收', value: formatBytes(trafficSummary.value.today_rx_bytes), icon: markRaw(Download), color: '#0ea5e9' },
      { label: '今日发送', value: formatBytes(trafficSummary.value.today_tx_bytes), icon: markRaw(Upload), color: '#14b8a6' },
    )
  }
  return cards
})

const quickActions = computed(() => [
  { label: '用户管理', desc: '查看和管理网络机器', path: '/users', icon: markRaw(Connection), color: 'rgba(79,70,229,.12)' },
  { label: '路由管理', desc: '管理子网路由通告', path: '/routes', icon: markRaw(Guide), color: 'rgba(6,182,212,.12)' },
  { label: '系统设置', desc: '配置 Headscale 连接', path: '/settings', icon: markRaw(Setting), color: 'rgba(245,158,11,.12)' },
  { label: 'DNS 配置', desc: '配置 MagicDNS 和下发 DNS', path: '/settings/dns', icon: markRaw(SetUp), color: 'rgba(59,130,246,.12)' },
].filter(item => userStore.isManager || !item.path.startsWith('/settings')))

function progressColor(v) {
  if (v > 80) return '#ef4444'
  if (v > 60) return '#f59e0b'
  return '#10b981'
}

function formatBytes(b) {
  if (!b) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let val = b
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++ }
  return val.toFixed(1) + ' ' + units[i]
}

onMounted(async () => {
  if (userStore.isManager) {
    try {
      const res = await getSystemInfo()
      const d = res.data || {}
      sysInfo.value.cpu = Math.round(d.cpu_usage ?? d.cpu ?? 0)
      sysInfo.value.memory = Math.round(d.memory_percent ?? d.memory ?? 0)
      sysInfo.value.memoryUsed = d.memory_used ?? 0
      sysInfo.value.memoryTotal = d.memory_total ?? 0
      if (Array.isArray(d.internal_ips)) internalIps.value = d.internal_ips
    } catch {}
  } else {
    try {
      const res = await getTrafficSummary()
      trafficSummary.value = res.data || trafficSummary.value
    } catch {}
  }

  // 节点统计
  try {
    const res = await getNodes()
    const d = res.data
    const nodes = Array.isArray(d) ? d : (d?.nodes || [])
    nodeCount.value = nodes.length
    const now = new Date()
    onlineCount.value = nodes.filter(n => {
      if (n.online) return true
      if (!n.lastSeen) return false
      return (now - new Date(n.lastSeen)) < 300000
    }).length
  } catch {}

  if (userStore.isManager) {
    try {
      const res = await getHsUsers()
      userCount.value = Array.isArray(res.data) ? res.data.length : 0
    } catch {}
  } else {
    userCount.value = userStore.userInfo?.userId ? 1 : 0
  }

  // 最近日志
  if (userStore.isManager) {
    try {
      const res = await getLogs({ page: 1, size: 10 })
      recentLogs.value = res.data || []
    } catch {}
  }
})
</script>

<style scoped>
.stat-row { margin-bottom: 0; }
.stat-card { padding: 20px 24px; }
.section-title {
  font-size: 15px; font-weight: 600; color: var(--v3s-text-primary);
  margin-bottom: 16px;
}

/* 等高卡片 */
.info-row { display: flex; flex-wrap: wrap; }
.equal-card { height: 100%; display: flex; flex-direction: column; }

/* HS 状态卡片 */
.hs-status-card { gap: 0; }

.hs-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.hs-header-left { display: flex; align-items: center; gap: 12px; }
.hs-logo {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(239,68,68,.1); color: #ef4444;
  transition: all .3s;
}
.hs-logo.healthy { background: rgba(16,185,129,.1); color: #10b981; }
.hs-title { font-size: 15px; font-weight: 600; color: var(--v3s-text-primary); }
.hs-subtitle { font-size: 12px; color: var(--v3s-text-muted); display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.hs-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.hs-dot.on { background: #10b981; box-shadow: 0 0 6px #10b981; }
.hs-dot.off { background: #ef4444; }
.hs-ver { background: rgba(79,70,229,.1); color: #4f46e5; font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.hs-server-url { font-size: 12px; color: var(--v3s-text-muted); background: var(--v3s-primary-bg); padding: 3px 10px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; }

/* 指标条 */
.hs-metrics { display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; }
.metric-item { display: flex; align-items: center; gap: 10px; }
.metric-icon {
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.cpu-icon { background: rgba(6,182,212,.1); color: #06b6d4; }
.mem-icon { background: rgba(168,85,247,.1); color: #a855f7; }
.metric-body { flex: 1; min-width: 0; }
.metric-label { font-size: 12px; color: var(--v3s-text-muted); margin-bottom: 4px; }
.metric-detail { margin-left: 6px; font-size: 11px; opacity: .7; }
.metric-bar-wrap { height: 6px; border-radius: 3px; background: rgba(255,255,255,.06); overflow: hidden; }
.metric-bar { height: 100%; border-radius: 3px; transition: width .6s ease; }
.metric-val { font-size: 13px; font-weight: 700; color: var(--v3s-text-primary); min-width: 40px; text-align: right; }

/* 内网 IP 行 */
.hs-ip-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; margin-bottom: 14px;
  background: var(--v3s-primary-bg); border-radius: 8px;
}
.ip-icon { color: var(--v3s-text-muted); display: flex; flex-shrink: 0; }
.ip-label { font-size: 12px; color: var(--v3s-text-muted); white-space: nowrap; }
.ip-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.ip-tag {
  font-size: 12px; font-family: 'JetBrains Mono', monospace;
  background: rgba(79,70,229,.08); color: var(--v3s-text-primary);
  padding: 2px 8px; border-radius: 4px;
}
.ip-iface { color: var(--v3s-text-muted); margin-left: 3px; font-size: 11px; }
.ip-loading { font-size: 12px; color: var(--v3s-text-muted); }

/* 流量行 */
.hs-traffic-row {
  display: flex; align-items: stretch; gap: 0;
  margin-bottom: 14px;
  background: var(--v3s-primary-bg); border-radius: 10px;
  overflow: hidden;
}
.traffic-half {
  flex: 1; padding: 10px 16px;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.traffic-head {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--v3s-text-muted);
}
.upload .traffic-head { color: #10b981; }
.download .traffic-head { color: #4f46e5; }
.traffic-num { font-size: 16px; font-weight: 700; color: var(--v3s-text-primary); font-family: 'JetBrains Mono', monospace; }
.traffic-rate { font-size: 11px; font-weight: 600; }
.upload .traffic-rate { color: #10b981; }
.download .traffic-rate { color: #4f46e5; }
.traffic-divider { width: 1px; background: rgba(255,255,255,.08); margin: 8px 0; }

/* 迷你趋势图 */
.hs-chart-area { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.chart-label { font-size: 12px; color: var(--v3s-text-muted); margin-bottom: 6px; }
.mini-chart { background: var(--v3s-primary-bg); border-radius: 8px; padding: 8px 10px 4px; flex: 1; display: flex; flex-direction: column; }
.mini-chart svg { flex: 1; }
.chart-legend { display: flex; justify-content: center; gap: 16px; padding-top: 4px; }
.legend-item { font-size: 11px; color: var(--v3s-text-muted); display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 8px; height: 3px; border-radius: 2px; display: inline-block; }

/* 快捷操作 */
.quick-actions { display: flex; flex-direction: column; gap: 12px; flex: 1; }
.quick-action-item {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}
.quick-action-item:hover { background: var(--v3s-primary-bg); }
.qa-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: var(--v3s-primary); flex-shrink: 0;
}
.qa-title { font-size: 14px; font-weight: 600; color: var(--v3s-text-primary); }
.qa-desc { font-size: 12px; color: var(--v3s-text-muted); margin-top: 2px; }
</style>
