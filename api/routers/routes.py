"""
路由管理模块
从节点数据提取路由信息（available_routes / approved_routes），
提供审批操作和 autoApprovers 管理
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .dependencies import CurrentUser, get_current_user, require_manager, get_db_conn, record_log
from .utils import hs_request

router = APIRouter(prefix="/api/routes", tags=["路由"])


@router.get('')
def list_routes(user: CurrentUser = Depends(get_current_user)):
    """获取所有节点的路由信息（从节点列表中提取）"""
    result = hs_request('GET', '/api/v1/node')
    nodes = []
    if isinstance(result, dict):
        nodes = result.get('nodes', [])
    elif isinstance(result, list):
        nodes = result

    route_list = []
    for node in nodes:
        node_id = node.get('id')
        node_name = node.get('givenName') or node.get('name') or str(node_id)
        user_info = node.get('user', {})
        group_name = user_info.get('name', '-') if user_info else '-'

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
def approve_routes(node_id: int, req: ApproveRoutesReq, user: CurrentUser = Depends(get_current_user)):
    """批准指定节点的路由"""
    result = hs_request('POST', f'/api/v1/node/{node_id}/approve_routes', {'routes': req.routes})
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'批准节点 {node_id} 路由: {",".join(req.routes)}')
        conn.commit()
    finally:
        conn.close()
    return result


@router.post('/node/{node_id}/revoke')
def revoke_routes(node_id: int, req: ApproveRoutesReq, user: CurrentUser = Depends(get_current_user)):
    """撤销指定节点的某些路由（保留其余已批准路由）"""
    # 先获取当前节点已批准路由
    node_result = hs_request('GET', f'/api/v1/node/{node_id}')
    node_data = node_result.get('node', node_result) if isinstance(node_result, dict) else {}
    current_approved = set(node_data.get('approvedRoutes') or node_data.get('approved_routes') or [])

    # 移除要撤销的路由
    revoke_set = set(req.routes)
    new_approved = list(current_approved - revoke_set)

    result = hs_request('POST', f'/api/v1/node/{node_id}/approve_routes', {'routes': new_approved})
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'撤销节点 {node_id} 路由: {",".join(req.routes)}')
        conn.commit()
    finally:
        conn.close()
    return result
