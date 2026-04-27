<template>
  <div>
    <div class="page-header"><h2>个人资料</h2><p>查看和修改您的个人信息</p></div>
    <div class="glass-card content-card" style="max-width:600px">
      <div style="display:flex;align-items:center;gap:20px;margin-bottom:24px">
        <el-avatar :size="64" style="background:var(--v3s-primary);font-size:26px">
          {{ userStore.userInfo?.name?.[0]?.toUpperCase() || 'U' }}
        </el-avatar>
        <div>
          <div style="font-size:18px;font-weight:700">{{ userStore.userInfo?.name }}</div>
          <el-tag :type="userStore.isManager ? 'danger' : 'info'" size="small" style="margin-top:4px">
            {{ userStore.isManager ? '管理员' : '用户' }}
          </el-tag>
        </div>
      </div>
      <el-form :model="form" label-width="80px">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.cellphone" placeholder="输入手机号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { updateProfile } from '@/api'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const saving = ref(false)
const form = reactive({ email: '', cellphone: '' })

onMounted(() => {
  form.email = userStore.userInfo?.email || ''
  form.cellphone = userStore.userInfo?.cellphone || ''
})

async function handleSave() {
  saving.value = true
  try {
    await updateProfile(form)
    ElMessage.success('保存成功')
    await userStore.fetchUserInfo()
  } catch {}
  saving.value = false
}
</script>
