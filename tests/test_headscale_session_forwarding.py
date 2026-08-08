import ast
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from api.routers import utils


class HeadscaleSessionForwardingTests(unittest.TestCase):
    def test_every_gateway_helper_call_passes_an_explicit_session(self):
        routers = Path(__file__).resolve().parents[1] / "api" / "routers"
        missing: list[str] = []
        for source_path in routers.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "hs_request":
                    continue
                if not any(keyword.arg == "token" for keyword in node.keywords):
                    missing.append(f"{source_path.name}:{node.lineno}")

        self.assertEqual(missing, [], f"hs_request calls without token: {missing}")

    def test_gateway_helper_fails_closed_without_account_session(self):
        with patch.object(utils, "headscale_request") as request:
            with self.assertRaises(HTTPException) as raised:
                utils.hs_request("GET", "/api/v1/node", token="")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.detail["code"], "session_required")
        request.assert_not_called()

    def test_gateway_helper_forwards_explicit_account_session(self):
        response = httpx.Response(
            200,
            json={"nodes": []},
            request=httpx.Request("GET", "http://headscale.local/api/v1/node"),
        )
        with patch.object(utils, "headscale_request", return_value=response) as request:
            result = utils.hs_request(
                "GET",
                "/api/v1/node",
                token="opaque-session",
            )

        self.assertEqual(result, {"code": 0, "data": {"nodes": []}})
        request.assert_called_once_with(
            "GET",
            "/api/v1/node",
            token="opaque-session",
            json=None,
        )

    def test_gateway_helper_preserves_upstream_failure_status(self):
        response = httpx.Response(
            409,
            json={"code": "account_changed", "message": "retry"},
            request=httpx.Request("POST", "http://headscale.local/api/v1/node"),
        )
        with patch.object(utils, "headscale_request", return_value=response):
            with self.assertRaises(HTTPException) as raised:
                utils.hs_request("POST", "/api/v1/node", token="opaque-session")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "account_changed")


if __name__ == "__main__":
    unittest.main()
