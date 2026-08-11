# 账户体系快速升级

本流程用于把现有 ScaleForge、Headscale-Admin-AE 和 PostgreSQL 数据升级到账号密码认证体系。升级脚本不会执行 `docker compose down`，不会删除卷，也不会自动恢复数据库。

## 前置条件

- `HEADSCALE_SERVER_URL` 必须是客户端可达、仅包含 scheme/host/可选端口的 `http://` 或 `https://` origin；禁止用户信息、路径、查询参数和片段。
- `.env` 中 `AE_VERSION`、`BACKEND_VERSION`、`NGINX_VERSION` 必须固定为明确标签，不能使用 `latest`。
- `secrets/scaleforge_bootstrap_password` 必须非空。
- `secrets/scaleforge_internal_auth_key` 必须是至少 32 字节的独立随机值。
- 远端服务器需要 Docker Engine 和 Docker Compose v2。

ScaleTail 客户端密码不会经过 ScaleForge。客户端先与 Headscale 建立 Noise 加密通道，再在该通道内提交账户证明，因此使用 HTTP 控制地址时密码也不会作为明文 HTTP 正文发送。HTTP 首次连接采用 TOFU 固定 Headscale Noise 公钥，后续公钥变化会直接阻断连接；首次连接应在可信网络完成或独立核对公钥指纹。HTTPS 能额外提供证书身份校验，仍然推荐，但不是客户端账户登录的必要条件。

## 本地构建

Docker daemon 可用时，在 ScaleForge 仓库执行：

```bash
./docker/build-account-images.sh --push
```

脚本会输出应写入远端 `docker/.env` 的三个镜像标签。不能访问 Docker Hub 时，可使用 `--save /secure/output` 导出离线镜像包。

## 远端升级

把三个镜像标签写入 `.env` 后执行：

```bash
cd /opt/headscale-admin
./manage-account-stack.sh preflight
./manage-account-stack.sh upgrade
```

`upgrade` 的执行顺序固定为：拉取镜像、备份数据库、Headscale 状态/配置和部署配置、重建有变化的容器、等待三个服务健康、核对迁移记录和 `accounts` 表。备份位于 `backups/<UTC时间>/`，权限为 `0700`。

切换 Headscale 容器时，现有 ScaleTail 内网入口可能短暂断开。镜像拉取在切换前完成；如果网络长期未恢复，应停止后续人工操作并通过备用链路进入服务器查看：

```bash
./manage-account-stack.sh status
docker compose logs --tail=120 headscale scaleforge-migrate admin-backend-public admin-backend-client nginx
```

## 验证

升级脚本已自动执行基础验证。恢复内网后还需要人工验证：

1. ScaleForge 管理员账户可以登录并被要求按策略修改初始/过期密码。
2. Linux ScaleTail 可以使用账号密码登录，不再使用预认证 Key。
3. 节点、路由宣告、DNS、ACL 和客户端策略仍可读取。
4. `docker compose ps` 中常驻服务均为 running/healthy，`scaleforge-migrate` 为成功退出。

## 回退边界

镜像回退只需恢复备份目录中的 `.env` 并再次执行 `docker compose up -d --remove-orphans`。账户迁移、密码哈希和节点有效期属于数据库状态；需要数据库回退时必须先停止写入，并由管理员明确确认后使用对应的 `postgres.dump` 恢复。脚本不会自动覆盖生产数据库。
