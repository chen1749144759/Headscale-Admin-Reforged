from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import internal_auth


class InternalAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.key_path = Path(self.temp_dir.name) / "internal-auth-key"
        self.key_path.write_bytes(b"0123456789abcdef0123456789abcdef")
        self.env = patch.dict(
            os.environ,
            {"SCALEFORGE_INTERNAL_AUTH_KEY_FILE": str(self.key_path)},
            clear=False,
        )
        self.env.start()
        internal_auth.internal_auth_key.cache_clear()

    def tearDown(self):
        internal_auth.internal_auth_key.cache_clear()
        self.env.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def lower_headers(headers: dict[str, str]) -> dict[str, str]:
        return {key.lower(): value for key, value in headers.items()}

    def test_signed_request_is_accepted_once(self):
        now = 1_800_000_000
        body = b'{"machine":7}'
        headers = internal_auth.internal_auth_headers(
            "POST",
            "/internal/v1/client/traffic",
            "",
            body,
            now=now,
            nonce="00112233445566778899aabbccddeeff",
        )
        replay = internal_auth.ReplayCache()
        self.assertTrue(
            internal_auth.verify_internal_request(
                "POST",
                "/internal/v1/client/traffic",
                "",
                body,
                self.lower_headers(headers),
                now=now,
                replay_cache=replay,
            )
        )
        self.assertFalse(
            internal_auth.verify_internal_request(
                "POST",
                "/internal/v1/client/traffic",
                "",
                body,
                self.lower_headers(headers),
                now=now,
                replay_cache=replay,
            )
        )

    def test_tampered_body_and_stale_timestamp_are_rejected(self):
        now = 1_800_000_000
        body = b"payload"
        identity_headers = {
            "Authorization": "Bearer session-token",
            "X-ScaleForge-User-ID": "11",
        }
        headers = internal_auth.internal_auth_headers(
            "POST",
            "/v1/session/password",
            "",
            body,
            now=now,
            nonce="ffeeddccbbaa99887766554433221100",
            auth_headers=identity_headers,
        )
        signed_headers = self.lower_headers(headers | identity_headers)
        self.assertFalse(
            internal_auth.verify_internal_request(
                "POST",
                "/v1/session/password",
                "",
                body + b"!",
                signed_headers,
                now=now,
                replay_cache=internal_auth.ReplayCache(),
            )
        )
        self.assertFalse(
            internal_auth.verify_internal_request(
                "POST",
                "/v1/session/password",
                "",
                body,
                signed_headers,
                now=now + internal_auth.CLOCK_SKEW_SECONDS + 1,
                replay_cache=internal_auth.ReplayCache(),
            )
        )
        tampered_headers = signed_headers | {"x-scaleforge-user-id": "12"}
        self.assertFalse(
            internal_auth.verify_internal_request(
                "POST",
                "/v1/session/password",
                "",
                body,
                tampered_headers,
                now=now,
                replay_cache=internal_auth.ReplayCache(),
            )
        )

    def test_canonical_signature_vector(self):
        identity_headers = {
            "Authorization": "Bearer session-token",
            "X-ScaleForge-Node-ID": "7",
            "X-ScaleForge-Source": "198.51.100.8",
            "X-ScaleForge-Source-IP": "203.0.113.9",
            "X-ScaleForge-User-ID": "11",
        }
        headers = internal_auth.internal_auth_headers(
            "POST",
            "/internal/v1/client/traffic",
            "a=1&b=2",
            b'{"rx":123}',
            now=1_800_000_000,
            nonce="00112233445566778899aabbccddeeff",
            auth_headers=identity_headers,
        )
        self.assertEqual(
            headers["X-ScaleForge-Auth-Signature"],
            "f45999ddd2efe3c9fd7805a8ef6d130a529a2e2e071a9ca85dccbe753f2008e6",
        )


if __name__ == "__main__":
    unittest.main()
