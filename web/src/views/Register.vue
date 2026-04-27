<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="grid-overlay"></div>
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
      <div class="glow glow-3"></div>
    </div>

    <div class="login-container">
      <div class="login-card-glass">
        <div class="card-left">
          <div class="brand-content">
            <img src="/img/logo.ico" alt="Logo" class="brand-logo" />
            <h1 class="brand-title">Headscale Admin</h1>
            <p class="brand-subtitle">组网管理平台</p>
            <div class="brand-divider"></div>
            <ul class="brand-features">
              <li>安全组网 — 基于 WireGuard 的零信任网络</li>
              <li>集中管控 — 节点、用户、路由一站式管理</li>
              <li>开箱即用 — 简洁部署，即刻启用</li>
            </ul>
          </div>
          <div class="brand-footer">Powered by Headscale v0.28</div>
        </div>

        <div class="card-right">
          <h2 class="form-title">注册</h2>
          <p class="form-desc">创建您的管理账户</p>

          <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleRegister" class="register-form">
            <el-form-item prop="username">
              <el-input v-model="form.username" placeholder="用户名" size="large" prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="form.password" placeholder="密码" type="password" show-password size="large" prefix-icon="Lock" />
            </el-form-item>
            <el-form-item prop="confirmPassword">
              <el-input v-model="form.confirmPassword" placeholder="确认密码" type="password" show-password size="large" prefix-icon="Lock" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" :loading="loading" @click="handleRegister" style="width:100%">
                {{ loading ? '注册中...' : '注 册' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <span>已有账户？<router-link to="/login" class="link-primary">返回登录</router-link></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { register } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '', confirmPassword: '' })

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度 2-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: (rule, value, cb) => value === form.password ? cb() : cb(new Error('两次密码不一致')), trigger: 'blur' },
  ],
}

async function handleRegister() {
  await formRef.value.validate()
  loading.value = true
  try {
    const res = await register(form)
    if (res.data?.role === 'manager') {
      ElMessage.success('注册成功！首个用户已自动成为管理员')
    } else {
      ElMessage.success('注册成功，请登录')
    }
    router.push('/login')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, var(--v3s-login-bg-from), var(--v3s-login-bg-to));
}
.login-bg { position: absolute; inset: 0; z-index: 0; }
.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.glow { position: absolute; border-radius: 50%; filter: blur(80px); animation: glowFloat 8s ease-in-out infinite; }
.glow-1 { width: 400px; height: 400px; background: rgba(79,70,229,.3); top: -10%; left: -5%; }
.glow-2 { width: 300px; height: 300px; background: rgba(6,182,212,.2); bottom: -5%; right: -5%; animation-delay: 3s; }
.glow-3 { width: 200px; height: 200px; background: rgba(168,85,247,.15); top: 50%; left: 60%; animation-delay: 5s; }
@keyframes glowFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -30px) scale(1.05); }
  66% { transform: translate(-15px, 20px) scale(0.95); }
}
.login-container { position: relative; z-index: 1; }
.login-card-glass {
  display: flex; width: 820px; min-height: 480px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 24px; overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1);
}
.card-left {
  flex: 0 0 320px; padding: 40px 32px;
  display: flex; flex-direction: column; justify-content: space-between;
  background: rgba(255,255,255,0.03);
  border-right: 1px solid rgba(255,255,255,0.08);
}
.brand-content { flex: 1; }
.brand-logo { width: 56px; height: 56px; border-radius: 14px; margin-bottom: 20px; }
.brand-title { font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.brand-subtitle { font-size: 13px; color: rgba(255,255,255,0.5); }
.brand-divider { width: 40px; height: 3px; background: var(--v3s-primary); border-radius: 2px; margin: 24px 0; }
.brand-features { list-style: none; padding: 0; }
.brand-features li { font-size: 13px; color: rgba(255,255,255,0.6); margin-bottom: 14px; line-height: 1.5; padding-left: 8px; }
.brand-footer { font-size: 11px; color: rgba(255,255,255,0.25); }
.card-right { flex: 1; padding: 48px 40px; display: flex; flex-direction: column; justify-content: center; }
.form-title { font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.form-desc { font-size: 13px; color: rgba(255,255,255,0.45); margin-bottom: 28px; }

.register-form :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: none; color: #fff;
}
.register-form :deep(.el-input__wrapper:hover),
.register-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--v3s-primary);
  box-shadow: 0 0 0 2px rgba(79,70,229,0.15);
}
.register-form :deep(.el-input__inner) { color: #fff; }
.register-form :deep(.el-input__inner::placeholder) { color: rgba(255,255,255,0.35); }
.register-form :deep(.el-input__prefix .el-icon) { color: rgba(255,255,255,0.4); }
.register-form :deep(.el-button--primary) { height: 44px; font-size: 15px; font-weight: 600; border-radius: 10px; }

.form-footer { text-align: center; font-size: 13px; color: rgba(255,255,255,0.4); margin-top: 4px; }
.link-primary { color: var(--v3s-primary-light); font-weight: 500; }
.link-primary:hover { color: #fff; }

@media (max-width: 860px) {
  .login-card-glass { width: 95vw; flex-direction: column; }
  .card-left { flex: 0 0 auto; padding: 24px; border-right: none; border-bottom: 1px solid rgba(255,255,255,0.08); }
  .brand-features { display: none; }
  .card-right { padding: 24px; }
}
</style>
