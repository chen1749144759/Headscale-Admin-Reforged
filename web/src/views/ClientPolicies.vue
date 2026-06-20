<template>
  <div>
    <div class="page-header">
      <h2>限速策略</h2>
      <p>按全局、分组、机器三层配置客户端限速与月流量配额，多个策略命中时取最严格的限制。</p>
    </div>

    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-tag effect="plain">最终生效规则：命中的策略共同计算，限速/配额取最小有效值</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增策略</el-button>
        </div>
      </div>

      <el-table :data="policies" v-loading="loading" stripe>
        <el-table-column label="作用域" width="100">
          <template #default="{ row }">
            <el-tag :type="scopeType(row.scope)" effect="plain">{{ scopeText(row.scope) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象" min-width="150">
          <template #default="{ row }">{{ targetText(row) }}</template>
        </el-table-column>
        <el-table-column label="上传限速" width="110">
          <template #default="{ row }">{{ speedText(row.rate_up_mbps) }}</template>
        </el-table-column>
        <el-table-column label="下载限速" width="110">
          <template #default="{ row }">{{ speedText(row.rate_down_mbps) }}</template>
        </el-table-column>
        <el-table-column label="月配额" width="110">
          <template #default="{ row }">{{ quotaText(row.monthly_quota_gb) }}</template>
        </el-table-column>
        <el-table-column label="超额动作" width="110">
          <template #default="{ row }">{{ actionText(row.exceed_action) }}</template>
        </el-table-column>
        <el-table-column label="优先级" prop="priority" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="removePolicy(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="glass-card content-card" style="margin-top:16px">
      <div class="section-title">客户端应用状态</div>
      <el-table :data="states" size="small" stripe>
        <el-table-column prop="machine_name" label="机器" min-width="140" />
        <el-table-column prop="policy_id" label="策略ID" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.applied ? 'success' : 'warning'" effect="plain">{{ row.applied ? '已应用' : '待应用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误" min-width="180" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="170" />
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑策略' : '新增策略'" width="560px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="作用域">
          <el-radio-group v-model="form.scope" @change="resetTarget">
            <el-radio-button label="global">全局</el-radio-button>
            <el-radio-button label="group">分组</el-radio-button>
            <el-radio-button label="machine">机器</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.scope === 'group'" label="分组">
          <el-select v-model="form.group_id" filterable placeholder="选择分组" style="width:100%" @change="syncGroupName">
            <el-option v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.scope === 'machine'" label="机器">
          <el-select v-model="form.machine_id" filterable placeholder="选择机器" style="width:100%" @change="syncMachineName">
            <el-option
              v-for="node in nodes"
              :key="node.id"
              :label="`${node.givenName || node.name} / ${node.user?.name || '-'}`"
              :value="node.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="上传限速">
          <el-input-number v-model="form.rate_up_mbps" :min="0" :precision="2" :step="1" />
          <span class="unit">Mbps，0 或空表示不限制</span>
        </el-form-item>
        <el-form-item label="下载限速">
          <el-input-number v-model="form.rate_down_mbps" :min="0" :precision="2" :step="1" />
          <span class="unit">Mbps，0 或空表示不限制</span>
        </el-form-item>
        <el-form-item label="月配额">
          <el-input-number v-model="form.monthly_quota_gb" :min="0" :precision="2" :step="10" />
          <span class="unit">GB，0 或空表示不限制</span>
        </el-form-item>
        <el-form-item label="超额动作">
          <el-select v-model="form.exceed_action" style="width:220px">
            <el-option label="仅告警" value="alert" />
            <el-option label="降速" value="throttle" />
            <el-option label="阻断" value="block" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePolicy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createClientPolicy,
  deleteClientPolicy,
  getClientPolicies,
  getClientPolicyStates,
  getHsUsers,
  getNodes,
  updateClientPolicy,
} from '@/api'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const policies = ref([])
const states = ref([])
const groups = ref([])
const nodes = ref([])

const emptyForm = {
  id: null,
  scope: 'global',
  group_id: null,
  group_name: '',
  machine_id: null,
  machine_name: '',
  rate_up_mbps: null,
  rate_down_mbps: null,
  monthly_quota_gb: null,
  exceed_action: 'throttle',
  enabled: true,
  priority: 100,
  remark: '',
}
const form = reactive({ ...emptyForm })

function scopeText(scope) {
  return ({ global: '全局', group: '分组', machine: '机器' })[scope] || scope
}

function scopeType(scope) {
  return ({ global: 'danger', group: 'warning', machine: 'success' })[scope] || ''
}

function actionText(action) {
  return ({ alert: '仅告警', throttle: '降速', block: '阻断' })[action] || action
}

function speedText(value) {
  const n = Number(value)
  return n > 0 ? `${n} Mbps` : '不限制'
}

function quotaText(value) {
  const n = Number(value)
  return n > 0 ? `${n} GB/月` : '不限制'
}

function targetText(row) {
  if (row.scope === 'global') return '所有机器'
  if (row.scope === 'group') return row.group_name || `分组#${row.group_id}`
  return row.machine_name || `机器#${row.machine_id}`
}

function normalizeLimit(value) {
  const n = Number(value)
  return n > 0 ? n : null
}

function resetForm(row = null) {
  Object.assign(form, emptyForm, row || {})
}

function resetTarget() {
  form.group_id = null
  form.group_name = ''
  form.machine_id = null
  form.machine_name = ''
}

function syncGroupName() {
  const group = groups.value.find(item => item.id === form.group_id)
  form.group_name = group?.name || ''
}

function syncMachineName() {
  const node = nodes.value.find(item => item.id === form.machine_id)
  form.machine_name = node ? (node.givenName || node.name || '') : ''
}

async function loadOptions() {
  const [groupRes, nodeRes] = await Promise.all([getHsUsers(), getNodes()])
  groups.value = groupRes.data || []
  const nodeData = nodeRes.data
  nodes.value = Array.isArray(nodeData) ? nodeData : (nodeData?.nodes || [])
}

async function loadAll() {
  loading.value = true
  try {
    const [policyRes, stateRes] = await Promise.all([getClientPolicies(), getClientPolicyStates()])
    policies.value = policyRes.data || []
    states.value = stateRes.data || []
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  resetForm()
  await loadOptions()
  dialogVisible.value = true
}

async function openEdit(row) {
  resetForm(row)
  await loadOptions()
  dialogVisible.value = true
}

async function savePolicy() {
  if (form.scope === 'group') syncGroupName()
  if (form.scope === 'machine') syncMachineName()
  saving.value = true
  try {
    const payload = {
      ...form,
      rate_up_mbps: normalizeLimit(form.rate_up_mbps),
      rate_down_mbps: normalizeLimit(form.rate_down_mbps),
      monthly_quota_gb: normalizeLimit(form.monthly_quota_gb),
    }
    if (form.id) {
      await updateClientPolicy(form.id, payload)
      ElMessage.success('策略已更新')
    } else {
      await createClientPolicy(payload)
      ElMessage.success('策略已创建')
    }
    dialogVisible.value = false
    loadAll()
  } finally {
    saving.value = false
  }
}

async function removePolicy(row) {
  await ElMessageBox.confirm(`确认删除策略 #${row.id}？`, '删除策略', { type: 'warning' })
  await deleteClientPolicy(row.id)
  ElMessage.success('策略已删除')
  loadAll()
}

onMounted(loadAll)
</script>

<style scoped>
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--v3s-text-primary);
  margin-bottom: 12px;
}
.unit {
  margin-left: 10px;
  color: var(--v3s-text-muted);
  font-size: 12px;
}
</style>
