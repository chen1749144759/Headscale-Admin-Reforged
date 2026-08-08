<template>
  <div>
    <div class="page-header"><h2>平台账户</h2><p>账户与网络分组一对一绑定，身份由 Headscale 统一管理</p></div>

    <div class="glass-card content-card">
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索账户或网络分组" prefix-icon="Search" clearable style="width:260px" />
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadData">刷新</el-button>
          <el-button type="primary" @click="openCreate">新建账户</el-button>
        </div>
      </div>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
        <template #title>普通账户必须绑定一个未占用的 Headscale 网络分组；新建或重置产生的密码仅用于首次登录，用户必须立即修改。</template>
      </el-alert>

      <el-table :data="filteredAccounts" v-loading="loading" stripe>
        <el-table-column prop="username" label="账户" min-width="130" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'manager' ? 'danger' : 'info'" effect="plain">
              {{ row.role === 'manager' ? '管理员' : '普通账户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="networkName" label="网络分组" min-width="130">
          <template #default="{ row }">{{ row.networkName || '未绑定' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账户到期" min-width="170">
          <template #default="{ row }">{{ formatTime(row.expiresAt) || '永不过期' }}</template>
        </el-table-column>
        <el-table-column label="密码状态" min-width="180">
          <template #default="{ row }">
            <el-tag v-if="row.mustChangePassword" type="warning">下次登录必须修改</el-tag>
            <span v-else>{{ formatTime(row.passwordChangedAt) || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" link @click="openReset(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="accountDialog" :title="editing ? '编辑账户' : '新建账户'" width="520px" destroy-on-close>
      <el-form ref="accountFormRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" maxlength="255" /></el-form-item>
        <template v-if="!editing">
          <el-form-item label="初始密码" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword"><el-input v-model="form.confirmPassword" type="password" show-password /></el-form-item>
        </template>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="普通账户" value="user" />
            <el-option label="管理员" value="manager" />
          </el-select>
        </el-form-item>
        <el-form-item label="网络分组" :required="form.role === 'user'">
          <el-select v-model="form.userId" clearable placeholder="选择唯一绑定分组" style="width:100%">
            <el-option
              v-for="group in networkGroups"
              :key="group.id"
              :label="group.name"
              :value="Number(group.id)"
              :disabled="isGroupUsed(group.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="账户到期">
          <el-date-picker v-model="form.expiresAt" type="datetime" placeholder="留空表示永不过期" style="width:100%" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialog" title="重置账户密码" width="460px" destroy-on-close>
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:16px">
        <template #title>重置后现有会话和设备认证立即失效；此处设置的是临时密码，用户下次登录必须修改。</template>
      </el-alert>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="100px">
        <el-form-item label="账户">{{ resetTarget?.username }}</el-form-item>
        <el-form-item label="新密码" prop="password"><el-input v-model="resetForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword"><el-input v-model="resetForm.confirmPassword" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { createUser, getHsUsers, getUsers, resetUserPassword, updateUser } from '@/api'

const accounts = ref([])
const networkGroups = ref([])
const loading = ref(false)
const saving = ref(false)
const search = ref('')
const accountDialog = ref(false)
const editing = ref(null)
const accountFormRef = ref(null)
const resetDialog = ref(false)
const resetTarget = ref(null)
const resetFormRef = ref(null)

const emptyForm = () => ({ username: '', password: '', confirmPassword: '', role: 'user', userId: null, expiresAt: null, enabled: true })
const form = reactive(emptyForm())
const resetForm = reactive({ password: '', confirmPassword: '' })

const passwordRules = [
  { required: true, message: '请输入密码', trigger: 'blur' },
  { min: 12, message: '密码至少 12 个字符', trigger: 'blur' },
  { max: 72, message: '密码最多 72 个字符', trigger: 'blur' },
]
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: passwordRules,
  confirmPassword: [{ validator: (_r, value, callback) => value === form.password ? callback() : callback(new Error('两次密码不一致')), trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}
const resetRules = {
  password: passwordRules,
  confirmPassword: [{ validator: (_r, value, callback) => value === resetForm.password ? callback() : callback(new Error('两次密码不一致')), trigger: 'blur' }],
}

const filteredAccounts = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return accounts.value
  return accounts.value.filter((item) => `${item.username} ${item.networkName || ''}`.toLowerCase().includes(keyword))
})

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function isGroupUsed(groupId) {
  return accounts.value.some((item) => Number(item.userId) === Number(groupId) && item.id !== editing.value?.id)
}

async function loadData() {
  loading.value = true
  try {
    const [accountResult, groupResult] = await Promise.all([getUsers(), getHsUsers()])
    accounts.value = accountResult.data || []
    networkGroups.value = groupResult.data || []
  } finally {
    loading.value = false
  }
}

function assignForm(values) {
  Object.assign(form, emptyForm(), values)
}

function openCreate() {
  editing.value = null
  assignForm({})
  accountDialog.value = true
}

function openEdit(row) {
  editing.value = row
  assignForm({
    username: row.username,
    role: row.role,
    userId: row.userId == null ? null : Number(row.userId),
    expiresAt: row.expiresAt ? new Date(row.expiresAt) : null,
    enabled: row.enabled,
  })
  accountDialog.value = true
}

async function saveAccount() {
  await accountFormRef.value.validate()
  if (form.role === 'user' && form.userId == null) return ElMessage.warning('普通账户必须绑定网络分组')
  if (form.userId != null && isGroupUsed(form.userId)) return ElMessage.warning('该网络分组已绑定其他账户')
  saving.value = true
  try {
    const common = {
      username: form.username.trim(),
      role: form.role,
      enabled: form.enabled,
      userId: form.userId,
    }
    if (editing.value) {
      await updateUser(editing.value.id, {
        ...common,
        ...(form.userId == null ? { clearUser: true } : {}),
        ...(form.expiresAt ? { expiresAt: form.expiresAt.toISOString() } : { clearExpiresAt: true }),
      })
    } else {
      await createUser({
        ...common,
        password: form.password,
        ...(form.expiresAt ? { expiresAt: form.expiresAt.toISOString() } : {}),
      })
    }
    ElMessage.success(editing.value ? '账户已更新' : '账户已创建，初始密码需由用户首次登录后修改')
    accountDialog.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

function openReset(row) {
  resetTarget.value = row
  Object.assign(resetForm, { password: '', confirmPassword: '' })
  resetDialog.value = true
}

async function savePassword() {
  await resetFormRef.value.validate()
  saving.value = true
  try {
    await resetUserPassword(resetTarget.value.id, { newPassword: resetForm.password })
    ElMessage.success('临时密码已重置，用户下次登录必须修改')
    resetDialog.value = false
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>
