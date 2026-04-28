"""
Headscale 用户(分组)路由模块
管理 headscale 的用户命名空间（即分组：dev, uat, devops 等）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, require_manager, get_db_conn, record_log
from .utils import hs_request

router = APIRouter(prefix="/api/hs-users", tags=["Headscale 分组"])


class CreateHsUserReq(BaseModel):
    name: str


@router.get('')
def list_hs_users(user: CurrentUser = Depends(require_manager)):
    """获取 headscale 用户(分组)列表"""
    result = hs_request('GET', '/api/v1/user')
    if result.get('code') != 0:
        return result

    raw = result.get('data', {})
    users = raw.get('users', []) if isinstance(raw, dict) else []

    formatted = []
    for u in users:
        formatted.append({
            'id': u.get('id', ''),
            'name': u.get('name', ''),
            'created_at': u.get('createdAt', ''),
        })

    return {'code': 0, 'data': formatted}


@router.post('')
def create_hs_user(req: CreateHsUserReq, user: CurrentUser = Depends(require_manager)):
    """创建 headscale 用户(分组)"""
    name = req.name.strip()
    if not name:
        raise HTTPException(400, '分组名称不能为空')

    result = hs_request('POST', '/api/v1/user', {'name': name})

    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'创建 headscale 分组: {name}')
        conn.commit()
    finally:
        conn.close()

    if result.get('code') == 0:
        return {'code': 0, 'msg': f'分组 {name} 创建成功'}
    return result


@router.delete('/{uid}')
def delete_hs_user(uid: int, user: CurrentUser = Depends(require_manager)):
    """删除 headscale 用户(分组) — 需传数字 ID，用户下有节点时会拒绝"""
    result = hs_request('DELETE', f'/api/v1/user/{uid}')

    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'删除 headscale 分组 (ID: {uid})')
        conn.commit()
    finally:
        conn.close()

    if result.get('code') == 0:
        return {'code': 0, 'msg': '分组删除成功'}
    return result
