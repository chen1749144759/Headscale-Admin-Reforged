"""
用户路由模块
处理用户管理、权限控制等
"""
import psycopg2
import psycopg2.extras
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, get_current_user, require_manager, get_db_conn, record_log

router = APIRouter(prefix="/api/users", tags=["用户"])

# 请求模型
class UserUpdateReq(BaseModel):
    expire_days: Optional[int] = None
    node_count: Optional[int] = None
    route_enable: Optional[bool] = None
    user_enable: Optional[bool] = None

class UserExpireReq(BaseModel):
    new_expire: str

class UserNodeCountReq(BaseModel):
    new_node_count: int

class UserToggleReq(BaseModel):
    enable: bool

@router.get('')
def list_users(user: CurrentUser = Depends(get_current_user)):
    """获取用户列表"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, name, role, email, cellphone, node, route, enable, "
            "TO_CHAR(expire, 'YYYY-MM-DD HH24:MI:SS') as expire, "
            "TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at "
            "FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        return {'code': 0, 'data': rows}
    finally:
        conn.close()

@router.get('/stats')
def user_stats(user: CurrentUser = Depends(get_current_user)):
    """获取当前用户的统计信息"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at, "
            "TO_CHAR(expire, 'YYYY-MM-DD HH24:MI:SS') as expire "
            "FROM users WHERE id = %s",
            (user.id,)
        )
        user_info = cur.fetchone()
        
        return {
            'code': 0,
            'data': {
                'created_at': user_info['created_at'] if user_info else '',
                'expire': user_info['expire'] if user_info else '',
            }
        }
    finally:
        conn.close()

@router.delete('/{uid}')
def delete_user(uid: int, user: CurrentUser = Depends(require_manager)):
    """删除用户"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s AND role != 'manager'", (uid,))
        record_log(conn, user.id, f'删除用户 {uid}')
        conn.commit()
        return {'code': 0, 'msg': '删除成功'}
    finally:
        conn.close()

@router.post('/{uid}/update')
def update_user(uid: int, req: UserUpdateReq, user: CurrentUser = Depends(require_manager)):
    """更新用户信息（批量）"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        updates = []
        params = []
        
        if req.expire_days is not None:
            updates.append(f"expire=NOW() + INTERVAL '{req.expire_days} days'")
        if req.node_count is not None:
            updates.append("node=%s")
            params.append(req.node_count)
        if req.route_enable is not None:
            updates.append("route=%s")
            params.append(1 if req.route_enable else 0)
        if req.user_enable is not None:
            updates.append("enable=%s")
            params.append(1 if req.user_enable else 0)
        
        if updates:
            sql = f"UPDATE users SET {', '.join(updates)}, updated_at=NOW() WHERE id=%s"
            params.append(uid)
            cur.execute(sql, params)
            record_log(conn, user.id, f'更新用户 {uid}')
        
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()

@router.post('/{uid}/update-expire')
def update_user_expire(uid: int, req: UserExpireReq, user: CurrentUser = Depends(require_manager)):
    """修改用户过期时间"""
    if not req.new_expire:
        raise HTTPException(400, '新的过期时间不能为空')
    
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET expire = %s WHERE id = %s", (req.new_expire, uid))
        record_log(conn, user.id, f'修改用户 {uid} 的过期时间为 {req.new_expire}')
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()

@router.post('/{uid}/update-node-count')
def update_user_node_count(uid: int, req: UserNodeCountReq, user: CurrentUser = Depends(require_manager)):
    """修改用户节点配额"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET node = %s WHERE id = %s", (req.new_node_count, uid))
        record_log(conn, user.id, f'修改用户 {uid} 的节点配额为 {req.new_node_count}')
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()

@router.post('/{uid}/toggle-enable')
def toggle_user_enable(uid: int, req: UserToggleReq, user: CurrentUser = Depends(require_manager)):
    """启用/禁用用户"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT name FROM users WHERE id = %s", (uid,))
        target_user = cur.fetchone()
        
        if not target_user:
            raise HTTPException(404, '用户不存在')
        
        if target_user['name'] == 'admin' and not req.enable:
            raise HTTPException(400, '停用失败，无法停用admin用户')
        
        cur.execute("UPDATE users SET enable = %s WHERE id = %s", (1 if req.enable else 0, uid))
        record_log(conn, user.id, f'{"启用" if req.enable else "禁用"}用户 {uid}')
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()

@router.post('/{uid}/toggle-route')
def toggle_user_route(uid: int, req: UserToggleReq, user: CurrentUser = Depends(require_manager)):
    """启用/禁用用户路由权限"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET route = %s WHERE id = %s", (1 if req.enable else 0, uid))
        record_log(conn, user.id, f'{"启用" if req.enable else "禁用"}用户 {uid} 的路由权限')
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()
