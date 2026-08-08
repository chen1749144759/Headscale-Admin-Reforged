"""HMAC authentication shared by the two private Unix-socket directions."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Mapping


AUTH_VERSION = "1"
CLOCK_SKEW_SECONDS = 60
MAX_REPLAY_ENTRIES = 8192
MAX_BODY_BYTES = 1 << 20
AUTH_CONTEXT_HEADERS = (
    "authorization",
    "x-scaleforge-node-id",
    "x-scaleforge-source",
    "x-scaleforge-source-ip",
    "x-scaleforge-user-id",
)
_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@lru_cache(maxsize=1)
def internal_auth_key() -> bytes:
    path = Path(
        os.environ.get(
            "SCALEFORGE_INTERNAL_AUTH_KEY_FILE",
            "/run/secrets/scaleforge_internal_auth_key",
        )
    )
    try:
        value = path.read_bytes().strip()
    except OSError as exc:
        raise RuntimeError(f"unable to read internal authentication key: {path}") from exc
    if len(value) < 32 or len(value) > 4096:
        raise RuntimeError("internal authentication key must contain 32 to 4096 bytes")
    return value


def canonical_request(
    method: str,
    path: str,
    query: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    auth_headers: Mapping[str, str] | None = None,
) -> bytes:
    body_digest = hashlib.sha256(body).hexdigest()
    normalized_headers = {
        key.lower(): str(value).strip()
        for key, value in (auth_headers or {}).items()
    }
    context = "".join(
        f"{name}:{normalized_headers.get(name, '')}\n"
        for name in AUTH_CONTEXT_HEADERS
    ).encode("utf-8")
    context_digest = hashlib.sha256(context).hexdigest()
    return "\n".join(
        (method.upper(), path, query, timestamp, nonce, body_digest, context_digest)
    ).encode("utf-8")


def internal_auth_headers(
    method: str,
    path: str,
    query: str,
    body: bytes,
    *,
    now: int | None = None,
    nonce: str | None = None,
    auth_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    timestamp = str(int(time.time()) if now is None else int(now))
    nonce = nonce or secrets.token_hex(16)
    signature = hmac.new(
        internal_auth_key(),
        canonical_request(method, path, query, timestamp, nonce, body, auth_headers),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-ScaleForge-Auth-Version": AUTH_VERSION,
        "X-ScaleForge-Auth-Timestamp": timestamp,
        "X-ScaleForge-Auth-Nonce": nonce,
        "X-ScaleForge-Auth-Signature": signature,
    }


class ReplayCache:
    def __init__(self, max_entries: int = MAX_REPLAY_ENTRIES):
        self.max_entries = max_entries
        self._entries: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    def accept(self, nonce: str, now: int) -> bool:
        cutoff = now - CLOCK_SKEW_SECONDS
        with self._lock:
            while self._entries:
                _, seen_at = next(iter(self._entries.items()))
                if seen_at >= cutoff:
                    break
                self._entries.popitem(last=False)
            if nonce in self._entries:
                return False
            while len(self._entries) >= self.max_entries:
                self._entries.popitem(last=False)
            self._entries[nonce] = now
            return True


internal_replay_cache = ReplayCache()


def verify_internal_request(
    method: str,
    path: str,
    query: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    now: int | None = None,
    replay_cache: ReplayCache = internal_replay_cache,
) -> bool:
    now = int(time.time()) if now is None else int(now)
    version = headers.get("x-scaleforge-auth-version", "")
    timestamp = headers.get("x-scaleforge-auth-timestamp", "")
    nonce = headers.get("x-scaleforge-auth-nonce", "")
    signature = headers.get("x-scaleforge-auth-signature", "")
    if version != AUTH_VERSION or not _HEX_32.fullmatch(nonce) or not _HEX_64.fullmatch(signature):
        return False
    try:
        signed_at = int(timestamp)
    except ValueError:
        return False
    if abs(now - signed_at) > CLOCK_SKEW_SECONDS:
        return False
    expected = hmac.new(
        internal_auth_key(),
        canonical_request(method, path, query, timestamp, nonce, body, headers),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    return replay_cache.accept(nonce, now)
