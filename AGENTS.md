# ScaleForge 项目协作规则

本文件是 ScaleForge 仓库的项目级约束。处理本仓库时，优先级高于通用规范和个人习惯；如与上级系统/安全规则冲突，以上级规则为准。

## 项目识别

- 项目名称：ScaleForge。
- 本地路径：`D:\workspace-qoder\ScaleForge`。
- 项目类型：自建 Headscale/ScaleTail 网络的全栈管理后台。
- 前端：Vue 3 + Vite + Element Plus + Pinia + Vue Router。
- 后端：Python 3.13 + FastAPI + Uvicorn。
- 数据库：PostgreSQL 16，管理端与 `Headscale-Admin-AE` 共享业务数据库。
- 数据访问：后端主要使用 `psycopg2` 和项目内工具函数，不默认引入 ORM。
- 配置读写：使用 `ruamel.yaml`，不要改成普通字符串拼接。
- 默认部署：Docker Compose。

## 关联项目边界

- `D:\workspace-qoder\ScaleForge`：管理平台，负责账户、用户/机器、路由、ACL、预认证密钥、流量统计、安全审计、客户端策略、客户端版本发布、DNS 下发配置。
- `D:\workspace-qoder\Headscale-Admin-AE`：Headscale 控制服务裂变项目，负责控制面协议、节点注册、路由宣告、策略执行、数据库初始化等核心服务端能力。
- `D:\workspace-qoder\tailscale-main`：ScaleTail 客户端，负责 Windows Electron UI、LocalAPI/daemon 通信、客户端上报、策略领取、版本更新提示。
- ScaleForge 不直接替代 headscale 控制面；涉及节点注册、控制协议、路由宣告和核心数据库结构时，必须核对 `Headscale-Admin-AE`。

## 目录约定

- 后端入口：`api/main.py`。
- 后端路由：`api/routers/*.py`。
- 后端公共依赖和数据库初始化：`api/routers/dependencies.py`。
- 前端入口：`web/src/main.js`。
- 前端路由：`web/src/router/index.js`。
- 前端主布局和左侧菜单：`web/src/views/Layout.vue`。
- 系统设置和 DNS 下发页面：`web/src/views/Settings.vue`。
- Docker Compose：`docker/docker-compose.yml`。
- Headscale 配置模板：`docker/config.yaml.tmpl`。
- Headscale 容器入口：`docker/entrypoint.sh`。
- Nginx 配置：`docker/nginx/nginx.conf`。

## 修改前安全规则

- 修改已有文件前，先备份到 `D:\codex_backups\ScaleForge`，允许覆盖上一次备份。
- 不要回滚用户未说明要回滚的改动。
- 不要把已有文件的修改委派给子任务代理。
- 不要把生产 `.env`、真实 token、验证码 secret、数据库密码、GitHub token 写进仓库或最终回复。
- 新增配置时优先使用 `.env` 和 Docker Compose 环境变量；默认值只能放非敏感值。

## 后端开发规则

- 新接口放入对应的 `api/routers/*.py`，并确认 `api/main.py` 已注册 router。
- 管理员权限沿用现有 `get_current_user`、`require_manager` 等依赖，不要另起权限体系。
- 涉及数据库表结构时，先查看 `api/routers/dependencies.py` 中的初始化/迁移逻辑，并同步确认 `Headscale-Admin-AE` 是否也需要创建同样字段或表。
- 新增表或字段要保证老数据库可增量启动，不依赖手动清空 PostgreSQL 数据卷。
- YAML 配置用 `ruamel.yaml` 读写，避免破坏 Headscale 配置结构。
- 后端健康检查固定为 `/api/health`，部署后必须验证。

## 前端开发规则

- 页面框架跟随现有 Vue 3 + Element Plus，不引入新的 UI 框架。
- 新页面必须注册到 `web/src/router/index.js`。
- 左侧菜单入口在 `web/src/views/Layout.vue` 维护。
- 管理员页面必须设置 `meta: { requiresManager: true }`，并在菜单项上设置 `managerOnly: true`。
- 新增“查看、进入、打开、跳转”类操作必须有真实路由或真实弹窗，不用 Toast 代替目标页面。
- 修改页面后必须运行 `npm run build`。
- Nginx 静态资源规则：`/assets/` 可长缓存，`/` 和 `/index.html` 必须 no-cache，避免部署后浏览器继续使用旧入口。

## DNS 下发业务线

- 平台侧入口是 `系统管理 -> DNS 配置`，路由为 `/settings/dns`。
- 后端接口仍复用 `/api/settings`，字段包括：
  - `dns_magic_dns`
  - `dns_base_domain`
  - `dns_override_local`
  - `dns_global_nameservers`
  - `dns_search_domains`
  - `headscale_config_path`
  - `headscale_config_writable`
- 部署时 Headscale 容器把配置写到 `/var/lib/headscale/config.yaml`。
- ScaleForge backend 通过同一个 `headscale-data` volume 以 `/data/headscale/config.yaml` 读写配置。
- Docker 环境变量包括：
  - `HEADSCALE_DNS_DOMAIN`
  - `HEADSCALE_MAGIC_DNS`
  - `HEADSCALE_DNS_OVERRIDE_LOCAL`
  - `HEADSCALE_DNS_GLOBAL`
  - `HEADSCALE_DNS_SEARCH_DOMAINS`
  - `HEADSCALE_CONFIG_PATH`
- 保存 DNS 后，配置写入 ScaleForge 配置和 Headscale 配置文件；完整生效通常需要重启 Headscale 服务。
- 客户端侧只配置“是否采用服务端 DNS”，DNS 地址由服务端下发，避免每台客户端手填。

## 验证码规则

- 登录验证码使用 Cap CAPTCHA。
- 前端 challenge 配置使用 `CAPTCHA_WIDGET_SRC` 和 `CAPTCHA_API_ENDPOINT`。
- 后端二次校验使用 `CAPTCHA_SITEVERIFY_URL` 和 `CAPTCHA_SECRET_KEY`。
- challenge endpoint 和 siteverify 必须对应同一套 Cap 服务和站点。
- `CAPTCHA_SECRET_KEY` 只能存在部署环境 `.env` 或容器环境变量中，不得提交。
- 前端报 `Invalid site key or secret` 时，优先检查：
  - `CAPTCHA_API_ENDPOINT` 是否包含正确 site key 和末尾 `/`。
  - `CAPTCHA_SITEVERIFY_URL` 是否能从 backend 容器访问。
  - `CAPTCHA_SECRET_KEY` 是否进入 backend 容器环境。

## 客户端上报和策略

- `SCALETAIL_CLIENT_TOKEN` 只用于 ScaleTail 客户端上报、策略领取、版本检查。
- `SCALETAIL_CLIENT_TOKEN` 不影响 Headscale 控制面连接，不要把客户端连不上误判为该 token 问题。
- 客户端版本发布在 ScaleForge 管理端维护，ScaleTail 客户端通过上报/检查通道获取建议更新或强制更新策略。
- 限速策略按全局、分组、机器三层取最小有效值；当前业务概念中“机器就是用户，用户为分组”。
- 下载限速目前仍是 TODO，不要在文档或 UI 中宣称已实现 TUN/内核级强制下载限速。

## Docker 镜像和版本

- ScaleForge backend 镜像：`chenzeshi/scaleforge-backend`。
- ScaleForge nginx 镜像：`chenzeshi/scaleforge-nginx`。
- Headscale 服务镜像：`chenzeshi/headscale-admin-ae`。
- 远端可使用镜像加速前缀 `docker.1ms.run/`，通过 `.env` 的 `REGISTRY_MIRROR` 控制。
- 推荐 tag 规则：`YYYYMMDD-短提交号`，同时可更新 `latest`。
- Compose 使用以下版本变量：
  - `AE_VERSION`
  - `BACKEND_VERSION`
  - `NGINX_VERSION`
- 构建并推送后，远端 `.env` 必须切到对应 tag，避免“部署产物和 Git 提交对不上”。

## 远端部署

- 当前远端服务器：`10.2.0.240`，root ssh key 免密。
- 当前部署目录：`/opt/headscale-admin`。
- 远端备份目录：`/root/codex_backups/scaleforge`。
- 部署前先备份远端 `.env`：
  - `cp /opt/headscale-admin/.env /root/codex_backups/scaleforge/opt-headscale-admin/.env`
- 不要动 PostgreSQL 数据卷，除非用户明确要求重置数据。
- 只更新前端或管理后端时，优先只重启 `admin-backend` 和 `nginx`。
- 修改 Headscale 配置模板、DNS、DERP 或核心控制面能力时，才重启 `headscale`。
- 部署后至少验证：
  - `docker compose ps`
  - `curl -sf http://127.0.0.1/api/health`
  - `curl -sf http://127.0.0.1:60090/health`
  - `curl -sI http://127.0.0.1/`，确认入口 HTML no-cache

## 常用本地验证命令

```powershell
cd D:\workspace-qoder\ScaleForge
git diff --check
py -3 -m py_compile api\routers\settings.py gen-config.py update-config.py
cd web
npm run build
```

```powershell
cd D:\workspace-qoder\ScaleForge
docker compose -f docker\docker-compose.yml config
wsl sh -n /mnt/d/workspace-qoder/ScaleForge/docker/entrypoint.sh
```

## 常用构建命令

```powershell
cd D:\workspace-qoder\ScaleForge
docker build -f docker\backend\Dockerfile -t chenzeshi/scaleforge-backend:YYYYMMDD-commit -t chenzeshi/scaleforge-backend:latest .
docker build -f docker\nginx\Dockerfile -t chenzeshi/scaleforge-nginx:YYYYMMDD-commit -t chenzeshi/scaleforge-nginx:latest .
docker push chenzeshi/scaleforge-backend:YYYYMMDD-commit
docker push chenzeshi/scaleforge-nginx:YYYYMMDD-commit
```

## 提交规则

- 提交前运行与改动相关的最小验证。
- 每次改动完成后，默认必须完成最小验证、提交并 push 到当前远端分支。
- 除非用户明确说“先别提交”“先别 push”“只本地改”，否则不要停在未提交或只本地提交状态。
- 如果同一轮涉及 `ScaleTail`、`ScaleForge`、`Headscale-Admin-AE` 多仓库，必须分别提交并分别 push。
- 如果发现已有未提交改动，先区分本次改动和用户已有改动，向用户说明后再决定是否纳入提交；不要混入未确认的无关改动。
- 提交信息要说明业务含义，例如 `feat: add managed DNS settings`。
- README、部署文档、Docker Compose、前后端接口字段同时变化时，必须一起核对，避免页面能保存但容器环境不生效。
- 推送前确认 `git status --short --branch`，不要夹带临时构建产物或密钥文件；推送后再次确认工作区状态。
