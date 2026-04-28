"""
用户(机器)路由模块
处理 Tailscale 机器（用户）相关的增删改查、注册、重命名等
"""
import json

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException

from .dependencies import CurrentUser, get_current_user, require_manager, get_db_conn, record_log
from .utils import hs_request

router = APIRouter(prefix="/api/users", tags=["用户(机器)"])


def _get_node_name(node_id) -> str:
    """从 Headscale 查询节点名称，失败时返回 ID"""
    try:
        nr = hs_request('GET', f'/api/v1/node/{node_id}')
        nd = nr.get('data', nr) if isinstance(nr, dict) else {}
        nd = nd.get('node', nd) if isinstance(nd, dict) else {}
        return nd.get('givenName') or nd.get('name') or str(node_id)
    except Exception:
        return str(node_id)

@router.get('')
def list_nodes(user: CurrentUser = Depends(get_current_user)):
    """获取节点列表"""
    result = hs_request('GET', '/api/v1/node')
    return result

@router.post('/register')
def register_node(registration_id: str, user: CurrentUser = Depends(get_current_user)):
    """使用 registrationID 注册节点"""
    # 检查当前用户节点数量是否超过限制
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) as count FROM nodes WHERE user_id = %s", (user.id,))
        node_count = cur.fetchone()['count']
        
        cur.execute("SELECT node FROM users WHERE id = %s", (user.id,))
        user_result = cur.fetchone()
        user_node_limit = user_result['node'] if user_result else 0
        
        if int(node_count) >= int(user_node_limit):
            raise HTTPException(400, '超过此用户节点限制')
    finally:
        conn.close()
    
    # 调用 headscale API 注册节点
    url_path = f'/api/v1/node/register?user={user.name}&key={registration_id}'
    result = hs_request('POST', url_path)
    
    if result.get('code') == 0:
        conn = get_db_conn()
        try:
            record_log(conn, user.id, '节点注册成功')
            conn.commit()
        finally:
            conn.close()
        return {'code': 0, 'msg': '节点添加成功', 'data': result.get('data')}
    else:
        raise HTTPException(400, result.get('msg', '节点注册失败'))

@router.delete('/{node_id}')
def delete_node(node_id: str, user: CurrentUser = Depends(get_current_user)):
    """删除节点"""
    node_name = _get_node_name(node_id)
    result = hs_request('DELETE', f'/api/v1/node/{node_id}')
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'删除节点 {node_name}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.post('/{node_id}/expire')
def expire_node(node_id: str, user: CurrentUser = Depends(get_current_user)):
    """过期节点"""
    node_name = _get_node_name(node_id)
    result = hs_request('POST', f'/api/v1/node/{node_id}/expire')
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'过期节点 {node_name}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.post('/{node_id}/rename')
def rename_node(node_id: str, name: str, user: CurrentUser = Depends(get_current_user)):
    """节点重命名"""
    if not name:
        raise HTTPException(400, '节点名称不能为空')
    
    result = hs_request('POST', f'/api/v1/node/{node_id}/rename/{name}')
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'重命名节点 {_get_node_name(node_id)} 为 {name}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.get('/{node_id}/info')
def get_node_info(node_id: str, user: CurrentUser = Depends(get_current_user)):
    """获取节点详细信息（从数据库）"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_query = """
            SELECT n.host_info, n.user_id
            FROM nodes n
            JOIN users u ON n.user_id = u.id
            WHERE n.id = %s
        """
        params = [node_id]
        
        # 非管理员只能查看自己的节点
        if not user.is_manager():
            base_query += " AND n.user_id = %s"
            params.append(user.id)
        
        cur.execute(base_query, params)
        node = cur.fetchone()
        
        if not node:
            raise HTTPException(404, f'未找到ID为 {node_id} 的节点，或您没有权限查看')
        
        host_info = json.loads(node['host_info']) if node['host_info'] else {}
        
        return {
            'code': 0,
            'data': {
                'OS': (host_info.get('OS') or '') + (host_info.get('OSVersion') or ''),
                'Client': host_info.get('IPNVersion') or '',
                'user_id': node['user_id'],
            }
        }
    finally:
        conn.close()

@router.get('/{node_id}/routes')
def get_node_routes(node_id: str, user: CurrentUser = Depends(get_current_user)):
    """获取节点路由"""
    result = hs_request('GET', f'/api/v1/node/{node_id}/routes')
    return result


from pydantic import BaseModel as _BaseModel

class ChangeUserReq(_BaseModel):
    new_user: str

@router.post('/{node_id}/move-user')
def move_node_user(node_id: str, req: ChangeUserReq, user: CurrentUser = Depends(require_manager)):
    """将节点移动到另一个 headscale 分组(user) — 调用 Headscale AE MoveNode API"""
    new_user = req.new_user
    if not new_user:
        raise HTTPException(400, '目标分组不能为空')

    # 调用 Headscale AE 原生 MoveNode API，热更新内存+DB，无需重启
    result = hs_request('POST', f'/api/v1/node/{node_id}/user', {'user': new_user})

    if result.get('code') == 0:
        conn = get_db_conn()
        try:
            record_log(conn, user.id, f'移动节点 {_get_node_name(node_id)} 到分组 {new_user}')
            conn.commit()
        finally:
            conn.close()
        return {'code': 0, 'msg': f'节点已移动到分组「{new_user}」'}
    else:
        raise HTTPException(400, result.get('msg', '移动节点失败'))

class SetTagsReq(_BaseModel):
    tags: list

@router.post('/{node_id}/tags')
def set_node_tags(node_id: str, req: SetTagsReq, user: CurrentUser = Depends(require_manager)):
    """设置节点的强制标签 — 调用 Headscale SetTags API"""
    tags = req.tags or []
    # 确保 tag 格式为 tag:xxx
    formatted = [t if t.startswith('tag:') else f'tag:{t}' for t in tags]

    result = hs_request('POST', f'/api/v1/node/{node_id}/tags', {'tags': formatted})

    if result.get('code') == 0:
        conn = get_db_conn()
        try:
            record_log(conn, user.id, f'设置节点 {_get_node_name(node_id)} 标签: {formatted}')
            conn.commit()
        finally:
            conn.close()
        return {'code': 0, 'msg': '标签已更新', 'data': result.get('data')}
    else:
        raise HTTPException(400, result.get('msg', '设置标签失败'))

@router.post('/{node_id}/approve-routes')
def approve_routes(node_id: str, routes: list, user: CurrentUser = Depends(get_current_user)):
    """批准路由（需要用户开启路由权限）"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT route FROM users WHERE id = %s", (user.id,))
        row = cur.fetchone()
        
        if not row or row['route'] == 0:
            raise HTTPException(403, '你当前无此权限！请联系管理员')
    finally:
        conn.close()
    
    result = hs_request('POST', f'/api/v1/node/{node_id}/approve_routes', {'routes': routes})
    return result
