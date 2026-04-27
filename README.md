# Headscale-Admin-Reforged

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.x-409EFF?logo=element&logoColor=white)](https://element-plus.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Headscale Web 管理面板 — 完全重写版**
>
> A completely rewritten web management panel for [headscale](https://github.com/juanfont/headscale).

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介

**Headscale-Admin-Reforged** 是基于 [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) v4.0.0 的**完全重写**版本。

原项目采用 Flask + Jinja2 的单体架构，本项目将其彻底重构为现代化的**前后端分离**架构：后端使用 FastAPI 提供 REST API，前端使用 Vue 3 构建 SPA 单页应用，并采用全新的深色玻璃拟态 UI 设计。

### 致谢与溯源

本项目 fork 自 [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) tag 4.0.0，感谢原作者 **arounyf** 的出色工作。Reforged 版本在保留原项目功能理念的基础上，对技术架构和 UI 进行了完整的重新实现。

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.13 + FastAPI + Uvicorn |
| 前端框架 | Vue 3 + Vite + Element Plus + Pinia + Vue Router 4 |
| 认证鉴权 | JWT + 原生 bcrypt（兼容 Python 3.13 + bcrypt 5.x） |
| 数据库 | 直接共享 headscale 的 SQLite / PostgreSQL（扩展 users 表） |
| API 代理 | Bearer Token 调用 headscale HTTP API，支持 `headscale apikey create` 自动刷新 |

### 架构概览

```
                          ┌─────────────────────────────────┐
                          │           Browser               │
                          └──────────────┬──────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────┐
                          │     Nginx (port 5174)           │
                          │  ┌───────────┬────────────┐     │
                          │  │ Vue SPA   │ /api/*     │     │
                          │  │ 静态文件   │ 反向代理    │     │
                          │  └───────────┴─────┬──────┘     │
                          └────────────────────┼────────────┘
                                               │
                                               ▼
                          ┌─────────────────────────────────┐
                          │   FastAPI + Uvicorn (port 5175) │
                          │          REST API Server        │
                          └──────┬──────────────────┬───────┘
                                 │                  │
                                 ▼                  ▼
                    ┌────────────────────┐  ┌───────────────┐
                    │  Headscale API     │  │  SQLite /     │
                    │  (port 18919)      │  │  PostgreSQL   │
                    └────────────────────┘  └───────────────┘
```

### 相较原版的核心变化

| # | 变更项 | 原版 4.0.0 | Reforged |
|---|--------|-----------|----------|
| 1 | 架构模式 | Flask + Jinja2 单体 | 前后端分离（SPA + REST API） |
| 2 | 后端框架 | Flask | FastAPI + Pydantic 请求模型 + 规范参数绑定 |
| 3 | 前端方案 | Jinja2 服务端渲染 | Vue 3 SPA + Element Plus 组件库 |
| 4 | UI 设计 | 原版样式 | 深色玻璃拟态主题（深蓝侧边栏、毛玻璃卡片、靛蓝强调色） |
| 5 | 认证库 | passlib | 原生 bcrypt（解决 Python 3.13 兼容性问题） |
| 6 | PreAuthKey | user 字段类型错误 | 修正为 uint64 ID |
| 7 | 数据处理 | — | 正确解析 headscale API 嵌套响应结构 |
| 8 | 系统设置 | — | 新增锁定/解锁模式 + 敏感操作密码确认 |
| 9 | ACL 编辑器 | — | 全高度深色编辑器，支持行号和 JSON 格式化 |
| 10 | 控制台仪表盘 | — | 实时 CPU/内存/流量监控，修正 API 字段映射 |

### UI 亮点

- **登录页**：左右分栏布局 + 拼图滑块验证码
- **独立注册页**：支持独立访问的注册流程
- **侧边栏**：深蓝色调（`#0d1117`）
- **卡片组件**：`backdrop-filter: blur` 毛玻璃效果
- **强调色**：靛蓝（`#4f46e5`）

### 功能列表

- **用户管理** — 增删改查、过期设置、节点配额、路由权限、启用/禁用
- **节点管理** — 列表、搜索、按用户筛选、重命名、删除、路由详情
- **路由管理** — 列表查看、启用/禁用切换
- **预授权密钥** — 创建（过期时间/可复用/临时节点）、删除、一键复制
- **ACL 规则编辑器** — HuJSON 支持、格式化、行号显示
- **系统设置** — headscale 连接配置、API Key 管理、注册策略、安全锁定保护
- **操作日志** — 分页查看操作记录
- **部署指南** — 内置部署说明页面
- **个人中心** — 资料编辑、密码修改
- **健康监测** — 顶部栏实时显示 headscale 连接状态

### 截图预览

> 截图即将补充，敬请期待。

<!-- 
![登录页](docs/screenshots/login.png)
![控制台](docs/screenshots/dashboard.png)
![节点管理](docs/screenshots/nodes.png)
-->

### 快速开始

#### 前置要求

- Python 3.13+
- Node.js 18+ & npm
- Nginx
- [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE)（修改版 headscale，需部署在同一服务器）

#### 1. 部署后端

```bash
# 克隆仓库
git clone https://github.com/chen1749144759/Headscale-Admin-Reforged.git
cd Headscale-Admin-Reforged/backend

# 创建虚拟环境并安装依赖
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启动后端服务（默认端口 5175）
uvicorn main:app --host 0.0.0.0 --port 5175
```

**systemd 服务示例：**

```ini
[Unit]
Description=Headscale Admin Reforged Backend
After=network.target

[Service]
Type=simple
User=headscale-admin
WorkingDirectory=/opt/Headscale-Admin-Reforged/backend
ExecStart=/opt/Headscale-Admin-Reforged/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 5175
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 2. 构建并部署前端

```bash
cd Headscale-Admin-Reforged/frontend

# 安装依赖并构建
npm install
npm run build
```

将构建产物（`dist/`）部署到 Nginx：

```bash
sudo cp -r dist/* /var/www/headscale-admin/
```

#### 3. 配置 Nginx

```nginx
server {
    listen 5174;
    server_name _;

    root /var/www/headscale-admin;
    index index.html;

    # Vue Router history 模式
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:5175;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

#### 4. 访问面板

打开浏览器访问 `http://<your-server-ip>:5174`

### 配置说明

| 配置项 | 说明 | 位置 |
|--------|------|------|
| 后端端口 | 默认 `5175` | uvicorn 启动参数 |
| 前端端口 | 默认 `5174` | Nginx 配置 |
| Headscale 地址 | headscale HTTP API 地址 | 面板「系统设置」页 |
| API Key | headscale API 密钥 | 面板「系统设置」页，支持自动刷新 |
| 数据库 | 共享 headscale 的 SQLite/PostgreSQL | 后端配置文件 |

### 路线图

- [ ] Docker Compose 一键部署
- [ ] 深色/浅色模式切换
- [ ] 仪表盘图表（流量趋势、节点活跃度）
- [ ] 多语言 i18n 支持（当前仅中文 UI）
- [ ] OIDC / SSO 集成
- [ ] 移动端响应式优化

### 相关项目

| 项目 | 说明 |
|------|------|
| [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) | 本项目依赖的修改版 headscale |
| [Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) | 原版项目（arounyf） |
| [headscale](https://github.com/juanfont/headscale) | headscale 官方项目 |

### 参与贡献

欢迎提交 Issue 和 Pull Request。在提交 PR 之前，请确保：

1. 代码能正常构建（前端 `npm run build` 无报错）
2. 后端接口保持向后兼容
3. 提交信息清晰描述变更内容

### 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

## English

### About

**Headscale-Admin-Reforged** is a **complete rewrite** of [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) v4.0.0.

The original project was a monolithic application built with Flask + Jinja2. This project has been entirely rebuilt with a modern **frontend-backend separated** architecture: FastAPI serves the REST API on the backend, while Vue 3 powers a SPA on the frontend — all wrapped in a brand-new dark glassmorphism UI.

### Credits & Origin

This project is forked from [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) tag 4.0.0. Special thanks to **arounyf** for the original work. The Reforged edition preserves the core feature set while completely reimplementing the technical architecture and user interface.

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13 + FastAPI + Uvicorn |
| Frontend | Vue 3 + Vite + Element Plus + Pinia + Vue Router 4 |
| Authentication | JWT + native bcrypt (Python 3.13 + bcrypt 5.x compatible) |
| Database | Shares headscale's SQLite / PostgreSQL directly (extended users table) |
| API Proxy | Bearer Token to headscale HTTP API, auto-refresh via `headscale apikey create` |

### Architecture

```
                          ┌─────────────────────────────────┐
                          │           Browser               │
                          └──────────────┬──────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────┐
                          │     Nginx (port 5174)           │
                          │  ┌───────────┬────────────┐     │
                          │  │ Vue SPA   │ /api/*     │     │
                          │  │ Static    │ Reverse    │     │
                          │  │ Files     │ Proxy      │     │
                          │  └───────────┴─────┬──────┘     │
                          └────────────────────┼────────────┘
                                               │
                                               ▼
                          ┌─────────────────────────────────┐
                          │   FastAPI + Uvicorn (port 5175) │
                          │          REST API Server        │
                          └──────┬──────────────────┬───────┘
                                 │                  │
                                 ▼                  ▼
                    ┌────────────────────┐  ┌───────────────┐
                    │  Headscale API     │  │  SQLite /     │
                    │  (port 18919)      │  │  PostgreSQL   │
                    └────────────────────┘  └───────────────┘
```

### Key Changes from Original 4.0.0

| # | Area | Original 4.0.0 | Reforged |
|---|------|----------------|----------|
| 1 | Architecture | Flask + Jinja2 monolith | Frontend-backend separation (SPA + REST API) |
| 2 | Backend | Flask | FastAPI + Pydantic models + proper parameter binding |
| 3 | Frontend | Jinja2 server-rendered | Vue 3 SPA + Element Plus component library |
| 4 | UI Design | Original styling | Dark glassmorphism (deep blue sidebar, glass cards, indigo accent) |
| 5 | Auth library | passlib | Native bcrypt (Python 3.13 compatibility fix) |
| 6 | PreAuthKey | Wrong user field type | Fixed to uint64 ID |
| 7 | Data handling | — | Correctly parses headscale API nested response structures |
| 8 | Settings | — | Lock/unlock mode + password confirmation for sensitive operations |
| 9 | ACL editor | — | Full-height dark editor with line numbers and JSON formatting |
| 10 | Dashboard | — | Real-time CPU/memory/traffic monitoring with correct API field mapping |

### UI Highlights

- **Login page**: Left-right split layout + puzzle slider CAPTCHA
- **Standalone registration page**: Dedicated registration flow
- **Sidebar**: Deep blue tone (`#0d1117`)
- **Card components**: `backdrop-filter: blur` glassmorphism effect
- **Accent color**: Indigo (`#4f46e5`)

### Features

- **User management** — CRUD, expiration, node quota, route permissions, enable/disable
- **Node management** — List, search, filter by user, rename, delete, route details
- **Route management** — List, enable/disable toggle
- **Preauthkey management** — Create (expiry/reusable/ephemeral), delete, one-click copy
- **ACL rule editor** — HuJSON support, formatting, line numbers
- **System settings** — Headscale connection, API key, registration policy, security lock
- **Operation logs** — Paginated audit trail
- **Deployment guide** — Built-in deployment instructions page
- **Profile & password** — Edit profile and change password
- **Health monitoring** — Real-time headscale connection status in header bar

### Screenshots

> Screenshots coming soon.

<!-- 
![Login](docs/screenshots/login.png)
![Dashboard](docs/screenshots/dashboard.png)
![Nodes](docs/screenshots/nodes.png)
-->

### Quick Start

#### Prerequisites

- Python 3.13+
- Node.js 18+ & npm
- Nginx
- [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) (modified headscale binary, must run on the same server)

#### 1. Deploy the Backend

```bash
# Clone the repository
git clone https://github.com/chen1749144759/Headscale-Admin-Reforged.git
cd Headscale-Admin-Reforged/backend

# Set up virtual environment and install dependencies
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the backend (default port 5175)
uvicorn main:app --host 0.0.0.0 --port 5175
```

**systemd service example:**

```ini
[Unit]
Description=Headscale Admin Reforged Backend
After=network.target

[Service]
Type=simple
User=headscale-admin
WorkingDirectory=/opt/Headscale-Admin-Reforged/backend
ExecStart=/opt/Headscale-Admin-Reforged/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 5175
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 2. Build and Deploy the Frontend

```bash
cd Headscale-Admin-Reforged/frontend

# Install dependencies and build
npm install
npm run build
```

Deploy the build output (`dist/`) to Nginx:

```bash
sudo cp -r dist/* /var/www/headscale-admin/
```

#### 3. Configure Nginx

```nginx
server {
    listen 5174;
    server_name _;

    root /var/www/headscale-admin;
    index index.html;

    # Vue Router history mode
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5175;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

#### 4. Access the Panel

Open your browser and navigate to `http://<your-server-ip>:5174`

### Configuration

| Setting | Description | Location |
|---------|-------------|----------|
| Backend port | Default `5175` | uvicorn startup args |
| Frontend port | Default `5174` | Nginx config |
| Headscale URL | Headscale HTTP API address | Panel "System Settings" page |
| API Key | Headscale API key | Panel "System Settings" page (supports auto-refresh) |
| Database | Shares headscale's SQLite/PostgreSQL | Backend config file |

### Roadmap

- [ ] Docker Compose one-click deployment
- [ ] Dark / Light mode toggle
- [ ] Dashboard charts (traffic trends, node activity)
- [ ] Multi-language i18n support (currently Chinese-only UI)
- [ ] OIDC / SSO integration
- [ ] Mobile responsive improvements

### Related Projects

| Project | Description |
|---------|-------------|
| [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) | Modified headscale binary required by this project |
| [Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) | Original project by arounyf |
| [headscale](https://github.com/juanfont/headscale) | Official headscale project |

### Contributing

Issues and Pull Requests are welcome. Before submitting a PR, please make sure:

1. The code builds successfully (frontend `npm run build` with no errors)
2. Backend API changes remain backward compatible
3. Commit messages clearly describe the changes

### License

This project is open-sourced under the [MIT License](LICENSE).
