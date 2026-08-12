"""Platform account administration proxied to Headscale over UDS."""

from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .dependencies import CurrentUser, require_manager
from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error
from .acl import refresh_acl_business_groups


router = APIRouter(prefix="/api/accounts", tags=["用户"])
class AccountCreateReq(BaseModel):
    username: str
    password: str
    group_id: Optional[int] = Field(default=None, alias="groupId")
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
    group_id: Optional[int] = Field(default=None, alias="groupId")
    clear_group: bool = Field(default=False, alias="clearGroup")

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


@router.get("")
def list_accounts(user: CurrentUser = Depends(require_manager)):
    return {"code": 0, "data": _list_private_accounts(user)}


@router.post("")
def create_account(req: AccountCreateReq, user: CurrentUser = Depends(require_manager)):
    if req.role == 'user' and req.group_id is None:
        raise HTTPException(400, '普通用户必须属于一个业务分组')
    response = _private_or_error(
        "POST",
        "/v1/accounts",
        user,
        data={
            "username": req.username.strip(),
            "password": req.password,
            "groupId": req.group_id,
            "role": req.role,
            "enabled": req.enabled,
            "expiresAt": req.expires_at,
        },
        expected=(201,),
    )
    account = response.json()
    refresh_acl_business_groups(user)
    return {"code": 0, "msg": "账户已创建", "data": account}


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    req: AccountUpdateReq,
    user: CurrentUser = Depends(require_manager),
):
    payload = req.model_dump(by_alias=True, exclude_none=True)
    accounts = _list_private_accounts(user)
    target = next((item for item in accounts if int(item.get('id', 0)) == account_id), None)
    if target is None:
        raise HTTPException(404, '账户不存在')
    resulting_role = req.role or target.get('role') or 'user'
    if req.clear_group:
        resulting_group_id = None
    elif req.group_id is not None:
        resulting_group_id = req.group_id
    else:
        resulting_group_id = target.get('groupId')
    if resulting_role == 'user' and resulting_group_id is None:
        raise HTTPException(400, '普通用户必须属于一个业务分组')
    response = _private_or_error(
        "PATCH",
        f"/v1/accounts/{account_id}",
        user,
        data=payload,
    )
    account = response.json()
    refresh_acl_business_groups(user)
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
