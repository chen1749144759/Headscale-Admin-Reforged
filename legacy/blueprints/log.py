from flask_login import login_required, current_user
from flask import Blueprint,  request
from exts import DB

bp = Blueprint("log", __name__, url_prefix='/api/log')


@bp.route('/getLogs')
@login_required
def getLogs():
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('limit', default=10, type=int)
    offset = (page - 1) * per_page

    with DB() as cursor:
        # 构建基础查询语句
        base_query = """
            SELECT
                log.id,
                log.content,
                users.name,
                TO_CHAR(log.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at
            FROM
                log
            JOIN
                users ON log.user_id = users.id
        """

        # 判断用户角色
        if current_user.role != 'manager':
            base_query += " WHERE log.user_id = %s "
            params = (current_user.id,)
        else:
            params = ()

        # 查询总记录数
        count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as sub"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['total']

        # 分页查询
        paginated_query = f"{base_query} LIMIT %s OFFSET %s"
        paginated_params = params + (per_page, offset)
        cursor.execute(paginated_query, paginated_params)
        logs = cursor.fetchall()

    # 数据格式化
    logs_list = []
    for log in logs:
        logs_list.append({
            'id': log['id'],
            'content': log['content'],
            'name': log['name'],
            'create_time': log['created_at']
        })

    # 接口返回json数据
    res_json = {
        'code': '0',
        'data': logs_list,
        'msg': '获取成功',
        'count': total_count,
        'totalRow': {
            'count': len(logs_list)
        }
    }

    return res_json
