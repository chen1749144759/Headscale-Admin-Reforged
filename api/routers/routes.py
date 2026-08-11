"""
路由管理模块
从节点数据提取路由信息（available_routes / approved_routes），
提供审批操作和 autoApprovers 管理
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .dependencies import CurrentUser, get_current_user, get_db_conn, record_log, require_manager
from .utils import hs_request

router = APIRouter(prefix="/api/routes", tags=["路由"])


@router.get('')
def list_routes(user: CurrentUser = Depends(get_current_user)):
    """获取所有节点的路由信息（从节点列表中提取）"""
    if not user.is_manager() and user.network_user_id is None:
        return {'code': 0, 'data': []}
    result = hs_request('GET', '/api/v1/node', token=user.session_token)
    nodes = []
    if isinstance(result, dict):
        # hs_request 返回 {'code': 0, 'data': {'nodes': [...]}}
        data = result.get('data', result)
        if isinstance(data, dict):
            nodes = data.get('nodes', [])
        elif isinstance(data, list):
            nodes = data

    user_ids = {
        int((node.get('user') or {}).get('id'))
        for node in nodes
        if str((node.get('user') or {}).get('id') or '').isdigit()
    }
    account_by_user_id = {}
    if user_ids:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.user_id, a.username, COALESCE(g.name, '') AS group_name
                FROM accounts a
                LEFT JOIN account_groups g ON g.id = a.group_id AND g.deleted_at IS NULL
                WHERE a.deleted_at IS NULL AND a.user_id = ANY(%s)
                """,
                (list(user_ids),),
            )
            account_by_user_id = {
                int(row['user_id']): row
                for row in cur.fetchall()
                if row.get('user_id') is not None
            }
        finally:
            conn.close()

    route_list = []
    for node in nodes:
        node_user_id = (node.get('user') or {}).get('id')
        if not user.is_manager() and str(node_user_id or '') != str(user.network_user_id or ''):
            continue
        node_id = node.get('id')
        account_info = account_by_user_id.get(int(node_user_id or 0), {})
        node_name = account_info.get('username') or node.get('givenName') or node.get('name') or str(node_id)
        user_info = node.get('user', {})
        group_name = account_info.get('group_name') or '-'

        available = node.get('availableRoutes') or node.get('available_routes') or []
        approved = node.get('approvedRoutes') or node.get('approved_routes') or []
        subnet = node.get('subnetRoutes') or node.get('subnet_routes') or []

        # 去重合并所有路由
        all_routes = set(available) | set(approved)
        for r in all_routes:
            route_list.append({
                'nodeId': node_id,
                'nodeName': node_name,
                'group': group_name,
                'prefix': r,
                'available': r in available,
                'approved': r in approved,
                'active': r in subnet,
            })

    return {'code': 0, 'data': route_list}


class ApproveRoutesReq(BaseModel):
    routes: List[str]


@router.post('/node/{node_id}/approve')
def approve_routes(node_id: int, req: ApproveRoutesReq, user: CurrentUser = Depends(require_manager)):
    """批准指定节点的路由"""
    result = hs_request(
        'POST',
        f'/api/v1/node/{node_id}/approve_routes',
        {'routes': req.routes},
        token=user.session_token,
    )
    # 查询节点名称用于日志
    node_name = str(node_id)
    try:
        nr = hs_request(
            'GET',
            f'/api/v1/node/{node_id}',
            token=user.session_token,
        )
        nd = nr.get('data', nr) if isinstance(nr, dict) else {}
        nd = nd.get('node', nd) if isinstance(nd, dict) else {}
        node_name = nd.get('givenName') or nd.get('name') or str(node_id)
    except Exception:
        pass
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'批准 {node_name} 宣告路由: {", ".join(req.routes)}')
        conn.commit()
    finally:
        conn.close()
    return result


@router.post('/node/{node_id}/revoke')
def revoke_routes(node_id: int, req: ApproveRoutesReq, user: CurrentUser = Depends(require_manager)):
    """撤销指定节点的某些路由（保留其余已批准路由）"""
    # 先获取当前节点已批准路由
    node_result = hs_request(
        'GET',
        f'/api/v1/node/{node_id}',
        token=user.session_token,
    )
    node_data = node_result.get('data', {}) if isinstance(node_result, dict) else {}
    node_data = node_data.get('node', node_data) if isinstance(node_data, dict) else {}
    current_approved = set(node_data.get('approvedRoutes') or node_data.get('approved_routes') or [])

    # 移除要撤销的路由
    revoke_set = set(req.routes)
    new_approved = list(current_approved - revoke_set)

    # 获取节点名称用于日志
    node_name = node_data.get('givenName') or node_data.get('name') or str(node_id)

    result = hs_request(
        'POST',
        f'/api/v1/node/{node_id}/approve_routes',
        {'routes': new_approved},
        token=user.session_token,
    )
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'撤销 {node_name} 宣告路由: {", ".join(req.routes)}')
        conn.commit()
    finally:
        conn.close()
    return result
