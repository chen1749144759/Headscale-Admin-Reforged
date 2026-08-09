#!/bin/sh
set -eu

umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir"

fail() {
  echo "ScaleForge upgrade: $*" >&2
  exit 1
}

compose() {
  docker compose "$@"
}

env_value() {
  value=$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" .env | tail -n 1 | tr -d '\r')
  case "$value" in
    \"*\") value=${value#\"}; value=${value%\"} ;;
    \'*\') value=${value#\'}; value=${value%\'} ;;
  esac
  printf '%s' "$value"
}

require_file() {
  [ -f "$1" ] || fail "missing required file: $1"
}

preflight() {
  command -v docker >/dev/null 2>&1 || fail "docker is not installed"
  docker info >/dev/null 2>&1 || fail "docker daemon is not available"
  docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not available"

  require_file .env
  require_file secrets/scaleforge_bootstrap_password
  require_file secrets/scaleforge_internal_auth_key
  [ -s secrets/scaleforge_bootstrap_password ] || fail "bootstrap password secret is empty"
  internal_key_bytes=$(wc -c < secrets/scaleforge_internal_auth_key | tr -d ' ')
  [ "$internal_key_bytes" -ge 32 ] || fail "internal authentication key must contain at least 32 bytes"

  control_url=$(env_value HEADSCALE_SERVER_URL)
  case "$control_url" in
    https://*) ;;
    *) fail "HEADSCALE_SERVER_URL must be a trusted HTTPS URL" ;;
  esac

  for variable in AE_VERSION BACKEND_VERSION NGINX_VERSION; do
    version=$(env_value "$variable")
    [ -n "$version" ] || fail "$variable must pin an explicit image tag"
    [ "$version" != "latest" ] || fail "$variable must not use latest"
  done

  chmod 0600 .env secrets/scaleforge_bootstrap_password secrets/scaleforge_internal_auth_key
  compose config --quiet
  echo "Preflight passed for $control_url"
}

backup_stack() {
  postgres_container=$(compose ps -q postgres)
  [ -n "$postgres_container" ] || fail "postgres is not running; refusing to create an empty backup"
  headscale_container=$(compose ps -q headscale)
  [ -n "$headscale_container" ] || fail "headscale is not running; refusing to create an incomplete backup"
  docker exec "$headscale_container" sh -ec 'command -v tar >/dev/null' || \
    fail "tar is unavailable in the headscale container"

  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  backup_dir="$script_dir/backups/$stamp"
  mkdir -p "$backup_dir/config"
  chmod 0700 "$script_dir/backups" "$backup_dir" "$backup_dir/config"
  cp -p .env "$backup_dir/config/.env"
  cp -p secrets/scaleforge_bootstrap_password "$backup_dir/config/scaleforge_bootstrap_password"
  cp -p secrets/scaleforge_internal_auth_key "$backup_dir/config/scaleforge_internal_auth_key"
  compose config --images > "$backup_dir/images.txt"

  database_partial="$backup_dir/postgres.dump.partial"
  if docker exec "$postgres_container" sh -ec \
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$database_partial"; then
    mv "$database_partial" "$backup_dir/postgres.dump"
  else
    rm -f "$database_partial"
    fail "PostgreSQL backup failed; no services were changed"
  fi

  for source in headscale-data:/var/lib/headscale headscale-config:/var/lib/headscale-config; do
    archive_name=${source%%:*}
    source_path=${source#*:}
    archive_partial="$backup_dir/$archive_name.tar.gz.partial"
    if docker exec "$headscale_container" tar -C "$source_path" -czf - . > "$archive_partial"; then
      mv "$archive_partial" "$backup_dir/$archive_name.tar.gz"
    else
      rm -f "$archive_partial"
      fail "failed to back up $source_path; no services were changed"
    fi
  done

  echo "Backup created: $backup_dir"
}

service_health() {
  [ -n "$(compose ps --status running -q headscale)" ] || return 1
  [ -n "$(compose ps --status running -q admin-backend-public)" ] || return 1
  [ -n "$(compose ps --status running -q admin-backend-client)" ] || return 1
  [ -n "$(compose ps --status running -q nginx)" ] || return 1
  compose exec -T headscale curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1 || return 1
  compose exec -T admin-backend-public curl -fsS \
    --unix-socket /var/run/scaleforge/public/api.sock \
    http://localhost/api/health >/dev/null 2>&1 || return 1
  compose exec -T admin-backend-client curl -fsS \
    --unix-socket /var/run/scaleforge/client/api.sock \
    http://localhost/internal/health >/dev/null 2>&1 || return 1
}

verify_database() {
  migration_count=$(compose exec -T postgres sh -ec \
    'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT count(*) FROM scaleforge_schema_migrations"' \
    | tr -d '\r[:space:]')
  case "$migration_count" in
    ''|*[!0-9]*) fail "invalid migration count returned by PostgreSQL" ;;
  esac
  [ "$migration_count" -ge "${SCALEFORGE_MIN_MIGRATIONS:-4}" ] || \
    fail "only $migration_count ScaleForge migrations are recorded"

  accounts_ready=$(compose exec -T postgres sh -ec \
    'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT CASE WHEN to_regclass('"'"'public.accounts'"'"') IS NULL THEN 0 ELSE 1 END"' \
    | tr -d '\r[:space:]')
  [ "$accounts_ready" = "1" ] || fail "accounts table is missing"
  echo "Database verified: $migration_count migrations, accounts table present"
}

verify_stack() {
  timeout_seconds=${SCALEFORGE_UPGRADE_TIMEOUT_SECONDS:-180}
  elapsed=0
  while [ "$elapsed" -lt "$timeout_seconds" ]; do
    if service_health; then
      verify_database
      compose ps
      echo "ScaleForge account stack is healthy"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done

  compose ps >&2 || true
  compose logs --tail=120 postgres db-bootstrap headscale scaleforge-migrate \
    admin-backend-public admin-backend-client nginx >&2 || true
  fail "stack did not become healthy within ${timeout_seconds}s"
}

upgrade_stack() {
  preflight
  echo "Pulling images before changing the running stack..."
  compose pull
  backup_stack
  echo "Applying pinned images without removing PostgreSQL or Headscale volumes..."
  compose up -d --remove-orphans
  verify_stack
}

usage() {
  cat >&2 <<'EOF'
Usage: ./manage-account-stack.sh preflight|backup|upgrade|verify|status

  preflight  Validate Docker, HTTPS, pinned image tags and secrets.
  backup     Back up PostgreSQL, .env, image references and deployment secrets.
  upgrade    Pull images, back up data, recreate changed services and verify them.
  verify     Wait for service health and verify migrations/account schema.
  status     Show the current Compose service state.
EOF
  exit 2
}

case "${1:-}" in
  preflight) preflight ;;
  backup) preflight; backup_stack ;;
  upgrade) upgrade_stack ;;
  verify) preflight; verify_stack ;;
  status) compose ps ;;
  *) usage ;;
esac
