<template>
  <div>
    <div class="page-header"><h2>修改密码</h2><p>更新您的登录密码</p></div>
    <div class="glass-card content-card" style="max-width:480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="form.old_password" type="password" show-password placeholder="输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="form.new_password" type="password" show-password placeholder="输入新密码" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="form.confirm_password" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSubmit">修改密码</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useUserStore } from '@/stores/user'
import { changePassword } from '@/api'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const formRef = ref(null)
const saving = ref(false)
const form = reactive({ old_password: '', new_password: '', confirm_password: '' })

const rules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: (r, v, cb) => v === form.new_password ? cb() : cb(new Error('两次密码不一致')), trigger: 'blur' },
  ],
}

async function handleSubmit() {
  await formRef.value.validate()
  saving.value = true
  try {
    await changePassword({ old_password: form.old_password, new_password: form.new_password })
    ElMessage.success('密码修改成功，请重新登录')
    setTimeout(() => userStore.logout(), 1500)
  } catch {}
  saving.value = false
}
</script>
