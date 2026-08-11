<template>
  <div>
    <div class="page-header">
      <h2>安全中心</h2>
      <p>跟踪异常 IP 变化、客户端风险事件和可信网络白名单。</p>
    </div>

    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="6" v-for="item in statCards" :key="item.label">
        <div class="glass-card stat-card security-stat">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="glass-card content-card" style="margin-top:16px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="安全事件" name="events">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-select v-model="eventQuery.level" clearable placeholder="风险等级" style="width:130px" @change="loadEvents">
                <el-option label="严重" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
                <el-option label="信息" value="info" />
              </el-select>
              <el-select v-model="eventQuery.status" clearable placeholder="状态" style="width:120px" @change="loadEvents">
                <el-option label="待处理" value="open" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已关闭" value="closed" />
              </el-select>
            </div>
            <div class="toolbar-right">
              <el-button :icon="Refresh" @click="loadEvents">刷新</el-button>
            </div>
          </div>

          <el-table :data="events" v-loading="eventLoading" stripe>
            <el-table-column label="等级" width="90">
              <template #default="{ row }">
                <el-tag :type="levelType(row.level)" effect="plain">{{ levelText(row.level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="事件" min-width="190" show-overflow-tooltip />
            <el-table-column prop="machine_name" label="用户" width="130" />
            <el-table-column prop="group_name" label="分组" width="110" />
            <el-table-column prop="ip" label="IP" width="140" />
            <el-table-column label="位置" min-width="140">
              <template #default="{ row }">{{ [row.country, row.city].filter(Boolean).join(' / ') || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ statusText(row.status) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="170" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'open'" type="primary" link size="small" @click="setEventStatus(row, 'acknowledged')">确认</el-button>
                <el-button v-if="row.status !== 'closed'" type="success" link size="small" @click="setEventStatus(row, 'closed')">关闭</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager-wrap">
            <el-pagination
              layout="prev, pager, next"
              :total="eventTotal"
              :page-size="eventQuery.size"
              v-model:current-page="eventQuery.page"
              @current-change="loadEvents"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="IP 观测" name="ips">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-tag effect="plain">用于识别频繁变更公网 IP、跨地区漂移等风险</el-tag>
            </div>
            <div class="toolbar-right">
              <el-button :icon="Refresh" @click="loadIpObservations">刷新</el-button>
            </div>
          </div>
          <el-table :data="ipObservations" v-loading="ipLoading" stripe>
            <el-table-column prop="machine_name" label="用户" min-width="130" />
            <el-table-column prop="group_name" label="分组" width="110" />
            <el-table-column prop="ip" label="公网 IP" width="140" />
            <el-table-column label="位置" min-width="180">
              <template #default="{ row }">
                {{ [row.country, row.region, row.city].filter(Boolean).join(' / ') || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="asn" label="ASN" width="120" />
            <el-table-column prop="isp" label="运营商" min-width="140" show-overflow-tooltip />
            <el-table-column label="可信" width="80">
              <template #default="{ row }">
                <el-tag :type="row.risk_flags?.trusted ? 'success' : 'warning'" effect="plain">
                  {{ row.risk_flags?.trusted ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="seen_count" label="出现次数" width="90" />
            <el-table-column prop="last_seen" label="最后出现" width="170" />
          </el-table>
          <div class="pager-wrap">
            <el-pagination
              layout="prev, pager, next"
              :total="ipTotal"
              :page-size="ipQuery.size"
              v-model:current-page="ipQuery.page"
              @current-change="loadIpObservations"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="可信网络" name="trusted">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-tag effect="plain">单位出口、办公网段、机房网段可以加入可信范围</el-tag>
            </div>
            <div class="toolbar-right">
              <el-button :icon="Refresh" @click="loadTrustedNetworks">刷新</el-button>
              <el-button type="primary" :icon="Plus" @click="trustedDialogVisible = true">新增</el-button>
            </div>
          </div>

          <el-table :data="trustedNetworks" v-loading="trustedLoading" stripe>
            <el-table-column label="类型" width="120">
              <template #default="{ row }">{{ trustedKindText(row.kind) }}</template>
            </el-table-column>
            <el-table-column prop="value" label="值" min-width="170" />
            <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">{{ row.enabled ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" link size="small" :icon="Delete" @click="removeTrusted(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="风险规则" name="rules">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-tag effect="plain">配置安全事件的触发阈值，例如敏感端口、目标地址突增</el-tag>
            </div>
            <div class="toolbar-right">
              <el-button :icon="Refresh" @click="loadRiskRules">刷新</el-button>
            </div>
          </div>

          <el-table :data="riskRules" v-loading="riskLoading" stripe>
            <el-table-column prop="name" label="规则" min-width="180" />
            <el-table-column prop="rule_key" label="标识" width="170" />
            <el-table-column label="等级" width="90">
              <template #default="{ row }">
                <el-tag :type="levelType(row.level)" effect="plain">{{ levelText(row.level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">{{ row.enabled ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="配置" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">{{ JSON.stringify(row.config || {}) }}</template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="170" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openRiskRule(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="trustedDialogVisible" title="新增可信网络" width="460px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="trustedForm.kind" style="width:100%">
            <el-option label="IP 地址" value="ip" />
            <el-option label="CIDR 网段" value="cidr" />
            <el-option label="ASN" value="asn" />
            <el-option label="国家/地区" value="country" />
          </el-select>
        </el-form-item>
        <el-form-item label="值">
          <el-input v-model="trustedForm.value" placeholder="例如 203.0.113.10 或 203.0.113.0/24" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="trustedForm.description" type="textarea" :rows="3" maxlength="160" show-word-limit />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="trustedForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="trustedDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="trustedSaving" @click="saveTrusted">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="riskDialogVisible" title="编辑风险规则" width="560px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="规则名称">
          <el-input v-model="riskForm.name" />
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="riskForm.level" style="width:180px">
            <el-option label="严重" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
            <el-option label="信息" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="riskForm.enabled" />
        </el-form-item>
        <el-form-item label="配置 JSON">
          <el-input v-model="riskForm.configText" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="riskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="riskSaving" @click="saveRiskRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTrustedNetwork,
  deleteTrustedNetwork,
  getIpObservations,
  getRiskRules,
  getSecurityEvents,
  getSecuritySummary,
  getTrustedNetworks,
  updateSecurityEventStatus,
  updateRiskRule,
} from '@/api'

const activeTab = ref('events')
const summary = ref({ levels: {} })

const events = ref([])
const eventTotal = ref(0)
const eventLoading = ref(false)
const eventQuery = reactive({ page: 1, size: 20, level: '', status: 'open' })

const ipObservations = ref([])
const ipTotal = ref(0)
const ipLoading = ref(false)
const ipQuery = reactive({ page: 1, size: 20 })

const trustedNetworks = ref([])
const trustedLoading = ref(false)
const trustedSaving = ref(false)
const trustedDialogVisible = ref(false)
const trustedForm = reactive({ kind: 'cidr', value: '', description: '', enabled: true })
const riskRules = ref([])
const riskLoading = ref(false)
const riskSaving = ref(false)
const riskDialogVisible = ref(false)
const riskForm = reactive({ rule_key: '', name: '', level: 'medium', enabled: true, configText: '{}' })

const statCards = computed(() => {
  const levels = summary.value.levels || {}
  return [
    { label: '严重/高风险', value: Number(levels.critical || 0) + Number(levels.high || 0) },
    { label: '中低风险', value: Number(levels.medium || 0) + Number(levels.low || 0) },
    { label: 'IP 观测记录', value: summary.value.ip_observations || 0 },
    { label: '可信网络', value: summary.value.trusted_networks || 0 },
    { label: '定位服务', value: summary.value.geo_lookup_enabled ? '已启用' : '未配置' },
  ]
})

function levelText(level) {
  return ({ critical: '严重', high: '高', medium: '中', low: '低', info: '信息' })[level] || level
}

function levelType(level) {
  return ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info', info: 'success' })[level] || ''
}

function statusText(status) {
  return ({ open: '待处理', acknowledged: '已确认', closed: '已关闭' })[status] || status
}

function trustedKindText(kind) {
  return ({ ip: 'IP 地址', cidr: 'CIDR 网段', asn: 'ASN', country: '国家/地区' })[kind] || kind
}

async function loadSummary() {
  const res = await getSecuritySummary()
  summary.value = res.data || { levels: {} }
}

async function loadEvents() {
  eventLoading.value = true
  try {
    const res = await getSecurityEvents(eventQuery)
    events.value = res.data || []
    eventTotal.value = res.total || 0
  } finally {
    eventLoading.value = false
  }
}

async function loadIpObservations() {
  ipLoading.value = true
  try {
    const res = await getIpObservations(ipQuery)
    ipObservations.value = res.data || []
    ipTotal.value = res.total || 0
  } finally {
    ipLoading.value = false
  }
}

async function loadTrustedNetworks() {
  trustedLoading.value = true
  try {
    const res = await getTrustedNetworks()
    trustedNetworks.value = res.data || []
  } finally {
    trustedLoading.value = false
  }
}

async function loadRiskRules() {
  riskLoading.value = true
  try {
    const res = await getRiskRules()
    riskRules.value = res.data || []
  } finally {
    riskLoading.value = false
  }
}

async function setEventStatus(row, status) {
  await updateSecurityEventStatus(row.id, { status })
  ElMessage.success('事件状态已更新')
  await Promise.all([loadSummary(), loadEvents()])
}

async function saveTrusted() {
  if (!trustedForm.value.trim()) return ElMessage.warning('请输入可信网络值')
  trustedSaving.value = true
  try {
    await createTrustedNetwork({ ...trustedForm })
    ElMessage.success('可信网络已创建')
    Object.assign(trustedForm, { kind: 'cidr', value: '', description: '', enabled: true })
    trustedDialogVisible.value = false
    await Promise.all([loadSummary(), loadTrustedNetworks()])
  } finally {
    trustedSaving.value = false
  }
}

async function removeTrusted(row) {
  await ElMessageBox.confirm(`确认删除 ${row.value}？`, '删除可信网络', { type: 'warning' })
  await deleteTrustedNetwork(row.id)
  ElMessage.success('可信网络已删除')
  await Promise.all([loadSummary(), loadTrustedNetworks()])
}

function openRiskRule(row) {
  Object.assign(riskForm, {
    rule_key: row.rule_key,
    name: row.name,
    level: row.level || 'medium',
    enabled: Boolean(row.enabled),
    configText: JSON.stringify(row.config || {}, null, 2),
  })
  riskDialogVisible.value = true
}

async function saveRiskRule() {
  let config
  try {
    config = JSON.parse(riskForm.configText || '{}')
  } catch {
    ElMessage.error('配置 JSON 格式不正确')
    return
  }
  riskSaving.value = true
  try {
    await updateRiskRule(riskForm.rule_key, {
      name: riskForm.name,
      level: riskForm.level,
      enabled: riskForm.enabled,
      config,
    })
    ElMessage.success('风险规则已更新')
    riskDialogVisible.value = false
    await loadRiskRules()
  } finally {
    riskSaving.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'events') loadEvents()
  if (tab === 'ips') loadIpObservations()
  if (tab === 'trusted') loadTrustedNetworks()
  if (tab === 'rules') loadRiskRules()
})

onMounted(async () => {
  await Promise.all([loadSummary(), loadEvents()])
})
</script>

<style scoped>
.security-stat { padding: 20px 24px; }
.pager-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}
</style>
