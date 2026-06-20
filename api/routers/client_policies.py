"""
客户端策略路由
管理全局、分组、机器三层限速和流量配额策略。
"""
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, require_manager, get_db_conn, record_log

router = APIRouter(prefix="/api/client-policies", tags=["客户端策略"])


class PolicyReq(BaseModel):
    scope: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None
    rate_up_mbps: Optional[float] = None
    rate_down_mbps: Optional[float] = None
    monthly_quota_gb: Optional[float] = None
    exceed_action: str = 'throttle'
    enabled: bool = True
    priority: int = 100
    remark: str = ''


def _validate_policy(req: PolicyReq):
    if req.scope not in ('global', 'group', 'machine'):
        raise HTTPException(400, '策略作用域只能是 global/group/machine')
    if req.scope == 'group' and not (req.group_id or req.group_name):
        raise HTTPException(400, '分组策略必须选择分组')
    if req.scope == 'machine' and not req.machine_id:
        raise HTTPException(400, '机器策略必须选择机器')
    if req.exceed_action not in ('alert', 'throttle', 'block'):
        raise HTTPException(400, '超额动作只能是 alert/throttle/block')


@router.get('')
def list_policies(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                id, scope, group_id, group_name, machine_id, machine_name,
                rate_up_mbps, rate_down_mbps, monthly_quota_gb,
                exceed_action, enabled, priority, remark,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM client_policies
            ORDER BY enabled DESC, priority ASC, id DESC
        """)
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()


@router.post('')
def create_policy(req: PolicyReq, user: CurrentUser = Depends(require_manager)):
    _validate_policy(req)
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO client_policies (
                scope, group_id, group_name, machine_id, machine_name,
                rate_up_mbps, rate_down_mbps, monthly_quota_gb,
                exceed_action, enabled, priority, created_by, remark
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            req.scope, req.group_id, req.group_name, req.machine_id, req.machine_name,
            req.rate_up_mbps, req.rate_down_mbps, req.monthly_quota_gb,
            req.exceed_action, req.enabled, req.priority, user.id, req.remark,
        ))
        row = cur.fetchone()
        record_log(conn, user.id, f'创建客户端策略 #{row["id"]} ({req.scope})')
        conn.commit()
        return {'code': 0, 'msg': '策略已创建', 'data': row}
    finally:
        conn.close()


@router.put('/{policy_id}')
def update_policy(policy_id: int, req: PolicyReq, user: CurrentUser = Depends(require_manager)):
    _validate_policy(req)
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE client_policies SET
                scope=%s, group_id=%s, group_name=%s, machine_id=%s, machine_name=%s,
                rate_up_mbps=%s, rate_down_mbps=%s, monthly_quota_gb=%s,
                exceed_action=%s, enabled=%s, priority=%s, remark=%s, updated_at=NOW()
            WHERE id=%s
        """, (
            req.scope, req.group_id, req.group_name, req.machine_id, req.machine_name,
            req.rate_up_mbps, req.rate_down_mbps, req.monthly_quota_gb,
            req.exceed_action, req.enabled, req.priority, req.remark, policy_id,
        ))
        record_log(conn, user.id, f'更新客户端策略 #{policy_id}')
        conn.commit()
        return {'code': 0, 'msg': '策略已更新'}
    finally:
        conn.close()


@router.delete('/{policy_id}')
def delete_policy(policy_id: int, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM client_policies WHERE id=%s", (policy_id,))
        record_log(conn, user.id, f'删除客户端策略 #{policy_id}')
        conn.commit()
        return {'code': 0, 'msg': '策略已删除'}
    finally:
        conn.close()


@router.get('/states')
def policy_states(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                id, policy_id, machine_id, machine_name, applied, error,
                TO_CHAR(applied_at, 'YYYY-MM-DD HH24:MI:SS') AS applied_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM client_policy_states
            ORDER BY updated_at DESC
            LIMIT 100
        """)
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()

