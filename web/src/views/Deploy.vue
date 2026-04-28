<template>
  <div>
    <div class="page-header"><h2>部署帮助</h2><p>在各平台上安装 Tailscale 客户端并连接到本服务器</p></div>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="8" v-for="(p, i) in platforms" :key="i">
        <div class="glass-card content-card platform-card">
          <div class="platform-icon">{{ p.icon }}</div>
          <h3 class="platform-title">{{ p.title }}</h3>
          <p class="platform-desc">{{ p.desc }}</p>
          <div class="code-block" style="margin-top:12px;font-size:12px;position:relative">
            <span>{{ p.cmd }}</span>
            <el-button type="primary" link size="small" class="copy-btn" @click="copy(p.cmd)">复制</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="glass-card content-card" style="margin-top:16px">
      <h3 style="font-size:16px;font-weight:600;margin-bottom:12px">连接命令</h3>
      <p style="color:var(--v3s-text-secondary);margin-bottom:12px">安装 Tailscale 客户端后，使用以下命令连接到本 Headscale 服务器：</p>
      <div class="code-block" style="position:relative">
        <span>tailscale up --login-server {{ serverUrl }} --authkey YOUR_AUTH_KEY</span>
        <el-button type="primary" link size="small" class="copy-btn"
          @click="copy(`tailscale up --login-server ${serverUrl} --authkey YOUR_AUTH_KEY`)">复制</el-button>
      </div>
      <p style="color:var(--v3s-text-muted);font-size:12px;margin-top:8px">
        将 YOUR_AUTH_KEY 替换为在「预认证密钥」页面创建的密钥。注意：--login-server 地址是 Headscale 控制服务器（默认端口 8080），而非管理面板地址。
      </p>
    </div>

    <div class="glass-card content-card" style="margin-top:16px">
      <h3 style="font-size:16px;font-weight:600;margin-bottom:12px">子网路由通告</h3>
      <p style="color:var(--v3s-text-secondary);margin-bottom:12px">如需将本机作为子网路由器，使机器可以访问其他子网，在目标机器上执行：</p>
      <div class="code-block" style="position:relative">
        <span>tailscale up --login-server {{ serverUrl }} --advertise-routes=10.0.0.0/24,192.168.1.0/24</span>
        <el-button type="primary" link size="small" class="copy-btn"
          @click="copy(`tailscale up --login-server ${serverUrl} --advertise-routes=10.0.0.0/24,192.168.1.0/24`)">复制</el-button>
      </div>
      <p style="color:var(--v3s-text-muted);font-size:12px;margin-top:8px">
        通告后需在「路由管理」页面批准路由才会生效。也可在 ACL 中配置 autoApprovers 实现自动批准。
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const serverUrl = ref('')

const platforms = [
  {
    icon: '🐧', title: 'Linux',
    desc: '通过官方脚本一键安装',
    cmd: 'curl -fsSL https://tailscale.com/install.sh | sh',
  },
  {
    icon: '🪟', title: 'Windows',
    desc: '下载官方 MSI 安装包',
    cmd: 'winget install tailscale.tailscale',
  },
  {
    icon: '📱', title: 'iOS / Android',
    desc: '在应用商店搜索 Tailscale',
    cmd: 'App Store / Google Play → 搜索 "Tailscale"',
  },
]

function copy(text) {
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制')).catch(() => ElMessage.error('复制失败'))
}

onMounted(() => {
  // login-server 应指向 headscale 控制服务器（默认8080），而非前端面板地址
  const hsUrl = userStore.systemStatus?.server_url
  if (hsUrl) {
    serverUrl.value = hsUrl
  } else {
    // fallback: 用当前域名 + headscale 默认端口
    serverUrl.value = `http://${window.location.hostname}:8080`
  }
})
</script>

<style scoped>
.platform-card { text-align: center; }
.platform-icon { font-size: 36px; margin-bottom: 8px; }
.platform-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.platform-desc { font-size: 13px; color: var(--v3s-text-muted); }
.copy-btn { position: absolute; top: 8px; right: 8px; }
</style>
