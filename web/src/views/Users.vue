<template>
  <div>
    <div class="page-header"><h2>用户管理</h2><p>管理平台用户账户和权限</p></div>
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索用户名" prefix-icon="Search" clearable style="width:220px" />
        </div>
        <div class="toolbar-right">
          <el-button type="primary" @click="loadUsers" :icon="Refresh">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredUsers" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="用户名" width="120">
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
        <el-table-column label="节点配额" width="100">
          <template #default="{ row }">
            <el-link type="primary" @click="showEditNode(row)">{{ row.node || 0 }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="路由权限" width="100">
          <template #default="{ row }">
            <el-switch :model-value="String(row.route) === '1'" @change="v => handleToggleRoute(row, v)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="启用状态" width="100">
          <template #default="{ row }">
            <el-switch :model-value="String(row.enable) === '1'" @change="v => handleToggleEnable(row, v)"
              :disabled="row.name === 'admin'" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="170">
          <template #default="{ row }">
            <span v-if="row.expire">{{ row.expire }}</span>
            <el-tag v-else type="success" size="small" effect="plain">永不过期</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
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

    <!-- 修改节点配额弹窗 -->
    <el-dialog v-model="nodeVisible" title="修改节点配额" width="400px">
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
import { getUsers, deleteUser, toggleUserEnable, toggleUserRoute, updateUserExpire, updateUserNodeCount } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const users = ref([])
const search = ref('')
const saveLoading = ref(false)

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

// 修改节点配额
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

onMounted(loadUsers)
</script>
