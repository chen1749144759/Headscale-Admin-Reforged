#!/bin/sh
set -e

CONFIG_TMPL="/etc/headscale/config.yaml.tmpl"
CONFIG_OUT="/etc/headscale/config.yaml"

# 用 envsubst 将模板中的 ${VAR} 替换为环境变量值
echo "[entrypoint] Rendering config from template..."
envsubst < "$CONFIG_TMPL" > "$CONFIG_OUT"
echo "[entrypoint] Config generated at $CONFIG_OUT"

# 启动 headscale
exec headscale serve -c "$CONFIG_OUT"
