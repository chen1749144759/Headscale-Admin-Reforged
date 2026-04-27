"""
操作日志路由模块
处理日志的获取、查询等
"""
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends

from .dependencies import CurrentUser, get_current_user, get_db_conn

router = APIRouter(prefix="/api/logs", tags=["日志"])

@router.get('')
def list_logs(
    page: int = 1,
    size: int = 20,
    user: CurrentUser = Depends(get_current_user)
):
    """获取操作日志列表"""
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        offset = (page - 1) * size
        
        cur.execute("SELECT COUNT(*) FROM log")
        total = cur.fetchone()['count']
        
        cur.execute("""
            SELECT l.id, l.content, TO_CHAR(l.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at, u.name as user_name
            FROM log l LEFT JOIN users u ON l.user_id = u.id
            ORDER BY l.created_at DESC LIMIT %s OFFSET %s
        """, (size, offset))
        rows = cur.fetchall()
        
        return {'code': 0, 'data': rows, 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()
