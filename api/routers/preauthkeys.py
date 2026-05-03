"""
预认证密钥路由模块
处理预认证密钥的获取、创建、删除等
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from .dependencies import CurrentUser, get_current_user, record_log, get_db_conn
from .utils import hs_request

router = APIRouter(prefix="/api/preauthkeys", tags=["预认证密钥"])

class CreateKeyReq(BaseModel):
    reusable: bool = False
    ephemeral: bool = False
    expire_days: int = 7
    hs_user_id: Optional[int] = None  # headscale 用户(分组) ID，为空则用当前登录用户 ID

@router.get('')
def list_preauthkeys(user: CurrentUser = Depends(get_current_user)):
    """获取预认证密钥列表 — 全量拉取再按角色过滤"""
    result = hs_request('GET', '/api/v1/preauthkey')
    if result.get('code') != 0:
        return result

    raw_data = result.get('data', {})
    all_keys = raw_data.get('preAuthKeys', []) if isinstance(raw_data, dict) else []

    # 非管理员只能看自己的密钥
    if user.role != 'manager':
        all_keys = [k for k in all_keys if str(k.get('user', {}).get('id', '')) == str(user.id)]

    # 格式化
    formatted = []
    for k in all_keys:
        # 处理过期时间
        exp = k.get('expiration', '')
        try:
            if exp:
                exp_dt = datetime.fromisoformat(exp.replace('Z', '+00:00'))
                exp = exp_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass

        created = k.get('createdAt', '')
        try:
            if created:
                c_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                created = c_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass

        formatted.append({
            'id': k.get('id', ''),
            'key': k.get('key', ''),
            'user_name': k.get('user', {}).get('name', ''),
            'reusable': k.get('reusable', False),
            'ephemeral': k.get('ephemeral', False),
            'used': k.get('used', False),
            'expiration': exp,
            'created_at': created,
        })

    return {'code': 0, 'data': formatted}

@router.post('')
def create_preauthkey(req: CreateKeyReq, user: CurrentUser = Depends(get_current_user)):
    """创建预认证密钥 — 支持指定 headscale 用户(分组)"""
    expire_date = datetime.utcnow() + timedelta(days=req.expire_days)

    # 使用指定的 headscale 用户 ID，若未指定则用当前登录用户 ID
    target_user_id = req.hs_user_id if req.hs_user_id is not None else user.id

    result = hs_request('POST', '/api/v1/preauthkey', {
        'user': target_user_id,
        'reusable': req.reusable,
        'ephemeral': req.ephemeral,
        'expiration': expire_date.isoformat() + 'Z',
    })

    # 记录日志
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'创建预认证密钥 (用户: {user.name})')
        conn.commit()
    finally:
        conn.close()

    # 提取创建出来的 key 返给前端
    if result.get('code') == 0:
        raw = result.get('data', {})
        if isinstance(raw, dict) and 'preAuthKey' in raw:
            key_data = raw['preAuthKey']
            return {'code': 0, 'data': {'key': key_data.get('key', '')}}
    return result

@router.delete('/{key_id}')
def delete_preauthkey(key_id: str, user: CurrentUser = Depends(get_current_user)):
    """删除预认证密钥 — 直接从 headscale DB 删除"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        # 非管理员只能删自己的密钥
        if user.role != 'manager':
            cur.execute("SELECT user_id FROM pre_auth_keys WHERE id = %s", (key_id,))
            row = cur.fetchone()
            if not row or str(row[0]) != str(user.id):
                return {'code': 1, 'msg': '无权限删除此密钥'}
        cur.execute("DELETE FROM pre_auth_keys WHERE id = %s", (key_id,))
        conn.commit()
        record_log(conn, user.id, f'删除预认证密钥 (ID: {key_id})')
        conn.commit()
    except Exception as e:
        return {'code': 1, 'msg': f'删除失败: {str(e)}'}
    finally:
        conn.close()
    return {'code': 0, 'msg': '删除成功'}
