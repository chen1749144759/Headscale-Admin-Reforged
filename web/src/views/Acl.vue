<template>
  <div>
    <div class="page-header"><h2>ACL 规则</h2><p>管理 Headscale 访问控制策略 (HuJSON)</p></div>
    <div class="glass-card content-card acl-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-text type="info" size="small">
            Headscale 将整个 ACL 策略存储为单个 JSON 文档，支持 HuJSON 格式（可写注释和尾部逗号）
          </el-text>
        </div>
        <div class="toolbar-right">
          <el-button @click="handleFormat" plain size="small">格式化</el-button>
          <el-button @click="loadAcl" :icon="Refresh">刷新</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存 ACL</el-button>
        </div>
      </div>

      <div class="acl-editor-container">
        <div class="acl-line-numbers" ref="lineNumRef">
          <div v-for="n in lineCount" :key="n" class="line-num">{{ n }}</div>
        </div>
        <textarea
          ref="editorRef"
          v-model="aclContent"
          class="acl-editor"
          placeholder="// 在此输入 HuJSON 格式的 ACL 规则&#10;{&#10;  &quot;acls&quot;: [&#10;    { &quot;action&quot;: &quot;accept&quot;, &quot;src&quot;: [&quot;*&quot;], &quot;dst&quot;: [&quot;*:*&quot;] }&#10;  ]&#10;}"
          spellcheck="false"
          @scroll="syncScroll"
          @input="updateLineCount"
          @keydown.tab.prevent="insertTab"
        ></textarea>
      </div>

      <div class="acl-footer">
        <el-text type="info" size="small">提示：保存后若 headscale 使用 database 模式会自动生效；若使用 file 模式则需要点击"重载"。</el-text>
        <el-button type="warning" size="small" @click="handleReload">重载 Headscale</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { getAcl, updateAcl, reloadHeadscale } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const aclContent = ref('')
const saving = ref(false)
const editorRef = ref(null)
const lineNumRef = ref(null)

const lineCount = computed(() => {
  const count = (aclContent.value || '').split('\n').length
  return Math.max(count, 20)
})

function syncScroll() {
  if (lineNumRef.value && editorRef.value) {
    lineNumRef.value.scrollTop = editorRef.value.scrollTop
  }
}

function updateLineCount() {
  nextTick(syncScroll)
}

function insertTab(e) {
  const el = e.target
  const start = el.selectionStart
  const end = el.selectionEnd
  aclContent.value = aclContent.value.substring(0, start) + '  ' + aclContent.value.substring(end)
  nextTick(() => { el.selectionStart = el.selectionEnd = start + 2 })
}

function handleFormat() {
  const raw = aclContent.value.trim()
  if (!raw) return
  try {
    // 移除 HuJSON 注释和尾部逗号后尝试解析
    const cleaned = raw
      .replace(/\/\/.*$/gm, '')  // 移除单行注释
      .replace(/\/\*[\s\S]*?\*\//g, '')  // 移除多行注释
      .replace(/,\s*([}\]])/g, '$1')  // 移除尾部逗号
    const obj = JSON.parse(cleaned)
    aclContent.value = JSON.stringify(obj, null, 2)
    ElMessage.success('格式化成功')
  } catch (e) {
    ElMessage.warning('JSON 解析失败，请检查语法：' + e.message)
  }
}

async function loadAcl() {
  try {
    const res = await getAcl()
    aclContent.value = res.data || ''
  } catch {}
}

async function handleSave() {
  if (!aclContent.value.trim()) return ElMessage.warning('ACL 内容不能为空')
  saving.value = true
  try {
    await updateAcl({ acl: aclContent.value })
    ElMessage.success('ACL 已保存')
  } catch {}
  saving.value = false
}

async function handleReload() {
  try {
    await ElMessageBox.confirm('确认重载 Headscale 服务？重载后新 ACL 规则立即生效。', '重载确认', { type: 'warning' })
    await reloadHeadscale()
    ElMessage.success('Headscale 重载成功')
  } catch {}
}

onMounted(loadAcl)
</script>

<style scoped>
.acl-card {
  display: flex;
  flex-direction: column;
}

.acl-editor-container {
  display: flex;
  border: 1px solid #313244;
  border-radius: 10px;
  overflow: hidden;
  background: #1e1e2e;
  margin-bottom: 12px;
}

.acl-line-numbers {
  flex-shrink: 0;
  width: 48px;
  padding: 16px 0;
  background: #181825;
  border-right: 1px solid #313244;
  overflow: hidden;
  user-select: none;
}
.line-num {
  height: 21.45px; /* match line-height: 1.65 * 13px */
  line-height: 21.45px;
  text-align: right;
  padding-right: 10px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #585b70;
}

.acl-editor {
  flex: 1;
  min-height: 560px;
  max-height: calc(100vh - 300px);
  background: transparent;
  color: #cdd6f4;
  border: none;
  padding: 16px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.65;
  resize: vertical;
  outline: none;
  tab-size: 2;
  overflow-y: auto;
}
.acl-editor::placeholder {
  color: #585b70;
}
.acl-editor:focus {
  box-shadow: inset 0 0 0 1px rgba(79,70,229,0.3);
}

.acl-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}
</style>
