<template>
  <div class="login-page">
    <canvas ref="bgCanvas" class="login-bg-canvas"></canvas>

    <main class="login-shell">
      <section class="brand-panel">
        <div class="brand-top">
          <img src="/img/logo.ico" alt="ScaleForge" class="brand-logo" />
          <div>
            <div class="brand-name">ScaleForge</div>
            <div class="brand-tag">Private Network Console</div>
          </div>
        </div>

        <div class="brand-copy">
          <span class="brand-kicker">Zero-trust network operations</span>
          <h1>统一管理 ScaleTail 节点、路由、流量与安全事件。</h1>
          <p>为自有 Headscale 网络提供更清晰的控制台入口，面向日常运维、节点审计和客户端策略管理。</p>
        </div>

        <div class="signal-grid">
          <div class="signal-card">
            <span>节点</span>
            <strong>Identity</strong>
          </div>
          <div class="signal-card">
            <span>路由</span>
            <strong>Subnet</strong>
          </div>
          <div class="signal-card">
            <span>流量</span>
            <strong>Telemetry</strong>
          </div>
          <div class="signal-card">
            <span>安全</span>
            <strong>Audit</strong>
          </div>
        </div>
      </section>

      <section class="form-panel">
        <div class="form-card">
          <div class="form-heading">
            <span class="form-kicker">Secure Login</span>
            <h2>登录控制台</h2>
            <p>输入账户信息并完成验证后进入管理后台。</p>
          </div>

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
            <span v-if="openReg">首次登录？<router-link to="/register" class="link-primary">初始化系统</router-link></span>
            <span v-else>首次登录？请联系管理员创建账户</span>
            <small>ScaleForge 管理端入口</small>
          </div>
        </div>
      </section>
    </main>
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
  position: relative;
  overflow: hidden;
  display: grid;
  place-items: center;
  padding: 32px;
  background:
    linear-gradient(120deg, rgba(30, 64, 175, 0.22), transparent 34%),
    linear-gradient(240deg, rgba(16, 185, 129, 0.18), transparent 38%),
    linear-gradient(135deg, #07111f 0%, #0f172a 48%, #111827 100%);
}

.login-bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  opacity: 0.72;
}

.login-page::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    repeating-linear-gradient(90deg, rgba(148, 163, 184, 0.08) 0 1px, transparent 1px 58px),
    repeating-linear-gradient(0deg, rgba(148, 163, 184, 0.07) 0 1px, transparent 1px 58px);
  mask-image: linear-gradient(to bottom, #000 0%, rgba(0, 0, 0, 0.35) 82%, transparent 100%);
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  min-height: 640px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: stretch;
}

.brand-panel,
.form-card {
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.64);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(24px) saturate(135%);
  -webkit-backdrop-filter: blur(24px) saturate(135%);
}

.brand-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 34px;
  border-radius: 28px;
  overflow: hidden;
}

.brand-panel::after {
  content: "";
  position: absolute;
  left: 34px;
  right: 34px;
  bottom: 0;
  height: 3px;
  background: linear-gradient(90deg, #3b82f6, #10b981, #f59e0b);
}

.brand-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-logo {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  box-shadow: 0 14px 34px rgba(59, 130, 246, 0.34);
}

.brand-name {
  font-size: 18px;
  font-weight: 800;
  color: #fff;
}

.brand-tag {
  margin-top: 2px;
  color: rgba(226, 232, 240, 0.58);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-copy {
  position: relative;
  z-index: 1;
  max-width: 620px;
  padding: 72px 0 54px;
}

.brand-kicker,
.form-kicker {
  color: #93c5fd;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.brand-copy h1 {
  margin: 14px 0 16px;
  color: #f8fafc;
  font-size: 42px;
  line-height: 1.13;
  font-weight: 850;
}

.brand-copy p {
  max-width: 520px;
  color: rgba(226, 232, 240, 0.68);
  font-size: 15px;
  line-height: 1.6;
}

.signal-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.signal-card {
  min-height: 86px;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
}

.signal-card span {
  display: block;
  color: rgba(226, 232, 240, 0.54);
  font-size: 12px;
}

.signal-card strong {
  display: block;
  margin-top: 22px;
  color: #f8fafc;
  font-size: 13px;
  font-family: "Fira Code", Consolas, monospace;
}

.form-panel {
  display: flex;
  align-items: stretch;
}

.form-card {
  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 38px;
  border-radius: 26px;
  background: rgba(248, 250, 252, 0.86);
  color: #0f172a;
}

.form-heading {
  margin-bottom: 28px;
}

.form-kicker {
  color: #2563eb;
}

.form-heading h2 {
  margin: 8px 0 8px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 850;
  line-height: 1.15;
}

.form-heading p {
  color: #64748b;
  font-size: 14px;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 46px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px !important;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.03);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.login-form :deep(.el-input__wrapper:hover),
.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: #3b82f6;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
}

.login-form :deep(.el-input__inner) { color: #0f172a; }
.login-form :deep(.el-input__inner::placeholder) { color: #94a3b8; }
.login-form :deep(.el-input__prefix .el-icon) { color: #64748b; }

.login-form :deep(.el-button--primary) {
  height: 46px;
  font-size: 15px;
  font-weight: 800;
  border-radius: 12px;
  border: 0;
  background: linear-gradient(90deg, #1e40af, #2563eb);
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.22);
}

.login-form :deep(.el-button--primary:hover) {
  background: linear-gradient(90deg, #1d4ed8, #3b82f6);
  box-shadow: 0 18px 36px rgba(37, 99, 235, 0.30);
}

.form-footer {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
  font-size: 13px;
  color: #64748b;
  margin-top: 14px;
}

.form-footer small {
  color: #94a3b8;
  font-size: 12px;
}

.link-primary {
  color: #2563eb;
  font-weight: 800;
}

.link-primary:hover { color: #1e40af; }

.cap-verify-wrap {
  width: 100%;
}

.cap-verify-wrap cap-widget {
  width: 100%;
  --cap-widget-width: 100%;
  --cap-widget-height: 46px;
  --cap-background: rgba(255, 255, 255, 0.72);
  --cap-border-color: rgba(148, 163, 184, 0.28);
  --cap-border-radius: 12px;
  --cap-color: #0f172a;
  --cap-checkbox-background: #ffffff;
  --cap-checkbox-border: 1px solid rgba(100, 116, 139, 0.38);
  --cap-spinner-color: #2563eb;
  --cap-spinner-background-color: rgba(37, 99, 235, 0.16);
}

.captcha-placeholder {
  min-height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  color: #64748b;
  font-size: 13px;
}

.captcha-disabled {
  color: #94a3b8;
}

@media (max-width: 980px) {
  .login-page {
    padding: 20px;
    align-items: start;
  }

  .login-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .form-card {
    min-height: auto;
  }

  .brand-copy {
    padding: 46px 0 36px;
  }

  .brand-copy h1 {
    font-size: 34px;
  }
}

@media (max-width: 620px) {
  .brand-panel,
  .form-card {
    border-radius: 20px;
    padding: 24px;
  }

  .brand-copy h1 {
    font-size: 28px;
  }

  .signal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
