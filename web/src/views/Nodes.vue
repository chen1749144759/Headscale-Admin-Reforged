<template>
  <div>
    <div class="page-header"><h2>用户管理</h2><p>管理所有 Tailscale 机器（用户 = 机器节点），可直接设置访问控制和分组</p></div>
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索机器名称 / IP" prefix-icon="Search" clearable style="width:260px" />
          <el-select v-model="filterUser" placeholder="筛选分组" clearable style="width:150px">
            <el-option v-for="u in userList" :key="u" :label="u" :value="u" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button @click="loadNodes" :icon="Refresh">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredNodes" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="givenName" label="机器名称" min-width="130">
          <template #default="{ row }">
            <span class="node-name">{{ row.givenName || row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="user" label="分组" width="100">
          <template #default="{ row }">{{ row.user?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="IP 地址" min-width="140">
          <template #default="{ row }">
            <el-tag v-for="ip in (row.ipAddresses || [])" :key="ip" size="small" effect="plain" style="margin:2px">{{ ip }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span v-if="isOnline(row)"><span class="status-dot online"></span>在线</span>
            <span v-else><span class="status-dot offline"></span>离线</span>
          </template>
        </el-table-column>
        <el-table-column label="最后上线" width="140">
          <template #default="{ row }">{{ row.lastSeen ? timeAgo(row.lastSeen) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showAclControl(row)">控制</el-button>
            <el-button type="warning" link size="small" @click="showChangeGroup(row)">分组</el-button>
            <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
            <el-button type="primary" link size="small" @click="showRename(row)">重命名</el-button>
            <el-popconfirm title="确认删除此机器？" @confirm="handleDelete(row)">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- ═══ ACL 控制弹窗 ═══ -->
    <el-dialog v-model="aclVisible" title="访问控制" width="660px" destroy-on-close>
      <div v-if="aclTarget" style="margin-bottom:16px">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="机器">{{ aclTarget.givenName || aclTarget.name }}</el-descriptions-item>
          <el-descriptions-item label="分组">{{ aclTarget.user?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Tailscale IP" :span="2">
            <el-tag v-for="ip in (aclTarget.ipAddresses || [])" :key="ip" size="small" style="margin:2px">{{ ip }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div style="font-weight:600;margin-bottom:8px">此机器可以访问（出站规则）</div>
      <el-table :data="aclOutboundRules" size="small" border style="margin-bottom:16px" empty-text="无出站规则（默认遵循全局 ACL）">
        <el-table-column label="目标" min-width="200">
          <template #default="{ row }">
            <code>{{ row.dst }}</code>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="aclOutboundRules.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;gap:8px;margin-bottom:20px">
        <el-input v-model="newOutboundDst" placeholder="目标 IP/网段:端口  例如 10.0.0.0/24:* 或 100.64.0.2:22" style="flex:1" @keyup.enter="addOutbound" />
        <el-button type="primary" size="small" @click="addOutbound">添加</el-button>
      </div>

      <div style="font-weight:600;margin-bottom:8px">允许访问此机器（入站规则）</div>
      <el-table :data="aclInboundRules" size="small" border style="margin-bottom:16px" empty-text="无入站规则（默认遵循全局 ACL）">
        <el-table-column label="来源" min-width="140">
          <template #default="{ row }"><code>{{ row.src }}</code></template>
        </el-table-column>
        <el-table-column label="端口" min-width="100">
          <template #default="{ row }"><code>{{ row.port }}</code></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="aclInboundRules.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <el-input v-model="newInboundSrc" placeholder="来源：用户名/group:xxx/*" style="flex:1" />
        <el-input v-model="newInboundPort" placeholder="端口：* 或 22,80,443" style="width:160px" @keyup.enter="addInbound" />
        <el-button type="primary" size="small" @click="addInbound">添加</el-button>
      </div>

      <template #footer>
        <el-button @click="aclVisible = false">取消</el-button>
        <el-button type="primary" :loading="aclSaving" @click="handleSaveAcl">保存到 ACL</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 分组变更弹窗 ═══ -->
    <el-dialog v-model="groupVisible" title="变更分组" width="420px">
      <el-form label-width="80px" v-if="groupTarget">
        <el-form-item label="机器">{{ groupTarget.givenName || groupTarget.name }}</el-form-item>
        <el-form-item label="当前分组">
          <el-tag>{{ groupTarget.user?.name || '-' }}</el-tag>
        </el-form-item>
        <el-form-item label="目标分组">
          <el-select v-model="newGroupName" placeholder="选择目标分组" style="width:100%">
            <el-option v-for="g in hsGroupList" :key="g.name" :label="g.name" :value="g.name"
              :disabled="g.name === groupTarget.user?.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupVisible = false">取消</el-button>
        <el-button type="primary" :loading="groupSaving" @click="handleMoveGroup">确认变更</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 详情弹窗 ═══ -->
    <el-dialog v-model="detailVisible" title="机器详情" width="560px" destroy-on-close>
      <el-descriptions :column="2" border size="small" v-if="currentNode">
        <el-descriptions-item label="机器名称">{{ currentNode.givenName || currentNode.name }}</el-descriptions-item>
        <el-descriptions-item label="所属分组">{{ currentNode.user?.name }}</el-descriptions-item>
        <el-descriptions-item label="IP 地址" :span="2">
          <el-tag v-for="ip in (currentNode.ipAddresses || [])" :key="ip" size="small" style="margin:2px">{{ ip }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentNode.createdAt }}</el-descriptions-item>
        <el-descriptions-item label="过期时间">{{ currentNode.expiry }}</el-descriptions-item>
        <el-descriptions-item label="最后上线">{{ currentNode.lastSeen }}</el-descriptions-item>
        <el-descriptions-item label="在线状态">
          <el-tag :type="isOnline(currentNode) ? 'success' : 'info'" size="small">{{ isOnline(currentNode) ? '在线' : '离线' }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div style="margin-top:16px" v-if="nodeRoutes.length">
        <div style="font-weight:600;margin-bottom:8px">路由通告</div>
        <el-table :data="nodeRoutes" size="small" border>
          <el-table-column prop="prefix" label="网段" />
          <el-table-column prop="advertised" label="通告" width="80">
            <template #default="{ row }"><el-tag :type="row.advertised ? 'success' : 'info'" size="small">{{ row.advertised ? '是' : '否' }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="enabled" label="启用" width="80">
            <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag></template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <!-- ═══ 重命名弹窗 ═══ -->
    <el-dialog v-model="renameVisible" title="重命名机器" width="400px">
      <el-input v-model="newName" placeholder="输入新名称" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="renameLoading" @click="handleRename">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getNodes, deleteNode, renameNode, getNodeRoutes, getHsUsers, moveNodeUser, getAcl, updateAcl } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const nodes = ref([])
const search = ref('')
const filterUser = ref('')

const userList = computed(() => [...new Set(nodes.value.map(n => n.user?.name).filter(Boolean))])
const filteredNodes = computed(() => {
  return nodes.value.filter(n => {
    const s = search.value.toLowerCase()
    const matchSearch = !s || (n.givenName || n.name || '').toLowerCase().includes(s) ||
      (n.ipAddresses || []).some(ip => ip.includes(s))
    const matchUser = !filterUser.value || n.user?.name === filterUser.value
    return matchSearch && matchUser
  })
})

function isOnline(node) {
  if (node.online) return true
  if (!node.lastSeen) return false
  return (Date.now() - new Date(node.lastSeen).getTime()) < 300000
}

function timeAgo(dt) {
  const diff = (Date.now() - new Date(dt).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
  return Math.floor(diff / 86400) + ' 天前'
}

async function loadNodes() {
  loading.value = true
  try {
    const res = await getNodes()
    const d = res.data
    nodes.value = Array.isArray(d) ? d : (d?.nodes || [])
  } catch {}
  loading.value = false
}

async function handleDelete(row) {
  try {
    await deleteNode(row.id)
    ElMessage.success('删除成功')
    loadNodes()
  } catch {}
}

// ─── 详情 ───
const detailVisible = ref(false)
const currentNode = ref(null)
const nodeRoutes = ref([])
async function showDetail(row) {
  currentNode.value = row
  detailVisible.value = true
  try {
    const res = await getNodeRoutes(row.id)
    nodeRoutes.value = res.data || []
  } catch { nodeRoutes.value = [] }
}

// ─── 重命名 ───
const renameVisible = ref(false)
const renameLoading = ref(false)
const newName = ref('')
let renameTarget = null
function showRename(row) {
  renameTarget = row
  newName.value = row.givenName || row.name || ''
  renameVisible.value = true
}
async function handleRename() {
  if (!newName.value.trim()) return ElMessage.warning('请输入名称')
  renameLoading.value = true
  try {
    await renameNode(renameTarget.id, newName.value.trim())
    ElMessage.success('重命名成功')
    renameVisible.value = false
    loadNodes()
  } catch {}
  renameLoading.value = false
}

// ═══ ACL 控制 ═══
const aclVisible = ref(false)
const aclSaving = ref(false)
const aclTarget = ref(null)
const aclOutboundRules = ref([])   // [{dst: '10.0.0.0/24:*'}]
const aclInboundRules = ref([])    // [{src: 'user1', port: '22'}]
const newOutboundDst = ref('')
const newInboundSrc = ref('')
const newInboundPort = ref('*')

function getNodeIdentifier(node) {
  // 用 user name 作为 ACL 标识（headscale ACL 中 src/dst 用 user name 匹配该 user 下所有节点）
  // 如果节点有 Tailscale IP，也可以用 IP 做精确匹配
  const ips = node.ipAddresses || []
  const ipv4 = ips.find(ip => !ip.includes(':'))
  return ipv4 || node.user?.name || node.givenName || node.name
}

async function showAclControl(row) {
  aclTarget.value = row
  aclOutboundRules.value = []
  aclInboundRules.value = []
  newOutboundDst.value = ''
  newInboundSrc.value = ''
  newInboundPort.value = '*'

  // 从当前 ACL 中解析与此机器相关的规则
  try {
    const res = await getAcl()
    const raw = res.data || ''
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    const acls = obj.acls || []
    const nodeId = getNodeIdentifier(row)
    const nodeIps = row.ipAddresses || []
    const userName = row.user?.name

    for (const rule of acls) {
      if (rule.action !== 'accept') continue
      const srcMatch = (rule.src || []).some(s => s === nodeId || s === userName || nodeIps.includes(s))
      const dstMatch = (rule.dst || []).some(d => {
        const dHost = d.split(':')[0]
        return dHost === nodeId || dHost === userName || nodeIps.includes(dHost)
      })

      if (srcMatch) {
        // 出站规则：此机器作为 src
        for (const d of (rule.dst || [])) {
          aclOutboundRules.value.push({ dst: d })
        }
      }
      if (dstMatch) {
        // 入站规则：此机器作为 dst
        for (const s of (rule.src || [])) {
          for (const d of (rule.dst || [])) {
            const parts = d.split(':')
            const port = parts.length > 1 ? parts.slice(1).join(':') : '*'
            aclInboundRules.value.push({ src: s, port })
          }
        }
      }
    }
  } catch {
    // ACL 解析失败不影响打开弹窗
  }

  aclVisible.value = true
}

function addOutbound() {
  const val = newOutboundDst.value.trim()
  if (!val) return ElMessage.warning('请输入目标地址')
  // 自动补 :* 如果没写端口
  const dst = val.includes(':') ? val : val + ':*'
  aclOutboundRules.value.push({ dst })
  newOutboundDst.value = ''
}

function addInbound() {
  const src = newInboundSrc.value.trim()
  const port = newInboundPort.value.trim() || '*'
  if (!src) return ElMessage.warning('请输入来源')
  aclInboundRules.value.push({ src, port })
  newInboundSrc.value = ''
  newInboundPort.value = '*'
}

async function handleSaveAcl() {
  if (!aclTarget.value) return
  aclSaving.value = true
  try {
    // 读取当前 ACL
    const res = await getAcl()
    const raw = res.data || '{}'
    const cleaned = raw.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    if (!obj.acls) obj.acls = []

    const nodeId = getNodeIdentifier(aclTarget.value)

    // 移除旧的与此节点相关的规则（通过特殊注释字段 _nodeId 标识）
    obj.acls = obj.acls.filter(r => r._nodeId !== nodeId)

    // 生成出站规则
    if (aclOutboundRules.value.length > 0) {
      obj.acls.push({
        action: 'accept',
        src: [nodeId],
        dst: aclOutboundRules.value.map(r => r.dst),
        _nodeId: nodeId,  // 标记为自动生成
      })
    }

    // 生成入站规则
    if (aclInboundRules.value.length > 0) {
      // 按 src 分组
      const srcMap = {}
      for (const r of aclInboundRules.value) {
        if (!srcMap[r.src]) srcMap[r.src] = []
        srcMap[r.src].push(nodeId + ':' + r.port)
      }
      for (const [src, dsts] of Object.entries(srcMap)) {
        obj.acls.push({
          action: 'accept',
          src: [src],
          dst: dsts,
          _nodeId: nodeId,
        })
      }
    }

    await updateAcl({ acl: JSON.stringify(obj, null, 2) })
    ElMessage.success('ACL 规则已更新')
    aclVisible.value = false
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || '未知错误'))
  }
  aclSaving.value = false
}

// ═══ 分组变更 ═══
const groupVisible = ref(false)
const groupSaving = ref(false)
const groupTarget = ref(null)
const newGroupName = ref('')
const hsGroupList = ref([])

async function showChangeGroup(row) {
  groupTarget.value = row
  newGroupName.value = ''
  groupVisible.value = true
  // 加载分组列表
  try {
    const res = await getHsUsers()
    hsGroupList.value = res.data || []
  } catch { hsGroupList.value = [] }
}

async function handleMoveGroup() {
  if (!newGroupName.value) return ElMessage.warning('请选择目标分组')
  groupSaving.value = true
  try {
    await moveNodeUser(groupTarget.value.id, newGroupName.value)
    ElMessage.success(`已移动到分组 ${newGroupName.value}`)
    groupVisible.value = false
    loadNodes()
  } catch (e) {
    ElMessage.error('移动失败：' + (e?.response?.data?.detail || e.message || '可能当前 Headscale 版本不支持'))
  }
  groupSaving.value = false
}

onMounted(loadNodes)
</script>

<style scoped>
.node-name { font-weight: 600; }
</style>
