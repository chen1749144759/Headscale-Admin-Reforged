<template>
  <div>
    <div class="page-header"><h2>预认证密钥</h2><p>创建和管理设备注册密钥</p></div>
    <div class="glass-card content-card">
      <div class="toolbar">
        <div class="toolbar-left"></div>
        <div class="toolbar-right">
          <el-button @click="loadKeys" :icon="Refresh">刷新</el-button>
          <el-button type="primary" @click="showCreate">创建密钥</el-button>
        </div>
      </div>
      <el-table :data="keys" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="密钥" min-width="200">
          <template #default="{ row }">
            <code style="font-size:12px;word-break:break-all">{{ row.key }}</code>
            <el-button type="primary" link size="small" @click="copyKey(row.key)" style="margin-left:6px">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column label="分组" width="100">
          <template #default="{ row }">{{ row.user_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="可复用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.reusable ? 'success' : 'info'" size="small">{{ row.reusable ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="临时机器" width="90">
          <template #default="{ row }">
            <el-tag :type="row.ephemeral ? 'warning' : 'info'" size="small">{{ row.ephemeral ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="180">
          <template #default="{ row }">{{ row.expiration || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确认删除此密钥？" @confirm="handleDelete(row)">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建密钥弹窗 -->
    <el-dialog v-model="createVisible" title="创建预认证密钥" width="440px">
      <el-form label-width="90px">
        <el-form-item label="所属分组">
          <el-select v-model="createForm.hsUserId" placeholder="选择 Headscale Group" style="width:100%">
            <el-option v-for="u in hsUsers" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="可复用">
          <el-switch v-model="createForm.reusable" />
          <el-text type="info" size="small" style="margin-left:8px">允许多个设备使用同一密钥</el-text>
        </el-form-item>
        <el-form-item label="临时机器">
          <el-switch v-model="createForm.ephemeral" />
          <el-text type="info" size="small" style="margin-left:8px">机器离线后自动删除</el-text>
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="createForm.expireDays" style="width:100%">
            <el-option :value="1" label="1 天" />
            <el-option :value="7" label="7 天" />
            <el-option :value="30" label="30 天" />
            <el-option :value="90" label="90 天" />
            <el-option :value="365" label="1 年" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 密钥展示弹窗 -->
    <el-dialog v-model="showKeyVisible" title="密钥已创建" width="560px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:16px">
        <template #title>请立即复制密钥，此密钥只显示一次！</template>
      </el-alert>

      <div class="key-label">密钥</div>
      <div class="key-block">
        <code class="key-text">{{ createdKey }}</code>
        <span class="key-copy-btn" @click="copyKey(createdKey)" title="复制密钥">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
        </span>
      </div>

      <div class="key-label" style="margin-top:14px">连接命令</div>
      <div class="key-block">
        <code class="key-text">tailscale up --login-server {{ serverUrl }} --authkey {{ createdKey }} --accept-routes</code>
        <span class="key-copy-btn" @click="copyKey(`tailscale up --login-server ${serverUrl} --authkey ${createdKey} --accept-routes`)" title="复制命令">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
        </span>
      </div>

      <template #footer>
        <el-button @click="showKeyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getPreauthkeys, createPreauthkey, deletePreauthkey, getHsUsers } from '@/api'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const userStore = useUserStore()
const loading = ref(false)
const keys = ref([])
const createVisible = ref(false)
const createLoading = ref(false)
const showKeyVisible = ref(false)
const createdKey = ref('')
const createForm = reactive({ reusable: false, ephemeral: false, expireDays: 30, hsUserId: null })
const serverUrl = ref('')

// headscale 分组列表
const hsUsers = ref([])
async function loadHsUsers() {
  try { const res = await getHsUsers(); hsUsers.value = res.data || [] } catch {}
}

async function loadKeys() {
  loading.value = true
  try {
    const res = await getPreauthkeys()
    const d = res.data
    keys.value = Array.isArray(d) ? d : []
  } catch {}
  loading.value = false
}

function showCreate() {
  createForm.hsUserId = null
  createVisible.value = true
}

async function handleCreate() {
  createLoading.value = true
  try {
    const payload = {
      reusable: createForm.reusable,
      ephemeral: createForm.ephemeral,
      expire_days: createForm.expireDays,
    }
    if (createForm.hsUserId != null) {
      payload.hs_user_id = createForm.hsUserId
    }
    const res = await createPreauthkey(payload)
    createVisible.value = false
    createdKey.value = res.data?.key || res.data || ''
    showKeyVisible.value = true
    loadKeys()
  } catch {}
  createLoading.value = false
}

async function handleDelete(row) {
  try { await deletePreauthkey(row.id); ElMessage.success('删除成功'); loadKeys() } catch {}
}

function copyKey(key) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(key).then(() => ElMessage.success('已复制到剪贴板')).catch(() => fallbackCopy(key))
  } else {
    fallbackCopy(key)
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy'); ElMessage.success('已复制到剪贴板') } catch { ElMessage.error('复制失败') }
  document.body.removeChild(ta)
}

onMounted(() => {
  loadKeys()
  loadHsUsers()
  const hsUrl = userStore.systemStatus?.server_url
  serverUrl.value = hsUrl || `http://${window.location.hostname}:8080`
})
</script>

<style scoped>
.key-label {
  font-size: 12px;
  color: var(--v3s-text-muted);
  margin-bottom: 6px;
  font-weight: 500;
}
.key-block {
  position: relative;
  background: #0d0d0d;
  border-radius: 8px;
  padding: 14px 44px 14px 14px;
  border: 1px solid rgba(255,255,255,.06);
}
.key-text {
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: #e2e8f0;
  word-break: break-all;
  line-height: 1.6;
}
.key-copy-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: rgba(255,255,255,.4);
  cursor: pointer;
  transition: all .2s;
}
.key-copy-btn:hover {
  color: #fff;
  background: rgba(255,255,255,.1);
}
</style>
