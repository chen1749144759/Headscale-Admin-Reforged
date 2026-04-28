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
    <el-dialog v-model="showKeyVisible" title="密钥已创建" width="500px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px">
        <template #title>请立即复制密钥，此密钥只显示一次！</template>
      </el-alert>
      <div class="code-block" style="word-break:break-all">{{ createdKey }}</div>
      <template #footer>
        <el-button type="primary" @click="copyKey(createdKey); showKeyVisible = false">复制并关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getPreauthkeys, createPreauthkey, deletePreauthkey, getHsUsers } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const keys = ref([])
const createVisible = ref(false)
const createLoading = ref(false)
const showKeyVisible = ref(false)
const createdKey = ref('')
const createForm = reactive({ reusable: false, ephemeral: false, expireDays: 30, hsUserId: null })

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
  navigator.clipboard.writeText(key).then(() => ElMessage.success('已复制到剪贴板')).catch(() => ElMessage.error('复制失败'))
}

onMounted(() => {
  loadKeys()
  loadHsUsers()
})
</script>
