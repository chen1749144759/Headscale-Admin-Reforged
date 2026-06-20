<template>
  <div>
    <div class="page-header">
      <h2>流量统计</h2>
      <p>查看全局、分组、机器三个维度的收发流量与最近采样。</p>
    </div>

    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="6" v-for="item in statCards" :key="item.label">
        <div class="glass-card stat-card traffic-stat">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="glass-card content-card" style="margin-top:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select v-model="days" style="width:140px" @change="loadRanking">
            <el-option label="最近 24 小时" :value="1" />
            <el-option label="最近 7 天" :value="7" />
            <el-option label="最近 30 天" :value="30" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <div class="section-title">机器流量排行</div>
          <el-table :data="topMachines" v-loading="rankingLoading" size="small" stripe>
            <el-table-column prop="machine_name" label="机器" min-width="140" />
            <el-table-column prop="group_name" label="分组" width="120" />
            <el-table-column label="接收" width="110">
              <template #default="{ row }">{{ formatBytes(row.rx_bytes) }}</template>
            </el-table-column>
            <el-table-column label="发送" width="110">
              <template #default="{ row }">{{ formatBytes(row.tx_bytes) }}</template>
            </el-table-column>
          </el-table>
        </el-col>

        <el-col :xs="24" :md="12">
          <div class="section-title">分组流量排行</div>
          <el-table :data="topGroups" v-loading="rankingLoading" size="small" stripe>
            <el-table-column prop="group_name" label="分组" min-width="140" />
            <el-table-column prop="machines" label="机器数" width="90" />
            <el-table-column label="接收" width="110">
              <template #default="{ row }">{{ formatBytes(row.rx_bytes) }}</template>
            </el-table-column>
            <el-table-column label="发送" width="110">
              <template #default="{ row }">{{ formatBytes(row.tx_bytes) }}</template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </div>

    <div class="glass-card content-card" style="margin-top:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="section-title" style="margin:0">请求分析</div>
          <el-tag effect="plain">按客户端活跃连接聚合，展示目标地址、端口、进程与连接数</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadFlows">刷新</el-button>
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <div class="section-title">目标地址排行</div>
          <el-table :data="topDestinations" v-loading="flowLoading" size="small" stripe>
            <el-table-column prop="dst_ip" label="目标 IP" min-width="140" />
            <el-table-column prop="dst_port" label="端口" width="80" />
            <el-table-column prop="protocol" label="协议" width="80" />
            <el-table-column prop="process_name" label="进程" min-width="120" show-overflow-tooltip />
            <el-table-column prop="connection_count" label="连接数" width="90" />
            <el-table-column prop="machines" label="机器数" width="90" />
          </el-table>
        </el-col>

        <el-col :xs="24" :md="12">
          <div class="section-title">最近连接明细</div>
          <el-table :data="flows" v-loading="flowLoading" size="small" stripe>
            <el-table-column prop="window_start" label="时间" width="160" />
            <el-table-column prop="machine_name" label="机器" min-width="120" />
            <el-table-column label="目标" min-width="160">
              <template #default="{ row }">{{ row.dst_ip }}{{ row.dst_port ? ':' + row.dst_port : '' }}</template>
            </el-table-column>
            <el-table-column prop="process_name" label="进程" min-width="110" show-overflow-tooltip />
            <el-table-column prop="connection_count" label="连接数" width="90" />
          </el-table>
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
        </el-col>
      </el-row>
    </div>

    <div class="glass-card content-card" style="margin-top:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="section-title" style="margin:0">最近采样</div>
        </div>
        <div class="toolbar-right">
          <el-pagination
            small
            layout="prev, pager, next"
            :total="sampleTotal"
            :page-size="sampleQuery.size"
            v-model:current-page="sampleQuery.page"
            @current-change="loadSamples"
          />
        </div>
      </div>

      <el-table :data="samples" v-loading="sampleLoading" size="small" stripe>
        <el-table-column prop="observed_at" label="时间" width="170" />
        <el-table-column prop="machine_name" label="机器" min-width="130" />
        <el-table-column prop="group_name" label="分组" width="120" />
        <el-table-column label="接收增量" width="110">
          <template #default="{ row }">{{ formatBytes(row.rx_bytes_delta) }}</template>
        </el-table-column>
        <el-table-column label="发送增量" width="110">
          <template #default="{ row }">{{ formatBytes(row.tx_bytes_delta) }}</template>
        </el-table-column>
        <el-table-column label="接收速率" width="120">
          <template #default="{ row }">{{ formatRate(row.rx_rate_bps) }}</template>
        </el-table-column>
        <el-table-column label="发送速率" width="120">
          <template #default="{ row }">{{ formatRate(row.tx_rate_bps) }}</template>
        </el-table-column>
        <el-table-column prop="endpoint_type" label="连接类型" width="110" />
        <el-table-column prop="derp" label="DERP" width="90" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import {
  getTrafficFlows,
  getTrafficSamples,
  getTrafficSummary,
  getTrafficTopDestinations,
  getTrafficTopGroups,
  getTrafficTopMachines,
} from '@/api'

const summary = ref({})
const topMachines = ref([])
const topGroups = ref([])
const topDestinations = ref([])
const samples = ref([])
const flows = ref([])
const days = ref(7)
const rankingLoading = ref(false)
const sampleLoading = ref(false)
const flowLoading = ref(false)
const sampleTotal = ref(0)
const flowTotal = ref(0)
const sampleQuery = reactive({ page: 1, size: 20 })
const flowQuery = reactive({ page: 1, size: 20 })

const statCards = computed(() => [
  { label: '今日接收', value: formatBytes(summary.value.today_rx_bytes) },
  { label: '今日发送', value: formatBytes(summary.value.today_tx_bytes) },
  { label: '30天总量', value: formatBytes((summary.value.month_rx_bytes || 0) + (summary.value.month_tx_bytes || 0)) },
  { label: '活跃机器', value: summary.value.active_machines || 0 },
])

function toNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
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

function formatRate(value) {
  return `${formatBytes(toNumber(value) / 8)}/s`
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

async function loadSamples() {
  sampleLoading.value = true
  try {
    const res = await getTrafficSamples(sampleQuery)
    samples.value = res.data || []
    sampleTotal.value = res.total || 0
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

async function loadAll() {
  await Promise.all([loadSummary(), loadRanking(), loadSamples(), loadFlows()])
}

onMounted(loadAll)
</script>

<style scoped>
.traffic-stat { padding: 20px 24px; }
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--v3s-text-primary);
  margin-bottom: 12px;
}
</style>
