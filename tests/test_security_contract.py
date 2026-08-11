import base64
import inspect
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from api.routers import headscale_client
from api.routers import dependencies as deps
from api import migrate
from api.routers.acl import _parse_policy, _reject_identity_tags
from api.routers.accounts import _assert_user_binding_available
from api.routers.client_reports import (
    PolicyStateReport,
    TrafficReport,
    TrustedNode,
    _bind_policy_state_identity,
    _bind_traffic_identity,
    _client_update_response,
    _geo_lookup_url,
    require_trusted_node,
)
from api.routers.dependencies import CurrentUser
from api.routers.logs import list_logs
from api.routers.auth import LoginRateLimiter, logout
from api.routers.dependencies import trusted_service_url
from api.routers import ota
from api.routers.ota import (
    encode_v3_signature,
    ota_message,
    validated_download_url,
    verify_release_signature,
)
from api.routers.traffic import _sample_window
from api.routers.versioning import compare_versions, parse_semver


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return httpx.Response(200, json={"status": "ok"})


class FakeLogCursor:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def fetchone(self):
        return {"count": 0}

    def fetchall(self):
        return []


class FakeLogConnection:
    def __init__(self):
        self.cursor_instance = FakeLogCursor()
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        self.closed = True


class FakeMigrationCursor:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))


class FakeReleaseCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def fetchall(self):
        return self.rows


class FakeReleaseConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeReleaseCursor(rows)
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        self.closed = True


class HeadscaleSocketContractTests(unittest.TestCase):
    def test_rejects_external_url(self):
        with self.assertRaises(ValueError):
            headscale_client._validate_path("https://attacker.example/api/v1/node")

    def test_gateway_has_no_implicit_bearer(self):
        client = FakeClient()
        with (
            patch.object(headscale_client, "_get_client", return_value=client),
            patch.object(
                headscale_client,
                "internal_auth_headers",
                return_value={"X-ScaleForge-Auth-Signature": "signed"},
            ),
        ):
            headscale_client.request("GET", "/api/v1/node")
        self.assertNotIn("Authorization", client.calls[0][2]["headers"])
        self.assertEqual(
            client.calls[0][2]["headers"]["X-ScaleForge-Auth-Signature"],
            "signed",
        )

    def test_session_token_is_forwarded_only_when_explicit(self):
        client = FakeClient()
        with (
            patch.object(headscale_client, "_get_client", return_value=client),
            patch.object(headscale_client, "internal_auth_headers", return_value={}),
        ):
            headscale_client.request("GET", "/v1/session", token="opaque")
        self.assertEqual(client.calls[0][2]["headers"]["Authorization"], "Bearer opaque")


class AccountOwnershipTests(unittest.TestCase):
    def test_current_user_uses_network_user_id(self):
        user = CurrentUser(
            {
                "id": 7,
                "username": "alice",
                "role": "user",
                "enabled": True,
                "userId": 42,
                "networkName": "engineering",
            },
            "opaque",
            False,
        )
        self.assertEqual(user.id, 7)
        self.assertEqual(user.network_user_id, 42)
        self.assertNotEqual(user.id, user.network_user_id)

    def test_duplicate_network_binding_is_rejected(self):
        accounts = [{"id": 1, "username": "alice", "userId": 42}]
        with self.assertRaises(HTTPException) as raised:
            _assert_user_binding_available(accounts, 42)
        self.assertEqual(raised.exception.status_code, 409)

    def test_editing_current_binding_is_allowed(self):
        accounts = [{"id": 1, "username": "alice", "userId": 42}]
        _assert_user_binding_available(accounts, 42, exclude_account_id=1)


class MigrationAndLogContractTests(unittest.TestCase):
    def test_log_query_uses_account_id_without_removed_legacy_column(self):
        conn = FakeLogConnection()
        with patch("api.routers.logs.get_db_conn", return_value=conn):
            result = list_logs()
        query = conn.cursor_instance.calls[1][0]
        self.assertEqual(result["total"], 0)
        self.assertIn("l.account_id = a.id", query)
        self.assertNotIn("l.user_id", query)
        self.assertTrue(conn.closed)

    def test_migration_timeouts_are_local_and_bounded(self):
        cur = FakeMigrationCursor()
        with patch.dict(
            "os.environ",
            {
                "SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS": "12000",
                "SCALEFORGE_MIGRATION_STATEMENT_TIMEOUT_MS": "240000",
            },
            clear=False,
        ):
            migrate._configure_transaction_timeouts(cur)
        self.assertEqual(
            cur.calls,
            [
                ("SET LOCAL lock_timeout = %s", ("12000ms",)),
                ("SET LOCAL statement_timeout = %s", ("240000ms",)),
            ],
        )

    def test_migration_timeout_rejects_invalid_configuration(self):
        with patch.dict("os.environ", {"SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS": "0"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS"):
                migrate._timeout_ms(
                    "SCALEFORGE_MIGRATION_LOCK_TIMEOUT_MS",
                    migrate.DEFAULT_LOCK_TIMEOUT_MS,
                )

    def test_runtime_role_cannot_read_account_password_hash(self):
        expected_columns = {
            "id",
            "username",
            "user_id",
            "enabled",
            "expires_at",
            "must_change_password",
            "password_changed_at",
        }
        self.assertNotIn("accounts", migrate.CORE_READ_TABLES)
        self.assertEqual(set(migrate.ACCOUNT_READ_COLUMNS), expected_columns)
        self.assertNotIn("password_hash", migrate.ACCOUNT_READ_COLUMNS)

        grant_source = inspect.getsource(migrate._grant_runtime_access)
        self.assertIn("REVOKE ALL PRIVILEGES ON accounts", grant_source)
        self.assertIn("GRANT SELECT ({}) ON accounts", grant_source)
        self.assertIn("REVOKE ALL PRIVILEGES ON {} FROM {}", grant_source)
        self.assertIn("GRANT SELECT, INSERT ON {} TO {}", grant_source)
        self.assertNotIn("log", migrate.PLATFORM_MUTABLE_TABLES)

        headscale_grant_source = inspect.getsource(migrate._grant_headscale_audit_access)
        self.assertIn("REVOKE ALL PRIVILEGES ON {} FROM {}", headscale_grant_source)
        self.assertIn("GRANT INSERT ON {} TO {}", headscale_grant_source)
        self.assertNotIn("GRANT SELECT", headscale_grant_source)

        routers_dir = Path(__file__).resolve().parents[1] / "api" / "routers"
        for router_path in routers_dir.glob("*.py"):
            self.assertNotIn(
                "password_hash",
                router_path.read_text(encoding="utf-8"),
                f"runtime router must not query password hashes: {router_path.name}",
            )

    def test_platform_ownership_skips_matching_relations(self):
        cur = FakeMigrationCursor()
        with (
            patch.dict("os.environ", {"SCALEFORGE_DB_OWNER": "scaleforge_owner"}, clear=False),
            patch.object(migrate, "_relation_owner", return_value="scaleforge_owner"),
            patch.object(migrate, "_serial_sequences", return_value=["public.client_releases_id_seq"]),
        ):
            migrate._set_platform_ownership(cur)
        self.assertEqual(cur.calls, [])

    def test_database_bootstrap_transfers_only_application_objects(self):
        bootstrap = (
            Path(__file__).resolve().parents[1]
            / "docker"
            / "postgres"
            / "bootstrap.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn("REASSIGN OWNED", bootstrap)
        self.assertIn("n.nspname = 'public'", bootstrap)
        self.assertIn("ALTER TABLE %s OWNER TO %I", bootstrap)
        self.assertIn("ALTER SEQUENCE %s OWNER TO %I", bootstrap)
        self.assertIn("ALTER FUNCTION %s OWNER TO %I", bootstrap)

    def test_legacy_policy_id_is_backfilled_before_column_drop(self):
        migration = (
            Path(__file__).resolve().parents[1] / "migrations" / "001_platform_schema.sql"
        ).read_text(encoding="utf-8")
        backfill_at = migration.index("jsonb_build_array(policy_id)")
        drop_at = migration.index("DROP COLUMN IF EXISTS policy_id")
        self.assertLess(backfill_at, drop_at)

    def test_nginx_uds_and_forwarded_protocol_contract(self):
        root = Path(__file__).resolve().parents[1]
        nginx_config = (root / "docker/nginx/nginx.conf").read_text(encoding="utf-8")
        nginx_dockerfile = (root / "docker/nginx/Dockerfile").read_text(encoding="utf-8")
        compose = (root / "docker/docker-compose.yml").read_text(encoding="utf-8")
        entrypoint = (root / "docker/backend/entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn(
            "proxy_set_header X-Forwarded-Proto ${SCALEFORGE_EXTERNAL_SCHEME};",
            nginx_config,
        )
        self.assertNotIn("$http_x_forwarded_proto", nginx_config)
        self.assertIn(
            "SCALEFORGE_EXTERNAL_SCHEME: ${SCALEFORGE_EXTERNAL_SCHEME:-https}",
            compose,
        )
        validate_script = (root / "docker/nginx/validate-env.sh").read_text(encoding="utf-8")
        self.assertIn('case "${SCALEFORGE_EXTERNAL_SCHEME:-https}" in', validate_script)
        self.assertIn("http|https", validate_script)
        self.assertIn("05-validate-scaleforge-env.sh", nginx_dockerfile)
        self.assertIn(
            "/etc/nginx/templates/default.conf.template",
            nginx_dockerfile,
        )
        self.assertIn("addgroup -S -g 10101 scaleforge", nginx_dockerfile)
        self.assertIn("user nginx scaleforge;", nginx_dockerfile)
        self.assertIn('group_add: ["10101"]', compose)
        self.assertIn("socket_group=10101", entrypoint)
        self.assertNotIn("\nname: scaleforge\n", "\n" + compose)
        self.assertIn("proxy_set_header Host $http_host;", nginx_config)

    def test_upgrade_migration_removes_legacy_telemetry_foreign_keys(self):
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "003_drop_legacy_platform_foreign_keys.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("traffic_samples_machine_id_fkey", migration)
        self.assertIn("flow_summaries_machine_id_fkey", migration)
        self.assertNotIn("fk_log_account", migration)

    def test_ota_v3_migration_is_incremental_and_disables_legacy_signatures(self):
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "004_client_release_policy_v3.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS policy_revision BIGINT", migration)
        self.assertIn("update_type IN ('suggested', 'forced', 'clear')", migration)
        self.assertIn("!~ '^v3\\.[A-Za-z0-9+/]{86}==$'", migration)
        self.assertIn("ux_client_releases_platform_policy_revision", migration)
        self.assertIn("client_releases_append_only", migration)
        self.assertNotIn("DROP TABLE", migration.upper())
        disable_legacy_at = migration.index("SET enabled = FALSE")
        signature_constraint_at = migration.index("client_releases_signature_v3_check")
        self.assertLess(disable_legacy_at, signature_constraint_at)

        release_router = (
            Path(__file__).resolve().parents[1]
            / "api"
            / "routers"
            / "client_releases.py"
        ).read_text(encoding="utf-8")
        self.assertIn("pg_advisory_xact_lock", release_router)
        self.assertNotIn('@router.put("/{release_id}")', release_router)
        self.assertNotIn('@router.patch("/{release_id}/toggle")', release_router)
        self.assertNotIn('@router.delete("/{release_id}")', release_router)


class ClientNoiseIdentityTests(unittest.TestCase):
    def test_direct_request_without_headscale_identity_is_rejected(self):
        request = Request({"type": "http", "method": "POST", "path": "/internal/v1/client/traffic", "headers": []})
        with self.assertRaises(HTTPException) as raised:
            require_trusted_node(request)
        self.assertEqual(raised.exception.status_code, 401)

    def test_client_payload_cannot_override_trusted_identity(self):
        node = TrustedNode(
            id=9,
            user_id=42,
            machine_name="office-pc",
            group_name="engineering",
            scaletail_ips=["100.64.0.9"],
            source_ip="203.0.113.8",
        )
        traffic = TrafficReport(
            machine_id=777,
            machine_name="spoofed",
            group_id=888,
            group_name="other",
            public_ip="198.51.100.99",
            country="spoofed",
        )
        _bind_traffic_identity(traffic, node)
        self.assertEqual((traffic.machine_id, traffic.group_id), (9, 42))
        self.assertEqual((traffic.machine_name, traffic.group_name), ("office-pc", "engineering"))
        self.assertEqual(traffic.scaletail_ips, ["100.64.0.9"])
        self.assertEqual(traffic.public_ip, "203.0.113.8")
        self.assertEqual(traffic.country, "")

        state = PolicyStateReport(machine_id=777, machine_name="spoofed")
        _bind_policy_state_identity(state, node)
        self.assertEqual((state.machine_id, state.machine_name), (9, "office-pc"))


class AuthenticationBoundaryTests(unittest.TestCase):
    @staticmethod
    def _logout_request() -> Request:
        cookie = f"{deps.SESSION_COOKIE_NAME}=opaque-session".encode("latin-1")
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/auth/logout",
                "headers": [(b"cookie", cookie)],
            }
        )

    def assert_logout_cookie_cleared(self, response: Response) -> None:
        set_cookie = response.headers.get("set-cookie", "").lower()
        self.assertIn(f"{deps.SESSION_COOKIE_NAME.lower()}=", set_cookie)
        self.assertIn("max-age=0", set_cookie)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_logout_clears_cookie_when_headscale_is_unavailable(self):
        response = Response()
        with patch(
            "api.routers.auth.headscale_request",
            side_effect=headscale_client.HeadscaleUnavailable("socket unavailable"),
        ):
            result = logout(self._logout_request(), response)

        self.assert_logout_cookie_cleared(response)
        self.assertTrue(result["data"]["browserSessionCleared"])
        self.assertFalse(result["data"]["serverSessionRevoked"])
        self.assertEqual(result["data"]["revocationStatus"], "unavailable")

    def test_logout_clears_cookie_when_revocation_fails(self):
        response = Response()
        upstream = httpx.Response(
            500,
            json={"code": "internal_error", "message": "revoke failed"},
            request=httpx.Request("DELETE", "http://headscale.local/v1/session"),
        )
        with patch("api.routers.auth.headscale_request", return_value=upstream):
            result = logout(self._logout_request(), response)

        self.assert_logout_cookie_cleared(response)
        self.assertTrue(result["data"]["browserSessionCleared"])
        self.assertFalse(result["data"]["serverSessionRevoked"])
        self.assertEqual(result["data"]["revocationStatus"], "failed")

    def test_login_limiter_is_temporary_and_resettable(self):
        limiter = LoginRateLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow("192.0.2.1", "alice"))
        self.assertTrue(limiter.allow("192.0.2.1", "alice"))
        self.assertFalse(limiter.allow("192.0.2.1", "alice"))
        limiter.reset("192.0.2.1", "alice")
        self.assertTrue(limiter.allow("192.0.2.1", "alice"))

    def test_remote_http_service_url_is_rejected(self):
        self.assertEqual(trusted_service_url("http://10.0.0.5:3000/site"), "")
        self.assertEqual(
            trusted_service_url("http://127.0.0.1:3000/site"),
            "http://127.0.0.1:3000/site",
        )
        self.assertEqual(
            trusted_service_url("https://captcha.example.com/site"),
            "https://captcha.example.com/site",
        )

    def test_geo_lookup_requires_https_for_remote_service(self):
        with patch.dict("os.environ", {"IP_GEOLOOKUP_URL": "http://geo.example.com/{ip}"}):
            self.assertEqual(_geo_lookup_url("203.0.113.8"), "")
        with patch.dict("os.environ", {"IP_GEOLOOKUP_URL": "https://geo.example.com/{ip}"}):
            self.assertEqual(
                _geo_lookup_url("203.0.113.8"),
                "https://geo.example.com/203.0.113.8",
            )

    def test_ota_release_metadata_signature_is_verified(self):
        private_key = Ed25519PrivateKey.generate()
        public_key = base64.b64encode(
            private_key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")
        download_url = "https://downloads.example.com/releases/ScaleTail.exe?channel=stable~1"
        signature = encode_v3_signature(
            private_key.sign(
                ota_message(
                    42,
                    "forced",
                    "0.0.7",
                    "windows-amd64",
                    "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                    131792174,
                    download_url,
                )
            ),
        )
        with patch.object(ota, "OTA_PUBLIC_KEY_BASE64", public_key):
            verify_release_signature(
                42,
                "forced",
                "0.0.7",
                "windows-amd64",
                "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                131792174,
                download_url,
                signature,
            )
            with self.assertRaises(ValueError):
                verify_release_signature(
                    42,
                    "forced",
                    "0.0.7",
                    "windows-amd64",
                    "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                    131792174,
                    "https://downloads.example.com/releases/other.exe",
                    signature,
                )
            with self.assertRaises(ValueError):
                verify_release_signature(
                    42,
                    "forced",
                    "0.0.7",
                    "windows-amd64",
                    "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                    131792174,
                    download_url,
                    signature.split(".")[1],
                )

            with self.assertRaises(ValueError):
                verify_release_signature(
                    43,
                    "forced",
                    "0.0.7",
                    "windows-amd64",
                    "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                    131792174,
                    download_url,
                    signature,
                )
            with self.assertRaises(ValueError):
                verify_release_signature(
                    42,
                    "suggested",
                    "0.0.7",
                    "windows-amd64",
                    "52f6869ec801f9b954810e4781248ac59f3203b5692bd4ec7521d497c0cc04c9",
                    131792174,
                    download_url,
                    signature,
                )

    def test_ota_v3_message_matches_cross_language_vector(self):
        self.assertEqual(
            ota_message(
                42,
                "FORCED",
                "0.0.8",
                "WINDOWS-AMD64",
                "a" * 64,
                42,
                "https://downloads.example.com/releases/ScaleTail.exe?channel=stable~1",
            ),
            (
                "scaletail-update-v3\n"
                "42\n"
                "forced\n"
                "0.0.8\n"
                "windows-amd64\n"
                f"{'a' * 64}\n"
                "42\n"
                "https://downloads.example.com/releases/ScaleTail.exe?channel=stable~1\n"
            ).encode("utf-8"),
        )

    def test_ota_signed_clear_policy_has_no_installer_metadata(self):
        private_key = Ed25519PrivateKey.generate()
        public_key = base64.b64encode(
            private_key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")
        signature = encode_v3_signature(private_key.sign(ota_message(
            43,
            "clear",
            "0.0.8",
            "windows-amd64",
            "",
            0,
            "",
        )))
        with patch.object(ota, "OTA_PUBLIC_KEY_BASE64", public_key):
            policy = verify_release_signature(
                43,
                "clear",
                "0.0.8",
                "windows-amd64",
                "",
                0,
                "",
                signature,
            )
            self.assertEqual(policy["update_type"], "clear")
            with self.assertRaises(ValueError):
                verify_release_signature(
                    43,
                    "clear",
                    "0.0.8",
                    "windows-amd64",
                    "a" * 64,
                    1,
                    "https://downloads.example.com/ScaleTail.exe",
                    signature,
                )

    def test_ota_download_url_rejects_credentials_fragments_and_local_hosts(self):
        self.assertEqual(
            validated_download_url("HTTPS://Downloads.Example.Com:443/releases/ScaleTail.exe?channel=stable%7e1"),
            "https://downloads.example.com/releases/ScaleTail.exe?channel=stable~1",
        )
        for raw in (
            "https://user:secret@downloads.example.com/ScaleTail.exe",
            "https://downloads.example.com/ScaleTail.exe#ignored",
            "https://localhost/ScaleTail.exe",
            "https://127.0.0.1/ScaleTail.exe",
            "https://2130706433/ScaleTail.exe",
            "https://0x7f000001/ScaleTail.exe",
            "https://10.0.0.1/ScaleTail.exe",
            "https://[::1]/ScaleTail.exe",
            "https://downloads.example.com/ScaleTail.exe?",
        ):
            with self.assertRaises(ValueError, msg=raw):
                validated_download_url(raw)

    def test_ota_download_url_rejects_credentials_and_fragments(self):
        # Kept as a focused regression name for existing test selectors.
        with self.assertRaises(ValueError):
            validated_download_url("https://user:secret@downloads.example.com/ScaleTail.exe")
        with self.assertRaises(ValueError):
            validated_download_url("https://downloads.example.com/ScaleTail.exe#ignored")


class AclIdentityTests(unittest.TestCase):
    def test_account_policy_rejects_tag_owners(self):
        policy = _parse_policy('{"tagOwners": {"tag:server": ["group:ops"]}}')
        with self.assertRaises(HTTPException) as raised:
            _reject_identity_tags(policy)
        self.assertEqual(raised.exception.status_code, 400)

    def test_account_policy_rejects_tag_references(self):
        policy = _parse_policy('{"acls": [{"action": "accept", "src": ["tag:server"], "dst": ["*:*"]}]}')
        with self.assertRaises(HTTPException) as raised:
            _reject_identity_tags(policy)
        self.assertEqual(raised.exception.status_code, 400)

    def test_account_policy_accepts_users_groups_and_ips(self):
        policy = _parse_policy(
            '{"groups": {"group:ops": ["alice"]}, "acls": '
            '[{"action": "accept", "src": ["group:ops"], "dst": ["10.0.0.0/8:443"]}]}'
        )
        _reject_identity_tags(policy)


class TrafficSamplingTests(unittest.TestCase):
    def test_offline_gap_starts_new_active_session(self):
        start = datetime(2026, 8, 8, tzinfo=timezone.utc)
        result = _sample_window(
            [start, start + timedelta(seconds=15), start + timedelta(hours=12), start + timedelta(hours=12, seconds=15)],
            24,
            15,
        )
        self.assertEqual(result['samples'], 4)
        self.assertEqual(result['expected'], 4)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['sessions'], 2)

    def test_short_gap_counts_missed_report(self):
        start = datetime(2026, 8, 8, tzinfo=timezone.utc)
        result = _sample_window([start, start + timedelta(seconds=30)], 24, 15)
        self.assertEqual(result['samples'], 2)
        self.assertEqual(result['expected'], 3)
        self.assertEqual(result['failed'], 1)


class SemanticVersionTests(unittest.TestCase):
    def test_prerelease_precedence(self):
        self.assertEqual(compare_versions("0.0.2", "0.0.2-rc.1"), 1)
        self.assertEqual(compare_versions("0.0.2-beta.2", "0.0.2-beta.11"), -1)

    def test_invalid_versions_fail_closed(self):
        self.assertIsNone(parse_semver("0.0"))
        self.assertIsNone(parse_semver("0.0.2-01"))
        self.assertIsNone(compare_versions("latest", "0.0.2"))

    def test_client_update_platform_is_exact(self):
        source = inspect.getsource(_client_update_response)
        self.assertIn("([platform],)", source)
        self.assertNotIn("platform_alias", source)

    def test_highest_signed_revision_is_authoritative_without_action_rewrite(self):
        rows = [
            {
                "id": 2,
                "policy_revision": 200,
                "version": "1.2.0",
                "platform": "windows-amd64",
                "update_type": "suggested",
                "download_url": "https://updates.example/1.2.0.exe",
            },
            {
                "id": 1,
                "policy_revision": 100,
                "version": "1.1.0",
                "platform": "windows-amd64",
                "update_type": "forced",
                "download_url": "https://updates.example/1.1.0.exe",
            },
        ]
        conn = FakeReleaseConnection(rows)
        with (
            patch("api.routers.client_reports.get_db_conn", return_value=conn),
            patch("api.routers.client_reports.release_signature_valid", return_value=True),
        ):
            result = _client_update_response("1.0.0", "windows-amd64", 100)

        self.assertEqual(result["data"]["version"], "1.2.0")
        self.assertEqual(result["data"]["policy_revision"], 200)
        self.assertFalse(result["data"]["forced"])
        self.assertEqual(result["data"]["update_type"], "suggested")
        self.assertTrue(conn.closed)

    def test_signed_clear_policy_is_returned_as_tombstone(self):
        rows = [{
            "id": 3,
            "policy_revision": 300,
            "version": "1.2.0",
            "platform": "windows-amd64",
            "update_type": "clear",
            "download_url": "",
        }]
        conn = FakeReleaseConnection(rows)
        with (
            patch("api.routers.client_reports.get_db_conn", return_value=conn),
            patch("api.routers.client_reports.release_signature_valid", return_value=True),
        ):
            result = _client_update_response("1.0.0", "windows-amd64", 200)

        self.assertFalse(result["data"]["has_update"])
        self.assertEqual(result["data"]["update_type"], "clear")
        self.assertEqual(result["data"]["policy_revision"], 300)
        self.assertTrue(conn.closed)

    def test_server_never_replays_policy_older_than_client_revision(self):
        rows = [{
            "id": 2,
            "policy_revision": 200,
            "version": "1.2.0",
            "platform": "windows-amd64",
            "update_type": "forced",
            "download_url": "https://updates.example/1.2.0.exe",
        }]
        conn = FakeReleaseConnection(rows)
        with (
            patch("api.routers.client_reports.get_db_conn", return_value=conn),
            patch("api.routers.client_reports.release_signature_valid", return_value=True),
        ):
            with self.assertRaises(HTTPException) as raised:
                _client_update_response("1.0.0", "windows-amd64", 300)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue(conn.closed)

    def test_invalid_highest_revision_never_falls_back(self):
        rows = [
            {
                "id": 3,
                "policy_revision": 300,
                "version": "1.3.0",
                "platform": "windows-amd64",
                "update_type": "forced",
            },
            {
                "id": 2,
                "policy_revision": 200,
                "version": "1.2.0",
                "platform": "windows-amd64",
                "update_type": "suggested",
            },
        ]
        conn = FakeReleaseConnection(rows)
        with (
            patch("api.routers.client_reports.get_db_conn", return_value=conn),
            patch("api.routers.client_reports.release_signature_valid", return_value=False),
        ):
            with self.assertRaises(HTTPException) as raised:
                _client_update_response("1.0.0", "windows-amd64", 100)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
