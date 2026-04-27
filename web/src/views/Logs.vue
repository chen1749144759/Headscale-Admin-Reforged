<template>
  <div>
    <div class="page-header"><h2>操作日志</h2><p>记录平台用户的所有操作</p></div>
    <div class="glass-card content-card">
      <el-table :data="logs" v-loading="loading" stripe highlight-current-row>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="user_name" label="用户" width="120" />
        <el-table-column prop="content" label="操作内容" min-width="200" />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>
      <div style="display:flex;justify-content:flex-end;margin-top:16px">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
          layout="total, prev, pager, next" @current-change="loadLogs" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getLogs } from '@/api'

const loading = ref(false)
const logs = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function loadLogs() {
  loading.value = true
  try {
    const res = await getLogs({ page: page.value, size: pageSize })
    logs.value = res.data || []
    total.value = res.total || 0
  } catch {}
  loading.value = false
}

onMounted(loadLogs)
</script>
