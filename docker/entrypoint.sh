#!/bin/sh
set -e

CONFIG_TMPL="/etc/headscale/config.yaml.tmpl"
CONFIG_OUT="/etc/headscale/config.yaml"
DERP_TMPL="/etc/headscale/derp.yaml.tmpl"
DERP_OUT="/etc/headscale/derp.yaml"
API_KEY_FILE="/var/lib/headscale/api.key"
CERT_DIR="/etc/headscale/derp-certs"

# 1. 渲染 headscale 配置模板
if [ -f "$CONFIG_TMPL" ] && [ -n "$HEADSCALE_SERVER_URL" ]; then
  echo "[entrypoint] Rendering config from template..."
  envsubst < "$CONFIG_TMPL" > "$CONFIG_OUT"
  echo "[entrypoint] Config generated at $CONFIG_OUT"
fi

# 2. 渲染 DERP map 模板（独立 DERP 模式）
if [ -f "$DERP_TMPL" ] && [ -n "$DERP_DOMAIN" ]; then
  echo "[entrypoint] Rendering DERP map from template..."
  envsubst < "$DERP_TMPL" > "$DERP_OUT"
  echo "[entrypoint] DERP map generated at $DERP_OUT"
fi

# 3. 自动生成 DERP 自签名证书（一键部署，无需手动创建）
if [ -n "$DERP_DOMAIN" ]; then
  CERT_FILE="$CERT_DIR/$DERP_DOMAIN.crt"
  KEY_FILE="$CERT_DIR/$DERP_DOMAIN.key"
  mkdir -p "$CERT_DIR"
  if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "[entrypoint] Generating self-signed TLS certificate for DERP ($DERP_DOMAIN)..."
    # 判断是 IP 还是域名
    if echo "$DERP_DOMAIN" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
      SAN="IP:$DERP_DOMAIN"
    else
      SAN="DNS:$DERP_DOMAIN"
    fi
    openssl req -x509 -newkey rsa:2048 \
      -keyout "$KEY_FILE" -out "$CERT_FILE" \
      -days 3650 -nodes \
      -subj "/CN=$DERP_DOMAIN" \
      -addext "subjectAltName=$SAN" 2>/dev/null
    echo "[entrypoint] DERP certificate generated at $CERT_DIR"
  else
    echo "[entrypoint] DERP certificate already exists, skipping generation."
  fi
fi

# 检查配置文件
if [ ! -f "$CONFIG_OUT" ]; then
  echo "[entrypoint] ERROR: No config.yaml found at $CONFIG_OUT"
  exit 1
fi

# 3. 后台启动 headscale
headscale serve -c "$CONFIG_OUT" &
HS_PID=$!

# 4. 等待 headscale 就绪
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

# 5. 自动创建 API Key（仅首次）
if [ ! -f "$API_KEY_FILE" ]; then
  echo "[entrypoint] Creating initial API key..."
  API_KEY=$(headscale -c "$CONFIG_OUT" apikey create 2>/dev/null || true)
  if [ -n "$API_KEY" ]; then
    echo "$API_KEY" > "$API_KEY_FILE"
    echo "[entrypoint] API key created and saved to $API_KEY_FILE"
  else
    echo "[entrypoint] WARNING: Failed to create API key"
    echo "  docker exec hs-headscale headscale apikey create"
  fi
else
  echo "[entrypoint] API key file already exists, skipping creation."
fi

# 6. 前台等待 headscale 进程
wait $HS_PID
