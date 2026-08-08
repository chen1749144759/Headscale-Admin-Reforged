"""Headscale UDS gateway and system utility helpers."""

from __future__ import annotations

from fastapi import HTTPException

from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error


def hs_request(method: str, path: str, data=None, *, token: str) -> dict:
    """Call the authenticated Headscale REST gateway through the private socket."""
    if not token:
        raise HTTPException(
            401,
            detail={"code": "session_required", "message": "Headscale account session is required"},
        )
    try:
        response = headscale_request(method, path, token=token, json=data)
    except HeadscaleUnavailable as exc:
        raise HTTPException(
            503,
            detail={"code": "headscale_unavailable", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            502,
            detail={"code": "headscale_invalid_response", "message": str(exc)},
        ) from exc

    if response.status_code >= 400:
        code, message = response_error(response)
        status = response.status_code if 400 <= response.status_code <= 599 else 502
        raise HTTPException(status, detail={"code": code, "message": message})
    if response.status_code == 204 or not response.content:
        return {"code": 0, "data": None}
    try:
        return {"code": 0, "data": response.json()}
    except ValueError:
        return {"code": 0, "data": response.text}


def check_headscale_health() -> bool:
    try:
        response = headscale_request("GET", "/v1/health")
        return response.status_code == 200 and response.json().get("status") == "ok"
    except (HeadscaleUnavailable, ValueError):
        return False


def is_headscale_running() -> bool:
    return check_headscale_health()


def get_headscale_version(token: str) -> str:
    result = hs_request("GET", "/api/v1/version", token=token)
    if result.get("code") == 0:
        data = result.get("data")
        if isinstance(data, dict):
            return str(data.get("version") or data.get("Version") or "")
        if data:
            return str(data)
    return ""
