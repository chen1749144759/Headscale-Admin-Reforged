<template>
  <div class="login-page">
    <!-- 背景动画层 -->
    <div class="login-bg">
      <div class="grid-overlay"></div>
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
      <div class="glow glow-3"></div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-container">
      <div class="login-card-glass">
        <!-- 左侧品牌区 -->
        <div class="card-left">
          <div class="brand-content">
            <img src="/img/logo.ico" alt="Logo" class="brand-logo" />
            <h1 class="brand-title">Headscale Admin</h1>
            <p class="brand-subtitle">组网管理平台</p>
            <div class="brand-divider"></div>
            <ul class="brand-features">
              <li><span class="feature-icon">&#xe001;</span>安全组网 — 基于 WireGuard 的零信任网络</li>
              <li><span class="feature-icon">&#xe002;</span>集中管控 — 节点、用户、路由一站式管理</li>
              <li><span class="feature-icon">&#xe003;</span>开箱即用 — 简洁部署，即刻启用</li>
            </ul>
          </div>
          <div class="brand-footer">Powered by Headscale v0.28</div>
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

            <!-- 拼图滑块验证 -->
            <el-form-item>
              <div class="puzzle-verify" ref="puzzleRef">
                <div class="puzzle-canvas-wrap">
                  <canvas ref="bgCanvas" :width="puzzleW" :height="puzzleH"></canvas>
                  <canvas ref="blockCanvas" :width="puzzleW" :height="puzzleH" class="puzzle-block" :style="{ left: blockLeft + 'px' }"></canvas>
                  <div v-if="verified" class="puzzle-success-mask">
                    <el-icon color="#10b981" :size="28"><CircleCheckFilled /></el-icon>
                  </div>
                  <div v-if="showRefresh && !verified" class="puzzle-refresh" @click="initPuzzle">
                    <el-icon :size="16"><Refresh /></el-icon>
                  </div>
                </div>
                <div class="puzzle-slider" :class="{ verified, failed: sliderFailed }">
                  <div class="puzzle-slider-track">
                    <div class="puzzle-slider-fill" :style="{ width: sliderLeft + 'px' }"></div>
                    <div class="puzzle-slider-thumb" :style="{ left: sliderLeft + 'px' }" @mousedown="onSliderDown" @touchstart.prevent="onSliderDown">
                      <el-icon v-if="!verified"><Right /></el-icon>
                      <el-icon v-else color="#10b981"><Check /></el-icon>
                    </div>
                    <span class="puzzle-slider-text" v-if="!sliderLeft && !verified">拖动拼图完成验证</span>
                  </div>
                </div>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" size="large" :loading="loading" :disabled="!verified" @click="handleLogin" style="width:100%">
                {{ loading ? '登录中...' : '登 录' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <span v-if="openReg">还没有账户？<router-link to="/register" class="link-primary">立即注册</router-link></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
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

// ─── 拼图验证相关 ───
const puzzleW = 300
const puzzleH = 160
const pieceSize = 42
const bgCanvas = ref(null)
const blockCanvas = ref(null)
const puzzleRef = ref(null)

const blockLeft = ref(0)
const sliderLeft = ref(0)
const verified = ref(false)
const sliderFailed = ref(false)
const showRefresh = ref(false)
let targetX = 0
let puzzleImg = null

function initPuzzle() {
  verified.value = false
  sliderFailed.value = false
  sliderLeft.value = 0
  blockLeft.value = 0
  showRefresh.value = false

  const bgCtx = bgCanvas.value?.getContext('2d')
  const blkCtx = blockCanvas.value?.getContext('2d')
  if (!bgCtx || !blkCtx) return

  // 随机目标位置
  targetX = Math.floor(Math.random() * (puzzleW - pieceSize * 2 - 20)) + pieceSize + 20
  const targetY = Math.floor(Math.random() * (puzzleH - pieceSize - 20)) + 10

  // 生成随机渐变背景
  const colors = [
    ['#1e3a5f', '#2d5a87', '#1a4570'],
    ['#2d1b4e', '#4a2d7a', '#3b2260'],
    ['#1b3a2f', '#2d6b50', '#1e4a3a'],
    ['#3b1a1a', '#6b3030', '#4a2020'],
  ]
  const colorSet = colors[Math.floor(Math.random() * colors.length)]

  bgCtx.clearRect(0, 0, puzzleW, puzzleH)
  blkCtx.clearRect(0, 0, puzzleW, puzzleH)

  // 画渐变背景
  const grad = bgCtx.createLinearGradient(0, 0, puzzleW, puzzleH)
  grad.addColorStop(0, colorSet[0])
  grad.addColorStop(0.5, colorSet[1])
  grad.addColorStop(1, colorSet[2])
  bgCtx.fillStyle = grad
  bgCtx.fillRect(0, 0, puzzleW, puzzleH)

  // 画一些随机圆形装饰
  for (let i = 0; i < 12; i++) {
    bgCtx.beginPath()
    bgCtx.arc(Math.random() * puzzleW, Math.random() * puzzleH, Math.random() * 30 + 5, 0, Math.PI * 2)
    bgCtx.fillStyle = `rgba(255,255,255,${Math.random() * 0.08 + 0.02})`
    bgCtx.fill()
  }

  // 画拼图形状到背景（挖空）
  drawPuzzlePiece(bgCtx, targetX, targetY, 'fill')
  bgCtx.fillStyle = 'rgba(0,0,0,0.4)'
  bgCtx.fill()
  bgCtx.strokeStyle = 'rgba(255,255,255,0.3)'
  bgCtx.lineWidth = 1.5
  bgCtx.stroke()

  // 画拼图块
  blkCtx.clearRect(0, 0, puzzleW, puzzleH)
  drawPuzzlePiece(blkCtx, targetX, targetY, 'clip')
  // 复制背景对应区域
  const tempCanvas = document.createElement('canvas')
  tempCanvas.width = puzzleW
  tempCanvas.height = puzzleH
  const tempCtx = tempCanvas.getContext('2d')
  const grad2 = tempCtx.createLinearGradient(0, 0, puzzleW, puzzleH)
  grad2.addColorStop(0, colorSet[0])
  grad2.addColorStop(0.5, colorSet[1])
  grad2.addColorStop(1, colorSet[2])
  tempCtx.fillStyle = grad2
  tempCtx.fillRect(0, 0, puzzleW, puzzleH)
  for (let i = 0; i < 12; i++) {
    tempCtx.beginPath()
    tempCtx.arc(Math.random() * puzzleW, Math.random() * puzzleH, Math.random() * 30 + 5, 0, Math.PI * 2)
    tempCtx.fillStyle = `rgba(255,255,255,${Math.random() * 0.08 + 0.02})`
    tempCtx.fill()
  }
  blkCtx.drawImage(bgCanvas.value, 0, 0)
  // 加白色描边
  blkCtx.strokeStyle = 'rgba(255,255,255,0.8)'
  blkCtx.lineWidth = 2
  drawPuzzlePiece(blkCtx, targetX, targetY, 'stroke')
  blkCtx.stroke()
}

function drawPuzzlePiece(ctx, x, y, op) {
  const s = pieceSize
  const r = s * 0.2
  ctx.beginPath()
  ctx.moveTo(x, y)
  // 上凸
  ctx.lineTo(x + s * 0.36, y)
  ctx.arc(x + s * 0.5, y, r, Math.PI, 0, false)
  ctx.lineTo(x + s, y)
  // 右凸
  ctx.lineTo(x + s, y + s * 0.36)
  ctx.arc(x + s, y + s * 0.5, r, -Math.PI / 2, Math.PI / 2, false)
  ctx.lineTo(x + s, y + s)
  // 下
  ctx.lineTo(x, y + s)
  // 左凹
  ctx.lineTo(x, y + s * 0.64)
  ctx.arc(x, y + s * 0.5, r, Math.PI / 2, -Math.PI / 2, true)
  ctx.lineTo(x, y)
  ctx.closePath()

  if (op === 'clip') ctx.clip()
  else if (op === 'fill') { /* caller will fill */ }
  else if (op === 'stroke') { /* caller will stroke */ }
}

function onSliderDown(e) {
  if (verified.value) return
  sliderFailed.value = false
  const startX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX
  const startLeft = sliderLeft.value
  const maxLeft = puzzleW - 40

  function onMove(ev) {
    const curX = ev.type === 'touchmove' ? ev.touches[0].clientX : ev.clientX
    let dx = curX - startX + startLeft
    dx = Math.max(0, Math.min(dx, maxLeft))
    sliderLeft.value = dx
    blockLeft.value = dx
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.removeEventListener('touchmove', onMove)
    document.removeEventListener('touchend', onUp)

    const tolerance = 5
    if (Math.abs(sliderLeft.value - targetX) < tolerance) {
      verified.value = true
      blockLeft.value = targetX
      sliderLeft.value = targetX
    } else {
      sliderFailed.value = true
      sliderLeft.value = 0
      blockLeft.value = 0
      showRefresh.value = true
      setTimeout(() => { sliderFailed.value = false }, 400)
      setTimeout(initPuzzle, 600)
    }
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.addEventListener('touchmove', onMove)
  document.addEventListener('touchend', onUp)
}

// ─── 登录逻辑 ───
async function handleLogin() {
  if (!verified.value) return ElMessage.warning('请先完成拼图验证')
  await formRef.value.validate()
  loading.value = true
  try {
    const res = await login(form)
    userStore.setToken(res.data.token)
    userStore.userInfo = res.data.user
    ElMessage.success('登录成功')
    const target = res.data.user.role === 'manager' ? '/console' : '/nodes'
    router.push(target)
  } catch {
    verified.value = false
    initPuzzle()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getPublicStatus()
    openReg.value = res.data?.open_user_reg === 'on'
    userStore.systemStatus = res.data || userStore.systemStatus
  } catch {}
  nextTick(initPuzzle)
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
  background: linear-gradient(135deg, var(--v3s-login-bg-from), var(--v3s-login-bg-to));
}

/* ─── 背景层 ─── */
.login-bg { position: absolute; inset: 0; z-index: 0; }
.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  animation: glowFloat 8s ease-in-out infinite;
}
.glow-1 { width: 400px; height: 400px; background: rgba(79,70,229,.3); top: -10%; left: -5%; animation-delay: 0s; }
.glow-2 { width: 300px; height: 300px; background: rgba(6,182,212,.2); bottom: -5%; right: -5%; animation-delay: 3s; }
.glow-3 { width: 200px; height: 200px; background: rgba(168,85,247,.15); top: 50%; left: 60%; animation-delay: 5s; }

@keyframes glowFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -30px) scale(1.05); }
  66% { transform: translate(-15px, 20px) scale(0.95); }
}

/* ─── 卡片容器 ─── */
.login-container { position: relative; z-index: 1; }
.login-card-glass {
  display: flex;
  width: 820px;
  min-height: 520px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1);
}

/* ─── 左侧品牌 ─── */
.card-left {
  flex: 0 0 320px;
  padding: 40px 32px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: rgba(255,255,255,0.03);
  border-right: 1px solid rgba(255,255,255,0.08);
}
.brand-content { flex: 1; }
.brand-logo { width: 56px; height: 56px; border-radius: 14px; margin-bottom: 20px; }
.brand-title { font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.brand-subtitle { font-size: 13px; color: rgba(255,255,255,0.5); }
.brand-divider { width: 40px; height: 3px; background: var(--v3s-primary); border-radius: 2px; margin: 24px 0; }
.brand-features { list-style: none; padding: 0; }
.brand-features li {
  font-size: 13px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 14px;
  line-height: 1.5;
  padding-left: 8px;
}
.feature-icon { display: none; }
.brand-footer { font-size: 11px; color: rgba(255,255,255,0.25); }

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

/* ─── 拼图验证 ─── */
.puzzle-verify { width: 100%; }
.puzzle-canvas-wrap {
  position: relative;
  width: 300px;
  height: 160px;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 10px;
}
.puzzle-canvas-wrap canvas { display: block; border-radius: 10px; }
.puzzle-block {
  position: absolute;
  top: 0;
  left: 0;
  transition: none;
}
.puzzle-success-mask {
  position: absolute;
  inset: 0;
  background: rgba(16,185,129,0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}
.puzzle-refresh {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  background: rgba(0,0,0,0.45);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #fff;
  transition: background 0.2s;
}
.puzzle-refresh:hover { background: rgba(0,0,0,0.65); }

.puzzle-slider { margin-top: 2px; }
.puzzle-slider-track {
  position: relative;
  height: 38px;
  background: rgba(255,255,255,0.06);
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  overflow: hidden;
}
.puzzle-slider-fill {
  position: absolute; top: 0; left: 0; height: 100%;
  background: linear-gradient(90deg, rgba(79,70,229,.25), rgba(79,70,229,.4));
  border-radius: 8px 0 0 8px;
  transition: width 0.02s;
}
.puzzle-slider.verified .puzzle-slider-fill {
  background: linear-gradient(90deg, rgba(16,185,129,.2), rgba(16,185,129,.35));
}
.puzzle-slider.failed .puzzle-slider-track {
  animation: shake 0.3s;
  border-color: rgba(239,68,68,0.5);
}
.puzzle-slider-thumb {
  position: absolute;
  top: 2px;
  width: 34px;
  height: 34px;
  background: rgba(255,255,255,0.15);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 7px;
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255,255,255,0.8);
  z-index: 2;
  user-select: none;
  transition: background 0.15s;
}
.puzzle-slider-thumb:hover { background: rgba(255,255,255,0.25); }
.puzzle-slider-thumb:active { cursor: grabbing; }
.puzzle-slider.verified .puzzle-slider-thumb {
  background: rgba(16,185,129,0.2);
  border-color: rgba(16,185,129,0.4);
}
.puzzle-slider-text {
  position: absolute;
  width: 100%;
  text-align: center;
  line-height: 38px;
  font-size: 12px;
  color: rgba(255,255,255,0.3);
  user-select: none;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-6px); }
  75% { transform: translateX(6px); }
}

/* ─── 响应式 ─── */
@media (max-width: 860px) {
  .login-card-glass { width: 95vw; flex-direction: column; }
  .card-left { flex: 0 0 auto; padding: 24px; border-right: none; border-bottom: 1px solid rgba(255,255,255,0.08); }
  .brand-features { display: none; }
  .card-right { padding: 24px; }
}
</style>
