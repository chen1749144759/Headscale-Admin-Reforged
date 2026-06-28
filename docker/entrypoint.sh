#!/bin/sh
set -e

CONFIG_TMPL="/etc/headscale/config.yaml.tmpl"
CONFIG_OUT="${HEADSCALE_CONFIG_OUT:-/var/lib/headscale/config.yaml}"
DERP_TMPL="/etc/headscale/derp.yaml.tmpl"
DERP_OUT="/etc/headscale/derp.yaml"
API_KEY_FILE="/var/lib/headscale/api.key"
CERT_DIR="/etc/headscale/derp-certs"

render_yaml_list() {
  input="$1"
  fallback="$2"
  if [ -z "$input" ]; then
    input="$fallback"
  fi
  printf '%s' "$input" | awk -v RS='[,;]' '
    {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      if ($0 != "") {
        printf "      - %s\n", $0
      }
    }
  '
}

HEADSCALE_MAGIC_DNS="${HEADSCALE_MAGIC_DNS:-true}"
HEADSCALE_DNS_OVERRIDE_LOCAL="${HEADSCALE_DNS_OVERRIDE_LOCAL:-true}"
HEADSCALE_DNS_GLOBAL_YAML="$(render_yaml_list "${HEADSCALE_DNS_GLOBAL:-}" "1.1.1.1,8.8.8.8")"
HEADSCALE_DNS_SEARCH_YAML=""
if [ -n "${HEADSCALE_DNS_SEARCH_DOMAINS:-}" ]; then
  HEADSCALE_DNS_SEARCH_YAML="  search_domains:
$(render_yaml_list "$HEADSCALE_DNS_SEARCH_DOMAINS" "")"
fi
export HEADSCALE_MAGIC_DNS HEADSCALE_DNS_OVERRIDE_LOCAL HEADSCALE_DNS_GLOBAL_YAML HEADSCALE_DNS_SEARCH_YAML

if [ -f "$CONFIG_TMPL" ] && [ -n "$HEADSCALE_SERVER_URL" ]; then
  mkdir -p "$(dirname "$CONFIG_OUT")"
fi

if [ -f "$CONFIG_TMPL" ] && [ -n "$HEADSCALE_SERVER_URL" ] && { [ ! -f "$CONFIG_OUT" ] || [ "${HEADSCALE_FORCE_RENDER_CONFIG:-0}" = "1" ]; }; then
  echo "[entrypoint] Rendering config from template..."
  envsubst < "$CONFIG_TMPL" > "$CONFIG_OUT"
  echo "[entrypoint] Config generated at $CONFIG_OUT"
elif [ -f "$CONFIG_OUT" ]; then
  echo "[entrypoint] Keeping existing config at $CONFIG_OUT"
fi

if [ -f "$DERP_TMPL" ] && [ -n "$DERP_DOMAIN" ]; then
  echo "[entrypoint] Rendering DERP map from template..."
  envsubst < "$DERP_TMPL" > "$DERP_OUT"
  echo "[entrypoint] DERP map generated at $DERP_OUT"
fi

if [ -n "$DERP_DOMAIN" ]; then
  CERT_FILE="$CERT_DIR/$DERP_DOMAIN.crt"
  KEY_FILE="$CERT_DIR/$DERP_DOMAIN.key"
  mkdir -p "$CERT_DIR"
  if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    if command -v openssl >/dev/null 2>&1; then
      echo "[entrypoint] Generating self-signed TLS certificate for DERP ($DERP_DOMAIN)..."
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
      echo "[entrypoint] WARNING: openssl is not installed; skipping DERP certificate generation."
    fi
  else
    echo "[entrypoint] DERP certificate already exists, skipping generation."
  fi
fi

if [ ! -f "$CONFIG_OUT" ]; then
  echo "[entrypoint] ERROR: No config.yaml found at $CONFIG_OUT"
  exit 1
fi

headscale serve -c "$CONFIG_OUT" &
HS_PID=$!

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

wait "$HS_PID"
