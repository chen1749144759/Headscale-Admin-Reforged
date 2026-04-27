from flask_login import current_user, login_required
from exts import DB
from login_setup import role_required
from flask import Blueprint, request
from utils import res, table_res

bp = Blueprint("user", __name__, url_prefix='/api/user')


@bp.route('/getUsers')
@login_required
@role_required("manager")
def getUsers():
    # 获取分页参数，默认第1页，每页10条
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('limit', default=10, type=int)
    offset = (page - 1) * per_page

    with DB() as cursor:
        # 查询总记录数和当前页用户数据
        # PostgreSQL 用 COUNT(*) OVER() 窗口函数获取总数
        query = """
            SELECT 
                COUNT(*) OVER() as total_count, id, name, 
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                cellphone, 
                TO_CHAR(expire, 'YYYY-MM-DD HH24:MI:SS') as expire, role, node, route, enable, email
            FROM users
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (per_page, offset))
        rows = cursor.fetchall()

        total_count = rows[0]['total_count'] if rows else 0

        # 创建用户字典列表
        users_list = [
            {
                'id': row['id'],
                'userName': row['name'],
                'createTime': str(row['created_at']),
                'cellphone': row['cellphone'],
                'expire': str(row['expire']),
                'role': row['role'],
                'node': row['node'],
                'route': row['route'],
                'enable': row['enable'],
                'email': row['email']
            }
            for row in rows
        ]

    return table_res('0', '获取成功', users_list, total_count, len(users_list))


@bp.route('/re_expire',methods=['GET','POST'])
@login_required
@role_required("manager")
def re_expire():

    user_id = request.form.get('user_id')
    new_expire = request.form.get('new_expire')

    with DB() as cursor:
        # 更新用户的过期时间
        update_query = "UPDATE users SET expire = %s WHERE id = %s;"
        cursor.execute(update_query, (new_expire, user_id))

    return res('0', '更新成功','')


@bp.route('/re_node',methods=['GET','POST'])
@login_required
@role_required("manager")
def re_node():
    user_id = request.form.get('user_id')
    new_node = request.form.get('new_node')

    with DB() as cursor:
        # 更新用户的节点信息
        update_query = "UPDATE users SET node = %s WHERE id = %s;"
        cursor.execute(update_query, (new_node, user_id))

    return res('0', '更新成功')


@bp.route('/user_enable',methods=['GET','POST'])
@login_required
@role_required("manager")
def user_enable():
    user_id = request.form.get('user_id')
    enable = request.form.get('enable')

    with DB() as cursor:
        # 查询用户
        query = "SELECT * FROM users WHERE id = %s;"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()

        if enable == "true":
            update_query = "UPDATE users SET enable = 1 WHERE id = %s;"
            msg = '启用成功'
        else:
            if user['name'] == 'admin':
                return res('1', '停用失败，无法停用admin用户')
            update_query = "UPDATE users SET enable = 0 WHERE id = %s;"
            msg = '停用成功'

        cursor.execute(update_query, (user_id,))

    return res('0', msg)


@bp.route('/route_enable',methods=['GET','POST'])
@login_required
@role_required("manager")
def route_enable():
    user_id = request.form.get('user_id')
    enable = request.form.get('enable')

    with DB() as cursor:
        if enable == "true":
            update_query = "UPDATE users SET route = 1 WHERE id = %s;"
            msg = '启用成功'
        else:
            update_query = "UPDATE users SET route = 0 WHERE id = %s;"
            msg = '停用成功'
        cursor.execute(update_query, (user_id,))

    return res('0', msg)


@bp.route('/delUser',methods=['GET','POST'])
@login_required
@role_required("manager")
def delUser():
    user_id = request.form.get('user_id')

    with DB() as cursor:
        # 删除用户
        delete_query = "DELETE FROM users WHERE id = %s;"
        cursor.execute(delete_query, (user_id,))

    return res('0', '删除成功')


@bp.route('/init_data',methods=['GET'])
@login_required
def init_data():
    with DB() as cursor:
        # 查询当前用户的创建时间和过期时间
        current_user_id = current_user.id  # 假设 current_user 有 id 属性
        user_query = """
            SELECT 
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
            TO_CHAR(expire, 'YYYY-MM-DD HH24:MI:SS') as expire
            FROM users WHERE id = %s
        """
        cursor.execute(user_query, (current_user_id,))
        user_info = cursor.fetchone()


        created_at = str(user_info['created_at'])
        expire = str(user_info['expire'])

        # 查询节点数量（nodes 表由 headscale 管理，在 PostgreSQL 中需要确认是否存在）
        cursor.execute("SELECT COUNT(*) as count FROM nodes")
        node_count = cursor.fetchone()['count']
        # 查询路由数量
        cursor.execute("SELECT COUNT(*) as count FROM nodes where approved_routes IS NOT NULL")
        route_count = cursor.fetchone()['count']


    data = {
        "created_at": created_at,
        "expire": expire,
        "node_count": node_count,
        "route_count": route_count
    }

    return res('0', '查询成功', data)
