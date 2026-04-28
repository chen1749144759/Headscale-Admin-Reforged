<template>
  <div>
    <div class="page-header"><h2>ACL 规则</h2><p>管理 Headscale 访问控制策略 (HuJSON)</p></div>
    <div class="glass-card content-card acl-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-radio-group v-model="activeTab" size="small">
            <el-radio-button value="visual">可视化编辑</el-radio-button>
            <el-radio-button value="raw">源码编辑</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-right">
          <el-button v-if="activeTab === 'raw'" @click="handleFormat" plain size="small">格式化</el-button>
          <el-button @click="loadAcl" :icon="Refresh">刷新</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存 ACL</el-button>
        </div>
      </div>

      <!-- 可视化编辑模式 -->
      <div v-show="activeTab === 'visual'" class="visual-editor">
        <!-- 总览说明 -->
        <details class="tip-collapse">
          <summary class="tip-summary">ACL 概念说明（点击展开）</summary>
          <div class="tip-body">
            <p><b>ACL 规则页面</b>由三部分组成：<b>访问规则</b>、<b>分组定义</b>、<b>标签拥有者</b>。它们共同构成 Headscale 的访问控制策略。</p>
            <p><b>访问规则 (acls)</b>：定义「谁」可以访问「谁」的「哪些端口」。来源和目标可以是分组名、分组定义名（group:xxx）、标签（tag:xxx）、IP 地址等。</p>
            <p><b>分组定义 (groups)</b> 与 <b>分组管理页面</b> 的区别：分组管理页面管理的是 Headscale 的 <em>用户命名空间</em>（机器归属），而此处的分组定义是 ACL 策略层面的逻辑聚合 — 可以将多个用户命名空间归到一个 group:xxx 下，在访问规则中统一引用。例如 <code>group:devs = ["dev1", "dev2"]</code>，之后规则中写 <code>group:devs</code> 即代表 dev1 和 dev2 下的所有机器。你可以在「分组管理」页面快速管理分组定义。</p>
            <p><b>标签拥有者 (tagOwners)</b>：定义哪些分组可以为自己的机器打上特定标签。例如 <code>tag:server</code> 的拥有者设为 <code>group:ops</code>，那么 ops 组内的机器可以打 <code>tag:server</code> 标签。打了标签的机器可以在访问规则中作为来源或目标使用。你可以在「节点管理」页面直接为机器设置标签。</p>
          </div>
        </details>

        <!-- ACL 规则列表 -->
        <div class="visual-section">
          <div class="visual-section-header">
            <span class="visual-section-title">访问规则 (acls)</span>
            <el-button type="primary" size="small" @click="addAclRule">添加规则</el-button>
          </div>
          <el-table :data="visualAcls" size="small" border empty-text="暂无规则">
            <el-table-column label="动作" width="100">
              <template #default="{ row }">
                <el-tag :type="row.action === 'accept' ? 'success' : 'danger'" size="small">{{ row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="来源 (src)" min-width="200">
              <template #default="{ row, $index }">
                <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
                  <el-tag v-for="(s, si) in row.src" :key="si" size="small" closable
                    @close="removeAclItem($index, 'src', si)">{{ s }}</el-tag>
                  <el-button size="small" link @click="addAclItem($index, 'src')">+</el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="目标 (dst)" min-width="200">
              <template #default="{ row, $index }">
                <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
                  <el-tag v-for="(d, di) in row.dst" :key="di" size="small" type="warning" closable
                    @close="removeAclItem($index, 'dst', di)">{{ d }}</el-tag>
                  <el-button size="small" link @click="addAclItem($index, 'dst')">+</el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="visualAcls.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Groups -->
        <div class="visual-section">
          <div class="visual-section-header">
            <span class="visual-section-title">分组定义 (groups)</span>
            <el-button type="primary" size="small" @click="addGroup">添加分组</el-button>
          </div>
          <el-table :data="visualGroups" size="small" border empty-text="暂无分组">
            <el-table-column label="分组名称" width="180">
              <template #default="{ row }">
                <code style="font-size:13px">{{ row.name }}</code>
              </template>
            </el-table-column>
            <el-table-column label="成员" min-width="300">
              <template #default="{ row, $index }">
                <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
                  <el-tag v-for="(m, mi) in row.members" :key="mi" size="small" closable
                    @close="row.members.splice(mi, 1)">{{ m }}</el-tag>
                  <el-button size="small" link @click="addGroupMember($index)">+</el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="visualGroups.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- TagOwners -->
        <div class="visual-section">
          <div class="visual-section-header">
            <span class="visual-section-title">标签拥有者 (tagOwners)</span>
            <el-button type="primary" size="small" @click="addTagOwner">添加标签</el-button>
          </div>
          <el-table :data="visualTagOwners" size="small" border empty-text="暂无标签">
            <el-table-column label="标签名称" width="180">
              <template #default="{ row }">
                <code style="font-size:13px">{{ row.tag }}</code>
              </template>
            </el-table-column>
            <el-table-column label="拥有者" min-width="300">
              <template #default="{ row, $index }">
                <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
                  <el-tag v-for="(o, oi) in row.owners" :key="oi" size="small" closable
                    @close="row.owners.splice(oi, 1)">{{ o }}</el-tag>
                  <el-button size="small" link @click="addTagOwnerMember($index)">+</el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="visualTagOwners.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 源码编辑模式 -->
      <div v-show="activeTab === 'raw'">
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
      </div>

      <div class="acl-footer">
        <el-text type="info" size="small">提示：保存后若 headscale 使用 database 模式会自动生效；若使用 file 模式则需要点击"重载"。</el-text>
        <el-button type="warning" size="small" @click="handleReload">重载 Headscale</el-button>
      </div>
    </div>

    <!-- 通用输入弹窗 -->
    <el-dialog v-model="inputVisible" :title="inputTitle" width="400px">
      <el-input v-model="inputValue" :placeholder="inputPlaceholder" @keyup.enter="inputConfirm" />
      <template #footer>
        <el-button @click="inputVisible = false">取消</el-button>
        <el-button type="primary" @click="inputConfirm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { getAcl, updateAcl, reloadHeadscale } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const activeTab = ref('visual')
const aclContent = ref('')
const saving = ref(false)
const editorRef = ref(null)
const lineNumRef = ref(null)

// ─── 可视化数据 ───
const visualAcls = ref([])
const visualGroups = ref([])
const visualTagOwners = ref([])

// ─── 通用输入弹窗 ───
const inputVisible = ref(false)
const inputTitle = ref('')
const inputPlaceholder = ref('')
const inputValue = ref('')
let inputCallback = null

function showInput(title, placeholder, callback) {
  inputTitle.value = title
  inputPlaceholder.value = placeholder
  inputValue.value = ''
  inputCallback = callback
  inputVisible.value = true
}

function inputConfirm() {
  const val = inputValue.value.trim()
  if (!val) return ElMessage.warning('请输入内容')
  if (inputCallback) inputCallback(val)
  inputVisible.value = false
}

// ─── 源码编辑器 ───
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
    const cleaned = raw
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)
    aclContent.value = JSON.stringify(obj, null, 2)
    ElMessage.success('格式化成功')
  } catch (e) {
    ElMessage.warning('JSON 解析失败，请检查语法：' + e.message)
  }
}

// ─── 解析 ACL 到可视化数据 ───
function parseAclToVisual(raw) {
  try {
    const cleaned = raw
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/,\s*([}\]])/g, '$1')
    const obj = JSON.parse(cleaned)

    // acls
    visualAcls.value = (obj.acls || []).map(r => ({
      action: r.action || 'accept',
      src: Array.isArray(r.src) ? [...r.src] : [],
      dst: Array.isArray(r.dst) ? [...r.dst] : [],
    }))

    // groups
    const groups = []
    if (obj.groups) {
      for (const [name, members] of Object.entries(obj.groups)) {
        groups.push({ name, members: Array.isArray(members) ? [...members] : [] })
      }
    }
    visualGroups.value = groups

    // tagOwners
    const tags = []
    if (obj.tagOwners) {
      for (const [tag, owners] of Object.entries(obj.tagOwners)) {
        tags.push({ tag, owners: Array.isArray(owners) ? [...owners] : [] })
      }
    }
    visualTagOwners.value = tags
  } catch {
    visualAcls.value = []
    visualGroups.value = []
    visualTagOwners.value = []
  }
}

// ─── 可视化数据转回 ACL JSON ───
function visualToAclJson() {
  // 先解析现有 raw 保留其他字段
  let existing = {}
  try {
    const cleaned = aclContent.value
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/,\s*([}\]])/g, '$1')
    existing = JSON.parse(cleaned)
  } catch {}

  // 覆盖可视化管理的字段
  existing.acls = visualAcls.value.map(r => ({
    action: r.action,
    src: r.src,
    dst: r.dst,
  }))

  if (visualGroups.value.length > 0) {
    existing.groups = {}
    for (const g of visualGroups.value) {
      existing.groups[g.name] = g.members
    }
  }

  if (visualTagOwners.value.length > 0) {
    existing.tagOwners = {}
    for (const t of visualTagOwners.value) {
      existing.tagOwners[t.tag] = t.owners
    }
  }

  return JSON.stringify(existing, null, 2)
}

// ─── ACL 规则操作 ───
function addAclRule() {
  visualAcls.value.push({ action: 'accept', src: ['*'], dst: ['*:*'] })
}

function removeAclItem(ruleIdx, field, itemIdx) {
  visualAcls.value[ruleIdx][field].splice(itemIdx, 1)
}

function addAclItem(ruleIdx, field) {
  const label = field === 'src' ? '来源' : '目标'
  const placeholder = field === 'src' ? '分组名、group:xxx、*' : '分组名:port、*:*、10.0.0.0/24:*'
  showInput(`添加${label}`, placeholder, (val) => {
    visualAcls.value[ruleIdx][field].push(val)
  })
}

// ─── Groups 操作 ───
function addGroup() {
  showInput('添加分组', 'group:groupName', (val) => {
    const name = val.startsWith('group:') ? val : `group:${val}`
    if (visualGroups.value.find(g => g.name === name)) {
      return ElMessage.warning('分组已存在')
    }
    visualGroups.value.push({ name, members: [] })
  })
}

function addGroupMember(groupIdx) {
  showInput('添加成员', '分组名', (val) => {
    visualGroups.value[groupIdx].members.push(val)
  })
}

// ─── TagOwners 操作 ───
function addTagOwner() {
  showInput('添加标签', 'tag:tagName', (val) => {
    const tag = val.startsWith('tag:') ? val : `tag:${val}`
    if (visualTagOwners.value.find(t => t.tag === tag)) {
      return ElMessage.warning('标签已存在')
    }
    visualTagOwners.value.push({ tag, owners: [] })
  })
}

function addTagOwnerMember(tagIdx) {
  showInput('添加拥有者', '分组名或 group:xxx', (val) => {
    visualTagOwners.value[tagIdx].owners.push(val)
  })
}

// ─── 切换 tab 时同步数据 ───
watch(activeTab, (newTab, oldTab) => {
  if (oldTab === 'visual' && newTab === 'raw') {
    // 从可视化切到源码 → 将可视化数据写回 aclContent
    aclContent.value = visualToAclJson()
  } else if (oldTab === 'raw' && newTab === 'visual') {
    // 从源码切到可视化 → 解析源码到可视化数据
    parseAclToVisual(aclContent.value)
  }
})

// ─── 加载与保存 ───
async function loadAcl() {
  try {
    const res = await getAcl()
    aclContent.value = res.data || ''
    if (activeTab.value === 'visual') {
      parseAclToVisual(aclContent.value)
    }
  } catch {}
}

async function handleSave() {
  // 如果当前是可视化模式，先将可视化数据转为 JSON
  if (activeTab.value === 'visual') {
    aclContent.value = visualToAclJson()
  }
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

/* 可视化编辑器 */
.visual-editor {
  margin-bottom: 12px;
}
.visual-section {
  margin-bottom: 20px;
}
.visual-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.visual-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--v3s-text-primary);
}

/* 源码编辑器 */
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
  height: 21.45px;
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

/* 可折叠提示样式 */
.tip-collapse {
  margin-bottom: 16px;
  border: 1px solid #f0dca0;
  border-radius: 8px;
  background: #fdf6e3;
  overflow: hidden;
}
.tip-summary {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #92700c;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tip-summary::before {
  content: '▶';
  font-size: 10px;
  transition: transform 0.2s;
  display: inline-block;
}
details[open] > .tip-summary::before {
  transform: rotate(90deg);
}
.tip-summary::-webkit-details-marker {
  display: none;
}
.tip-body {
  padding: 0 16px 12px 16px;
  font-size: 13px;
  color: #5c4a0e;
  line-height: 1.7;
}
.tip-body p {
  margin: 6px 0;
}
.tip-body code {
  background: rgba(0,0,0,0.06);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}
</style>
