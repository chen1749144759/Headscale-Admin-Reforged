# DERP 中继服务器配置指南

[English](derp_en.md) | 中文

## 什么是 DERP

DERP（Designated Encrypted Relay for Packets）是 Tailscale 的 NAT 穿透中继协议。当两个节点之间无法建立直连（P2P）时，流量会通过 DERP 中继服务器转发。DERP 包含两个组件：

- **STUN**（UDP）— 帮助节点发现自己的公网地址并尝试打洞建立直连
- **DERP Relay**（TCP/TLS）— 当打洞失败时，作为加密中继转发流量

Headscale-Admin-Reforged 默认集成了独立的 DERP 服务器（`derper`），通过 Docker Compose 一键部署，无需额外配置证书或域名。

## 架构说明

```
                    Tailscale 客户端 A
                          │
              ┌───────────┼───────────┐
              │ STUN (UDP)│           │ DERP Relay (TLS)
              ▼           │           ▼
     ┌────────────────────┴────────────────────┐
     │              hs-derper 容器              │
     │  STUN :3478/udp    DERP Relay :3479/tcp │
     └─────────────────────────────────────────┘
              │ STUN (UDP)            │ DERP Relay (TLS)
              ▼                       ▼
                    Tailscale 客户端 B
```

DERP 服务器与 Headscale 之间**没有直接通信**。Headscale 通过 DERP Map（`derp.yaml`）告知客户端去哪里找 DERP 服务器，客户端自行连接。

## 默认配置

Docker Compose 一键部署默认包含以下 DERP 配置：

| 配置项 | .env 变量 | 默认值 | 说明 |
|--------|-----------|--------|------|
| DERP 域名/IP | `DERP_DOMAIN` | 与 `HEADSCALE_SERVER_URL` 相同 | 客户端连接 DERP 的公网地址 |
| STUN 端口 | `DERP_STUN_PORT` | `3478` | UDP，用于 NAT 穿透打洞 |
| DERP 端口 | `DERP_HTTP_PORT` | `3479` | TCP，DERP 中继（TLS 加密） |

## 一键部署（默认行为）

如果你在 `.env` 中配置了 `DERP_DOMAIN`，Docker Compose 启动时会自动完成以下操作：

1. **渲染 DERP Map** — `entrypoint.sh` 使用 `envsubst` 将 `derp.yaml.tmpl` 模板渲染为 `derp.yaml`，填入你的域名和端口
2. **生成自签名证书** — 如果 `derper-certs` 卷中不存在对应证书，自动用 `openssl` 生成 10 年有效期的自签名 TLS 证书
3. **启动 derper** — 使用自签名证书提供 STUN + DERP Relay 服务
4. **客户端信任** — DERP Map 中设置 `insecurefortests: true`，告知 Tailscale 客户端跳过证书验证

整个过程完全自动，无需手动操作。

## .env 配置示例

```bash
# DERP 中继 — 必须配置为你的公网 IP 或域名
DERP_DOMAIN=203.0.113.1

# STUN 端口（UDP）
DERP_STUN_PORT=3478

# DERP Relay 端口（TCP）
DERP_HTTP_PORT=3479
```

## 防火墙 / NAT 端口映射

确保以下端口在防火墙和路由器 NAT 中放行：

| 端口 | 协议 | 用途 |
|------|------|------|
| `DERP_STUN_PORT` | UDP | STUN 打洞 |
| `DERP_HTTP_PORT` | **TCP** | DERP 中继（注意是 TCP 不是 UDP） |

> **常见错误**：将 DERP Relay 端口映射为 UDP。DERP Relay 使用 HTTP/TLS 协议，必须映射为 **TCP**。

## 自定义端口

如果你的服务器端口被占用或需要使用非标准端口（如 NAT 映射限制），修改 `.env` 即可：

```bash
DERP_STUN_PORT=60091
DERP_HTTP_PORT=60092
```

然后重启：

```bash
docker compose down && docker compose up -d
```

证书和配置会自动适配新端口，无需额外操作。

## 验证 DERP 是否工作

### 1. 检查容器状态

```bash
docker compose ps
# hs-derper 应显示 Up 状态，端口映射正确
```

### 2. 查看 derper 日志

```bash
docker logs hs-derper
# 应看到：
# STUN server listening on [::]:3478
# derper: serving on :3479 with TLS
```

### 3. 客户端 netcheck

在任意已连接的 Tailscale 客户端上运行：

```bash
tailscale netcheck
```

输出应包含你的私有 DERP 节点及延迟：

```
* Nearest DERP: My Private DERP
* DERP latency:
    - myderp: 10ms  (My Private DERP)
```

### 4. 节点间 ping

```bash
tailscale ping <对端IP>
# 应看到：
# pong from xxx via DERP(myderp) in 10ms
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `config.yaml.tmpl` | Headscale 主配置模板，`derp.server.enabled: false` 禁用内嵌 DERP，`derp.paths` 指向 `derp.yaml` |
| `derp.yaml.tmpl` | DERP Map 模板，定义私有 DERP 节点信息（域名、端口、`insecurefortests`） |
| `entrypoint.sh` | 容器入口脚本，负责渲染模板、生成证书、启动 headscale |

## 安全说明

**DERP 中继流量安全吗？**

DERP 只是加密流量的中继。所有通过 DERP 转发的数据都经过 WireGuard 端到端加密，DERP 服务器本身无法解密或查看任何内容。

**公网能扫到我的 DERP 吗？**

DERP 服务器的地址只出现在 Headscale 私有的 DERP Map 中，只有你 Tailnet 内的已注册节点才能获取到这个地址。不会出现在任何公共 DERP 列表中。

**如果需要更强的隔离？**

可以在 derper 启动参数中启用 `--verify-clients=true`，这会让 derper 验证连入的每个客户端是否属于你的 Tailnet。启用方法：在 `docker-compose.yml` 中将 `--verify-clients=false` 改为 `--verify-clients=true`。注意：这需要 derper 能访问 Headscale 的协调服务器进行验证，配置较为复杂，一般场景下不需要。

## 故障排查

### DERP 显示 "tls: first record does not look like a TLS handshake"

客户端在用 TLS 连接 DERP，但服务器在响应明文 HTTP。检查：

- derper 日志是否显示 `with TLS`
- 证书文件是否存在：`docker exec hs-derper ls /app/certs/`
- DERP Map 中 `insecurefortests: true` 是否生效：在客户端运行 `tailscale debug derp-map`

### netcheck 显示延迟但 tailscale ping 超时

STUN（UDP）通了但 DERP Relay（TCP）不通。检查：

- 防火墙/NAT 是否放行了 `DERP_HTTP_PORT` 的 **TCP**（不是 UDP）
- 从外部测试：`curl -v https://<你的IP>:<DERP_HTTP_PORT>/`（应返回 TLS 握手响应）

### 容器启动后 `docker logs hs-derper` 报证书错误

证书可能损坏。删除卷后重启自动重新生成：

```bash
docker compose down
docker volume rm $(docker volume ls -q | grep derper-certs)
docker compose up -d
```
