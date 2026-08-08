"""Browser authentication backed by Headscale opaque account sessions."""

from __future__ import annotations

import threading
import time
import json
import ipaddress
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import dependencies as deps
from .dependencies import CurrentUser, get_current_user
from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error


router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRateLimiter:
    def __init__(self, limit: int = 10, window_seconds: int = 60, max_entries: int = 4096):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_entries = max_entries
        self._entries: dict[str, tuple[float, int, float]] = {}
        self._calls = 0
        self._lock = threading.Lock()

    def allow(self, source: str, username: str) -> bool:
        now = time.monotonic()
        key = f"{source.strip()}\0{username.strip().lower()}"
        with self._lock:
            self._calls += 1
            if self._calls % 256 == 0:
                cutoff = now - (self.window_seconds * 10)
                self._entries = {
                    entry_key: entry
                    for entry_key, entry in self._entries.items()
                    if entry[2] >= cutoff
                }
            entry = self._entries.get(key)
            if entry is None:
                if len(self._entries) >= self.max_entries:
                    oldest_key = min(
                        self._entries,
                        key=lambda entry_key: self._entries[entry_key][2],
                    )
                    self._entries.pop(oldest_key, None)
                self._entries[key] = (now, 1, now)
                return True
            started, attempts, _ = entry
            if now - started >= self.window_seconds:
                self._entries[key] = (now, 1, now)
                return True
            if attempts >= self.limit:
                self._entries[key] = (started, attempts, now)
                return False
            self._entries[key] = (started, attempts + 1, now)
            return True

    def reset(self, source: str, username: str) -> None:
        key = f"{source.strip()}\0{username.strip().lower()}"
        with self._lock:
            self._entries.pop(key, None)


login_rate_limiter = LoginRateLimiter()


def _authentication_source(request: Request) -> str:
    value = request.client.host if request.client else ""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"


class LoginReq(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=72)
    captchaToken: str = Field(default="", max_length=4096)


class ChangePasswordReq(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)


def _captcha_siteverify_url() -> str:
    if deps.CAPTCHA_SITEVERIFY_URL:
        return deps.CAPTCHA_SITEVERIFY_URL
    endpoint = deps.CAPTCHA_API_ENDPOINT.rstrip("/")
    if endpoint.startswith(("http://", "https://")):
        return f"{endpoint}/siteverify"
    return ""


def verify_captcha(token: str) -> None:
    if not deps.CAPTCHA_ENABLED:
        return
    if not token:
        raise HTTPException(400, "请先完成验证码")

    siteverify_url = _captcha_siteverify_url()
    if not siteverify_url or not deps.CAPTCHA_SECRET_KEY:
        raise HTTPException(500, "验证码服务未配置")

    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            with client.stream(
                "POST",
                siteverify_url,
                json={"secret": deps.CAPTCHA_SECRET_KEY, "response": token},
                headers={"Accept": "application/json"},
            ) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 64 * 1024:
                        raise ValueError("captcha response is too large")
                status_code = response.status_code
        payload = json.loads(bytes(raw).decode("utf-8"))
    except (httpx.HTTPError, ValueError, UnicodeError) as exc:
        raise HTTPException(502, "验证码服务不可用") from exc

    if not 200 <= status_code < 300 or not isinstance(payload, dict) or not payload.get("success"):
        raise HTTPException(400, "验证码校验失败，请重试")


def _raise_private_error(response: httpx.Response, fallback: str) -> None:
    code, message = response_error(response)
    status = response.status_code
    if status < 400 or status > 599:
        status = 502
    detail = {"code": code, "message": message or fallback}
    raise HTTPException(status, detail=detail)


def _cookie_max_age(expires_at: str | None) -> int | None:
    if not expires_at:
        return None
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        seconds = int((expires - datetime.now(timezone.utc)).total_seconds())
        return max(0, seconds)
    except (TypeError, ValueError):
        return None


def _public_account(account: dict, must_change_password: bool = False) -> dict:
    return {
        **account,
        "name": account.get("username", ""),
        "expire": account.get("expiresAt") or "",
        "mustChangePassword": bool(
            must_change_password or account.get("mustChangePassword", False)
        ),
    }


@router.post("/login")
def login(req: LoginReq, request: Request, response: Response):
    if deps.SESSION_COOKIE_SECURE and request.url.scheme != "https":
        raise HTTPException(426, "登录必须通过 HTTPS 访问")
    verify_captcha(req.captchaToken)
    source = _authentication_source(request)
    username = req.username.strip()
    if not login_rate_limiter.allow(source, username):
        raise HTTPException(429, "登录尝试过于频繁，请稍后重试")
    try:
        private_response = headscale_request(
            "POST",
            "/v1/sessions",
            source=source,
            json={"username": username, "password": req.password},
        )
    except HeadscaleUnavailable as exc:
        login_rate_limiter.reset(source, username)
        raise HTTPException(503, "认证服务暂不可用") from exc
    if private_response.status_code != 200:
        if private_response.status_code >= 500:
            login_rate_limiter.reset(source, username)
        _raise_private_error(private_response, "用户名或密码错误")

    login_rate_limiter.reset(source, username)

    payload = private_response.json()
    token = str(payload.get("token") or "")
    account = payload.get("account")
    if not token or not isinstance(account, dict):
        raise HTTPException(502, "认证服务返回了无效会话")

    max_age = _cookie_max_age(payload.get("expiresAt"))
    response.set_cookie(
        deps.SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        secure=deps.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"

    restricted = bool(payload.get("mustChangePassword"))
    return {
        "code": 0,
        "msg": "登录成功",
        "data": {
            "user": _public_account(account, restricted),
            "expiresAt": payload.get("expiresAt"),
            "mustChangePassword": restricted,
        },
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(deps.SESSION_COOKIE_NAME, "")
    server_session_revoked = True
    revocation_status = "not_required"
    message = "已退出"
    if token:
        try:
            private_response = headscale_request("DELETE", "/v1/session", token=token)
        except HeadscaleUnavailable:
            server_session_revoked = False
            revocation_status = "unavailable"
            message = "浏览器会话已清除，但认证服务暂不可用，服务端会话可能仍有效"
        else:
            if private_response.status_code == 204:
                revocation_status = "revoked"
            elif private_response.status_code == 401:
                revocation_status = "already_invalid"
            else:
                server_session_revoked = False
                revocation_status = "failed"
                message = "浏览器会话已清除，但服务端会话撤销失败"
    response.delete_cookie(
        deps.SESSION_COOKIE_NAME,
        secure=deps.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "code": 0,
        "msg": message,
        "data": {
            "browserSessionCleared": True,
            "serverSessionRevoked": server_session_revoked,
            "revocationStatus": revocation_status,
        },
    }


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {
        "code": 0,
        "data": _public_account(user.raw_account, user.must_change_password),
    }


@router.post("/password")
def change_password(
    req: ChangePasswordReq,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        private_response = headscale_request(
            "PUT",
            "/v1/session/password",
            token=user.session_token,
            source=_authentication_source(request),
            json={
                "currentPassword": req.old_password,
                "newPassword": req.new_password,
            },
        )
    except HeadscaleUnavailable as exc:
        raise HTTPException(503, "认证服务暂不可用") from exc
    if private_response.status_code != 204:
        _raise_private_error(private_response, "密码修改失败")

    response.delete_cookie(
        deps.SESSION_COOKIE_NAME,
        secure=deps.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"code": 0, "msg": "密码修改成功，请重新登录"}
