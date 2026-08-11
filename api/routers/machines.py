"""
用户(机器)路由模块
处理 Tailscale 机器（用户）相关的增删改查、注册、重命名等
"""
import json

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from urllib.parse import quote

from .dependencies import (
    CurrentUser,
    get_current_user,
    require_manager,
    get_db_conn,
    record_log,
    require_node_access,
)
from .utils import hs_request

router = APIRouter(prefix="/api/users", tags=["用户(机器)"])


def _get_node_name(node_id: int, token: str) -> str:
    """从 Headscale 查询节点名称，失败时返回 ID"""
    try:
        nr = hs_request('GET', f'/api/v1/node/{node_id}', token=token)
        nd = nr.get('data', nr) if isinstance(nr, dict) else {}
        nd = nd.get('node', nd) if isinstance(nd, dict) else {}
        return nd.get('givenName') or nd.get('name') or str(node_id)
    except Exception:
        return str(node_id)

@router.get('')
def list_nodes(user: CurrentUser = Depends(get_current_user)):
    """获取节点列表"""
    result = hs_request('GET', '/api/v1/node', token=user.session_token)
    if result.get('code') != 0 or user.is_manager():
        return result

    payload = result.get('data')
    if isinstance(payload, dict):
        nodes = payload.get('nodes', [])
        filtered = [
            node for node in nodes
            if str((node.get('user') or {}).get('id', '')) == str(user.network_user_id)
        ]
        result['data'] = {**payload, 'nodes': filtered}
    elif isinstance(payload, list):
        result['data'] = [
            node for node in payload
            if str((node.get('user') or {}).get('id', '')) == str(user.network_user_id)
        ]
    return result


@router.delete('/{node_id}')
def delete_node(node_id: int, user: CurrentUser = Depends(get_current_user)):
    """删除节点"""
    require_node_access(node_id, user)
    node_name = _get_node_name(node_id, user.session_token)
    result = hs_request(
        'DELETE',
        f'/api/v1/node/{node_id}',
        token=user.session_token,
    )
    if result.get('code') != 0:
        raise HTTPException(500, result.get('msg', '删除节点失败'))
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'删除节点 {node_name}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.post('/{node_id}/expire')
def expire_node(node_id: int, user: CurrentUser = Depends(get_current_user)):
    """过期节点"""
    require_node_access(node_id, user)
    node_name = _get_node_name(node_id, user.session_token)
    result = hs_request(
        'POST',
        f'/api/v1/node/{node_id}/expire',
        token=user.session_token,
    )
    if result.get('code') != 0:
        raise HTTPException(500, result.get('msg', '过期节点失败'))
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'过期节点 {node_name}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.post('/{node_id}/rename')
def rename_node(node_id: int, name: str, user: CurrentUser = Depends(get_current_user)):
    """节点重命名"""
    if not name:
        raise HTTPException(400, '节点名称不能为空')
    
    require_node_access(node_id, user)
    result = hs_request(
        'POST',
        f'/api/v1/node/{node_id}/rename/{quote(name, safe="")}',
        token=user.session_token,
    )
    if result.get('code') != 0:
        raise HTTPException(500, result.get('msg', '重命名失败'))
    conn = get_db_conn()
    try:
        record_log(
            conn,
            user.id,
            f'重命名节点 {_get_node_name(node_id, user.session_token)} 为 {name}',
        )
        conn.commit()
    finally:
        conn.close()
    return result

@router.get('/{node_id}/info')
def get_node_info(node_id: int, user: CurrentUser = Depends(get_current_user)):
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
            if user.network_user_id is None:
                raise HTTPException(403, '当前账户未绑定网络分组')
            base_query += " AND n.user_id = %s"
            params.append(user.network_user_id)
        
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
def get_node_routes(node_id: int, user: CurrentUser = Depends(get_current_user)):
    """获取节点路由"""
    require_node_access(node_id, user)
    result = hs_request(
        'GET',
        f'/api/v1/node/{node_id}/routes',
        token=user.session_token,
    )
    return result
