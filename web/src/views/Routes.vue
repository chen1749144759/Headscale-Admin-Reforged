<template>
  <div>
    <div class="page-header"><h2>路由管理</h2><p>管理子网路由通告</p></div>
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索网段 / 节点" prefix-icon="Search" clearable style="width:240px" />
        </div>
        <div class="toolbar-right">
          <el-button @click="loadRoutes" :icon="Refresh">刷新</el-button>
        </div>
      </div>
      <el-table :data="filteredRoutes" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="网段" min-width="180">
          <template #default="{ row }">
            <code class="route-prefix">{{ row.prefix || row.subnet || '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column label="节点" width="140">
          <template #default="{ row }">{{ row.node?.givenName || row.node?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="通告" width="80">
          <template #default="{ row }">
            <el-tag :type="row.advertised ? 'success' : 'info'" size="small">{{ row.advertised ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.enabled" type="success" link size="small" @click="handleEnable(row)">启用</el-button>
            <el-button v-else type="warning" link size="small" @click="handleDisable(row)">禁用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getRoutes, enableRoute, disableRoute } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const routes = ref([])
const search = ref('')

const filteredRoutes = computed(() => {
  const s = search.value.toLowerCase()
  return !s ? routes.value : routes.value.filter(r =>
    (r.prefix || r.subnet || '').toLowerCase().includes(s) ||
    (r.node?.givenName || r.node?.name || '').toLowerCase().includes(s)
  )
})

async function loadRoutes() {
  loading.value = true
  try {
    const res = await getRoutes()
    const d = res.data
    routes.value = Array.isArray(d) ? d : (d?.routes || [])
  } catch {}
  loading.value = false
}

async function handleEnable(row) {
  try { await enableRoute(row.id); ElMessage.success('已启用'); loadRoutes() } catch {}
}
async function handleDisable(row) {
  try { await disableRoute(row.id); ElMessage.success('已禁用'); loadRoutes() } catch {}
}

onMounted(loadRoutes)
</script>

<style scoped>
.route-prefix {
  background: #1e1e2e; color: #a6e3a1; padding: 2px 8px;
  border-radius: 4px; font-size: 13px; font-family: 'JetBrains Mono', monospace;
}
</style>
