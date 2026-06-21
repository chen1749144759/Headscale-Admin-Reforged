<template>
  <div class="login-page">
    <!-- 网络节点动画背景 -->
    <canvas ref="bgCanvas" class="login-bg-canvas"></canvas>

    <!-- 登录卡片 -->
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
          <h2 class="form-title">登录</h2>
          <p class="form-desc">欢迎回来，请输入您的账户信息</p>

          <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin" class="login-form">
            <el-form-item prop="username">
              <el-input v-model="form.username" placeholder="用户名" size="large" prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="form.password" placeholder="密码" type="password" show-password size="large" prefix-icon="Lock" @keyup.enter="handleLogin" />
            </el-form-item>

            <!-- Cap 挑战验证码 -->
            <el-form-item>
              <div class="cap-verify-wrap">
                <cap-widget
                  v-if="captchaEnabled && captchaReady && captchaConfig.apiEndpoint"
                  :key="captchaKey"
                  ref="capWidgetRef"
                  :data-cap-api-endpoint="captchaConfig.apiEndpoint"
                  data-cap-lang="zh-CN"
                  @solve="onCaptchaSolve"
                  @error="onCaptchaError"
                />
                <div v-else-if="captchaEnabled" class="captcha-placeholder">
                  {{ captchaError || '验证码加载中...' }}
                </div>
                <div v-else class="captcha-placeholder captcha-disabled">
                  验证码已关闭
                </div>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" size="large" :loading="loading" :disabled="captchaEnabled && !verified" @click="handleLogin" style="width:100%">
                {{ loading ? '登录中...' : '登 录' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <span v-if="openReg">首次使用？<router-link to="/register" class="link-primary">初始化系统</router-link></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { login, getPublicStatus } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const loading = ref(false)
const openReg = ref(false)

// ─── 挑战验证码 ───
const capWidgetRef = ref(null)
const verified = ref(false)
const captchaToken = ref('')
const captchaReady = ref(false)
const captchaKey = ref(0)
const captchaError = ref('')
const captchaEnabled = ref(true)
const captchaConfig = reactive({
  apiEndpoint: 'http://10.2.1.100:30030/62f60ca190/',
  widgetSrc: 'https://cdn.jsdelivr.net/npm/cap-widget',
})

function onCaptchaSolve(event) {
  captchaToken.value = event.detail?.token || ''
  verified.value = Boolean(captchaToken.value)
}
function onCaptchaError() {
  resetCaptcha()
}
function resetCaptcha() {
  captchaToken.value = ''
  verified.value = false
  captchaKey.value += 1
}

function loadCaptchaScript(src) {
  return new Promise((resolve, reject) => {
    if (!src) return reject(new Error('empty captcha widget src'))
    if (window.customElements?.get('cap-widget')) return resolve()

    const waitForDefinition = () => {
      if (!window.customElements?.whenDefined) return resolve()

      const timer = window.setTimeout(() => {
        reject(new Error('captcha widget registration timeout'))
      }, 8000)

      window.customElements.whenDefined('cap-widget')
        .then(() => {
          window.clearTimeout(timer)
          resolve()
        })
        .catch((error) => {
          window.clearTimeout(timer)
          reject(error)
        })
    }

    const existing = document.querySelector('script[data-cap-widget]')
    if (existing) {
      if (existing.dataset.loaded === 'true') {
        waitForDefinition()
        return
      }

      existing.addEventListener('load', waitForDefinition, { once: true })
      existing.addEventListener('error', reject, { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = src
    script.type = 'module'
    script.async = true
    script.dataset.capWidget = 'true'
    script.onload = () => {
      script.dataset.loaded = 'true'
      waitForDefinition()
    }
    script.onerror = reject
    document.head.appendChild(script)
  })
}

// ─── 登录逻辑 ───
async function handleLogin() {
  if (captchaEnabled.value && !verified.value) return ElMessage.warning('请先完成验证码')
  await formRef.value.validate()
  loading.value = true
  try {
    const res = await login({ ...form, captchaToken: captchaToken.value })
    userStore.setToken(res.data.token)
    userStore.userInfo = res.data.user
    ElMessage.success('登录成功')
    const target = res.data.user.role === 'manager' ? '/console' : '/users'
    router.push(target)
  } catch {
    resetCaptcha()
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

    // 连线
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

    // 粒子
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

  window.addEventListener('resize', () => {
    resize()
    createParticles()
  })
}

onMounted(async () => {
  try {
    const res = await getPublicStatus()
    const data = res.data || {}
    openReg.value = data.initialized === false
    userStore.systemStatus = data || userStore.systemStatus

    const captcha = data.captcha || {}
    captchaEnabled.value = captcha.enabled !== false
    captchaConfig.apiEndpoint = captcha.api_endpoint || captchaConfig.apiEndpoint
    captchaConfig.widgetSrc = captcha.widget_src || captchaConfig.widgetSrc
  } catch {
    captchaError.value = '验证码配置加载失败，请检查 /api/public/status 是否可访问'
  }

  if (captchaEnabled.value) {
    try {
      await loadCaptchaScript(captchaConfig.widgetSrc)
      captchaReady.value = true
    } catch {
      captchaError.value = '验证码加载失败，请刷新页面重试'
    }
  } else {
    verified.value = true
  }

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

/* ─── 网络节点动画背景 ─── */
.login-bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
}

/* ─── 卡片容器 ─── */
.login-container { position: relative; z-index: 1; }
.login-card-glass {
  display: flex;
  width: 820px;
  min-height: 520px;
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
}

/* ─── 左侧品牌：居中布局 ─── */
.card-left {
  flex: 0 0 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.03);
  border-right: 1px solid rgba(255,255,255,0.08);
}
.brand-center {
  text-align: center;
}
.brand-logo {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(79,70,229,0.3);
}
.brand-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 10px;
  letter-spacing: 1px;
}
.brand-subtitle {
  font-size: 14px;
  color: rgba(255,255,255,0.5);
  line-height: 1.6;
}

/* ─── 右侧表单 ─── */
.card-right {
  flex: 1;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.form-title { font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.form-desc { font-size: 13px; color: rgba(255,255,255,0.45); margin-bottom: 28px; }
.login-form :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: none;
  color: #fff;
}
.login-form :deep(.el-input__wrapper:hover),
.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--v3s-primary);
  box-shadow: 0 0 0 2px rgba(79,70,229,0.15);
}
.login-form :deep(.el-input__inner) { color: #fff; }
.login-form :deep(.el-input__inner::placeholder) { color: rgba(255,255,255,0.35); }
.login-form :deep(.el-input__prefix .el-icon) { color: rgba(255,255,255,0.4); }
.login-form :deep(.el-button--primary) {
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px;
}
.form-footer {
  text-align: center;
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin-top: 4px;
}
.link-primary { color: var(--v3s-primary-light); font-weight: 500; }
.link-primary:hover { color: #fff; }

/* ─── 挑战验证码适配深色主题 ─── */
.cap-verify-wrap {
  width: 100%;
}
.cap-verify-wrap cap-widget {
  width: 100%;
  --cap-widget-width: 100%;
  --cap-widget-height: 46px;
  --cap-background: rgba(255,255,255,0.06);
  --cap-border-color: rgba(255,255,255,0.1);
  --cap-border-radius: 10px;
  --cap-color: rgba(255,255,255,0.88);
  --cap-checkbox-background: rgba(255,255,255,0.08);
  --cap-checkbox-border: 1px solid rgba(255,255,255,0.24);
  --cap-spinner-color: #818cf8;
  --cap-spinner-background-color: rgba(255,255,255,0.16);
}
.captcha-placeholder {
  min-height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.48);
  font-size: 13px;
}
.captcha-disabled {
  color: rgba(255,255,255,0.35);
}

/* ─── 响应式 ─── */
@media (max-width: 860px) {
  .login-card-glass { width: 95vw; flex-direction: column; }
  .card-left {
    flex: 0 0 auto;
    padding: 32px 24px;
    border-right: none;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .card-right { padding: 24px; }
}
</style>
