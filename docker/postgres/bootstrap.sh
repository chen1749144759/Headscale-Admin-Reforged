#!/bin/sh
set -eu

case "${HEADSCALE_DB_USER:-}" in (*[!a-zA-Z0-9_]*|'') echo "Invalid HEADSCALE_DB_USER" >&2; exit 1;; esac
case "${SCALEFORGE_DB_USER:-}" in (*[!a-zA-Z0-9_]*|'') echo "Invalid SCALEFORGE_DB_USER" >&2; exit 1;; esac
case "${SCALEFORGE_DB_OWNER:-}" in (*[!a-zA-Z0-9_]*|'') echo "Invalid SCALEFORGE_DB_OWNER" >&2; exit 1;; esac
: "${HEADSCALE_DB_PASSWORD:?HEADSCALE_DB_PASSWORD is required}"
: "${SCALEFORGE_DB_PASSWORD:?SCALEFORGE_DB_PASSWORD is required}"

export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  sleep 1
done

psql -v ON_ERROR_STOP=1 \
  -h postgres \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -v db_name="$POSTGRES_DB" \
  -v admin_user="$POSTGRES_USER" \
  -v hs_user="$HEADSCALE_DB_USER" \
  -v hs_pass="$HEADSCALE_DB_PASSWORD" \
  -v sf_user="$SCALEFORGE_DB_USER" \
  -v sf_pass="$SCALEFORGE_DB_PASSWORD" \
  -v sf_owner="$SCALEFORGE_DB_OWNER" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'hs_user', :'hs_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'hs_user') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'hs_user', :'hs_pass') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'sf_user', :'sf_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'sf_user') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'sf_user', :'sf_pass') \gexec

SELECT format('CREATE ROLE %I NOLOGIN', :'sf_owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'sf_owner') \gexec
SELECT format('ALTER ROLE %I NOLOGIN', :'sf_owner') \gexec

SELECT format('REASSIGN OWNED BY %I TO %I', :'admin_user', :'hs_user')
WHERE :'admin_user' <> :'hs_user' \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'hs_user') \gexec
SELECT format('ALTER SCHEMA public OWNER TO %I', :'hs_user') \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db_name', :'hs_user') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db_name', :'sf_user') \gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'hs_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'sf_user') \gexec
SQL
