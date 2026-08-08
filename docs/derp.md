# ScaleTail DERP 说明

当前 Compose 使用 Headscale-Admin-AE 内嵌 DERP，不再部署独立第三方 derper。DERP 只在节点无法建立点对点连接时转发端到端加密数据，不能解密 ScaleTail 流量。

## 部署约束

- `DERP_DOMAIN` 必须解析到 Headscale 所在主机，并由可信 TLS 入口提供服务。
- `DERP_STUN_PORT` 默认为 UDP `3478`，需要在主机防火墙和上游网络放行。
- 服务端启用已注册客户端校验；不要设置 `insecurefortests`，也不要关闭客户端验证来规避证书或注册问题。
- DERP、Headscale 控制地址和 ScaleForge 管理站点可以共用主机，但管理 UDS 和客户端上报 UDS 不能暴露到公网。

## 验证

在已完成账户密码登录的 ScaleTail 节点执行：

```bash
scaletail netcheck
scaletail ping <对端 ScaleTail IP>
```

`netcheck` 应显示可达的 DERP 区域。`ping` 会优先尝试直连；无法直连时回退到 DERP。排障时同时检查公网域名、TLS 证书、UDP 3478、防火墙和 Headscale 日志。

账户登录、私有 UDS 和完整部署步骤以[根 README](../README.md)为准。
