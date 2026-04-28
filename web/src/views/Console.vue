<template>
  <div>
    <div class="page-header"><h2>控制台</h2><p>系统运行状态总览</p></div>

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
      <el-col :xs="24" :sm="14">
        <div class="glass-card content-card equal-card">
          <div class="section-title">Headscale 服务状态</div>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="运行状态">
              <el-tag :type="hsHealthy ? 'success' : 'danger'" size="small" effect="plain">
                {{ hsHealthy ? '运行中' : '未连接' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="版本">{{ hsVersion || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="CPU 使用率">
              <div style="display:flex;align-items:center;gap:8px">
                <el-progress :percentage="sysInfo.cpu" :stroke-width="14" :color="progressColor(sysInfo.cpu)" style="width:120px" />
                <span class="info-val">{{ sysInfo.cpu }}%</span>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="内存使用率">
              <div style="display:flex;align-items:center;gap:8px">
                <el-progress :percentage="sysInfo.memory" :stroke-width="14" :color="progressColor(sysInfo.memory)" style="width:120px" />
                <span class="info-val">{{ sysInfo.memory }}%</span>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="内存详情">
              {{ formatBytes(sysInfo.memoryUsed) }} / {{ formatBytes(sysInfo.memoryTotal) }}
            </el-descriptions-item>
            <el-descriptions-item label="服务器地址">
              {{ serverUrl || '未配置' }}
            </el-descriptions-item>
            <el-descriptions-item label="内网IP">
              <template v-if="internalIps.length">
                <el-tag v-for="item in internalIps" :key="item.ip" size="small" effect="plain" style="margin:2px">
                  {{ item.ip }}<span style="color:#999;margin-left:4px">({{ item.iface }})</span>
                </el-tag>
              </template>
              <span v-else style="color:#999">获取中...</span>
            </el-descriptions-item>
            <el-descriptions-item label="上行流量">{{ formatBytes(sysInfo.netSent) }} <span v-if="trafficRate.upRate" style="color:#10b981;margin-left:6px">↑ {{ formatBytes(trafficRate.upRate) }}/s</span></el-descriptions-item>
            <el-descriptions-item label="下行流量">{{ formatBytes(sysInfo.netRecv) }} <span v-if="trafficRate.downRate" style="color:#4f46e5;margin-left:6px">↓ {{ formatBytes(trafficRate.downRate) }}/s</span></el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>

      <el-col :xs="24" :sm="10">
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
import { ref, computed, onMounted, onUnmounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getSystemInfo, getSystemTraffic, getNodes, getUsers, getLogs } from '@/api'
import { Monitor, Cpu, Connection, UserFilled, Key, Setting, Guide, SetUp } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const sysInfo = ref({ cpu: 0, memory: 0, memoryUsed: 0, memoryTotal: 0, netSent: 0, netRecv: 0 })
const internalIps = ref([])
const trafficRate = ref({ upRate: 0, downRate: 0 })
let prevTraffic = { sent: 0, recv: 0, time: 0 }
let trafficTimer = null
const nodeCount = ref(0)
const onlineCount = ref(0)
const userCount = ref(0)
const recentLogs = ref([])

const hsHealthy = computed(() => userStore.systemStatus.headscale_healthy)
const hsVersion = computed(() => {
  const v = userStore.systemStatus.headscale_version || ''
  const m = v.match(/v[\d.]+/)
  return m ? m[0] : v.split('\n')[0]
})
const serverUrl = computed(() => userStore.systemStatus.server_url || '')

const statCards = computed(() => [
  { label: '在线机器', value: onlineCount.value, icon: markRaw(Connection), color: '#10b981' },
  { label: '总机器数', value: nodeCount.value, icon: markRaw(Monitor), color: '#4f46e5' },
  { label: '分组数', value: userCount.value, icon: markRaw(UserFilled), color: '#f59e0b' },
  { label: 'CPU 使用率', value: sysInfo.value.cpu + '%', icon: markRaw(Cpu), color: '#06b6d4' },
])

const quickActions = [
  { label: '节点管理', desc: '查看和管理网络机器', path: '/nodes', icon: markRaw(Connection), color: 'rgba(79,70,229,.12)' },
  { label: '预认证密钥', desc: '创建设备注册密钥', path: '/preauthkeys', icon: markRaw(Key), color: 'rgba(16,185,129,.12)' },
  { label: '路由管理', desc: '管理子网路由通告', path: '/routes', icon: markRaw(Guide), color: 'rgba(6,182,212,.12)' },
  { label: '系统设置', desc: '配置 Headscale 连接', path: '/settings', icon: markRaw(Setting), color: 'rgba(245,158,11,.12)' },
]

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
  // 系统信息（CPU/内存/内网IP）
  try {
    const res = await getSystemInfo()
    const d = res.data || {}
    sysInfo.value.cpu = Math.round(d.cpu_usage ?? d.cpu ?? 0)
    sysInfo.value.memory = Math.round(d.memory_percent ?? d.memory ?? 0)
    sysInfo.value.memoryUsed = d.memory_used ?? 0
    sysInfo.value.memoryTotal = d.memory_total ?? 0
    if (Array.isArray(d.internal_ips)) {
      internalIps.value = d.internal_ips
    }
  } catch {}

  // 流量数据（独立接口）
  try {
    const res = await getSystemTraffic()
    const d = res.data || {}
    sysInfo.value.netSent = d.bytes_sent ?? d.net_sent ?? 0
    sysInfo.value.netRecv = d.bytes_recv ?? d.net_recv ?? 0
    prevTraffic = { sent: sysInfo.value.netSent, recv: sysInfo.value.netRecv, time: Date.now() }
  } catch {}

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

  // 用户数
  try {
    const res = await getUsers()
    const d = res.data
    userCount.value = Array.isArray(d) ? d.length : 0
  } catch {}

  // 最近日志
  if (userStore.isManager) {
    try {
      const res = await getLogs({ page: 1, size: 10 })
      recentLogs.value = res.data || []
    } catch {}
  }

  // 实时流量速率：每5秒刷新
  trafficTimer = setInterval(async () => {
    try {
      const res = await getSystemTraffic()
      const d = res.data || {}
      const nowSent = d.bytes_sent ?? d.net_sent ?? 0
      const nowRecv = d.bytes_recv ?? d.net_recv ?? 0
      const now = Date.now()
      if (prevTraffic.time > 0) {
        const elapsed = (now - prevTraffic.time) / 1000
        if (elapsed > 0) {
          trafficRate.value.upRate = Math.max(0, (nowSent - prevTraffic.sent) / elapsed)
          trafficRate.value.downRate = Math.max(0, (nowRecv - prevTraffic.recv) / elapsed)
        }
      }
      sysInfo.value.netSent = nowSent
      sysInfo.value.netRecv = nowRecv
      prevTraffic = { sent: nowSent, recv: nowRecv, time: now }
    } catch {}
  }, 5000)
})

onUnmounted(() => {
  if (trafficTimer) clearInterval(trafficTimer)
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
.equal-card .el-descriptions { flex: 1; }

.info-val { font-size: 13px; font-weight: 600; color: var(--v3s-text-primary); min-width: 38px; }

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
