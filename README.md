# ScaleForge

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](#部署)

ScaleForge 是自建 ScaleTail 网络的管理平台，提供账户与网络分组、节点、路由、ACL、DNS、流量、安全审计、客户端策略和签名 OTA 版本管理。它与 [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) 和 [ScaleTail](https://github.com/chen1749144759/ScaleTail) 配套使用。

当前分支采用单一账户密码体系：用户不再创建或复制预认证密钥，客户端也不再进入浏览器注册流程。Headscale `users` 仅表示网络分组，登录身份由 Headscale `accounts` 统一管理。

## 项目定位

| 项目 | 责任边界 |
|---|---|
| ScaleForge | Web 管理、账户管理、DNS、策略、流量、安全审计和 OTA 发布 |
| Headscale-Admin-AE | 账户认证、控制协议、节点注册、网络地图、路由和内嵌 DERP |
| ScaleTail | Windows/Linux 客户端、LocalAPI、TUN 数据面、状态上报和 OTA 执行 |

ScaleForge 不是控制面代理，也不保存能代替用户登录的长期 Headscale API Key。控制协议和设备身份始终由 Headscale-Admin-AE 处理。

## 架构与信任边界

```text
浏览器 --HTTPS--> Nginx
                    |
                    +-- /var/run/scaleforge/public/api.sock
                            |
                            v
                    ScaleForge Public API
                            |
                    /var/run/scaleforge/control/api.sock
                            |
                            v
                    Headscale-Admin-AE

ScaleTail --HTTP(S) 承载的 Noise 控制连接--> Headscale-Admin-AE
                                  |
                         已验证节点身份后转发
                                  |
                    /var/run/scaleforge/client/api.sock
                                  |
                                  v
                       ScaleForge Client API
```

- Nginx 只挂载 Web API UDS，不接触 Headscale 管理 Socket 或客户端上报 Socket。
- ScaleForge Public API 只读挂载 Headscale 管理 UDS，通过相对路径调用私有接口，不使用 TCP 管理端口。
- Client API 不暴露给浏览器或公网。Headscale 完成 Noise 和节点身份校验后，才通过独立 UDS 转发上报、策略和版本请求。
- ScaleTail 客户端密码不会发送到 ScaleForge。客户端先与 Headscale 建立 Noise 加密通道，再在该通道内提交账户证明；外层控制地址使用 HTTP 时，密码仍不会以明文出现在 HTTP 正文中。
- HTTP 首次连接采用 TOFU：ScaleTail 固定首次观察到的 Headscale Noise 公钥，后续公钥变化会阻断连接并要求人工确认。首次连接仍应在可信网络中完成或独立核对公钥指纹；HTTPS 可额外提供 PKI 身份校验，仍然推荐，但不是 Noise 账户登录的必要条件。
- Headscale 与两个 ScaleForge API 的双向 UDS 请求还必须通过共享 HMAC 密钥校验；签名绑定方法、路径、查询、正文摘要、时间戳、随机 nonce、授权头和节点/用户上下文，并拒绝超时与重放。
- 浏览器只持有 Headscale 生成的 opaque session Cookie；Cookie 使用 `Secure`、`HttpOnly`、`SameSite=Strict`。
- Headscale 与 ScaleForge 使用不同 PostgreSQL 运行角色；高权限数据库账户只用于 bootstrap 和迁移。
- 默认使用 Headscale 内嵌 DERP 并校验已注册客户端，不需要额外部署第三方 derper。

这些 Socket 只能通过 Compose 私有 volume 共享，不应映射为 TCP 端口，也不应挂载给无关容器。

## 账户密码

- 管理员通过账户页面创建账户，并将普通账户一对一绑定到网络分组。
- 普通账户只能查看和管理其分组内的节点与路由；管理员可查看全局数据。
- 初始管理员只在数据库尚无账户时，由 Docker secret `scaleforge_bootstrap_password` 创建；没有公开注册入口。
- 管理员重置密码后，账户必须在下次登录时修改初始密码。
- 修改密码不能复用当前密码和最近四个历史密码；更新会撤销旧管理会话，并要求节点在新的控制会话中重新完成账户证明。
- 密码自最后修改起 90 天有效。到期后 Web 会话只允许修改密码或退出，客户端新会话、上报与策略领取也会被拒绝，直至密码更新。
- ScaleTail Linux 交互登录使用 `--username` 并在终端内隐藏读取密码；自动化使用权限为 `0600` 的 `--password-file`。密码不能放进命令行、环境变量、镜像层或 Git。
- ScaleTail 在新的 Noise 控制会话内直接向 Headscale 证明账户密码，密码不经过 ScaleForge；设备密钥只负责协议加密和节点身份，不形成第二套用户可维护的认证体系。

示例：

```bash
# 交互式登录，随后隐藏提示输入密码
sudo scaletail login --login-server https://headscale.example.com --username alice

# 自动化登录：密码文件只包含一行密码
sudo install -m 600 /dev/null /etc/scaletail/account-password
sudoedit /etc/scaletail/account-password
sudo scaletail login --login-server https://headscale.example.com \
  --username alice \
  --password-file /etc/scaletail/account-password

# 登录成功后再配置路由，不重复执行登录流程
sudo scaletail set --advertise-routes=192.168.1.0/24 --accept-routes=true
```

## 功能

- 账户、网络分组、节点、路由与 ACL 管理。
- MagicDNS、全局 DNS、搜索域和覆盖本地 DNS 策略下发。
- 全局、分组和机器维度的流量统计、目标地址 TOP20、采样健康度与连接摘要。
- IP 观测、可信网络、风险规则、安全事件和管理操作审计。
- 全局、分组和机器三层客户端策略，按最小有效限额合并。
- Windows/Linux 客户端建议更新和强制更新发布。
- 客户端状态、流量、策略执行结果和版本检查通过经过 Headscale 验证的私有通道完成。

上传和下载限速均在 ScaleTail TUN 数据路径按整台机器聚合执行，只影响经过 ScaleTail 覆盖网络的流量。策略可热更新，不按进程或单连接分别限额；物理局域网直连和普通公网流量不在统计与限速范围内。

## DNS

管理入口为“系统设置 -> DNS 配置”。平台通过 Headscale 私有 UDS 读取并热更新：

- MagicDNS
- 是否覆盖本地 DNS
- 全局上游 DNS
- 搜索域

`HEADSCALE_DNS_DOMAIN` 是启动期基础域配置；其余 `.env` DNS 值用于首次渲染。之后应在 ScaleForge 页面管理，客户端还需要在 ScaleTail 中显式选择“采用服务端 DNS”。

## CAPTCHA

登录验证码使用自托管 [Cap](https://capjs.js.org/)。浏览器组件由前端依赖 `@cap.js/widget` 打包，不依赖运行时 CDN。

- `CAPTCHA_API_ENDPOINT`：浏览器 challenge 地址，必须包含正确 site key。
- `CAPTCHA_SITEVERIFY_URL`：后端校验地址。
- `CAPTCHA_SECRET_KEY`：对应站点 secret，只能存在于部署环境。
- challenge、siteverify 和 secret 必须属于同一个 Cap 站点。
- 生产地址必须使用 HTTPS；仅本机回环开发允许 HTTP。

暂不启用时可设置 `CAPTCHA_ENABLED=false`。公网管理端不建议关闭验证码。

## OTA 签名

ScaleForge 发布页保存单调递增的策略 revision、版本、平台、建议/强制/撤销动作、HTTPS 下载地址、文件大小、SHA-256 和 Ed25519 签名。签名覆盖以下规范化 v3 消息：

```text
scaletail-update-v3
<policy_revision>
<suggested|forced|clear>
<version>
<platform>
<sha256>
<file_size>
<canonical_download_url>
```

- `signature` 格式固定为 `v3.<Ed25519 Base64>`；v1/v2 签名一律拒绝。
- 发布策略只追加、不原地改写；客户端和 daemon 持久化最高 revision，拒绝旧策略重放和相同 revision 的内容替换。
- `clear` 是签名撤销记录，不携带安装包元数据；用于解除强制策略并按升级前状态恢复网络。
- 下载地址只接受无凭据、无片段的 HTTPS DNS 主机名，拒绝 `localhost`、回环/私网/链路本地 IP literal 及所有 IP literal。客户端会在下载前验签，并在每个重定向节点重复执行该校验。
- 客户端当前不预解析下载域名来拦截私网 DNS 结果；受信任下载域必须由发布运维控制，DNS 重绑定或恶意 DNS 指向私网是该层的残余风险。
- 私钥只存在于受控发布环境，不能放入 ScaleForge、客户端或仓库。
- ScaleForge 在保存和下发前使用内置公钥验签；无效或旧的未签名发布不会下发给客户端。
- ScaleTail 下载后再次核对 HTTPS 地址、大小、SHA-256 和 Ed25519 签名，再执行覆盖安装。
- 强制更新会阻止继续使用旧客户端；建议更新允许用户延后处理。

## 数据库迁移

Compose 启动顺序为 PostgreSQL -> 数据库角色 bootstrap -> Headscale -> `scaleforge-migrate` -> 两个 ScaleForge API -> Nginx。

- `migrations/*.sql` 按文件名排序执行。
- 已执行版本及 SHA-256 存在 `scaleforge_schema_migrations`。
- 已执行迁移不可修改；校验和变化会让启动失败，修复必须新增下一号迁移。
- `001_platform_schema.sql` 创建并接管平台表，将旧 `user_id/created_by` 所有权字段迁移到账户字段。
- `002_normalize_platform_defaults.sql` 回填旧流量摘要和 OTA 行的新增字段，并统一默认值与 `NOT NULL` 约束。
- `003_drop_legacy_platform_foreign_keys.sql` 移除平台表对旧 Headscale 用户语义的外键依赖。
- `004_client_release_policy_v3.sql` 将旧发布记录迁入追加式 OTA v3 策略表；无法形成有效签名策略的旧记录只保留审计信息。
- 老版本未签名 OTA 行会保留用于审计，但在补齐有效元数据和签名前不会下发。
- 升级不删除 PostgreSQL 数据卷，不需要重建数据库。

迁移使用数据库管理员账户，运行期 Headscale 和 ScaleForge 角色只获得各自所需权限。

## 部署

推荐使用 Linux、Docker Engine 和 Docker Compose v2。管理站点仍推荐配置可信 HTTPS；Headscale 控制地址可使用 origin-only 的 `http://` 或 `https://`，HTTP 部署依赖 Noise 加密与 ScaleTail TOFU 公钥固定。

1. 准备配置和初始管理员密码：

```bash
git clone https://github.com/chen1749144759/ScaleForge.git
cd ScaleForge/docker
cp .env.example .env
cp secrets/scaleforge_bootstrap_password.example secrets/scaleforge_bootstrap_password
openssl rand -hex 32 > secrets/scaleforge_internal_auth_key
chmod 600 .env
chown 0:10102 secrets/scaleforge_bootstrap_password
chmod 640 secrets/scaleforge_bootstrap_password
chown 0:10101 secrets/scaleforge_internal_auth_key
chmod 640 secrets/scaleforge_internal_auth_key
```

2. 编辑 `.env`，至少替换：

- `HEADSCALE_SERVER_URL`：客户端可达的 origin-only HTTP(S) 控制地址，例如 `http://211.137.214.34:60090` 或 `https://headscale.example.com`；不能包含用户信息、路径、查询参数或片段。
- `TRUSTED_ORIGINS`：管理端完整 HTTPS origin；多个值用英文逗号分隔。
- `HEADSCALE_TRUSTED_PROXY_CIDRS`：仅填写真实反向代理所在的最小 CIDR；不在列表内的来源不能提供客户端 IP 头。
- `DERP_DOMAIN`：内嵌 DERP 使用的域名。
- `POSTGRES_PASSWORD`、`HEADSCALE_DB_PASSWORD`、`SCALEFORGE_DB_PASSWORD`：三个不同的随机强密码。
- `CAPTCHA_API_ENDPOINT`、`CAPTCHA_SITEVERIFY_URL`、`CAPTCHA_SECRET_KEY`：启用 Cap 时必填。
- `AE_VERSION`、`BACKEND_VERSION`、`NGINX_VERSION`：生产环境应固定到明确镜像标签，不长期使用 `latest`。

将初始管理员密码写入 `secrets/scaleforge_bootstrap_password`。`scaleforge_internal_auth_key` 必须是至少 32 字节的独立随机值，两个 secret 都不能写入 README、`.env.example`、Compose、镜像或命令历史。

Compose 以宿主机文件绑定方式挂载 secret，因此权限会原样进入容器。固定 GID `10102` 供 Headscale 读取 bootstrap secret，固定 GID `10101` 供 Headscale 与 ScaleForge 共同读取内部认证密钥；不要把这两个文件改回 `root:root 0600`。

3. 检查并启动：

```bash
./manage-account-stack.sh preflight
./manage-account-stack.sh upgrade
```

4. 验证：

```bash
curl -fsS http://127.0.0.1/api/health
curl -fsS http://127.0.0.1:8080/health
docker exec scaleforge-backend-public test -S /var/run/scaleforge/control/api.sock
docker exec scaleforge-headscale test -S /var/run/scaleforge/client/api.sock
```

默认 Web 和 Headscale 端口绑定到回环地址，PostgreSQL 和三个 UDS 不应暴露到公网。Nginx 不信任入站的 `X-Forwarded-Proto`，而是使用部署参数 `SCALEFORGE_EXTERNAL_SCHEME` 生成后端协议；外层 TLS 终止时保持 `https`。仅在隔离的直连 HTTP 开发环境中，才同时设置 `SCALEFORGE_EXTERNAL_SCHEME=http` 与 `SESSION_COOKIE_SECURE=false`。

## 保留数据升级

统一使用 [`docker/manage-account-stack.sh`](docker/manage-account-stack.sh) 完成预检、备份、镜像切换、健康等待和数据库结构核对：

```bash
cd ScaleForge/docker
./manage-account-stack.sh preflight
./manage-account-stack.sh upgrade
```

脚本会先拉取镜像，再把 `.env`、部署 secret、当前镜像引用、PostgreSQL custom-format dump、Headscale 状态卷和生成配置保存到权限为 `0700` 的 `docker/backups/<UTC时间>/`，随后仅重建有变化的容器。它不会执行 `docker compose down`、不会删除 PostgreSQL/Headscale 数据卷，也不会自动覆盖数据库进行回退。

更新前必须把 `.env` 中的 `AE_VERSION`、`BACKEND_VERSION`、`NGINX_VERSION` 固定到明确标签，并确认 Headscale 与两个 ScaleForge 后端挂载同一个 `scaleforge_internal_auth_key`。迁移默认等待数据库锁 15 秒、单条语句最多 5 分钟；需要调整时设置 `SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS` 和 `SCALEFORGE_MIGRATION_STATEMENT_TIMEOUT_MS`。从旧的“节点即用户”模型升级时，`005_account_user_groups.sql` 需要重写历史流量归属；若 `flow_summaries` 已超过 100 万行，建议只在该次升级命令前临时设置 `SCALEFORGE_MIGRATION_STATEMENT_TIMEOUT_MS=1800000`，迁移完成后继续使用默认值。

完整的构建、升级、断线处置和回退边界见 [`docker/ACCOUNT_UPGRADE.md`](docker/ACCOUNT_UPGRADE.md)。不要执行 `docker compose down -v`，该命令会删除数据库和 Headscale 状态卷。

### 首次引入私有 UDS 配置

旧的 Headscale 配置若没有 `scaleforge:` 段，Headscale 会拒绝启动并明确提示，不会静默退回旧 API Key 模式。

1. 先备份 Headscale 配置卷。
2. 在 `.env` 临时设置 `HEADSCALE_FORCE_RENDER_CONFIG=1`。
3. 执行一次受控重启，确认控制 UDS、客户端 UDS、登录和 DNS 正常。
4. 立即恢复 `HEADSCALE_FORCE_RENDER_CONFIG=0`，避免以后重启覆盖平台保存的 DNS 配置。

该开关只用于从旧配置过渡，不是长期运行选项。

### 账户升级注意事项

- 旧预认证密钥和浏览器注册流程不会继续工作；新节点必须使用支持账户密码的 ScaleTail 版本。
- 已注册节点在建立新的控制会话时同样需要兼容的新客户端完成账户证明。
- 0.0.8 之前的客户端不能验证 OTA v3 策略；先手工覆盖安装一次 0.0.8，后续版本才可走 daemon OTA 无感覆盖升级。
- 如果旧数据库含不受支持的 Werkzeug `scrypt:` 或 `pbkdf2:` 密码哈希，配套 Headscale 会失败关闭，而不会把哈希误当明文。升级前应先按配套服务端迁移说明重置这些账户密码。

## 本地开发与验证

后端：

```powershell
cd D:\workspace-qoder\ScaleForge
py -3 -m pip install -r requirements-prod.txt
py -3 -m pytest -q
```

前端：

```powershell
cd D:\workspace-qoder\ScaleForge\web
npm ci
npm run typecheck
npm run build
```

Compose 静态检查不需要 Docker daemon：

```powershell
cd D:\workspace-qoder\ScaleForge
docker compose -f docker\docker-compose.yml config --quiet
```

部署后还应从 Nginx 容器验证公共 UDS 代理链路：

```bash
docker exec scaleforge-nginx wget -qO- http://127.0.0.1/api/health
```

## 交流学习

欢迎加入 ScaleForge 交流群，交流自建 Headscale、ScaleTail、ScaleForge 的部署、使用和二次开发。

群号：`1041671099`

<img src="docs/images/scaleforge-qq-group.jpg" alt="ScaleForge 交流群" width="360">

## 打赏

如果项目帮你节省了部署和维护时间，可以请作者喝杯咖啡：

![打赏](docs/screenshots/donate.jpg)

## 致谢与许可

项目基于 [juanfont/headscale](https://github.com/juanfont/headscale)、[tailscale/tailscale](https://github.com/tailscale/tailscale) 生态裂变演进，并使用 FastAPI、Vue 3、Element Plus、PostgreSQL 和 Cap。使用和分发时请同时遵守本仓库及对应上游许可证。
