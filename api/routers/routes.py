"""
路由管理模块
处理路由的获取、启用、禁用等
"""
from fastapi import APIRouter, Depends

from .dependencies import CurrentUser, get_current_user, record_log, get_db_conn
from .utils import hs_request

router = APIRouter(prefix="/api/routes", tags=["路由"])

@router.get('')
def list_routes(user: CurrentUser = Depends(get_current_user)):
    """获取路由列表"""
    result = hs_request('GET', '/api/v1/routes')
    return result

@router.post('/{route_id}/enable')
def enable_route(route_id: str, user: CurrentUser = Depends(get_current_user)):
    """启用路由"""
    result = hs_request('POST', f'/api/v1/routes/{route_id}/enable')
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'启用路由 {route_id}')
        conn.commit()
    finally:
        conn.close()
    return result

@router.post('/{route_id}/disable')
def disable_route(route_id: str, user: CurrentUser = Depends(get_current_user)):
    """禁用路由"""
    result = hs_request('POST', f'/api/v1/routes/{route_id}/disable')
    conn = get_db_conn()
    try:
        record_log(conn, user.id, f'禁用路由 {route_id}')
        conn.commit()
    finally:
        conn.close()
    return result
