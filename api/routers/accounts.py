"""Platform account administration proxied to Headscale over UDS."""

from __future__ import annotations

import threading
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .dependencies import CurrentUser, require_manager
from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error


router = APIRouter(prefix="/api/accounts", tags=["平台账户"])
_binding_lock = threading.Lock()


class AccountCreateReq(BaseModel):
    username: str
    password: str
    user_id: Optional[int] = Field(default=None, alias="userId")
    role: str = "user"
    enabled: bool = True
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


class AccountUpdateReq(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    enabled: Optional[bool] = None
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")
    clear_expires_at: bool = Field(default=False, alias="clearExpiresAt")
    user_id: Optional[int] = Field(default=None, alias="userId")
    clear_user: bool = Field(default=False, alias="clearUser")

    model_config = {"populate_by_name": True}


class PasswordResetReq(BaseModel):
    new_password: str = Field(alias="newPassword")

    model_config = {"populate_by_name": True}


def _private_or_error(
    method: str,
    path: str,
    user: CurrentUser,
    *,
    data=None,
    expected: tuple[int, ...] = (200,),
) -> httpx.Response:
    try:
        response = headscale_request(method, path, token=user.session_token, json=data)
    except HeadscaleUnavailable as exc:
        raise HTTPException(503, "账户服务暂不可用") from exc
    if response.status_code not in expected:
        code, message = response_error(response)
        raise HTTPException(
            response.status_code if 400 <= response.status_code <= 599 else 502,
            detail={"code": code, "message": message},
        )
    return response


def _list_private_accounts(user: CurrentUser) -> list[dict]:
    response = _private_or_error("GET", "/v1/accounts", user)
    payload = response.json()
    if not isinstance(payload, list):
        raise HTTPException(502, "账户服务返回了无效列表")
    return payload


def _assert_user_binding_available(
    accounts: list[dict],
    user_id: int | None,
    *,
    exclude_account_id: int | None = None,
) -> None:
    if user_id is None:
        return
    for account in accounts:
        if exclude_account_id is not None and int(account.get("id", 0)) == exclude_account_id:
            continue
        if account.get("userId") is not None and int(account["userId"]) == user_id:
            raise HTTPException(409, "该网络分组已绑定其他账户；账户与分组必须一对一")


@router.get("")
def list_accounts(user: CurrentUser = Depends(require_manager)):
    return {"code": 0, "data": _list_private_accounts(user)}


@router.post("")
def create_account(req: AccountCreateReq, user: CurrentUser = Depends(require_manager)):
    if req.role == 'user' and req.user_id is None:
        raise HTTPException(400, '普通账户必须绑定一个网络分组')
    with _binding_lock:
        _assert_user_binding_available(_list_private_accounts(user), req.user_id)
        response = _private_or_error(
            "POST",
            "/v1/accounts",
            user,
            data={
                "username": req.username.strip(),
                "password": req.password,
                "userId": req.user_id,
                "role": req.role,
                "enabled": req.enabled,
                "expiresAt": req.expires_at,
            },
            expected=(201,),
        )
    account = response.json()
    return {"code": 0, "msg": "账户已创建", "data": account}


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    req: AccountUpdateReq,
    user: CurrentUser = Depends(require_manager),
):
    payload = req.model_dump(by_alias=True, exclude_none=True)
    with _binding_lock:
        accounts = _list_private_accounts(user)
        target = next((item for item in accounts if int(item.get('id', 0)) == account_id), None)
        if target is None:
            raise HTTPException(404, '账户不存在')
        resulting_role = req.role or target.get('role') or 'user'
        if req.clear_user:
            resulting_user_id = None
        elif req.user_id is not None:
            resulting_user_id = req.user_id
        else:
            resulting_user_id = target.get('userId')
        if resulting_role == 'user' and resulting_user_id is None:
            raise HTTPException(400, '普通账户必须绑定一个网络分组')
        if req.user_id is not None and not req.clear_user:
            _assert_user_binding_available(
                accounts,
                req.user_id,
                exclude_account_id=account_id,
            )
        response = _private_or_error(
            "PATCH",
            f"/v1/accounts/{account_id}",
            user,
            data=payload,
        )
    account = response.json()
    return {"code": 0, "msg": "账户已更新", "data": account}


@router.put("/{account_id}/password")
def reset_account_password(
    account_id: int,
    req: PasswordResetReq,
    user: CurrentUser = Depends(require_manager),
):
    _private_or_error(
        "PUT",
        f"/v1/accounts/{account_id}/password",
        user,
        data={"newPassword": req.new_password},
        expected=(204,),
    )
    return {"code": 0, "msg": "账户密码已重置"}
