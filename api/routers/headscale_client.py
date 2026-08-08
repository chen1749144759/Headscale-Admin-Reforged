"""Headscale private Unix-socket client.

The management plane is intentionally unreachable over TCP. ScaleForge only
accepts relative paths and always sends them through the configured UDS.
"""

from __future__ import annotations

import os
import json as json_module
import threading
from typing import Any
from urllib.parse import urlsplit

import httpx

from api.internal_auth import internal_auth_headers


SOCKET_PATH = os.environ.get(
    "HEADSCALE_SOCKET",
    "/var/run/scaleforge/control/api.sock",
)
BASE_URL = "http://headscale.local"


class HeadscaleUnavailable(RuntimeError):
    """The private Headscale socket cannot be reached."""


_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                transport = httpx.HTTPTransport(uds=SOCKET_PATH, retries=1)
                _client = httpx.Client(
                    base_url=BASE_URL,
                    transport=transport,
                    timeout=httpx.Timeout(10.0, connect=3.0),
                    follow_redirects=False,
                    trust_env=False,
                )
    return _client


def close_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


def _validate_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Headscale private API path must be absolute-path relative")
    if "://" in path or "\\" in path:
        raise ValueError("Headscale private API path is invalid")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("Headscale private API path is invalid")
    return path


def request(
    method: str,
    path: str,
    *,
    token: str = "",
    source: str = "",
    json: Any = None,
) -> httpx.Response:
    validated_path = _validate_path(path)
    parsed = urlsplit(validated_path)
    body = b""
    if json is not None:
        body = json_module.dumps(
            json,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if source:
        headers["X-ScaleForge-Source"] = source
    if body:
        headers["Content-Type"] = "application/json"
    headers.update(
        internal_auth_headers(
            method,
            parsed.path,
            parsed.query,
            body,
            auth_headers=headers,
        )
    )

    try:
        return _get_client().request(
            method.upper(),
            validated_path,
            headers=headers,
            content=body or None,
        )
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        raise HeadscaleUnavailable(
            f"Headscale private socket is unavailable: {SOCKET_PATH}"
        ) from exc


def response_error(response: httpx.Response) -> tuple[str, str]:
    code = "headscale_request_failed"
    message = response.text.strip() or f"Headscale returned HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return code, message

    if isinstance(payload, dict):
        code = str(payload.get("code") or code)
        message = str(
            payload.get("error")
            or payload.get("message")
            or payload.get("detail")
            or message
        )
    return code, message
