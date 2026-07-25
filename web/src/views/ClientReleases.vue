<template>
  <div>
    <div class="page-header">
      <h2>客户端版本</h2>
      <p>发布 ScaleTail 客户端更新策略，客户端会根据当前版本自动判断是否弹出建议更新或强制更新提示。</p>
    </div>

    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-tag effect="plain">客户端检查路径：/api/client-reports/client-update</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadReleases">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">发布新版本</el-button>
        </div>
      </div>

      <el-table :data="releases" v-loading="loading" stripe>
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
            <div v-if="row.sha256 && row.signature && row.file_size" class="integrity-cell">
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
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="toggleRelease(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="removeRelease(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑客户端版本' : '发布新版本'" width="680px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="签名元数据">
          <el-upload accept=".json,application/json" :auto-upload="false" :show-file-list="false" :on-change="importMetadata">
            <el-button>导入构建生成的 .ota.json</el-button>
          </el-upload>
          <span class="unit">自动填入版本、平台、SHA-256、大小和签名。</span>
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
          <el-radio-group v-model="form.update_type">
            <el-radio-button label="suggested">建议更新</el-radio-button>
            <el-radio-button label="forced">强制更新</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="例如 ScaleTail 0.0.2 已发布" />
        </el-form-item>
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
        <el-form-item label="Ed25519 签名">
          <el-input v-model="form.signature" type="textarea" :rows="3" placeholder="Base64 签名" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="300" show-word-limit />
        </el-form-item>
        <el-form-item label="更新内容">
          <el-input v-model="form.release_notes" type="textarea" :rows="5" maxlength="1200" show-word-limit />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
          <span class="unit">停用后客户端不会收到该版本。</span>
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
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createClientRelease,
  deleteClientRelease,
  getClientReleases,
  toggleClientRelease,
  updateClientRelease,
} from '@/api'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const releases = ref([])

const emptyForm = {
  id: null,
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
  enabled: true,
}
const form = reactive({ ...emptyForm })

function releaseType(value) {
  return value === 'forced' ? 'danger' : 'warning'
}

function releaseTypeText(value) {
  return value === 'forced' ? '强制更新' : '建议更新'
}

function resetForm(row = null) {
  Object.assign(form, emptyForm, row || {})
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
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm(row)
  dialogVisible.value = true
}

async function importMetadata(uploadFile) {
  try {
    const raw = uploadFile.raw
    if (!raw) return
    const metadata = JSON.parse(await raw.text())
    form.version = String(metadata.version || '').trim()
    form.platform = String(metadata.platform || 'windows-amd64').trim().toLowerCase()
    form.sha256 = String(metadata.sha256 || '').trim().toLowerCase()
    form.signature = String(metadata.signature || '').trim()
    form.file_size = Number(metadata.file_size || 0)
    ElMessage.success('签名元数据已导入')
  } catch {
    ElMessage.error('签名元数据文件格式无效')
  }
}

function validateForm() {
  if (!String(form.version || '').trim()) {
    ElMessage.warning('请填写版本号')
    return false
  }
  if (!String(form.download_url || '').trim()) {
    ElMessage.warning('请填写下载地址')
    return false
  }
  if (!/^https?:\/\//i.test(String(form.download_url || '').trim())) {
    ElMessage.warning('下载地址必须以 http:// 或 https:// 开头')
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
  if (!String(form.signature || '').trim()) {
    ElMessage.warning('请填写 Ed25519 签名')
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
    if (form.id) {
      await updateClientRelease(form.id, payload)
      ElMessage.success('客户端版本已更新')
    } else {
      await createClientRelease(payload)
      ElMessage.success('客户端版本已发布')
    }
    dialogVisible.value = false
    loadReleases()
  } finally {
    saving.value = false
  }
}

async function toggleRelease(row) {
  await toggleClientRelease(row.id, !row.enabled)
  ElMessage.success(row.enabled ? '客户端版本已停用' : '客户端版本已启用')
  loadReleases()
}

async function removeRelease(row) {
  await ElMessageBox.confirm(`确认删除客户端版本 ${row.version} 吗？`, '删除客户端版本', { type: 'warning' })
  await deleteClientRelease(row.id)
  ElMessage.success('客户端版本已删除')
  loadReleases()
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
</style>
