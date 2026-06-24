<template>
  <div class="traffic-page">
    <section class="traffic-hero">
      <div class="hero-copy">
        <div class="hero-kicker">ScaleForge Traffic Intelligence</div>
        <h2>流量观测中心</h2>
        <p>按机器、分组、目标地址和采样频率查看 ScaleTail 网络运行质量。</p>
      </div>
      <div class="hero-actions">
        <el-radio-group v-model="days" size="large" @change="loadWindowData">
          <el-radio-button :label="1">24小时</el-radio-button>
          <el-radio-button :label="7">7天</el-radio-button>
          <el-radio-button :label="30">30天</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :icon="Refresh" :loading="loadingAll" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <section class="metric-grid">
      <article v-for="item in statCards" :key="item.label" class="metric-card">
        <div class="metric-icon" :style="{ color: item.color, background: item.bg }">
          <component :is="item.icon" />
        </div>
        <div>
          <div class="metric-value">{{ item.value }}</div>
          <div class="metric-label">{{ item.label }}</div>
        </div>
      </article>
    </section>

    <section class="rank-grid">
      <div class="traffic-panel">
        <div class="panel-head">
          <div>
            <span class="panel-eyebrow">Machine Ranking</span>
            <h3>机器流量排行</h3>
          </div>
          <el-tag effect="plain">{{ windowLabel }}</el-tag>
        </div>
        <div v-loading="rankingLoading" class="rank-list">
          <article v-for="(row, index) in topMachines" :key="row.machine_id || row.machine_name" class="rank-row">
            <span class="rank-index">{{ padRank(index + 1) }}</span>
            <div class="rank-main">
              <div class="rank-title">{{ row.machine_name || '未知机器' }}</div>
              <div class="rank-sub">{{ row.group_name || '未分组' }}</div>
              <div class="rank-bar"><span :style="{ width: machineShare(row) + '%' }"></span></div>
            </div>
            <div class="rank-numbers">
              <strong>{{ formatBytes(totalBytes(row)) }}</strong>
              <span>收 {{ formatBytes(row.rx_bytes) }} / 发 {{ formatBytes(row.tx_bytes) }}</span>
            </div>
          </article>
          <el-empty v-if="!topMachines.length && !rankingLoading" description="暂无机器流量" />
        </div>
      </div>

      <div class="traffic-panel">
        <div class="panel-head">
          <div>
            <span class="panel-eyebrow">Group Ranking</span>
            <h3>分组流量排行</h3>
          </div>
          <el-tag type="success" effect="plain">{{ topGroups.length }} 个分组</el-tag>
        </div>
        <div v-loading="rankingLoading" class="rank-list">
          <article v-for="(row, index) in topGroups" :key="row.group_id || row.group_name" class="rank-row">
            <span class="rank-index">{{ padRank(index + 1) }}</span>
            <div class="rank-main">
              <div class="rank-title">{{ row.group_name || '未分组' }}</div>
              <div class="rank-sub">{{ row.machines || 0 }} 台机器</div>
              <div class="rank-bar emerald"><span :style="{ width: groupShare(row) + '%' }"></span></div>
            </div>
            <div class="rank-numbers">
              <strong>{{ formatBytes(totalBytes(row)) }}</strong>
              <span>收 {{ formatBytes(row.rx_bytes) }} / 发 {{ formatBytes(row.tx_bytes) }}</span>
            </div>
          </article>
          <el-empty v-if="!topGroups.length && !rankingLoading" description="暂无分组流量" />
        </div>
      </div>
    </section>

    <section class="traffic-panel request-panel">
      <div class="panel-head">
        <div>
          <span class="panel-eyebrow">Request Analysis</span>
          <h3>请求分析</h3>
        </div>
        <el-button :icon="Refresh" :loading="flowLoading" @click="loadFlows">刷新请求</el-button>
      </div>

      <div class="request-grid">
        <div class="destination-card">
          <div class="section-head">
            <h4>目标地址排行 TOP20</h4>
            <span>仅统计 Tailnet 地址与已宣告路由</span>
          </div>
          <div v-loading="flowLoading" class="destination-list">
            <article v-for="(row, index) in destinationRows" :key="destinationKey(row)" class="destination-row">
              <span class="rank-index">{{ padRank(index + 1) }}</span>
              <div class="destination-main">
                <div class="destination-title">
                  <span>{{ row.dst_ip }}{{ row.dst_port ? ':' + row.dst_port : '' }}</span>
                  <el-tag size="small" effect="plain">{{ row.protocol || 'tcp' }}</el-tag>
                </div>
                <div class="destination-meta">
                  {{ row.process_name || '未知进程' }} · {{ row.machines || 0 }} 台机器 · 最后 {{ row.last_seen || '-' }}
                </div>
                <div class="rank-bar amber"><span :style="{ width: destinationShare(row) + '%' }"></span></div>
              </div>
              <div class="destination-count">
                <strong>{{ row.connection_count || 0 }}</strong>
                <span>连接</span>
              </div>
            </article>
            <el-empty v-if="!destinationRows.length && !flowLoading" description="暂无 ScaleTail 目标连接" />
          </div>
        </div>

        <div class="flow-card">
          <div class="section-head">
            <h4>最近连接明细</h4>
            <span>按用户(机器)分组</span>
          </div>
          <div v-loading="flowLoading" class="flow-groups">
            <article v-for="group in groupedFlows" :key="group.machine" class="flow-group">
              <div class="flow-group-head">
                <div>
                  <strong>{{ group.machine }}</strong>
                  <span>{{ group.group || '未分组' }}</span>
                </div>
                <div class="flow-summary">
                  <b>{{ group.connections }}</b>
                  <span>连接 / {{ group.destinations }} 目标</span>
                </div>
              </div>
              <div class="flow-detail-list">
                <div v-for="row in group.items" :key="row.id || `${row.window_start}-${row.dst_ip}-${row.dst_port}`" class="flow-detail-row">
                  <div class="flow-target">{{ row.dst_ip }}{{ row.dst_port ? ':' + row.dst_port : '' }}</div>
                  <div class="flow-process">{{ row.process_name || '未知进程' }}</div>
                  <div class="flow-time">{{ row.window_start || '-' }}</div>
                  <el-tag size="small" effect="plain">{{ row.connection_count || 0 }}</el-tag>
                </div>
              </div>
            </article>
            <el-empty v-if="!groupedFlows.length && !flowLoading" description="暂无连接明细" />
          </div>
          <div class="pager-wrap">
            <el-pagination
              small
              layout="prev, pager, next"
              :total="flowTotal"
              :page-size="flowQuery.size"
              v-model:current-page="flowQuery.page"
              @current-change="loadFlows"
            />
          </div>
        </div>
      </div>
    </section>

    <section class="traffic-panel sample-panel">
      <div class="panel-head">
        <div>
          <span class="panel-eyebrow">Sampling Frequency</span>
          <h3>采样频率</h3>
        </div>
        <el-tag type="warning" effect="plain">按 15 秒上报间隔估算缺失</el-tag>
      </div>

      <div v-loading="sampleLoading" class="sample-grid">
        <article v-for="row in sampleHealth" :key="row.machine_id || row.machine_name" class="sample-card">
          <div class="sample-head">
            <div>
              <strong>{{ row.machine_name || '未知机器' }}</strong>
              <span>{{ row.group_name || '未分组' }}</span>
            </div>
            <span class="sample-last">最后 {{ row.last_seen || '-' }}</span>
          </div>

          <div class="sample-window">
            <div class="window-title">
              <span>最近24小时</span>
              <b>{{ formatPercent(windowInfo(row, 'h24').normal_percent) }}</b>
            </div>
            <el-progress :percentage="safePercent(windowInfo(row, 'h24').normal_percent)" :stroke-width="8" :show-text="false" />
            <div class="sample-metrics">
              <span>正常 {{ windowInfo(row, 'h24').normal }}</span>
              <span>缺失 {{ windowInfo(row, 'h24').failed }}</span>
              <span>{{ windowInfo(row, 'h24').samples_per_hour }}/小时</span>
            </div>
          </div>

          <div class="sample-window compact">
            <div class="window-title">
              <span>最近12小时</span>
              <b>{{ formatPercent(windowInfo(row, 'h12').normal_percent) }}</b>
            </div>
            <el-progress :percentage="safePercent(windowInfo(row, 'h12').normal_percent)" :stroke-width="8" :show-text="false" status="success" />
            <div class="sample-metrics">
              <span>正常 {{ windowInfo(row, 'h12').normal }}</span>
              <span>缺失 {{ windowInfo(row, 'h12').failed }}</span>
              <span>{{ windowInfo(row, 'h12').samples_per_hour }}/小时</span>
            </div>
          </div>
        </article>
        <el-empty v-if="!sampleHealth.length && !sampleLoading" description="暂无采样数据" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, reactive, ref } from 'vue'
import { Connection, Cpu, DataAnalysis, Monitor, Refresh } from '@element-plus/icons-vue'
import {
  getTrafficFlows,
  getTrafficSampleHealth,
  getTrafficSummary,
  getTrafficTopDestinations,
  getTrafficTopGroups,
  getTrafficTopMachines,
} from '@/api'

const summary = ref({})
const topMachines = ref([])
const topGroups = ref([])
const topDestinations = ref([])
const sampleHealth = ref([])
const flows = ref([])
const days = ref(7)
const loadingAll = ref(false)
const rankingLoading = ref(false)
const sampleLoading = ref(false)
const flowLoading = ref(false)
const flowTotal = ref(0)
const flowQuery = reactive({ page: 1, size: 60 })

const windowLabel = computed(() => {
  if (days.value === 1) return '最近24小时'
  return `最近${days.value}天`
})

const statCards = computed(() => [
  {
    label: '今日接收',
    value: formatBytes(summary.value.today_rx_bytes),
    icon: markRaw(DataAnalysis),
    color: '#1e40af',
    bg: 'rgba(37, 99, 235, 0.12)',
  },
  {
    label: '今日发送',
    value: formatBytes(summary.value.today_tx_bytes),
    icon: markRaw(Connection),
    color: '#047857',
    bg: 'rgba(16, 185, 129, 0.12)',
  },
  {
    label: '30天总量',
    value: formatBytes((summary.value.month_rx_bytes || 0) + (summary.value.month_tx_bytes || 0)),
    icon: markRaw(Monitor),
    color: '#b45309',
    bg: 'rgba(245, 158, 11, 0.14)',
  },
  {
    label: '活跃机器',
    value: summary.value.active_machines || 0,
    icon: markRaw(Cpu),
    color: '#7c3aed',
    bg: 'rgba(124, 58, 237, 0.12)',
  },
])

const maxMachineBytes = computed(() => Math.max(1, ...topMachines.value.map(totalBytes)))
const maxGroupBytes = computed(() => Math.max(1, ...topGroups.value.map(totalBytes)))
const destinationRows = computed(() => topDestinations.value.slice(0, 20))
const maxDestinationConnections = computed(() => Math.max(1, ...destinationRows.value.map((row) => toNumber(row.connection_count))))

const groupedFlows = computed(() => {
  const map = new Map()
  for (const row of flows.value) {
    const machine = row.machine_name || '未知机器'
    const item = map.get(machine) || {
      machine,
      group: row.group_name || '',
      connections: 0,
      destinations: 0,
      destinationSet: new Set(),
      items: [],
    }
    item.connections += toNumber(row.connection_count)
    item.destinationSet.add(`${row.dst_ip || ''}:${row.dst_port || ''}`)
    item.destinations = item.destinationSet.size
    if (item.items.length < 8) {
      item.items.push(row)
    }
    map.set(machine, item)
  }
  return [...map.values()].sort((a, b) => b.connections - a.connections)
})

function toNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function totalBytes(row) {
  return toNumber(row.rx_bytes) + toNumber(row.tx_bytes) + toNumber(row.bytes)
}

function machineShare(row) {
  return Math.max(6, Math.round((totalBytes(row) / maxMachineBytes.value) * 100))
}

function groupShare(row) {
  return Math.max(6, Math.round((totalBytes(row) / maxGroupBytes.value) * 100))
}

function destinationShare(row) {
  return Math.max(6, Math.round((toNumber(row.connection_count) / maxDestinationConnections.value) * 100))
}

function padRank(value) {
  return String(value).padStart(2, '0')
}

function destinationKey(row) {
  return `${row.dst_ip || ''}-${row.dst_port || ''}-${row.protocol || ''}-${row.process_name || ''}`
}

function safePercent(value) {
  return Math.max(0, Math.min(100, toNumber(value)))
}

function formatPercent(value) {
  return `${safePercent(value).toFixed(safePercent(value) >= 99 ? 0 : 1)}%`
}

function windowInfo(row, key) {
  return row?.windows?.[key] || {
    samples: 0,
    expected: 0,
    normal: 0,
    failed: 0,
    normal_percent: 0,
    samples_per_hour: 0,
  }
}

function formatBytes(value) {
  let n = toNumber(value)
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i += 1
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

async function loadSummary() {
  const res = await getTrafficSummary()
  summary.value = res.data || {}
}

async function loadRanking() {
  rankingLoading.value = true
  try {
    const [machinesRes, groupsRes] = await Promise.all([
      getTrafficTopMachines({ days: days.value }),
      getTrafficTopGroups({ days: days.value }),
    ])
    topMachines.value = machinesRes.data || []
    topGroups.value = groupsRes.data || []
  } finally {
    rankingLoading.value = false
  }
}

async function loadSampleHealth() {
  sampleLoading.value = true
  try {
    const res = await getTrafficSampleHealth({ interval_seconds: 15 })
    sampleHealth.value = res.data || []
  } finally {
    sampleLoading.value = false
  }
}

async function loadFlows() {
  flowLoading.value = true
  try {
    const [destRes, flowRes] = await Promise.all([
      getTrafficTopDestinations({ days: days.value }),
      getTrafficFlows(flowQuery),
    ])
    topDestinations.value = destRes.data || []
    flows.value = flowRes.data || []
    flowTotal.value = flowRes.total || 0
  } finally {
    flowLoading.value = false
  }
}

async function loadWindowData() {
  await Promise.all([loadRanking(), loadFlows()])
}

async function loadAll() {
  loadingAll.value = true
  try {
    await Promise.all([loadSummary(), loadRanking(), loadSampleHealth(), loadFlows()])
  } finally {
    loadingAll.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.traffic-page {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: calc(100vh - 96px);
  color: #0f172a;
}

.traffic-page::before {
  content: "";
  position: fixed;
  inset: 56px 0 0 var(--v3s-sidebar-width);
  pointer-events: none;
  background:
    linear-gradient(120deg, rgba(30, 64, 175, 0.10), transparent 34%),
    linear-gradient(240deg, rgba(16, 185, 129, 0.10), transparent 38%),
    repeating-linear-gradient(90deg, rgba(30, 64, 175, 0.05) 0 1px, transparent 1px 48px),
    repeating-linear-gradient(0deg, rgba(30, 64, 175, 0.04) 0 1px, transparent 1px 48px);
  mask-image: linear-gradient(to bottom, #000, transparent 92%);
}

.traffic-hero,
.traffic-panel,
.metric-card {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(255, 255, 255, 0.78);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 20px 55px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(22px) saturate(140%);
  -webkit-backdrop-filter: blur(22px) saturate(140%);
}

.traffic-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  overflow: hidden;
  min-height: 148px;
  padding: 28px;
  border-radius: 22px;
}

.traffic-hero::after {
  content: "";
  position: absolute;
  inset: auto 24px 0 24px;
  height: 3px;
  background: linear-gradient(90deg, #1e40af, #10b981, #f59e0b);
  opacity: 0.85;
}

.hero-copy { max-width: 680px; }
.hero-kicker,
.panel-eyebrow {
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-copy h2 {
  margin: 8px 0 8px;
  font-size: 30px;
  line-height: 1.16;
  font-weight: 800;
  color: #0f172a;
}

.hero-copy p {
  color: #475569;
  font-size: 14px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.metric-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 108px;
  padding: 20px;
  border-radius: 18px;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 65px rgba(15, 23, 42, 0.12);
}

.metric-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
}

.metric-icon :deep(svg) {
  width: 22px;
  height: 22px;
}

.metric-value {
  font-size: 25px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.1;
}

.metric-label {
  margin-top: 6px;
  font-size: 13px;
  color: #64748b;
}

.rank-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.traffic-panel {
  border-radius: 20px;
  padding: 20px;
}

.panel-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.panel-head h3,
.section-head h4 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 800;
}

.section-head span {
  color: #64748b;
  font-size: 12px;
}

.rank-list,
.destination-list,
.flow-groups,
.sample-grid {
  min-height: 120px;
}

.rank-row,
.destination-row {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.rank-row:last-child,
.destination-row:last-child {
  border-bottom: 0;
}

.rank-index {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #1e40af;
  background: rgba(37, 99, 235, 0.10);
  font-size: 12px;
  font-weight: 800;
  font-family: "Fira Code", Consolas, monospace;
}

.rank-main,
.destination-main {
  min-width: 0;
}

.rank-title,
.destination-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: #0f172a;
  font-weight: 700;
}

.destination-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-sub,
.destination-meta {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
}

.rank-bar {
  height: 7px;
  margin-top: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
}

.rank-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #1e40af, #3b82f6);
}

.rank-bar.emerald span { background: linear-gradient(90deg, #059669, #34d399); }
.rank-bar.amber span { background: linear-gradient(90deg, #d97706, #fbbf24); }

.rank-numbers,
.destination-count,
.flow-summary {
  text-align: right;
  white-space: nowrap;
}

.rank-numbers strong,
.destination-count strong,
.flow-summary b {
  display: block;
  color: #0f172a;
  font-size: 15px;
}

.rank-numbers span,
.destination-count span,
.flow-summary span {
  color: #64748b;
  font-size: 12px;
}

.request-panel {
  padding: 22px;
}

.request-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 18px;
}

.destination-card,
.flow-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(226, 232, 240, 0.78);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.68);
}

.flow-groups {
  display: grid;
  gap: 12px;
}

.flow-group {
  padding: 14px;
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.66);
}

.flow-group-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.flow-group-head strong {
  display: block;
  color: #0f172a;
}

.flow-group-head span {
  color: #64748b;
  font-size: 12px;
}

.flow-detail-list {
  display: grid;
  gap: 8px;
}

.flow-detail-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(88px, 0.7fr) 132px auto;
  gap: 8px;
  align-items: center;
  min-height: 32px;
  padding: 7px 9px;
  border-radius: 10px;
  background: rgba(241, 245, 249, 0.72);
  color: #334155;
  font-size: 12px;
}

.flow-target,
.flow-process,
.flow-time {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-target {
  color: #0f172a;
  font-weight: 700;
  font-family: "Fira Code", Consolas, monospace;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.sample-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.sample-card {
  padding: 16px;
  border: 1px solid rgba(226, 232, 240, 0.84);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.68);
}

.sample-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.sample-head strong {
  display: block;
  color: #0f172a;
}

.sample-head span,
.sample-last {
  color: #64748b;
  font-size: 12px;
}

.sample-last {
  white-space: nowrap;
}

.sample-window + .sample-window {
  margin-top: 14px;
}

.window-title,
.sample-metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.window-title {
  margin-bottom: 8px;
}

.window-title span {
  color: #334155;
  font-weight: 700;
  font-size: 13px;
}

.window-title b {
  color: #1e40af;
  font-size: 13px;
}

.sample-metrics {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

:deep(.el-radio-button__inner),
:deep(.el-button),
:deep(.el-tag) {
  transition: all 0.2s ease;
}

:deep(.el-progress-bar__outer) {
  background-color: rgba(148, 163, 184, 0.18);
}

@media (max-width: 1200px) {
  .metric-grid,
  .sample-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .request-grid,
  .rank-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .traffic-page::before {
    inset: 56px 0 0 0;
  }

  .traffic-hero,
  .panel-head,
  .flow-group-head,
  .sample-head {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .metric-grid,
  .sample-grid {
    grid-template-columns: 1fr;
  }

  .rank-row,
  .destination-row {
    grid-template-columns: 32px minmax(0, 1fr);
  }

  .rank-numbers,
  .destination-count {
    grid-column: 2;
    text-align: left;
  }

  .flow-detail-row {
    grid-template-columns: 1fr auto;
  }

  .flow-process,
  .flow-time {
    grid-column: 1 / -1;
  }
}
</style>
