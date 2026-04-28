<template>
  <div class="login-page">
    <!-- 网络节点动画背景 -->
    <canvas ref="bgCanvas" class="login-bg-canvas"></canvas>

    <div class="login-container">
      <div class="login-card-glass">
        <!-- 左侧品牌区 -->
        <div class="card-left">
          <div class="brand-center">
            <img src="/img/logo.ico" alt="Logo" class="brand-logo" />
            <h1 class="brand-title">Headscale</h1>
            <p class="brand-subtitle">您的自有异地网络组建平台</p>
          </div>
        </div>

        <!-- 右侧表单区 -->
        <div class="card-right">
          <h2 class="form-title">初始化</h2>
          <p class="form-desc">创建首个管理员账户以完成系统初始化</p>

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
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { register, getPublicStatus } from '@/api'
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

// ─── 网络节点动画背景 ───
const bgCanvas = ref(null)
let animId = null

function initNetworkAnimation() {
  const canvas = bgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  let w, h, particles

  function resize() {
    w = canvas.width = window.innerWidth
    h = canvas.height = window.innerHeight
  }

  function createParticles() {
    const count = Math.floor((w * h) / 12000)
    particles = []
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        r: Math.random() * 1.8 + 0.8,
      })
    }
  }

  function draw() {
    ctx.clearRect(0, 0, w, h)
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 130) {
          const alpha = (1 - dist / 130) * 0.2
          ctx.beginPath()
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`
          ctx.lineWidth = 0.6
          ctx.stroke()
        }
      }
    }
    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(129, 140, 248, 0.5)'
      ctx.fill()
    }
    animId = requestAnimationFrame(draw)
  }

  resize()
  createParticles()
  draw()
  window.addEventListener('resize', () => { resize(); createParticles() })
}

onMounted(() => {
  // 检查系统是否已初始化，已初始化则跳转登录
  getPublicStatus().then(res => {
    if (res.data?.initialized) {
      ElMessage.warning('系统已初始化，无法注册新账户')
      router.replace('/login')
    }
  }).catch(() => {})
  initNetworkAnimation()
})

onBeforeUnmount(() => {
  if (animId) cancelAnimationFrame(animId)
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #0a0e1a, #111827, #0f172a);
}
.login-bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
}
.login-container { position: relative; z-index: 1; }
.login-card-glass {
  display: flex; width: 820px; min-height: 480px;
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 24px; overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
}
.card-left {
  flex: 0 0 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.03);
  border-right: 1px solid rgba(255,255,255,0.08);
}
.brand-center { text-align: center; }
.brand-logo {
  width: 72px; height: 72px; border-radius: 18px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(79,70,229,0.3);
}
.brand-title { font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 10px; letter-spacing: 1px; }
.brand-subtitle { font-size: 14px; color: rgba(255,255,255,0.5); line-height: 1.6; }
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
  .card-left {
    flex: 0 0 auto; padding: 32px 24px;
    border-right: none; border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .card-right { padding: 24px; }
}
</style>
