<template>
  <div>
    <div class="page-header"><h2>节点管理</h2><p>管理网络中的所有 Tailscale 节点</p></div>
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索节点名称 / IP" prefix-icon="Search" clearable style="width:260px" />
          <el-select v-model="filterUser" placeholder="筛选用户" clearable style="width:150px">
            <el-option v-for="u in userList" :key="u" :label="u" :value="u" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button @click="loadNodes" :icon="Refresh">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredNodes" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="givenName" label="节点名称" min-width="140">
          <template #default="{ row }">
            <span class="node-name">{{ row.givenName || row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="user" label="用户" width="100">
          <template #default="{ row }">{{ row.user?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="IP 地址" min-width="140">
          <template #default="{ row }">
            <el-tag v-for="ip in (row.ipAddresses || [])" :key="ip" size="small" effect="plain" style="margin:2px">{{ ip }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span v-if="isOnline(row)"><span class="status-dot online"></span>在线</span>
            <span v-else><span class="status-dot offline"></span>离线</span>
          </template>
        </el-table-column>
        <el-table-column label="最后上线" width="170">
          <template #default="{ row }">{{ row.lastSeen ? timeAgo(row.lastSeen) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
            <el-button type="primary" link size="small" @click="showRename(row)">重命名</el-button>
            <el-popconfirm title="确认删除此节点？" @confirm="handleDelete(row)">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="节点详情" width="560px" destroy-on-close>
      <el-descriptions :column="2" border size="small" v-if="currentNode">
        <el-descriptions-item label="节点名称">{{ currentNode.givenName || currentNode.name }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ currentNode.user?.name }}</el-descriptions-item>
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

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameVisible" title="重命名节点" width="400px">
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
import { getNodes, deleteNode, renameNode, getNodeRoutes } from '@/api'
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

// 详情
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

// 重命名
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

onMounted(loadNodes)
</script>

<style scoped>
.node-name { font-weight: 600; }
</style>
