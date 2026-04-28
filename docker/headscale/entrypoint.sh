#!/bin/sh
set -e

CONFIG_TMPL="/etc/headscale/config.yaml.tmpl"
CONFIG_OUT="/etc/headscale/config.yaml"
API_KEY_FILE="/var/lib/headscale/api.key"

# 1. 用 envsubst 渲染配置模板
echo "[entrypoint] Rendering config from template..."
envsubst < "$CONFIG_TMPL" > "$CONFIG_OUT"
echo "[entrypoint] Config generated at $CONFIG_OUT"

# 2. 后台启动 headscale
headscale serve -c "$CONFIG_OUT" &
HS_PID=$!

# 3. 等待 headscale 就绪
echo "[entrypoint] Waiting for headscale to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo "[entrypoint] Headscale is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[entrypoint] WARNING: headscale health check timeout, continuing anyway..."
  fi
  sleep 1
done

# 4. 自动创建 API Key（仅首次，文件不存在时）
if [ ! -f "$API_KEY_FILE" ]; then
  echo "[entrypoint] Creating initial API key..."
  API_KEY=$(headscale -c "$CONFIG_OUT" apikey create 2>/dev/null || true)
  if [ -n "$API_KEY" ]; then
    echo "$API_KEY" > "$API_KEY_FILE"
    echo "[entrypoint] API key created and saved to $API_KEY_FILE"
  else
    echo "[entrypoint] WARNING: Failed to create API key, you may need to create it manually:"
    echo "  docker exec hs-headscale headscale apikey create"
  fi
else
  echo "[entrypoint] API key file already exists, skipping creation."
fi

# 5. 前台等待 headscale 进程
wait $HS_PID
