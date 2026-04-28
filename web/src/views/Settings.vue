<template>
  <div>
    <div class="page-header"><h2>系统设置</h2><p>配置 Headscale 连接和平台参数</p></div>

    <!-- Headscale 状态卡片 -->
    <div class="glass-card content-card" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px">
          <el-tag :type="form.headscale_running ? 'success' : 'danger'" size="large" effect="dark">
            {{ form.headscale_running ? 'Headscale 运行中' : 'Headscale 已停止' }}
          </el-tag>
          <el-text v-if="form.headscale_version" type="info" size="small">{{ versionShort }}</el-text>
        </div>
        <div style="display:flex;gap:8px">
          <el-button :type="form.headscale_running ? 'danger' : 'success'" @click="handleSwitch">
            {{ form.headscale_running ? '停止服务' : '启动服务' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 设置表单 -->
    <div class="glass-card content-card">
      <!-- 编辑锁定提示栏 -->
      <div class="edit-guard">
        <div class="guard-info">
          <el-icon :size="16" :color="editMode ? '#10b981' : '#f59e0b'">
            <Unlock v-if="editMode" /><Lock v-else />
          </el-icon>
          <span v-if="!editMode" style="color:var(--v3s-text-secondary);font-size:13px">设置已锁定，点击右侧按钮解锁后编辑</span>
          <span v-else style="color:#10b981;font-size:13px">编辑模式已开启，修改后请保存</span>
        </div>
        <el-button v-if="!editMode" type="warning" plain size="small" @click="handleUnlock">
          <el-icon style="margin-right:4px"><Unlock /></el-icon>解锁编辑
        </el-button>
        <el-button v-else type="info" plain size="small" @click="handleLock">
          <el-icon style="margin-right:4px"><Lock /></el-icon>锁定
        </el-button>
      </div>

      <el-form :model="form" label-width="130px" label-position="right" style="max-width:600px" :disabled="!editMode">
        <el-divider content-position="left">Headscale 连接</el-divider>
        <el-form-item label="服务器地址">
          <el-input v-model="form.server_url" placeholder="http://127.0.0.1:18919" />
          <div class="form-tip">Headscale 监听的地址和端口</div>
        </el-form-item>
        <el-form-item label="监听网卡">
          <el-select v-model="form.server_net" placeholder="选择网卡" clearable style="width:100%">
            <el-option v-for="n in netInterfaces" :key="n" :label="n" :value="n" />
          </el-select>
          <div class="form-tip">用于流量统计的网卡接口</div>
        </el-form-item>

        <el-divider content-position="left">API 密钥</el-divider>
        <el-form-item label="Bearer Token">
          <div style="display:flex;gap:8px;width:100%">
            <el-input :model-value="maskedToken" readonly />
            <el-button type="warning" @click="handleRefreshKey" :loading="refreshing" :disabled="!editMode">刷新</el-button>
          </div>
          <div class="form-tip">Headscale API 认证密钥，刷新后旧密钥失效</div>
        </el-form-item>

        <el-form-item v-if="editMode">
          <el-button type="primary" :loading="saving" @click="handleSave" size="large">
            <el-icon style="margin-right:4px"><Check /></el-icon>保存设置
          </el-button>
          <el-button @click="handleLock" size="large">取消</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 密码确认弹窗 -->
    <el-dialog v-model="pwdDialogVisible" title="安全验证" width="400px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:16px">
        <template #title>修改系统设置属于敏感操作，请输入当前账户密码以确认身份</template>
      </el-alert>
      <el-form @submit.prevent="confirmSave">
        <el-form-item label="当前密码" label-width="80px">
          <el-input v-model="confirmPwd" type="password" show-password placeholder="请输入当前账户密码" ref="pwdInputRef" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmSave">确认保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useUserStore } from '@/stores/user'
import { getSettings, updateSettings, refreshApiKey, login } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lock, Unlock, Check } from '@element-plus/icons-vue'

const userStore = useUserStore()
const saving = ref(false)
const refreshing = ref(false)
const netInterfaces = ref([])
const editMode = ref(false)
const pwdDialogVisible = ref(false)
const confirmPwd = ref('')
const pwdInputRef = ref(null)
let formBackup = null

const form = ref({
  server_url: '', server_net: '', bearer_token: '',
  headscale_running: false, headscale_version: '',
})

const maskedToken = computed(() => {
  const t = form.value.bearer_token || ''
  return t.length > 12 ? t.slice(0, 8) + '****' + t.slice(-4) : t
})

const versionShort = computed(() => {
  const v = form.value.headscale_version || ''
  const m = v.match(/v[\d.]+/)
  return m ? m[0] : ''
})

async function loadSettings() {
  try {
    const res = await getSettings()
    const d = res.data || {}
    form.value = { ...form.value, ...d }
    netInterfaces.value = d.network_interfaces || []
  } catch {}
}

function handleUnlock() {
  formBackup = JSON.parse(JSON.stringify(form.value))
  editMode.value = true
}

function handleLock() {
  if (formBackup) form.value = JSON.parse(JSON.stringify(formBackup))
  editMode.value = false
  formBackup = null
}

// 点击保存 → 弹出密码确认
function handleSave() {
  confirmPwd.value = ''
  pwdDialogVisible.value = true
  nextTick(() => pwdInputRef.value?.focus())
}

// 密码确认后真正保存
async function confirmSave() {
  if (!confirmPwd.value) return ElMessage.warning('请输入密码')
  saving.value = true
  try {
    // 验证密码：调用 login 接口
    await login({ username: userStore.userInfo.name, password: confirmPwd.value })
    // 密码正确，执行保存
    await updateSettings({
      server_url: form.value.server_url,
      server_net: form.value.server_net,
    })
    ElMessage.success('设置已保存')
    pwdDialogVisible.value = false
    editMode.value = false
    formBackup = null
    await userStore.fetchSystemStatus()
  } catch (e) {
    const msg = e?.response?.data?.msg || e?.response?.data?.detail || ''
    if (msg.includes('密码') || msg.includes('password') || e?.response?.status === 401) {
      ElMessage.error('密码验证失败，请重新输入')
    }
  }
  saving.value = false
}

async function handleRefreshKey() {
  try {
    await ElMessageBox.confirm('刷新后旧 API Key 将失效，确认？', '刷新 API Key', { type: 'warning' })
    refreshing.value = true
    const res = await refreshApiKey()
    form.value.bearer_token = res.data || form.value.bearer_token
    ElMessage.success('API Key 已刷新')
  } catch {}
  refreshing.value = false
}

async function handleSwitch() {
  const action = form.value.headscale_running ? 'stop' : 'start'
  const label = form.value.headscale_running ? '停止' : '启动'
  try {
    await ElMessageBox.confirm(`确认${label} Headscale 服务？`, `${label}服务`, { type: 'warning' })
    await updateSettings({ headscale_action: action })
    ElMessage.success(`${label}指令已发送`)
    setTimeout(async () => { await loadSettings(); await userStore.fetchSystemStatus() }, 3000)
  } catch {}
}

onMounted(loadSettings)
</script>

<style scoped>
.form-tip { font-size: 12px; color: var(--v3s-text-muted); margin-top: 4px; line-height: 1.4; }

.edit-guard {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-bottom: 20px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
}
.guard-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
