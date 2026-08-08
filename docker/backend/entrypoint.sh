#!/bin/sh
set -eu

socket_path="${SCALEFORGE_SOCKET:?SCALEFORGE_SOCKET is required}"
application="${SCALEFORGE_APP:?SCALEFORGE_APP is required}"
socket_owner=10001
socket_group=10101
socket_dir="$(dirname "$socket_path")"

case "$socket_path" in
  /var/run/scaleforge/public/api.sock|/var/run/scaleforge/client/api.sock) ;;
  *)
    echo "[entrypoint] unsupported SCALEFORGE_SOCKET path: $socket_path" >&2
    exit 1
    ;;
esac

for path in /var/run/scaleforge "$socket_dir"; do
  if [ -L "$path" ]; then
    echo "[entrypoint] refusing symbolic-link socket directory: $path" >&2
    exit 1
  fi
done

install -d -m 2750 -o "$socket_owner" -g "$socket_group" "$socket_dir"
rm -f "$socket_path"

umask 007
if [ "${SCALEFORGE_TRUST_PROXY:-false}" = "true" ]; then
  exec gosu scaleforge uvicorn "$application" \
    --uds "$socket_path" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*'
fi

exec gosu scaleforge uvicorn "$application" --uds "$socket_path" --workers 1
