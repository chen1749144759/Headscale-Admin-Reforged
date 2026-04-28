<template>
  <div>
    <div class="page-header"><h2>路由管理</h2><p>管理子网路由通告与自动审批规则</p></div>

    <!-- 路由通告列表 -->
    <div class="glass-card content-card" style="margin-bottom:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="section-title" style="margin:0">机器路由通告</div>
          <el-input v-model="search" placeholder="搜索网段 / 机器名" prefix-icon="Search" clearable style="width:240px;margin-left:12px" />
        </div>
        <div class="toolbar-right">
          <el-button @click="loadRoutes" :icon="Refresh">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredRoutes" v-loading="loading" stripe highlight-current-row empty-text="暂无路由通告（机器端需执行 tailscale up --advertise-routes=...）">
        <el-table-column label="机器" min-width="140">
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.nodeName }}</span>
            <el-tag size="small" effect="plain" style="margin-left:6px">{{ row.userName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通告网段" min-width="160">
          <template #default="{ row }">
            <code class="route-prefix">{{ row.prefix }}</code>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.approved ? 'success' : 'warning'" size="small">
              {{ row.approved ? '已批准' : '待审批' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.isExitNode" type="danger" size="small" effect="plain">Exit Node</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">子网路由</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.approved" type="success" link size="small" @click="handleApprove(row)">批准</el-button>
            <el-button v-else type="warning" link size="small" @click="handleRevoke(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- autoApprovers 可视化编辑 -->
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="section-title" style="margin:0">自动审批规则 (autoApprovers)</div>
          <el-text type="info" size="small" style="margin-left:12px">配置后，符合规则的路由通告将自动批准</el-text>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" size="small" @click="showAddRule">添加规则</el-button>
          <el-button type="success" :loading="savingAcl" @click="handleSaveAutoApprovers">保存到 ACL</el-button>
        </div>
      </div>

      <!-- 路由自动审批 -->
      <div style="margin-bottom:16px">
        <div style="font-weight:600;margin-bottom:8px;color:var(--v3s-text-primary)">路由规则 (routes)</div>
        <el-table :data="autoRouteRules" size="small" border empty-text="暂无路由自动审批规则">
          <el-table-column label="网段 (CIDR)" min-width="180">
            <template #default="{ row }">
              <code class="route-prefix">{{ row.prefix }}</code>
            </template>
          </el-table-column>
          <el-table-column label="允许的用户/Group" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="u in row.approvers" :key="u" size="small" style="margin:2px" closable
                @close="removeApprover('routes', row.prefix, u)">{{ u }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="removeRouteRule(row.prefix)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Exit Node 自动审批 -->
      <div>
        <div style="font-weight:600;margin-bottom:8px;color:var(--v3s-text-primary)">Exit Node 规则</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">
          <el-tag v-for="u in exitNodeApprovers" :key="u" size="large" closable @close="removeExitApprover(u)">{{ u }}</el-tag>
          <el-button size="small" @click="showAddExitApprover">添加</el-button>
        </div>
      </div>
    </div>

    <!-- 添加路由规则弹窗 -->
    <el-dialog v-model="addRuleVisible" title="添加自动审批规则" width="460px">
      <el-form label-width="100px">
        <el-form-item label="规则类型">
          <el-radio-group v-model="ruleForm.type">
            <el-radio value="route">路由网段</el-radio>
            <el-radio value="exit">Exit Node</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="ruleForm.type === 'route'" label="网段 (CIDR)">
          <el-input v-model="ruleForm.prefix" placeholder="例如: 10.0.0.0/24" />
        </el-form-item>
        <el-form-item label="允许的用户">
          <el-input v-model="ruleForm.approver" placeholder="用户名或 group:xxx 或 *" />
          <el-text type="info" size="small" style="margin-top:4px">支持格式: 用户名、group:groupName、tag:tagName、*（所有人）</el-text>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addRuleVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddRule">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加 Exit Node 审批者弹窗 -->
    <el-dialog v-model="addExitVisible" title="添加 Exit Node 审批者" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">
          <el-input v-model="exitApproverInput" placeholder="用户名或 group:xxx 或 *" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addExitVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddExitApprover">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { getRoutes, approveNodeRoutes, revokeNodeRoutes, getAcl, updateAcl } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const routes = ref([])
const search = ref('')
const savingAcl = ref(false)

// autoApprovers 数据
const autoRouteRules = ref([])  // [{prefix: '10.0.0.0/24', approvers: ['user1']}]
const exitNodeApprovers = ref([])

// ─── 路由列表 ───
const filteredRoutes = computed(() => {
  const s = search.value.toLowerCase()
  return !s ? routes.value : routes.value.filter(r =>
    r.prefix.toLowerCase().includes(s) || r.nodeName.toLowerCase().includes(s)
  )
})

async function loadRoutes() {
  loading.value = true
  try {
    const res = await getRoutes()
    const raw = res.data
    // 后端返回 {code:0, data: [{nodeId, nodeName, group, prefix, available, approved, active}]}
    const data = raw?.data || raw || []
    const flat = Array.isArray(data) ? data : []
    routes.value = flat.map(r => ({
      nodeId: r.nodeId,
      nodeName: r.nodeName || `Node#${r.nodeId}`,
      userName: r.group || r.userName || '-',
      prefix: r.prefix,
      approved: r.approved,
      available: r.available,
      active: r.active,
      isExitNode: r.prefix === '0.0.0.0/0' || r.prefix === '::/0',
    }))
  } catch {}
  loading.value = false
}

async function handleApprove(row) {
  try {
    // 获取当前已批准的路由，加上新批准的
    const nodeRoutes = routes.value.filter(r => r.nodeId === row.nodeId && r.approved)
    const approvedSet = new Set(nodeRoutes.map(r => r.prefix))
    approvedSet.add(row.prefix)
    await approveNodeRoutes(row.nodeId, [...approvedSet])
    ElMessage.success(`已批准路由 ${row.prefix}`)
    loadRoutes()
  } catch {}
}

async function handleRevoke(row) {
  try {
    await revokeNodeRoutes(row.nodeId, [row.prefix])
    ElMessage.success(`已撤销路由 ${row.prefix}`)
    loadRoutes()
  } catch {}
}

// ─── autoApprovers ───
async function loadAutoApprovers() {
  try {
    const res = await getAcl()
    const raw = res.data || ''
    // 解析 HuJSON
    const cleaned = raw
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    const aa = obj.autoApprovers || {}

    // 解析 routes
    const routeRules = []
    if (aa.routes) {
      for (const [prefix, approvers] of Object.entries(aa.routes)) {
        routeRules.push({
          prefix,
          approvers: Array.isArray(approvers) ? approvers : [approvers],
        })
      }
    }
    autoRouteRules.value = routeRules

    // 解析 exitNode
    exitNodeApprovers.value = Array.isArray(aa.exitNode) ? aa.exitNode : []
  } catch {
    autoRouteRules.value = []
    exitNodeApprovers.value = []
  }
}

async function handleSaveAutoApprovers() {
  savingAcl.value = true
  try {
    // 读取当前 ACL
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)

    // 组装 autoApprovers
    const routesMap = {}
    for (const rule of autoRouteRules.value) {
      if (rule.approvers.length > 0) {
        routesMap[rule.prefix] = rule.approvers
      }
    }
    obj.autoApprovers = {
      routes: routesMap,
      exitNode: exitNodeApprovers.value,
    }

    await updateAcl({ acl: JSON.stringify(obj, null, 2) })
    ElMessage.success('autoApprovers 已保存到 ACL')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || '未知错误'))
  }
  savingAcl.value = false
}

function removeRouteRule(prefix) {
  autoRouteRules.value = autoRouteRules.value.filter(r => r.prefix !== prefix)
}

function removeApprover(type, prefix, approver) {
  const rule = autoRouteRules.value.find(r => r.prefix === prefix)
  if (rule) {
    rule.approvers = rule.approvers.filter(a => a !== approver)
    if (rule.approvers.length === 0) {
      removeRouteRule(prefix)
    }
  }
}

function removeExitApprover(approver) {
  exitNodeApprovers.value = exitNodeApprovers.value.filter(a => a !== approver)
}

// ─── 添加规则弹窗 ───
const addRuleVisible = ref(false)
const ruleForm = reactive({ type: 'route', prefix: '', approver: '' })

function showAddRule() {
  ruleForm.type = 'route'
  ruleForm.prefix = ''
  ruleForm.approver = ''
  addRuleVisible.value = true
}

function handleAddRule() {
  const approver = ruleForm.approver.trim()
  if (!approver) return ElMessage.warning('请输入用户')

  if (ruleForm.type === 'route') {
    const prefix = ruleForm.prefix.trim()
    if (!prefix) return ElMessage.warning('请输入网段')
    const existing = autoRouteRules.value.find(r => r.prefix === prefix)
    if (existing) {
      if (!existing.approvers.includes(approver)) {
        existing.approvers.push(approver)
      }
    } else {
      autoRouteRules.value.push({ prefix, approvers: [approver] })
    }
  } else {
    if (!exitNodeApprovers.value.includes(approver)) {
      exitNodeApprovers.value.push(approver)
    }
  }
  addRuleVisible.value = false
  ElMessage.success('规则已添加（记得点击"保存到 ACL"）')
}

// ─── Exit Node 审批者弹窗 ───
const addExitVisible = ref(false)
const exitApproverInput = ref('')

function showAddExitApprover() {
  exitApproverInput.value = ''
  addExitVisible.value = true
}

function handleAddExitApprover() {
  const val = exitApproverInput.value.trim()
  if (!val) return ElMessage.warning('请输入用户')
  if (!exitNodeApprovers.value.includes(val)) {
    exitNodeApprovers.value.push(val)
  }
  addExitVisible.value = false
}

onMounted(() => {
  loadRoutes()
  loadAutoApprovers()
})
</script>

<style scoped>
.section-title {
  font-size: 15px; font-weight: 600; color: var(--v3s-text-primary);
}
.route-prefix {
  background: #1e1e2e; color: #a6e3a1; padding: 2px 8px;
  border-radius: 4px; font-size: 13px; font-family: 'JetBrains Mono', monospace;
}
</style>
