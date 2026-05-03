# ScaleForge

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.x-409EFF?logo=element&logoColor=white)](https://element-plus.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#方式一docker-compose-一键部署推荐)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

> **ScaleForge — Headscale Web 管理面板**

[English](README_en.md) | [中文](#) | [Deutsch](README_de.md) | [Français](README_fr.md) | [Русский](README_ru.md)

---

## 项目简介

**ScaleForge** 是基于 [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) v4.0.0 的**完全重写**版本。

原项目采用 Flask + Jinja2 的单体架构，本项目将其彻底重构为现代化的**前后端分离**架构：后端使用 FastAPI 提供 REST API，前端使用 Vue 3 构建 SPA 单页应用，并采用全新的深色玻璃拟态 UI 设计。

### 致谢与溯源

本项目 fork 自 [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) tag 4.0.0，感谢原作者 **arounyf** 的出色工作。ScaleForge 版本在保留原项目功能理念的基础上，对技术架构和 UI 进行了完整的重新实现。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.13 + FastAPI + Uvicorn |
| 前端框架 | Vue 3 + Vite + Element Plus + Pinia + Vue Router 4 |
| 认证鉴权 | JWT + 原生 bcrypt（兼容 Python 3.13 + bcrypt 5.x） |
| 数据库 | PostgreSQL 16（Docker 部署）/ SQLite（本地开发） |
| Headscale | [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE)（增强版，扩展 users 表） |
| DERP 中继 | 独立 [derper](https://pkg.go.dev/tailscale.com/cmd/derper)，自签名证书自动生成 |
| API 代理 | Bearer Token 调用 headscale HTTP API，自动创建并刷新 API Key |

### 架构概览

```
                              ┌─────────────────────────────────┐
                              │           Browser               │
                              └──────────────┬──────────────────┘
                                             │ :80
                                             ▼
                              ┌─────────────────────────────────┐
                              │        Nginx (前端+反代)          │
                              │  ┌───────────┬────────────────┐ │
                              │  │ Vue3 SPA  │ /api/* → :5175 │ │
                              │  │ 静态文件   │ /hs/*  → :8080 │ │
                              │  └───────────┴────────┬───────┘ │
                              └───────────────────────┼─────────┘
                                        ┌─────────────┤
                                        ▼             ▼
                    ┌──────────────────────┐   ┌───────────────────┐
                    │  FastAPI (port 5175) │   │  Headscale AE     │
                    │    管理面板后端        │   │   (port 8080)     │
                    └─────────┬────────────┘   └────────┬──────────┘
                              │                         │
                              ▼                         ▼
                    ┌──────────────────────────────────────────────┐
                    │          PostgreSQL 16 (共享数据库)            │
                    └──────────────────────────────────────────────┘

    ┌─────────────────────────────────────┐
    │   derper (独立 DERP 中继服务器)       │
    │   STUN :3478/udp  DERP :3479/tcp   │
    └─────────────────────────────────────┘
```

## 功能列表

- **控制台仪表盘** — 实时 CPU/内存/流量监控，平滑流量趋势曲线，节点统计
- **分组管理** — Headscale 用户命名空间管理、机器配额、ACL 规则模板自动生成
- **节点管理** — 列表、搜索、按分组筛选、重命名、删除、标签管理（forcedTags）、移动分组
- **路由管理** — 子网路由通告列表、批准/撤销、autoApprovers 可视化编辑、Exit Node 管理
- **ACL 规则编辑器** — HuJSON 支持、格式化、行号显示、database 模式自动同步
- **预授权密钥** — 创建（过期时间/可复用/临时节点）、删除、一键复制
- **DERP 中继** — 独立 DERP 服务器，自签证书自动生成，零配置部署
- **系统设置** — headscale 连接配置、API Key 管理、注册策略、安全锁定保护
- **操作日志** — 分页查看操作记录，日志内容显示机器名/分组名（非 ID）
- **个人中心** — 资料编辑、密码修改
- **健康监测** — 顶部栏实时显示 headscale 连接状态

## 截图预览

| 控制台 | 用户管理 |
|:---:|:---:|
| ![控制台](screenshots/首页.png) | ![用户管理](screenshots/用户.png) |

| 分组管理 | ACL 规则 |
|:---:|:---:|
| ![分组管理](screenshots/分组.png) | ![ACL 规则](screenshots/ACL.png) |

| 路由管理 | 预认证密钥 |
|:---:|:---:|
| ![路由管理](screenshots/路由.png) | ![预认证密钥](screenshots/预认证.png) |

---

## 部署指南

提供三种部署方式，根据你的场景选择：

| 方式 | 适用场景 | 难度 |
|------|----------|------|
| [Docker Compose 一键部署](#方式一docker-compose-一键部署推荐) | 生产环境、快速体验 | ⭐ |
| [Docker 单容器部署](#方式二docker-单容器部署) | 已有数据库/headscale，只需部分组件 | ⭐⭐ |
| [裸应用部署](#方式三裸应用部署) | 完全自主控制、开发调试 | ⭐⭐⭐ |

---

### 方式一：Docker Compose 一键部署（推荐）

最简单的部署方式，一条命令拉起全部服务（PostgreSQL + Headscale AE + DERP 中继 + 管理后端 + Nginx 前端）。

#### 前置要求

- Linux 服务器（推荐 Ubuntu 22/24）
- Docker + Docker Compose

还没装 Docker？一条命令搞定：

```bash
curl -fsSL https://get.docker.com | sh
```

#### 第一步：下载部署文件

```bash
mkdir -p ~/headscale-admin && cd ~/headscale-admin

# 下载 docker-compose.yml 及模板文件
for f in docker-compose.yml config.yaml.tmpl derp.yaml.tmpl entrypoint.sh .env.example; do
  curl -fsSL -o "$f" \
    "https://raw.githubusercontent.com/chen1749144759/ScaleForge/main/docker/$f"
done
chmod +x entrypoint.sh
```

#### 第二步：创建 .env 配置文件

```bash
cp .env.example .env
```

编辑 `.env`，**至少修改以下两项**：

```bash
# 必须修改 — Headscale 对外访问地址
HEADSCALE_SERVER_URL=http://你的公网IP:8080

# 必须修改 — DERP 中继公网地址（通常与上面相同）
DERP_DOMAIN=你的公网IP
```

> **最重要的配置**：`HEADSCALE_SERVER_URL` 必须改成你的服务器公网地址，Tailscale 客户端通过这个地址连接 Headscale。如果修改了 `HS_PORT`（如改为 60090），URL 的端口也必须同步修改。

#### 第三步：启动

```bash
docker compose up -d
```

首次启动会自动：

1. 拉取所有镜像（PostgreSQL、Headscale AE、derper、管理后端、Nginx）
2. 为 DERP 生成自签名 TLS 证书
3. 按依赖顺序启动所有服务（每一层都有健康检查）

#### 第四步：验证

```bash
docker compose ps   # 应全部显示 healthy / Up
```

全部就绪后访问：

| 地址 | 用途 |
|------|------|
| `http://你的IP` | 管理面板 Web 界面 |
| `http://你的IP:8080` | Headscale API（客户端连接地址） |

#### 第五步：初始化管理员

浏览器打开 `http://你的IP`，进入注册页面。**第一个注册的用户自动成为管理员**（之后注册入口关闭）。

#### 防火墙端口

确保以下端口已放行：

| 端口 | 协议 | 用途 |
|------|------|------|
| 80 | TCP | Web 管理面板 |
| 8080 | TCP | Headscale API + Noise 协议 |
| 3478 | UDP | STUN（NAT 穿透打洞） |
| 3479 | TCP | DERP 中继（TLS 加密） |

> DERP 中继相关的详细配置说明请参考 [DERP 配置指南](derp.md)。

#### 常用运维命令

```bash
# 停止所有服务
docker compose down

# 更新镜像并重启
docker compose pull && docker compose up -d

# 查看日志
docker compose logs -f --tail=50

# 数据备份（PostgreSQL）
docker exec hs-postgres pg_dump -U headscale_admin headscale_admin > backup.sql

# 手动创建 API Key
docker exec hs-headscale headscale apikey create
```

#### 数据持久化

所有数据通过 Docker Volume 持久化，`docker compose down` 不会丢失数据：

- `postgres-data` — 数据库
- `headscale-data` — Headscale 运行数据 + API Key
- `derper-certs` — DERP 服务器 TLS 证书

如需完全重置，执行 `docker compose down -v` 删除 Volume（**数据不可恢复**）。

---

### 方式二：Docker 单容器部署

适用于已有 PostgreSQL 数据库或 Headscale 实例，只需要部署部分组件的场景。

#### 前置条件

- 已有 PostgreSQL 数据库
- Docker 已安装

#### 2.1 只部署 Headscale AE

如果你只需要增强版 Headscale（支持管理面板的扩展表），不需要管理面板：

```bash
docker run -d \
  --name hs-headscale \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 3478:3478/udp \
  -v headscale-data:/var/lib/headscale \
  -e HEADSCALE_SERVER_URL=http://你的公网IP:8080 \
  -e HEADSCALE_DNS_DOMAIN=hs.admin.pro \
  -e DB_HOST=你的数据库IP \
  -e DB_PORT=5432 \
  -e DB_NAME=headscale_admin \
  -e DB_USER=headscale_admin \
  -e DB_PASS=你的数据库密码 \
  chenzeshi/headscale-admin-ae:latest
```

你也可以挂载自定义配置文件跳过环境变量模板渲染：

```bash
docker run -d \
  --name hs-headscale \
  -p 8080:8080 \
  -p 3478:3478/udp \
  -v headscale-data:/var/lib/headscale \
  -v /your/path/config.yaml:/etc/headscale/config.yaml \
  chenzeshi/headscale-admin-ae:latest
```

#### 2.2 只部署管理面板（后端 + 前端）

已有 Headscale AE 和 PostgreSQL 运行中，只加装管理面板：

```bash
# 创建 Docker 网络
docker network create hs-net

# 后端
docker run -d \
  --name hs-admin-backend \
  --network hs-net \
  --restart unless-stopped \
  -e HEADSCALE_URL=http://你的headscale地址:8080 \
  -e DB_HOST=你的数据库IP \
  -e DB_PORT=5432 \
  -e DB_NAME=headscale_admin \
  -e DB_USER=headscale_admin \
  -e DB_PASS=你的数据库密码 \
  -e SECRET_KEY=你的JWT密钥 \
  -e API_KEY_FILE=/data/headscale/api.key \
  -v headscale-data:/data/headscale:ro \
  chenzeshi/headscale-admin-backend:latest

# 前端（Nginx）
docker run -d \
  --name hs-nginx \
  --network hs-net \
  --restart unless-stopped \
  -p 80:80 \
  chenzeshi/headscale-admin-nginx:latest
```

> **注意**：Nginx 容器内置的反向代理配置通过容器名 `admin-backend` 和 `headscale` 连接后端和 Headscale。如果你的容器名不同，需要自定义 nginx.conf 并挂载覆盖。

#### 2.3 环境变量参考

**Headscale AE 容器：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HEADSCALE_SERVER_URL` | Headscale 对外访问地址 | `http://127.0.0.1:8080` |
| `HEADSCALE_DNS_DOMAIN` | MagicDNS 域名 | `hs.admin.pro` |
| `HEADSCALE_LOG_LEVEL` | 日志级别 | `info` |
| `DB_HOST` | PostgreSQL 主机 | — |
| `DB_PORT` | PostgreSQL 端口 | `5432` |
| `DB_NAME` | 数据库名 | — |
| `DB_USER` | 数据库用户 | — |
| `DB_PASS` | 数据库密码 | — |
| `DERP_DOMAIN` | DERP 公网 IP/域名 | — |
| `DERP_STUN_PORT` | STUN 端口 (UDP) | `3478` |
| `DERP_HTTP_PORT` | DERP Relay 端口 (TCP) | `3479` |

**管理后端容器：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HEADSCALE_URL` | Headscale API 内网地址 | `http://headscale:8080` |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASS` | 数据库连接 | — |
| `DATABASE_URL` | 完整 DSN（与分离参数二选一） | — |
| `SECRET_KEY` | JWT 签名密钥 | `change-me` |
| `API_KEY_FILE` | Headscale API Key 文件路径 | `/data/headscale/api.key` |

---

### 方式三：裸应用部署

不使用 Docker，直接在服务器上安装所有组件。适合需要完全控制每个组件或开发调试的场景。

#### 前置要求

- Linux 服务器（Ubuntu 22/24、Debian 12+）
- Python 3.13+
- Node.js 18+ & npm
- Nginx
- PostgreSQL 14+（或 SQLite）
- Go 1.22+（编译 Headscale AE）

#### 3.1 部署 Headscale AE

```bash
# 克隆并编译
git clone https://github.com/chen1749144759/Headscale-Admin-AE.git
cd Headscale-Admin-AE

go build -trimpath \
  -ldflags="-s -w -X github.com/juanfont/headscale/hscontrol/types.Version=v0.28.1" \
  -o headscale ./cmd/headscale

# 安装
sudo mv headscale /usr/local/bin/
sudo mkdir -p /etc/headscale /var/lib/headscale

# 编辑配置（参考 config-example.yaml）
sudo cp config-example.yaml /etc/headscale/config.yaml
sudo vim /etc/headscale/config.yaml
```

关键配置项需要修改：

```yaml
server_url: http://你的公网IP:8080
listen_addr: 0.0.0.0:8080
database:
  type: postgres
  postgres:
    host: 127.0.0.1
    port: 5432
    name: headscale_admin
    user: headscale_admin
    pass: 你的密码
policy:
  mode: database
```

创建 systemd 服务：

```bash
sudo tee /etc/systemd/system/headscale.service << 'EOF'
[Unit]
Description=Headscale Admin AE
After=network.target postgresql.service

[Service]
Type=simple
ExecStart=/usr/local/bin/headscale serve -c /etc/headscale/config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now headscale
```

创建 API Key：

```bash
headscale apikey create
# 记下输出的 key，后面配置后端要用
```

#### 3.2 部署管理面板后端

```bash
git clone https://github.com/chen1749144759/ScaleForge.git
cd ScaleForge

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-prod.txt
```

创建后端配置文件 `config.yaml`：

```yaml
server_url:
  headscale: http://127.0.0.1:8080
bearer_token: "上一步创建的 API Key"
server_net: eth0
database:
  postgresql:
    dsn: "host=127.0.0.1 port=5432 dbname=headscale_admin user=headscale_admin password=你的密码"
secret_key: "你的JWT密钥"
```

创建 systemd 服务：

```bash
sudo tee /etc/systemd/system/headscale-admin.service << 'EOF'
[Unit]
Description=Headscale Admin Backend
After=network.target headscale.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ScaleForge
ExecStart=/opt/ScaleForge/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 5175
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now headscale-admin
```

#### 3.3 构建并部署前端

```bash
cd ScaleForge/web

npm install
npm run build

# 复制构建产物
sudo mkdir -p /var/www/headscale-admin
sudo cp -r dist/* /var/www/headscale-admin/
```

#### 3.4 配置 Nginx

```bash
sudo tee /etc/nginx/conf.d/headscale-admin.conf << 'NGINX'
map $http_upgrade $connection_upgrade {
    default      keep-alive;
    'websocket'  upgrade;
    ''           close;
}

server {
    listen 80;
    server_name _;

    root /var/www/headscale-admin;
    index index.html;

    # API 反向代理 → 后端
    location /api/ {
        proxy_pass http://127.0.0.1:5175;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30;
        proxy_read_timeout 120;
    }

    # Headscale 协议反向代理
    location ~ ^/(health|oidc|windows|apple|key|derp|bootstrap-dns|swagger|ts2021|machine) {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $server_name;
        proxy_buffering off;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;
    }

    # SPA 路由 fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX

sudo nginx -t && sudo systemctl reload nginx
```

#### 3.5 访问面板

打开浏览器访问 `http://你的IP`，注册第一个管理员账户。

---

## 客户端连接

部署完成后，在需要组网的设备上安装 Tailscale 客户端并指向你的 Headscale：

```bash
# Linux
tailscale up --login-server=http://你的公网IP:8080

# Windows / macOS
# 在 Tailscale 客户端设置中将 Login Server 改为你的地址
```

连接成功后可在管理面板上查看和管理设备。

---

## 常见问题

### Tailscale 子网路由不通（ping 内网 IP 无响应）

**现象**：两个节点通过 `100.64.x.x` 互相 ping 正常，但从节点 A ping 节点 B advertise 的子网 IP（如 `10.2.0.88`）时无响应。

**原因**：如果节点 A 同时也是 Headscale 服务器所在的机器，Headscale 自己的 WireGuard 隧道接口（如 `tun-v3s`）已经注册了 `10.0.0.0/x` 网段的路由，优先级比 Tailscale 的子网路由更高。

**解决方案**：不要在 Headscale 服务器上同时运行 Tailscale 客户端来测试子网路由功能。使用一台独立的机器作为 Tailscale 客户端进行测试。

### 子网路由通告后仍然不通的检查清单

1. **通告节点开启 IP 转发**：`sysctl -w net.ipv4.ip_forward=1`
2. **Headscale 侧批准路由**：管理面板"路由管理"中批准，或 `headscale routes enable -r <route_id>`
3. **接收端开启 accept-routes**：`tailscale up --login-server=... --accept-routes`
4. **通告节点关闭严格反向路径过滤**：`sysctl -w net.ipv4.conf.all.rp_filter=2`

### Tailscale 客户端切换到新的 Headscale 服务器

如果旧服务器已不可达，`tailscale logout` 会报连接错误。直接重置本地状态：

```bash
# Linux
sudo systemctl stop tailscaled
sudo rm -rf /var/lib/tailscale
sudo systemctl start tailscaled
tailscale up --login-server=http://新服务器地址:8080
```

---

## 相关项目

| 项目 | 说明 |
|------|------|
| [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) | 本项目依赖的增强版 headscale |
| [Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) | 原版项目（arounyf） |
| [headscale](https://github.com/juanfont/headscale) | headscale 官方项目 |

## DERP 中继配置

DERP 中继在一键部署时自动配置。自定义端口、故障排查和安全加固请参考：

- [DERP 配置指南（中文）](derp.md)
- [DERP Configuration Guide (English)](derp_en.md)

## 路线图

- [x] Docker Compose 一键部署
- [x] 独立 DERP 中继 + 自动 TLS
- [x] 实时流量趋势曲线
- [ ] 深色/浅色模式切换
- [ ] 多语言 i18n 支持（当前仅中文 UI）
- [ ] OIDC / SSO 集成
- [ ] 移动端响应式优化

## 参与贡献

欢迎提交 Issue 和 Pull Request。在提交 PR 之前，请确保：

1. 代码能正常构建（前端 `npm run build` 无报错）
2. 后端接口保持向后兼容
3. 提交信息清晰描述变更内容

## 许可证

本项目基于 [MIT License](../LICENSE) 开源。
