<template>
  <div>
    <div class="page-header"><h2>网络分组</h2><p>管理 Headscale users 与机器归属；平台账户在独立页面维护</p></div>

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

      <details class="tip-collapse" style="margin-bottom:12px">
        <summary class="tip-summary">分组 与 ACL 分组定义 的区别（点击展开）</summary>
        <div class="tip-body">
          <p>此处的<b>分组 (Group)</b> 是 Headscale 的用户命名空间，每台机器注册时归属于一个分组。分组决定了机器的归属关系。</p>
          <p><b>ACL 分组定义</b>是访问控制策略层面的逻辑聚合（如 <code>group:devs</code>），可以将多个分组归到一起，在 ACL 规则中统一引用。例如 <code>group:devs = ["dev1", "dev2"]</code>，在规则中写 <code>group:devs</code> 即表示 dev1 和 dev2 下的所有机器。</p>
          <p>你可以在下方表格的「ACL 分组定义」列查看每个分组所属的定义，点击「定义」按钮可快速管理。</p>
        </div>
      </details>

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
        <el-table-column label="ACL 分组定义" min-width="160">
          <template #default="{ row }">
            <div style="display:flex;flex-wrap:wrap;gap:3px" v-if="getGroupDefinitions(row.name).length">
              <el-tag v-for="g in getGroupDefinitions(row.name)" :key="g" size="small" type="success" effect="plain">{{ g }}</el-tag>
            </div>
            <span v-else style="color:var(--v3s-text-muted);font-size:12px">未加入任何定义</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showGroupAcl(row)">ACL 设置</el-button>
            <el-button type="success" link size="small" @click="showGroupDefDialog(row)">定义</el-button>
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
        <el-input v-model="newGroupSrc" placeholder="来源：分组名/group:xxx/*" style="flex:1" />
        <el-input v-model="newGroupPort" placeholder="端口：* 或 22,80" style="width:140px" @keyup.enter="addGroupInbound" />
        <el-button type="primary" size="small" @click="addGroupInbound">添加</el-button>
      </div>

      <template #footer>
        <el-button @click="groupAclVisible = false">取消</el-button>
        <el-button type="primary" :loading="groupAclSaving" @click="handleSaveGroupAcl">保存到 ACL</el-button>
      </template>
    </el-dialog>

    <!-- 分组定义管理弹窗 -->
    <el-dialog v-model="groupDefVisible" :title="`管理「${groupDefTarget?.name}」的 ACL 分组定义`" width="560px" destroy-on-close>
      <details class="tip-collapse" style="margin-bottom:16px">
        <summary class="tip-summary">分组定义说明（点击展开）</summary>
        <div class="tip-body">
          <p>此处管理 ACL 中的 <code>groups</code> 字段。一个 ACL 分组定义 (如 <code>group:devs</code>) 可以包含多个 Headscale 分组。</p>
          <p>勾选后该分组将被加入对应的 ACL 定义中，在 ACL 规则中引用 <code>group:devs</code> 即包含该分组下所有机器。</p>
        </div>
      </details>
      <div v-if="groupDefTarget" style="margin-bottom:16px">
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="分组名称">{{ groupDefTarget.name }}</el-descriptions-item>
          <el-descriptions-item label="已属于定义">
            <el-tag v-for="g in getGroupDefinitions(groupDefTarget.name)" :key="g" size="small" type="success" style="margin:2px">{{ g }}</el-tag>
            <span v-if="!getGroupDefinitions(groupDefTarget.name).length" style="color:var(--v3s-text-muted);font-size:12px">无</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div style="font-weight:600;margin-bottom:8px;font-size:13px">现有 ACL 分组定义</div>
      <el-table :data="allGroupDefs" size="small" border style="margin-bottom:16px" empty-text="暂无分组定义">
        <el-table-column label="定义名称" width="160">
          <template #default="{ row }"><code>{{ row.name }}</code></template>
        </el-table-column>
        <el-table-column label="成员" min-width="200">
          <template #default="{ row }">
            <div style="display:flex;flex-wrap:wrap;gap:3px">
              <el-tag v-for="m in row.members" :key="m" size="small" :type="m === groupDefTarget?.name ? 'success' : ''" effect="plain">{{ m }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="包含此分组" width="100">
          <template #default="{ row }">
            <el-switch :model-value="row.members.includes(groupDefTarget?.name)" @change="(v) => toggleGroupDef(row.name, v)" size="small" />
          </template>
        </el-table-column>
      </el-table>

      <div style="font-weight:600;margin-bottom:8px;font-size:13px">新建分组定义</div>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <el-input v-model="newGroupDefName" placeholder="定义名称（如 devs，自动加 group: 前缀）" style="flex:1" @keyup.enter="handleCreateGroupDef" />
        <el-button type="primary" size="small" @click="handleCreateGroupDef">创建</el-button>
      </div>

      <template #footer>
        <el-button @click="groupDefVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getHsUsers, createHsUser, deleteHsUser, getNodes, getAcl, updateAcl
} from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

// ─── Headscale 分组 ───
const hsLoading = ref(false)
const hsUsers = ref([])
const hsCreateVisible = ref(false)
const hsCreateLoading = ref(false)
const hsNewName = ref('')
const aclTemplate = ref('internal')

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
  hsCreateVisible.value = true
}

async function handleCreateHsUser() {
  const name = hsNewName.value.trim()
  if (!name) return ElMessage.warning('请输入 Group 名称')
  hsCreateLoading.value = true
  try {
    await createHsUser({ name })

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

// ─── 分组定义管理 ───
const groupDefVisible = ref(false)
const groupDefTarget = ref(null)
const allGroupDefs = ref([])    // [{name: 'group:devs', members: ['dev1','dev2']}]
const newGroupDefName = ref('')

function getGroupDefinitions(groupName) {
  // 从 ACL groups 中查找包含此分组的定义
  const groups = aclObj.value.groups || {}
  const result = []
  for (const [name, members] of Object.entries(groups)) {
    if (Array.isArray(members) && members.includes(groupName)) {
      result.push(name)
    }
  }
  return result
}

async function showGroupDefDialog(group) {
  groupDefTarget.value = group
  newGroupDefName.value = ''

  // 重新加载 ACL 获取最新数据
  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    aclObj.value = JSON.parse(cleaned)
  } catch { aclObj.value = {} }

  // 解析所有分组定义
  const groups = aclObj.value.groups || {}
  allGroupDefs.value = Object.entries(groups).map(([name, members]) => ({
    name,
    members: Array.isArray(members) ? [...members] : [],
  }))

  groupDefVisible.value = true
}

async function toggleGroupDef(defName, include) {
  // 切换此分组是否属于某个 ACL 分组定义
  const groupName = groupDefTarget.value?.name
  if (!groupName) return

  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    if (!obj.groups) obj.groups = {}
    if (!obj.groups[defName]) obj.groups[defName] = []

    const members = obj.groups[defName]
    if (include) {
      if (!members.includes(groupName)) {
        members.push(groupName)
      }
    } else {
      obj.groups[defName] = members.filter(m => m !== groupName)
    }

    await updateAcl({ acl: JSON.stringify(obj, null, 2) })
    ElMessage.success(include ? `已将「${groupName}」加入 ${defName}` : `已从 ${defName} 移除「${groupName}」`)

    // 刷新数据
    aclObj.value = obj
    allGroupDefs.value = Object.entries(obj.groups || {}).map(([name, ms]) => ({
      name,
      members: Array.isArray(ms) ? [...ms] : [],
    }))
  } catch (e) {
    ElMessage.error('操作失败：' + (e.message || '未知错误'))
  }
}

async function handleCreateGroupDef() {
  let name = newGroupDefName.value.trim()
  if (!name) return ElMessage.warning('请输入定义名称')
  if (!name.startsWith('group:')) name = `group:${name}`

  try {
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    if (!obj.groups) obj.groups = {}

    if (obj.groups[name]) {
      return ElMessage.warning(`定义 ${name} 已存在`)
    }

    // 创建时自动将当前分组加入
    const groupName = groupDefTarget.value?.name
    obj.groups[name] = groupName ? [groupName] : []

    await updateAcl({ acl: JSON.stringify(obj, null, 2) })
    ElMessage.success(`分组定义 ${name} 已创建`)
    newGroupDefName.value = ''

    // 刷新
    aclObj.value = obj
    allGroupDefs.value = Object.entries(obj.groups || {}).map(([n, ms]) => ({
      name: n,
      members: Array.isArray(ms) ? [...ms] : [],
    }))
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || '未知错误'))
  }
}

onMounted(() => {
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

/* 可折叠提示样式 */
.tip-collapse {
  border: 1px solid #f0dca0;
  border-radius: 8px;
  background: #fdf6e3;
  overflow: hidden;
}
.tip-summary {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #92700c;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tip-summary::before {
  content: '▶';
  font-size: 10px;
  transition: transform 0.2s;
  display: inline-block;
}
details[open] > .tip-summary::before {
  transform: rotate(90deg);
}
.tip-summary::-webkit-details-marker {
  display: none;
}
.tip-body {
  padding: 0 16px 12px 16px;
  font-size: 13px;
  color: #5c4a0e;
  line-height: 1.7;
}
.tip-body p {
  margin: 6px 0;
}
.tip-body code {
  background: rgba(0,0,0,0.06);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}
</style>
