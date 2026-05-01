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
        <span>tailscale up --login-server {{ serverUrl }} --authkey YOUR_AUTH_KEY --accept-routes</span>
        <el-button type="primary" link size="small" class="copy-btn"
          @click="copy(`tailscale up --login-server ${serverUrl} --authkey YOUR_AUTH_KEY --accept-routes`)">复制</el-button>
      </div>
      <p style="color:var(--v3s-text-muted);font-size:12px;margin-top:8px">
        将 YOUR_AUTH_KEY 替换为在「预认证密钥」页面创建的密钥。<code>--accept-routes</code> 用于接收其他节点通告的子网路由。注意：--login-server 地址是 Headscale 控制服务器（默认端口 8080），而非管理面板地址。
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

    <!-- 站点到站点组网 -->
    <div class="glass-card content-card" style="margin-top:16px">
      <h3 style="font-size:16px;font-weight:600;margin-bottom:4px">站点到站点组网（Site-to-Site）</h3>
      <p style="color:var(--v3s-text-secondary);margin-bottom:16px;font-size:13px">通过子网路由器让内网无客户端设备也能双向访问远程网络</p>

      <!-- 网络拓扑图 -->
      <div class="topo">
        <div class="topo-lan">
          <div class="topo-zone-title">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            物理内网 <code>192.168.1.0/24</code>
          </div>
          <div class="topo-nodes">
            <div class="nd nd-hs"><div class="nd-letter">A</div><div class="nd-name">Headscale<br>服务端</div><div class="nd-ts">TS</div></div>
            <div class="nd nd-rt"><div class="nd-letter">B</div><div class="nd-name">子网<br>路由器</div><div class="nd-ts">TS</div></div>
            <div class="nd nd-bare"><div class="nd-letter">C</div><div class="nd-name">无客户端</div></div>
            <div class="nd nd-bare"><div class="nd-letter">D</div><div class="nd-name">无客户端</div></div>
            <div class="nd nd-bare"><div class="nd-letter">E</div><div class="nd-name">无客户端</div></div>
          </div>
        </div>

        <div class="topo-tunnel">
          <div class="tunnel-pipe"></div>
          <div class="tunnel-tag">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22V2M5 12l7-7 7 7"/></svg>
            Tailscale WireGuard 隧道
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M5 12l7 7 7-7"/></svg>
          </div>
          <div class="tunnel-pipe"></div>
        </div>

        <div class="topo-wan">
          <div class="topo-wan-box">
            <div class="topo-zone-title">外网 F <code>172.16.1.0/24</code></div>
            <div class="nd nd-ext"><div class="nd-letter">F</div><div class="nd-name">客户端</div><div class="nd-ts">TS</div></div>
          </div>
          <div class="topo-wan-box">
            <div class="topo-zone-title">外网 G <code>172.16.2.0/24</code></div>
            <div class="nd nd-ext"><div class="nd-letter">G</div><div class="nd-name">客户端</div><div class="nd-ts">TS</div></div>
          </div>
        </div>
      </div>

      <!-- 双向访问说明 -->
      <div class="s2s-flows">
        <div class="s2s-flow"><span class="flow-ok">✓</span><code>F → B → C / D / E</code><span class="flow-desc">外网通过 B 的子网路由访问内网设备</span></div>
        <div class="s2s-flow"><span class="flow-ok">✓</span><code>C / D / E → B → F / G</code><span class="flow-desc">内网通过静态路由 + B 的 SNAT 转发访问远程</span></div>
      </div>

      <!-- 原理说明 -->
      <div class="s2s-principle">
        <b>核心原理 — SNAT（源地址转换）</b><br>
        B 节点默认开启 SNAT（<code>--snat-subnet-routes=true</code>），C/D/E 的请求经 B 转发时，源 IP 被替换为 B 的 Tailscale 地址，远程节点的响应自然沿隧道返回 B，B 再转回内网。整个过程 C/D/E 无需安装客户端。<br>
        <span class="s2s-warn">⚠ 关键前提：C/D/E 必须添加指向 B 的静态路由，否则流量不知道发往何处。</span>
      </div>

      <!-- 配置步骤 -->
      <h4 style="font-size:14px;font-weight:600;margin:20px 0 12px">配置步骤</h4>

      <div class="s2s-step" v-for="(step, i) in s2sSteps" :key="i">
        <div class="step-num">{{ i + 1 }}</div>
        <div class="step-body">
          <div class="step-title">{{ step.title }}</div>
          <p v-if="step.hint" class="step-hint">{{ step.hint }}</p>
          <div class="code-block code-pre" style="position:relative">
            <code>{{ step.code }}</code>
            <el-button type="primary" link size="small" class="copy-btn" @click="copy(step.code)">复制</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const serverUrl = ref('')

const s2sSteps = computed(() => [
  {
    title: 'B 节点：宣告子网路由 + 开启 IP 转发',
    code: `tailscale up --login-server ${serverUrl.value} --advertise-routes=192.168.1.0/24 --accept-routes\n\n# 开启 IP 转发（永久生效）\necho 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf\necho 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.conf\nsysctl -p`
  },
  {
    title: 'F / G 节点：宣告各自子网（如需访问其背后的内网设备）',
    code: `# 在 F 上\ntailscale up --login-server ${serverUrl.value} --advertise-routes=172.16.1.0/24 --accept-routes\n\n# 在 G 上\ntailscale up --login-server ${serverUrl.value} --advertise-routes=172.16.2.0/24 --accept-routes\n\n# F / G 同样需要开启 IP 转发`
  },
  {
    title: 'Headscale：批准所有子网路由',
    hint: '在管理面板「路由管理」页面操作，或命令行：',
    code: `headscale routes list\nheadscale routes enable -r <route_id>`
  },
  {
    title: 'C / D / E：添加静态路由（关键步骤）',
    hint: '告诉无客户端设备将远程流量发给 B（将 192.168.1.x 替换为 B 的内网 IP）：',
    code: `# 访问远程 Tailscale 节点 (100.64.x.x)\nip route add 100.64.0.0/10 via 192.168.1.x\n\n# 访问 F 背后子网\nip route add 172.16.1.0/24 via 192.168.1.x\n\n# 访问 G 背后子网\nip route add 172.16.2.0/24 via 192.168.1.x\n\n# 如需永久生效，写入 /etc/network/interfaces 或 netplan 配置`
  },
  {
    title: 'ACL 策略：允许跨网段访问',
    code: `{\n  "acls": [\n    {\n      "action": "accept",\n      "src": ["dev"],\n      "dst": [\n        "dev:*",\n        "192.168.1.0/24:*",\n        "172.16.1.0/24:*",\n        "172.16.2.0/24:*"\n      ]\n    }\n  ]\n}`
  }
])

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
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制')).catch(() => fallbackCopy(text))
  } else {
    fallbackCopy(text)
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy'); ElMessage.success('已复制') } catch { ElMessage.error('复制失败') }
  document.body.removeChild(ta)
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

/* ========== 拓扑图 ========== */
.topo {
  background: var(--v3s-primary-bg);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.topo-lan, .topo-wan-box {
  border: 1px dashed rgba(255,255,255,.12);
  border-radius: 10px;
  padding: 14px;
}
.topo-zone-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600;
  color: var(--v3s-text-secondary);
  margin-bottom: 12px;
}
.topo-zone-title code {
  font-size: 11px; background: rgba(79,70,229,.12); color: #818cf8;
  padding: 1px 6px; border-radius: 4px;
}
.topo-nodes {
  display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;
}
.nd {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  width: 72px; padding: 10px 4px;
  border-radius: 8px;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.06);
  position: relative;
  transition: all .2s;
}
.nd:hover { background: rgba(255,255,255,.08); }
.nd-letter {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px; color: #fff;
}
.nd-hs .nd-letter { background: linear-gradient(135deg, #6366f1, #4f46e5); }
.nd-rt .nd-letter { background: linear-gradient(135deg, #10b981, #059669); }
.nd-bare .nd-letter { background: rgba(255,255,255,.15); color: rgba(255,255,255,.6); }
.nd-ext .nd-letter { background: linear-gradient(135deg, #f59e0b, #d97706); }
.nd-name {
  font-size: 10px; color: var(--v3s-text-muted);
  text-align: center; line-height: 1.4;
}
.nd-ts {
  font-size: 9px; font-weight: 700;
  background: rgba(16,185,129,.15); color: #10b981;
  padding: 1px 6px; border-radius: 3px;
}

/* 隧道连接 */
.topo-tunnel {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px 0;
}
.tunnel-pipe {
  flex: 1; height: 1px; max-width: 60px;
  background: repeating-linear-gradient(90deg, #6366f1 0, #6366f1 4px, transparent 4px, transparent 8px);
}
.tunnel-tag {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 500;
  color: #818cf8;
  background: rgba(99,102,241,.1);
  padding: 4px 12px; border-radius: 20px;
}

/* 外网区域 */
.topo-wan {
  display: flex; gap: 12px;
}
.topo-wan-box {
  flex: 1;
  display: flex; flex-direction: column; align-items: center;
}
.topo-wan-box .nd { margin-top: 0; }

/* ========== 双向访问流 ========== */
.s2s-flows {
  display: flex; flex-direction: column; gap: 8px;
  margin-bottom: 16px;
}
.s2s-flow {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--v3s-text-secondary);
  padding: 8px 12px;
  background: rgba(16,185,129,.06);
  border-radius: 8px;
  border-left: 3px solid #10b981;
}
.s2s-flow code {
  font-size: 12px; font-weight: 600;
  color: var(--v3s-text-primary);
  white-space: nowrap;
}
.flow-ok {
  color: #10b981; font-weight: 700; font-size: 14px;
  flex-shrink: 0;
}
.flow-desc { color: var(--v3s-text-muted); font-size: 12px; }

/* ========== 原理说明 ========== */
.s2s-principle {
  padding: 14px 16px;
  background: var(--v3s-primary-bg);
  border-radius: 8px;
  font-size: 13px;
  color: var(--v3s-text-secondary);
  line-height: 1.8;
  margin-bottom: 4px;
}
.s2s-principle b { color: var(--v3s-text-primary); }
.s2s-principle code { font-size: 12px; background: rgba(79,70,229,.1); color: #818cf8; padding: 1px 5px; border-radius: 3px; }
.s2s-warn { color: #f59e0b; font-size: 12px; font-weight: 500; }

/* ========== 配置步骤 ========== */
.s2s-step {
  display: flex; gap: 14px;
  margin-bottom: 16px;
}
.step-num {
  width: 28px; height: 28px; flex-shrink: 0;
  border-radius: 50%;
  background: rgba(99,102,241,.15); color: #818cf8;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
  margin-top: 2px;
}
.step-body { flex: 1; min-width: 0; }
.step-title { font-size: 13px; font-weight: 600; color: var(--v3s-text-primary); margin-bottom: 6px; }
.step-hint { font-size: 12px; color: var(--v3s-text-muted); margin-bottom: 8px; }
.code-pre code {
  display: block;
  white-space: pre;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  line-height: 1.6;
  padding-right: 48px;
}
</style>
