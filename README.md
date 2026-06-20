# ScaleForge

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.x-409EFF)](https://element-plus.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](#部署难度)
[![Headscale](https://img.shields.io/badge/Headscale--Admin--AE-v0.28.0%20%2B%20v0.29.1%20fixes-326CE5)](https://github.com/chen1749144759/Headscale-Admin-AE)

ScaleForge 是面向自建 Headscale/ScaleTail 网络的 Web 管理平台。它提供图形化的用户、节点、路由、ACL、预认证密钥、流量统计、客户端策略和安全审计能力，推荐与 `Headscale-Admin-AE` 和 `ScaleTail` 一起部署。

仓库地址：[chen1749144759/ScaleForge](https://github.com/chen1749144759/ScaleForge)

## 版本定位

| 项目项 | 当前说明 |
|---|---|
| 裂变来源 | 基于 `arounyf/Headscale-Admin-Pro v4.0.0` 的产品思路和管理能力重写 |
| 架构变化 | 从 Flask/Jinja 单体管理面板重构为 FastAPI + Vue 3 前后端分离架构 |
| 当前对标 | 配套 `Headscale-Admin-AE`，其基础为官方 headscale `v0.28.0`，并已回补官方 headscale `v0.29.1` 关键修复 |
| 客户端对标 | 配套 `ScaleTail`，客户端核心按 Tailscale `v1.98.5` 关键修复审计 |
| 默认数据库 | PostgreSQL 16，开发环境可使用 SQLite |
| 默认部署 | Docker Compose |

ScaleForge 本身不是 headscale 控制面进程，它是管理平台。真正处理节点注册、网络地图、控制协议的是 `Headscale-Admin-AE`；ScaleForge 通过共享数据库和 API 完成可视化管理。

## 自实现功能

- FastAPI 后端，提供 JWT 登录、用户资料、系统状态、节点、路由、ACL、预认证密钥、日志和部署状态 API。
- Vue 3 + Vite + Element Plus 前端，提供现代化管理后台界面。
- 支持 Cap 挑战验证码登录流程，后端登录接口执行二次校验。
- 用户/分组管理：管理 Headscale 用户命名空间、账户状态、过期时间、节点配额、路由权限。
- 节点管理：列表、搜索、重命名、删除、过期、移动分组、标签管理。
- 路由管理：查看、批准、撤销子网路由和出口节点相关路由。
- ACL 管理：在线读取、编辑、保存和重载 ACL/HuJSON 策略。
- 预认证密钥管理：创建、删除、复制，支持过期时间、可复用、临时节点等选项。
- 操作日志：记录平台侧关键管理操作。
- 流量统计：按全局、分组、机器展示收发流量、峰值速率和采样记录。
- 请求分析：接收 ScaleTail 客户端上报的连接摘要，统计目标 IP、端口、进程和连接次数。
- 客户端策略：配置全局、分组、机器三层上传限速、下载限速字段、月流量配额、超额动作。
- 安全审计：安全事件、IP 观测历史、可信网络、风险规则管理。
- IP 定位：支持可选外部 IP 地理信息接口；未配置时不会影响上报，只是不补充地理字段。
- 客户端上报接口：使用 `SCALETAIL_CLIENT_TOKEN` 或 `config.yaml: client_report_token` 作为共享密钥。

## 新增数据表

| 表名 | 用途 |
|---|---|
| `client_policies` | 全局、分组、机器维度客户端策略 |
| `client_policy_states` | 客户端策略应用状态回传 |
| `traffic_samples` | 原始流量采样 |
| `traffic_hourly` | 小时级聚合流量 |
| `traffic_daily` | 日级聚合流量 |
| `flow_summaries` | 客户端请求/连接摘要 |
| `node_ip_observations` | 节点公网 IP 观测和定位历史 |
| `security_events` | 安全事件 |
| `trusted_networks` | 可信 IP/CIDR/ASN/国家规则 |
| `risk_rules` | 安全风险规则配置 |

这些表也会在 `Headscale-Admin-AE` 启动时同步创建，避免服务端和管理平台字段不一致。

## 部署难度

| 场景 | 难度 | 说明 |
|---|---:|---|
| Docker Compose 一键部署 | 中 | 推荐方式。一次启动 PostgreSQL、Headscale-Admin-AE、ScaleForge 后端、Nginx 前端等组件。 |
| 只部署 ScaleForge 管理平台 | 中 | 适合已有 Headscale-Admin-AE 和数据库的场景，需要正确配置 API、数据库和 token。 |
| 源码开发运行 | 中高 | 需要 Python 3.13、Node.js、PostgreSQL、前后端分别启动。 |
| 从官方 headscale 迁移 | 高 | 需要确认数据库结构、配置文件、ACL、DERP、预认证密钥和客户端登录状态。 |

部署成败最关键的几项配置：

- 数据库连接必须和 Headscale-Admin-AE 使用同一套库。
- `SCALETAIL_CLIENT_TOKEN` 要和 ScaleTail 客户端页面里的上报密钥一致。
- 如果开启 IP 定位，需要配置 `IP_GEOLOOKUP_URL`，例如支持 `{ip}` 占位符的查询接口。
- Nginx 需要正确反代 `/api/*` 到 FastAPI，必要时反代 `/hs/*` 到 Headscale-Admin-AE。

## 快速部署

推荐使用 Docker Compose：

```bash
cd docker
cp .env.example .env
# 修改 .env 中的域名、数据库、token、DERP 和管理员配置
docker compose up -d
```

常见端口：

| 服务 | 默认端口 |
|---|---:|
| Nginx / Web 入口 | 80 |
| ScaleForge API | 5175 |
| Headscale-Admin-AE | 8080 |
| PostgreSQL | 5432 |
| DERP/STUN | 3478/3479，按 compose 配置为准 |

## 本地开发

后端：

```bash
cd api
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 5175 --reload
```

前端：

```bash
cd web
npm install
npm run dev
npm run build
```

## 与三件套关系

```text
ScaleTail 客户端
  | 定时上报流量/请求摘要/策略状态
  v
ScaleForge 管理平台
  | 共享数据库/API 管理用户、节点、路由、ACL、策略和安全事件
  v
Headscale-Admin-AE 控制服务
```

ScaleForge 负责看得见和管得动；Headscale-Admin-AE 负责控制协议和节点注册；ScaleTail 负责客户端连接和桌面体验。

## 当前已验证

- 后端核心文件使用 `py -3 -m py_compile` 编译通过。
- 前端 `npm run build` 构建通过。
- 新增路由已注册到 `api/main.py` 和 `api/routers/__init__.py`。
- 前端 API 调用路径已和后端路由核对。
- 数据库新增表和 Headscale-Admin-AE 启动同步逻辑已核对。

## 已知边界

- `rate_down_mbps` 字段已经存在，也会下发给客户端，但 ScaleTail 暂未做下载方向 TUN/内核级强制限速。
- Windows 上传限速依赖客户端侧 QoS，权限不足时会回传策略应用失败，不会阻塞平台。
- IP 定位是可选增强能力，未配置不会报错。
- 如果数据库用户没有建表/建索引权限，首次启动会影响新增功能表初始化。

## 打赏

如果这个项目帮你节省了部署和维护时间，可以请作者喝杯咖啡：

![打赏](docs/screenshots/donate.jpg)

感谢支持，项目会继续围绕自建 Headscale/ScaleTail 网络的易用性、稳定性和安全可视化迭代。

## 致谢

- [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro)
- [juanfont/headscale](https://github.com/juanfont/headscale)
- [tailscale/tailscale](https://github.com/tailscale/tailscale)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
