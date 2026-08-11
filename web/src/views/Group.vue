<template>
  <div>
    <div class="page-header">
      <h2>分组管理</h2>
      <p>业务分组用于归类用户和下发策略，不再充当 Headscale 网络身份</p>
    </div>

    <div class="glass-card content-card">
      <div class="toolbar">
        <el-input
          v-model="search"
          placeholder="搜索分组或用户"
          prefix-icon="Search"
          clearable
          style="width:260px"
        />
        <div class="toolbar-right">
          <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
          <el-button type="primary" @click="openCreate">新建分组</el-button>
        </div>
      </div>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
        <template #title>RD 等分组可以包含多个独立用户；删除前必须先将组内用户移到其他分组。</template>
      </el-alert>

      <el-table :data="filteredGroups" v-loading="loading" stripe>
        <el-table-column prop="name" label="分组" min-width="150">
          <template #default="{ row }"><el-tag effect="plain">{{ row.name }}</el-tag></template>
        </el-table-column>
        <el-table-column label="用户数" width="100">
          <template #default="{ row }">{{ members(row.id).length }}</template>
        </el-table-column>
        <el-table-column label="组内用户" min-width="300">
          <template #default="{ row }">
            <div v-if="members(row.id).length" class="member-list">
              <el-tag v-for="account in members(row.id)" :key="account.id" size="small" type="info" effect="plain">
                {{ account.username }}
              </el-tag>
            </div>
            <span v-else class="empty-text">暂无用户</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              :title="members(row.id).length ? '该分组仍有用户，无法删除' : `确认删除分组「${row.name}」？`"
              :confirm-button-disabled="members(row.id).length > 0"
              @confirm="removeGroup(row)"
            >
              <template #reference>
                <el-button type="danger" link :disabled="members(row.id).length > 0">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createVisible" title="新建业务分组" width="440px" destroy-on-close>
      <el-form @submit.prevent="createGroup">
        <el-form-item label="分组名称" label-width="90px">
          <el-input v-model="newName" maxlength="255" placeholder="例如 RD、运维、财务" @keyup.enter="createGroup" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createGroup">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { createHsUser, deleteHsUser, getHsUsers, getUsers } from '@/api'

const groups = ref([])
const accounts = ref([])
const search = ref('')
const loading = ref(false)
const saving = ref(false)
const createVisible = ref(false)
const newName = ref('')

const filteredGroups = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return groups.value
  return groups.value.filter((group) => {
    if (group.name.toLowerCase().includes(keyword)) return true
    return members(group.id).some((account) => account.username.toLowerCase().includes(keyword))
  })
})

function members(groupId) {
  return accounts.value.filter((account) => Number(account.groupId) === Number(groupId))
}

async function loadData() {
  loading.value = true
  try {
    const [groupResult, accountResult] = await Promise.all([getHsUsers(), getUsers()])
    groups.value = groupResult.data || []
    accounts.value = accountResult.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  newName.value = ''
  createVisible.value = true
}

async function createGroup() {
  const name = newName.value.trim()
  if (!name) return ElMessage.warning('请输入分组名称')
  saving.value = true
  try {
    await createHsUser({ name })
    ElMessage.success(`分组 ${name} 已创建`)
    createVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeGroup(group) {
  await deleteHsUser(group.id)
  ElMessage.success(`分组 ${group.name} 已删除`)
  await loadData()
}

onMounted(loadData)
</script>

<style scoped>
.member-list { display: flex; flex-wrap: wrap; gap: 6px; }
.empty-text { color: var(--v3s-text-muted); font-size: 13px; }
</style>
