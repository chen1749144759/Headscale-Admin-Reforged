<template>
  <div>
    <div class="page-header"><h2>系统设置</h2><p>管理客户端 DNS 下发策略</p></div>

    <!-- Headscale 状态卡片 -->
    <div class="glass-card content-card" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px">
          <el-tag :type="form.headscale_running ? 'success' : 'danger'" size="large" effect="dark">
            {{ form.headscale_running ? 'Headscale 运行中' : 'Headscale 已停止' }}
          </el-tag>
          <el-text v-if="form.headscale_version" type="info" size="small">{{ versionShort }}</el-text>
          <el-text v-if="form.server_url" type="info" size="small">{{ form.server_url }}</el-text>
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

      <el-form :model="form" label-width="130px" label-position="right" style="max-width:760px" :disabled="!editMode">
        <div ref="dnsSectionRef" class="settings-anchor"></div>
        <el-divider content-position="left">DNS 下发</el-divider>
        <el-form-item label="MagicDNS">
          <el-switch v-model="form.dns_magic_dns" active-text="开启" inactive-text="关闭" />
          <div class="form-tip">开启后客户端可解析节点名称和服务端下发的 DNS 记录</div>
        </el-form-item>
        <el-form-item label="基础域名">
          <el-input v-model="form.dns_base_domain" readonly />
          <div class="form-tip">由 Headscale 启动配置确定，避免运行中更名导致节点域名不一致</div>
        </el-form-item>
        <el-form-item label="覆盖本地 DNS">
          <el-switch v-model="form.dns_override_local" active-text="使用下发 DNS" inactive-text="仅作备用" />
          <div class="form-tip">开启后，勾选“采用服务端 DNS”的客户端会优先使用下方 DNS 地址</div>
        </el-form-item>
        <el-form-item label="DNS 地址">
          <el-input
            v-model="dnsGlobalNameserversText"
            type="textarea"
            :rows="4"
            placeholder="1.1.1.1&#10;8.8.8.8"
          />
          <div class="form-tip">每行一个 IP 或 HTTPS DoH 地址，保存后立即热下发</div>
        </el-form-item>
        <el-form-item label="搜索域">
          <el-input
            v-model="dnsSearchDomainsText"
            type="textarea"
            :rows="3"
            placeholder="corp.example.com"
          />
          <div class="form-tip">可选，每行一个搜索域；留空则只使用基础域名</div>
        </el-form-item>
        <el-form-item v-if="editMode">
          <el-button type="primary" :loading="saving" @click="handleSave" size="large">
            <el-icon style="margin-right:4px"><Check /></el-icon>保存设置
          </el-button>
          <el-button @click="handleLock" size="large">取消</el-button>
        </el-form-item>
      </el-form>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getSettings, updateSettings } from '@/api'
import { ElMessage } from 'element-plus'
import { Lock, Unlock, Check } from '@element-plus/icons-vue'

const userStore = useUserStore()
const route = useRoute()
const saving = ref(false)
const editMode = ref(false)
const dnsSectionRef = ref(null)
const dnsGlobalNameserversText = ref('')
const dnsSearchDomainsText = ref('')
let formBackup = null

const form = ref({
  server_url: '',
  headscale_running: false, headscale_version: '',
  dns_magic_dns: true,
  dns_base_domain: 'hs.admin.pro',
  dns_override_local: true,
  dns_global_nameservers: [],
  dns_search_domains: [],
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
    dnsGlobalNameserversText.value = (d.dns_global_nameservers || []).join('\n')
    dnsSearchDomainsText.value = (d.dns_search_domains || []).join('\n')
  } catch {}
}

function handleUnlock() {
  formBackup = {
    form: JSON.parse(JSON.stringify(form.value)),
    dnsGlobalNameserversText: dnsGlobalNameserversText.value,
    dnsSearchDomainsText: dnsSearchDomainsText.value,
  }
  editMode.value = true
}

function handleLock() {
  if (formBackup) {
    form.value = JSON.parse(JSON.stringify(formBackup.form))
    dnsGlobalNameserversText.value = formBackup.dnsGlobalNameserversText
    dnsSearchDomainsText.value = formBackup.dnsSearchDomainsText
  }
  editMode.value = false
  formBackup = null
}

function parseLines(value) {
  return [...new Set(String(value || '')
    .split(/[\n,，;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean))]
}

async function handleSave() {
  saving.value = true
  try {
    await updateSettings({
      dns_magic_dns: form.value.dns_magic_dns,
      dns_override_local: form.value.dns_override_local,
      dns_global_nameservers: parseLines(dnsGlobalNameserversText.value),
      dns_search_domains: parseLines(dnsSearchDomainsText.value),
    })
    ElMessage.success('设置已保存，DNS 配置已热下发')
    editMode.value = false
    formBackup = null
    await loadSettings()
    await userStore.fetchSystemStatus()
  } catch {}
  saving.value = false
}

function scrollToRouteSection() {
  if (route.path !== '/settings/dns') return
  nextTick(() => dnsSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

watch(() => route.path, scrollToRouteSection)

onMounted(async () => {
  await loadSettings()
  scrollToRouteSection()
})
</script>

<style scoped>
.settings-anchor { scroll-margin-top: 84px; }
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
