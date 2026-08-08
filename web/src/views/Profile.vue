<template>
  <div>
    <div class="page-header"><h2>账户信息</h2><p>账户身份由 Headscale 统一管理</p></div>
    <div class="glass-card content-card" style="max-width:680px">
      <div style="display:flex;align-items:center;gap:20px;margin-bottom:24px">
        <el-avatar :size="64" style="background:var(--v3s-primary);font-size:26px">
          {{ userStore.userInfo?.name?.[0]?.toUpperCase() || 'U' }}
        </el-avatar>
        <div>
          <div style="font-size:18px;font-weight:700">{{ userStore.userInfo?.name }}</div>
          <el-tag :type="userStore.isManager ? 'danger' : 'info'" size="small" style="margin-top:4px">
            {{ userStore.isManager ? '管理员' : '普通账户' }}
          </el-tag>
        </div>
      </div>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="网络分组">
          {{ userStore.userInfo?.networkName || '未绑定' }}
        </el-descriptions-item>
        <el-descriptions-item label="账户到期">
          {{ formatTime(userStore.userInfo?.expiresAt) || '永不过期' }}
        </el-descriptions-item>
        <el-descriptions-item label="密码更新时间">
          {{ formatTime(userStore.userInfo?.passwordChangedAt) || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
</script>
