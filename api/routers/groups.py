"""Reusable business groups for managed ScaleTail users."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, require_manager, get_db_conn, record_log
from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error

router = APIRouter(prefix="/api/groups", tags=["分组"])


class CreateHsUserReq(BaseModel):
    name: str


@router.get('')
def list_hs_users(user: CurrentUser = Depends(require_manager)):
    """List business groups; these are not Headscale protocol users."""
    response = _private_request('GET', '/v1/groups', user)
    return {'code': 0, 'data': response.json()}


@router.post('')
def create_hs_user(req: CreateHsUserReq, user: CurrentUser = Depends(require_manager)):
    """Create a reusable business group."""
    name = req.name.strip()
    if not name:
        raise HTTPException(400, '分组名称不能为空')

    response = _private_request('POST', '/v1/groups', user, data={'name': name}, expected=(201,))

    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'创建业务分组: {name}')
        conn.commit()
    finally:
        conn.close()

    return {'code': 0, 'msg': f'分组 {name} 创建成功', 'data': response.json()}


@router.delete('/{uid}')
def delete_hs_user(uid: int, user: CurrentUser = Depends(require_manager)):
    """Delete an empty business group."""
    groups = list_hs_users(user).get('data') or []
    group_name = next((item.get('name') for item in groups if int(item.get('id', 0)) == uid), str(uid))
    _private_request('DELETE', f'/v1/groups/{uid}', user, expected=(204,))

    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'删除业务分组: {group_name}')
        conn.commit()
    finally:
        conn.close()

    return {'code': 0, 'msg': '分组删除成功'}


def _private_request(method: str, path: str, user: CurrentUser, *, data=None, expected=(200,)):
    try:
        response = headscale_request(method, path, token=user.session_token, json=data)
    except HeadscaleUnavailable as exc:
        raise HTTPException(503, '业务分组服务暂不可用') from exc
    if response.status_code not in expected:
        code, message = response_error(response)
        raise HTTPException(
            response.status_code if 400 <= response.status_code <= 599 else 502,
            detail={'code': code, 'message': message},
        )
    return response
