<template>
  <div>
    <div class="page-header">
      <h2>客户端版本</h2>
      <p>发布带签名和单调修订号的 ScaleTail 更新策略，支持建议更新、强制更新与解除强制策略。</p>
    </div>

    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-tag effect="plain">策略只追加且不可修改；解除强制必须发布更高修订的 clear 策略</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadReleases">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">发布更新策略</el-button>
        </div>
      </div>

      <el-table :data="releases" v-loading="loading" stripe>
        <el-table-column prop="policy_revision" label="策略修订" width="130" />
        <el-table-column prop="version" label="版本号" width="120" />
        <el-table-column prop="platform" label="平台" width="150" />
        <el-table-column label="更新类型" width="110">
          <template #default="{ row }">
            <el-tag :type="releaseType(row.update_type)" effect="plain">{{ releaseTypeText(row.update_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="150" show-overflow-tooltip />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="下载地址" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link v-if="row.download_url" type="primary" :href="row.download_url" target="_blank">
              {{ row.download_url }}
            </el-link>
            <span v-else class="muted">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="OTA 校验" width="160">
          <template #default="{ row }">
            <div v-if="row.update_type === 'clear' && row.signature" class="integrity-cell">
              <el-tag type="success" effect="plain">已签名清除</el-tag>
            </div>
            <div v-else-if="row.sha256 && row.signature && row.file_size" class="integrity-cell">
              <el-tag type="success" effect="plain">已签名</el-tag>
              <span>{{ formatBytes(row.file_size) }}</span>
            </div>
            <el-tag v-else type="danger" effect="plain">不可自动安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发布时间" width="170" />
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="发布更新策略" width="680px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="签名元数据">
          <el-upload accept=".json,application/json" :auto-upload="false" :show-file-list="false" :on-change="importMetadata">
            <el-button>导入构建生成的 .ota.json</el-button>
          </el-upload>
          <span class="unit">自动填入策略修订、动作、版本、平台、安装包元数据和签名。</span>
        </el-form-item>
        <el-form-item label="策略修订">
          <el-input-number
            v-model="form.policy_revision"
            :min="1"
            :max="9007199254740991"
            :step="1"
            :precision="0"
            controls-position="right"
            style="width: 100%"
          />
          <span class="unit">同一平台必须持续递增；构建元数据会自动生成。</span>
        </el-form-item>
        <el-form-item label="版本号">
          <el-input v-model="form.version" placeholder="例如 0.0.2" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="form.platform" filterable allow-create default-first-option style="width: 100%">
            <el-option label="Windows x64" value="windows-amd64" />
            <el-option label="Windows ARM64" value="windows-arm64" />
          </el-select>
        </el-form-item>
        <el-form-item label="更新类型">
          <el-radio-group v-model="form.update_type" @change="onUpdateTypeChange">
            <el-radio-button label="suggested">建议更新</el-radio-button>
            <el-radio-button label="forced">强制更新</el-radio-button>
            <el-radio-button label="clear">解除强制</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="例如 ScaleTail 0.0.2 已发布" />
        </el-form-item>
        <template v-if="form.update_type !== 'clear'">
          <el-form-item label="下载地址">
            <el-input v-model="form.download_url" placeholder="https://..." />
          </el-form-item>
          <el-form-item label="SHA-256">
            <el-input v-model="form.sha256" maxlength="64" placeholder="64 位十六进制摘要" />
          </el-form-item>
          <el-form-item label="安装包大小">
            <el-input-number v-model="form.file_size" :min="1" :max="1073741824" :step="1048576" controls-position="right" />
            <span class="unit">字节</span>
          </el-form-item>
        </template>
        <el-alert
          v-else
          title="解除强制策略不携带安装包；请导入由签名工具生成的 clear 类型元数据。"
          type="info"
          :closable="false"
          show-icon
          class="policy-alert"
        />
        <el-form-item label="Ed25519 签名">
          <el-input v-model="form.signature" type="textarea" :rows="3" placeholder="v3.Base64签名" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="300" show-word-limit />
        </el-form-item>
        <el-form-item label="更新内容">
          <el-input v-model="form.release_notes" type="textarea" :rows="5" maxlength="1200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRelease">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  createClientRelease,
  getClientReleases,
} from '@/api'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const releases = ref([])

const emptyForm = {
  policy_revision: 0,
  version: '',
  platform: 'windows-amd64',
  update_type: 'suggested',
  title: '',
  description: '',
  download_url: '',
  sha256: '',
  signature: '',
  file_size: 0,
  release_notes: '',
}
const form = reactive({ ...emptyForm })

function releaseType(value) {
  if (value === 'forced') return 'danger'
  if (value === 'clear') return 'success'
  return 'warning'
}

function releaseTypeText(value) {
  if (value === 'forced') return '强制更新'
  if (value === 'clear') return '解除强制'
  return '建议更新'
}

function resetForm() {
  Object.assign(form, emptyForm)
}

async function loadReleases() {
  loading.value = true
  try {
    const res = await getClientReleases()
    releases.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  form.policy_revision = Date.now()
  dialogVisible.value = true
}

async function importMetadata(uploadFile) {
  try {
    const raw = uploadFile.raw
    if (!raw) return
    const metadata = JSON.parse(await raw.text())
    form.policy_revision = Number(metadata.policy_revision || 0)
    form.version = String(metadata.version || '').trim()
    form.platform = String(metadata.platform || 'windows-amd64').trim().toLowerCase()
    form.update_type = String(metadata.update_type || 'suggested').trim().toLowerCase()
    form.download_url = String(metadata.download_url || '').trim()
    form.sha256 = String(metadata.sha256 || '').trim().toLowerCase()
    form.signature = String(metadata.signature || '').trim()
    form.file_size = Number(metadata.file_size || 0)
    ElMessage.success('签名元数据已导入')
  } catch {
    ElMessage.error('签名元数据文件格式无效')
  }
}

function onUpdateTypeChange(value) {
  if (value !== 'clear') return
  form.download_url = ''
  form.sha256 = ''
  form.file_size = 0
  form.signature = ''
}

function validateForm() {
  if (!Number.isSafeInteger(Number(form.policy_revision)) || Number(form.policy_revision) <= 0) {
    ElMessage.warning('请填写有效的策略修订号')
    return false
  }
  if (!String(form.version || '').trim()) {
    ElMessage.warning('请填写版本号')
    return false
  }
  if (form.update_type !== 'clear') {
    if (!String(form.download_url || '').trim()) {
      ElMessage.warning('请填写下载地址')
      return false
    }
    if (!/^https:\/\//i.test(String(form.download_url || '').trim())) {
      ElMessage.warning('下载地址必须使用 HTTPS')
      return false
    }
    if (!/^[a-f0-9]{64}$/i.test(String(form.sha256 || '').trim())) {
      ElMessage.warning('请填写有效的 SHA-256')
      return false
    }
    if (!Number.isSafeInteger(Number(form.file_size)) || Number(form.file_size) <= 0) {
      ElMessage.warning('请填写有效的安装包大小')
      return false
    }
  } else if (form.download_url || form.sha256 || Number(form.file_size || 0) !== 0) {
    ElMessage.warning('解除强制策略不能包含安装包元数据')
    return false
  }
  if (!/^v3\.[A-Za-z0-9+/]{86}==$/.test(String(form.signature || '').trim())) {
    ElMessage.warning('请导入有效的 v3 Ed25519 签名')
    return false
  }
  return true
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MiB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KiB`
  return `${bytes} B`
}

async function saveRelease() {
  if (!validateForm()) return
  saving.value = true
  try {
    const payload = { ...form }
    await createClientRelease(payload)
    ElMessage.success('客户端更新策略已发布且不可修改')
    dialogVisible.value = false
    loadReleases()
  } finally {
    saving.value = false
  }
}

onMounted(loadReleases)
</script>

<style scoped>
.unit {
  margin-left: 10px;
  color: var(--v3s-text-muted);
  font-size: 12px;
}

.muted {
  color: var(--v3s-text-muted);
}

.integrity-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--v3s-text-muted);
  font-size: 12px;
}

.policy-alert {
  margin: 0 0 18px 100px;
  width: calc(100% - 100px);
}
</style>
