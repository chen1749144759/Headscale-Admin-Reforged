<template>
  <div>
    <div class="page-header"><h2>分组管理</h2><p>管理 Headscale Group 和平台用户，创建分组时自动生成 ACL 规则</p></div>

    <!-- Headscale 分组管理 -->
    <div class="glass-card content-card" style="margin-bottom:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <h3 style="font-size:15px;font-weight:600;color:var(--v3s-text-primary);margin:0">Headscale Group</h3>
          <span style="font-size:12px;color:var(--v3s-text-muted);margin-left:8px">管理 headscale 用户命名空间（机器分组）</span>
        </div>
        <div class="toolbar-right">
          <el-button @click="loadHsUsers" :icon="Refresh" size="small">刷新</el-button>
          <el-button type="primary" @click="showCreateGroup" size="small">新建分组</el-button>
        </div>
      </div>

      <el-table :data="hsUsers" v-loading="hsLoading" size="small" stripe>
        <el-table-column prop="name" label="Group 名称" min-width="120">
          <template #default="{ row }">
            <el-tag :type="row.name === 'admin' ? 'danger' : ''" effect="plain">{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前机器数" width="100">
          <template #default="{ row }">
            <span>{{ getGroupNodeCount(row.name) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="ACL 规则数" width="100">
          <template #default="{ row }">
            <span>{{ getGroupAclCount(row.name) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showGroupAcl(row)">ACL 设置</el-button>
            <el-popconfirm :title="`确认删除 Group「${row.name}」？`" @confirm="handleDeleteHsUser(row)">
              <template #reference>
                <el-button type="danger" link size="small" :disabled="row.name === 'admin'">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新建分组弹窗（带 ACL 模板） -->
    <el-dialog v-model="hsCreateVisible" title="新建 Headscale Group" width="520px">
      <el-form label-width="100px">
        <el-form-item label="Group 名称">
          <el-input v-model="hsNewName" placeholder="例如: dev, uat, devops" maxlength="30" />
        </el-form-item>
        <el-form-item label="机器配额">
          <el-input-number v-model="hsNodeCount" :min="1" :max="999" />
          <span style="margin-left:8px;color:var(--v3s-text-muted);font-size:12px">此分组下允许注册的最大机器数</span>
        </el-form-item>
        <el-form-item label="ACL 模板">
          <el-radio-group v-model="aclTemplate">
            <el-radio value="internal">组内互通（同组机器可互相访问）</el-radio>
            <el-radio value="none">无规则（手动配置 ACL）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="aclTemplate === 'internal'" label="预览">
          <div class="acl-preview">
            <code>{{ previewInternal }}</code>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="hsCreateVisible = false">取消</el-button>
        <el-button type="primary" :loading="hsCreateLoading" @click="handleCreateHsUser">创建</el-button>
      </template>
    </el-dialog>

    <!-- 分组 ACL 设置弹窗 -->
    <el-dialog v-model="groupAclVisible" :title="`Group「${groupAclTarget?.name}」ACL 设置`" width="620px" destroy-on-close>
      <div style="font-weight:600;margin-bottom:8px">此分组下机器可以访问的目标</div>
      <el-table :data="groupAclRules" size="small" border style="margin-bottom:12px" empty-text="无规则（默认遵循全局 ACL）">
        <el-table-column label="目标" min-width="200">
          <template #default="{ row }"><code>{{ row.dst }}</code></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="groupAclRules.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;gap:8px;margin-bottom:16px">
        <el-input v-model="newGroupDst" placeholder="目标：IP/网段:端口 或 group:xxx:* 或 *:*" style="flex:1" @keyup.enter="addGroupDst" />
        <el-button type="primary" size="small" @click="addGroupDst">添加</el-button>
      </div>

      <div style="font-weight:600;margin-bottom:8px">允许访问此分组的来源</div>
      <el-table :data="groupAclInbound" size="small" border style="margin-bottom:12px" empty-text="无入站规则">
        <el-table-column label="来源" min-width="150">
          <template #default="{ row }"><code>{{ row.src }}</code></template>
        </el-table-column>
        <el-table-column label="端口" width="120">
          <template #default="{ row }"><code>{{ row.port }}</code></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="groupAclInbound.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <el-input v-model="newGroupSrc" placeholder="来源：用户名/group:xxx/*" style="flex:1" />
        <el-input v-model="newGroupPort" placeholder="端口：* 或 22,80" style="width:140px" @keyup.enter="addGroupInbound" />
        <el-button type="primary" size="small" @click="addGroupInbound">添加</el-button>
      </div>

      <template #footer>
        <el-button @click="groupAclVisible = false">取消</el-button>
        <el-button type="primary" :loading="groupAclSaving" @click="handleSaveGroupAcl">保存到 ACL</el-button>
      </template>
    </el-dialog>

    <!-- 平台用户管理 -->
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索用户名" prefix-icon="Search" clearable style="width:220px" />
        </div>
        <div class="toolbar-right">
          <el-button type="primary" @click="loadUsers" :icon="Refresh">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredUsers" v-loading="loading" stripe highlight-current-row table-layout="auto">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="用户名" min-width="100">
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'manager' ? 'danger' : 'info'" size="small" effect="plain">
              {{ row.role === 'manager' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="机器配额" width="90">
          <template #default="{ row }">
            <el-link type="primary" @click="showEditNode(row)">{{ row.node || 0 }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="路由权限" width="90">
          <template #default="{ row }">
            <el-switch :model-value="String(row.route) === '1'" @change="v => handleToggleRoute(row, v)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="启用状态" width="90">
          <template #default="{ row }">
            <el-switch :model-value="String(row.enable) === '1'" @change="v => handleToggleEnable(row, v)"
              :disabled="row.name === 'admin'" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="过期时间" min-width="140">
          <template #default="{ row }">
            <span v-if="row.expire">{{ row.expire }}</span>
            <el-tag v-else type="success" size="small" effect="plain">永不过期</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="140" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditExpire(row)">修改到期</el-button>
            <el-popconfirm title="确认删除此用户？" @confirm="handleDelete(row)" v-if="row.role !== 'manager'">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 修改到期时间弹窗 -->
    <el-dialog v-model="expireVisible" title="修改到期时间" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">{{ editUser?.name }}</el-form-item>
        <el-form-item label="到期时间">
          <el-date-picker v-model="newExpire" type="datetime" placeholder="选择到期时间" style="width:100%" value-format="YYYY-MM-DD HH:mm:ss" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="expireVisible = false">取消</el-button>
        <el-button type="primary" :loading="saveLoading" @click="handleSaveExpire">保存</el-button>
      </template>
    </el-dialog>

    <!-- 修改机器配额弹窗 -->
    <el-dialog v-model="nodeVisible" title="修改机器配额" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">{{ editUser?.name }}</el-form-item>
        <el-form-item label="配额">
          <el-input-number v-model="newNodeCount" :min="1" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nodeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saveLoading" @click="handleSaveNode">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getUsers, deleteUser, toggleUserEnable, toggleUserRoute, updateUserExpire, updateUserNodeCount,
  getHsUsers, createHsUser, deleteHsUser, getNodes, getAcl, updateAcl
} from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const users = ref([])
const search = ref('')
const saveLoading = ref(false)

// ─── Headscale 分组 ───
const hsLoading = ref(false)
const hsUsers = ref([])
const hsCreateVisible = ref(false)
const hsCreateLoading = ref(false)
const hsNewName = ref('')
const aclTemplate = ref('internal')
const hsNodeCount = ref(2)

// 节点数据（用于统计）
const allNodes = ref([])
// ACL 数据（用于统计）
const aclObj = ref({})

async function loadAllData() {
  try {
    const res = await getNodes()
    const d = res.data
    allNodes.value = Array.isArray(d) ? d : (d?.nodes || [])
  } catch {}
  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    aclObj.value = JSON.parse(cleaned)
  } catch { aclObj.value = {} }
}

function getGroupNodeCount(groupName) {
  return allNodes.value.filter(n => n.user?.name === groupName).length
}

function getGroupAclCount(groupName) {
  const acls = aclObj.value.acls || []
  return acls.filter(r =>
    r._groupId === groupName ||
    (r.src || []).includes(groupName) ||
    (r.dst || []).some(d => d.startsWith(groupName + ':'))
  ).length
}

const previewInternal = computed(() => {
  const name = hsNewName.value.trim() || 'groupName'
  return `{"action":"accept","src":["${name}"],"dst":["${name}:*"]}`
})

async function loadHsUsers() {
  hsLoading.value = true
  try { const res = await getHsUsers(); hsUsers.value = res.data || [] } catch {}
  hsLoading.value = false
}

function showCreateGroup() {
  hsNewName.value = ''
  aclTemplate.value = 'internal'
  hsNodeCount.value = 2
  hsCreateVisible.value = true
}

async function handleCreateHsUser() {
  const name = hsNewName.value.trim()
  if (!name) return ElMessage.warning('请输入 Group 名称')
  hsCreateLoading.value = true
  try {
    await createHsUser({ name, node_count: hsNodeCount.value })

    // 根据模板生成 ACL 规则
    if (aclTemplate.value === 'internal') {
      try {
        const res = await getAcl()
        const raw = res.data || '{}'
        const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
        const obj = JSON.parse(cleaned)
        if (!obj.acls) obj.acls = []

        obj.acls.push({
          action: 'accept',
          src: [name],
          dst: [name + ':*'],
          _groupId: name,
        })

        await updateAcl({ acl: JSON.stringify(obj, null, 2) })
      } catch (e) {
        console.warn('ACL 自动生成失败：', e)
      }
    }

    ElMessage.success(`Group ${name} 创建成功`)
    hsNewName.value = ''
    hsCreateVisible.value = false
    loadHsUsers()
    loadAllData()
  } catch {}
  hsCreateLoading.value = false
}

async function handleDeleteHsUser(group) {
  try {
    await ElMessageBox.confirm(`确认删除 Group「${group.name}」？该分组下如有在线机器则无法删除。`, '删除 Group', { type: 'warning' })
    await deleteHsUser(group.id)

    // 同时清理该分组的 ACL 规则
    try {
      const res = await getAcl()
      const raw = res.data || '{}'
      const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
      const obj = JSON.parse(cleaned)
      if (obj.acls) {
        obj.acls = obj.acls.filter(r => r._groupId !== group.name)
        await updateAcl({ acl: JSON.stringify(obj, null, 2) })
      }
    } catch {}

    ElMessage.success(`Group ${group.name} 已删除`)
    loadHsUsers()
    loadAllData()
  } catch {}
}

// ─── 分组 ACL 设置弹窗 ───
const groupAclVisible = ref(false)
const groupAclSaving = ref(false)
const groupAclTarget = ref(null)
const groupAclRules = ref([])     // [{dst: '10.0.0.0/24:*'}]
const groupAclInbound = ref([])   // [{src: '*', port: '22'}]
const newGroupDst = ref('')
const newGroupSrc = ref('')
const newGroupPort = ref('*')

async function showGroupAcl(group) {
  groupAclTarget.value = group
  groupAclRules.value = []
  groupAclInbound.value = []
  newGroupDst.value = ''
  newGroupSrc.value = ''
  newGroupPort.value = '*'

  // 从 ACL 中解析此分组的规则
  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    const acls = obj.acls || []
    const gn = group.name

    for (const rule of acls) {
      if (rule.action !== 'accept') continue
      const isSrc = (rule.src || []).includes(gn)
      const isDst = (rule.dst || []).some(d => d.startsWith(gn + ':'))

      if (isSrc) {
        for (const d of (rule.dst || [])) {
          groupAclRules.value.push({ dst: d })
        }
      }
      if (isDst) {
        for (const s of (rule.src || [])) {
          if (s === gn) continue  // 排除自身对自身的出站规则
          for (const d of (rule.dst || [])) {
            if (!d.startsWith(gn + ':')) continue
            const port = d.split(':').slice(1).join(':') || '*'
            groupAclInbound.value.push({ src: s, port })
          }
        }
      }
    }
  } catch {}

  groupAclVisible.value = true
}

function addGroupDst() {
  const val = newGroupDst.value.trim()
  if (!val) return ElMessage.warning('请输入目标')
  const dst = val.includes(':') ? val : val + ':*'
  groupAclRules.value.push({ dst })
  newGroupDst.value = ''
}

function addGroupInbound() {
  const src = newGroupSrc.value.trim()
  const port = newGroupPort.value.trim() || '*'
  if (!src) return ElMessage.warning('请输入来源')
  groupAclInbound.value.push({ src, port })
  newGroupSrc.value = ''
  newGroupPort.value = '*'
}

async function handleSaveGroupAcl() {
  if (!groupAclTarget.value) return
  groupAclSaving.value = true
  const gn = groupAclTarget.value.name
  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    if (!obj.acls) obj.acls = []

    // 移除旧的分组规则
    obj.acls = obj.acls.filter(r => r._groupId !== gn)

    // 生成出站规则
    if (groupAclRules.value.length > 0) {
      obj.acls.push({
        action: 'accept',
        src: [gn],
        dst: groupAclRules.value.map(r => r.dst),
        _groupId: gn,
      })
    }

    // 生成入站规则
    if (groupAclInbound.value.length > 0) {
      const srcMap = {}
      for (const r of groupAclInbound.value) {
        if (!srcMap[r.src]) srcMap[r.src] = []
        srcMap[r.src].push(gn + ':' + r.port)
      }
      for (const [src, dsts] of Object.entries(srcMap)) {
        obj.acls.push({
          action: 'accept',
          src: [src],
          dst: dsts,
          _groupId: gn,
        })
      }
    }

    await updateAcl({ acl: JSON.stringify(obj, null, 2) })
    ElMessage.success('分组 ACL 规则已更新')
    groupAclVisible.value = false
    loadAllData()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || '未知错误'))
  }
  groupAclSaving.value = false
}

// ─── 平台用户管理 ───
const filteredUsers = computed(() => {
  const s = search.value.toLowerCase()
  return !s ? users.value : users.value.filter(u => u.name.toLowerCase().includes(s))
})

async function loadUsers() {
  loading.value = true
  try { const res = await getUsers(); users.value = res.data || [] } catch {}
  loading.value = false
}

async function handleDelete(row) {
  try { await deleteUser(row.id); ElMessage.success('删除成功'); loadUsers() } catch {}
}

async function handleToggleEnable(row, val) {
  try { await toggleUserEnable(row.id, { enable: val }); ElMessage.success('更新成功'); loadUsers() } catch {}
}

async function handleToggleRoute(row, val) {
  try { await toggleUserRoute(row.id, { enable: val }); ElMessage.success('更新成功'); loadUsers() } catch {}
}

// 修改到期
const expireVisible = ref(false)
const editUser = ref(null)
const newExpire = ref('')
function showEditExpire(row) { editUser.value = row; newExpire.value = row.expire || ''; expireVisible.value = true }
async function handleSaveExpire() {
  if (!newExpire.value) return ElMessage.warning('请选择时间')
  saveLoading.value = true
  try {
    await updateUserExpire(editUser.value.id, { new_expire: newExpire.value })
    ElMessage.success('更新成功'); expireVisible.value = false; loadUsers()
  } catch {}
  saveLoading.value = false
}

// 修改机器配额
const nodeVisible = ref(false)
const newNodeCount = ref(2)
function showEditNode(row) { editUser.value = row; newNodeCount.value = parseInt(row.node) || 2; nodeVisible.value = true }
async function handleSaveNode() {
  saveLoading.value = true
  try {
    await updateUserNodeCount(editUser.value.id, { new_node_count: newNodeCount.value })
    ElMessage.success('更新成功'); nodeVisible.value = false; loadUsers()
  } catch {}
  saveLoading.value = false
}

onMounted(() => {
  loadUsers()
  loadHsUsers()
  loadAllData()
})
</script>

<style scoped>
.acl-preview {
  background: #1e1e2e;
  color: #a6e3a1;
  padding: 10px 14px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  word-break: break-all;
  line-height: 1.6;
}
</style>
