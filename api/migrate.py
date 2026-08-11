"""Apply immutable, versioned ScaleForge PostgreSQL migrations."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql


ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"

CORE_READ_TABLES = ("users", "nodes", "account_groups")
ACCOUNT_READ_COLUMNS = (
    "id",
    "username",
    "user_id",
    "group_id",
    "enabled",
    "expires_at",
    "must_change_password",
    "password_changed_at",
)
PLATFORM_TABLES = (
    "acl",
    "log",
    "client_policies",
    "client_policy_states",
    "traffic_samples",
    "traffic_hourly",
    "traffic_daily",
    "node_ip_observations",
    "flow_summaries",
    "security_events",
    "trusted_networks",
    "risk_rules",
    "client_releases",
)
AUDIT_TABLE = "log"
PLATFORM_MUTABLE_TABLES = tuple(name for name in PLATFORM_TABLES if name != AUDIT_TABLE)
MIGRATION_TABLE = "scaleforge_schema_migrations"
DEFAULT_LOCK_TIMEOUT_MS = 15_000
DEFAULT_STATEMENT_TIMEOUT_MS = 300_000


def _dsn() -> str:
    if value := os.environ.get("MIGRATION_DATABASE_URL"):
        return value
    host = os.environ.get("MIGRATION_DB_HOST") or os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("MIGRATION_DB_PORT") or os.environ.get("DB_PORT", "5432")
    name = os.environ.get("MIGRATION_DB_NAME") or os.environ.get("DB_NAME", "headscale_admin")
    user = os.environ.get("MIGRATION_DB_USER") or os.environ.get("DB_USER", "headscale_admin")
    password = os.environ.get("MIGRATION_DB_PASS") or os.environ.get("DB_PASS", "")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


def _timeout_ms(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer number of milliseconds") from exc
    if value < 1 or value > 3_600_000:
        raise RuntimeError(f"{name} must be between 1 and 3600000 milliseconds")
    return value


def _configure_transaction_timeouts(cur) -> None:
    lock_timeout_ms = _timeout_ms(
        "SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS",
        DEFAULT_LOCK_TIMEOUT_MS,
    )
    statement_timeout_ms = _timeout_ms(
        "SCALEFORGE_MIGRATION_STATEMENT_TIMEOUT_MS",
        DEFAULT_STATEMENT_TIMEOUT_MS,
    )
    cur.execute("SET LOCAL lock_timeout = %s", (f"{lock_timeout_ms}ms",))
    cur.execute("SET LOCAL statement_timeout = %s", (f"{statement_timeout_ms}ms",))


def _timeout_failure(exc: Exception) -> RuntimeError | None:
    code = getattr(exc, "pgcode", "")
    if code == "55P03":
        return RuntimeError(
            "ScaleForge migration timed out waiting for a database lock; "
            "stop conflicting application instances or raise SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS"
        )
    if code == "57014":
        return RuntimeError(
            "ScaleForge migration statement timed out; "
            "reduce migration contention or raise SCALEFORGE_MIGRATION_STATEMENT_TIMEOUT_MS"
        )
    return None


def _serial_sequences(cur, tables: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for table in tables:
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (f"public.{table}",))
        sequence = cur.fetchone()[0]
        if sequence:
            result.append(sequence)
    return result


def _qualified_identifier(name: str) -> sql.Composed:
    return sql.SQL(".").join(sql.Identifier(part) for part in name.split("."))


def _relation_owner(cur, relation_name: str) -> str:
    cur.execute(
        """
        SELECT pg_get_userbyid(relowner)
        FROM pg_class
        WHERE oid = to_regclass(%s)
        """,
        (relation_name,),
    )
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else ""


def _set_platform_ownership(cur) -> None:
    owner = os.environ.get("SCALEFORGE_DB_OWNER", "").strip()
    if not owner:
        return
    owner_identifier = sql.Identifier(owner)
    for table in (MIGRATION_TABLE, *PLATFORM_TABLES):
        if _relation_owner(cur, f"public.{table}") == owner:
            continue
        cur.execute(sql.SQL("ALTER TABLE {} OWNER TO {}").format(
            sql.Identifier(table),
            owner_identifier,
        ))
    for sequence in _serial_sequences(cur, PLATFORM_TABLES):
        if _relation_owner(cur, sequence) == owner:
            continue
        cur.execute(sql.SQL("ALTER SEQUENCE {} OWNER TO {}").format(
            _qualified_identifier(sequence),
            owner_identifier,
        ))


def _grant_runtime_access(cur) -> None:
    runtime_role = os.environ.get("SCALEFORGE_DB_USER", "").strip()
    if not runtime_role:
        return
    role_identifier = sql.Identifier(runtime_role)
    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
        sql.Identifier(cur.connection.info.dbname),
        role_identifier,
    ))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_identifier))
    cur.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
        sql.SQL(", ").join(sql.Identifier(name) for name in CORE_READ_TABLES),
        role_identifier,
    ))
    cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON accounts FROM {}").format(role_identifier))
    cur.execute(sql.SQL("GRANT SELECT ({}) ON accounts TO {}").format(
        sql.SQL(", ").join(sql.Identifier(name) for name in ACCOUNT_READ_COLUMNS),
        role_identifier,
    ))
    cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON {} FROM {}").format(
        sql.SQL(", ").join(sql.Identifier(name) for name in PLATFORM_TABLES),
        role_identifier,
    ))
    cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO {}").format(
        sql.SQL(", ").join(sql.Identifier(name) for name in PLATFORM_MUTABLE_TABLES),
        role_identifier,
    ))
    cur.execute(sql.SQL("GRANT SELECT, INSERT ON {} TO {}").format(
        sql.Identifier(AUDIT_TABLE),
        role_identifier,
    ))
    sequences = _serial_sequences(cur, PLATFORM_TABLES)
    if sequences:
        cur.execute(sql.SQL("GRANT USAGE, SELECT ON {} TO {}").format(
            sql.SQL(", ").join(_qualified_identifier(name) for name in sequences),
            role_identifier,
        ))


def _grant_headscale_audit_access(cur) -> None:
    runtime_role = os.environ.get("HEADSCALE_DB_USER", "").strip()
    if not runtime_role:
        return
    role_identifier = sql.Identifier(runtime_role)
    cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON {} FROM {}").format(
        sql.Identifier(AUDIT_TABLE),
        role_identifier,
    ))
    cur.execute(sql.SQL("GRANT INSERT ON {} TO {}").format(
        sql.Identifier(AUDIT_TABLE),
        role_identifier,
    ))
    sequences = _serial_sequences(cur, (AUDIT_TABLE,))
    if sequences:
        cur.execute(sql.SQL("GRANT USAGE, SELECT ON {} TO {}").format(
            sql.SQL(", ").join(_qualified_identifier(name) for name in sequences),
            role_identifier,
        ))


def run() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No migration files found in {MIGRATIONS_DIR}")

    conn = psycopg2.connect(_dsn())
    try:
        with conn.cursor() as cur:
            _configure_transaction_timeouts(cur)
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('scaleforge-schema-migrations'))")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scaleforge_schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("SELECT version, checksum FROM scaleforge_schema_migrations")
            applied = dict(cur.fetchall())

            for path in migration_files:
                body = path.read_bytes()
                checksum = hashlib.sha256(body).hexdigest()
                if path.name in applied:
                    if applied[path.name] != checksum:
                        raise RuntimeError(f"Migration checksum changed after apply: {path.name}")
                    continue
                cur.execute(body.decode("utf-8"))
                cur.execute(
                    "INSERT INTO scaleforge_schema_migrations(version, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )

            _set_platform_ownership(cur)
            _grant_runtime_access(cur)
            _grant_headscale_audit_access(cur)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if timeout_error := _timeout_failure(exc):
            raise timeout_error from exc
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
