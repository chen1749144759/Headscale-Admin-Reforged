from flask_login import login_required, current_user
from login_setup import role_required
from flask import Blueprint, render_template, current_app, request, json
from utils import get_server_net, get_headscale_pid, get_headscale_version



bp = Blueprint("admin", __name__, url_prefix='/admin')




@bp.route('/')
@login_required
def admin():
    role = current_user.role
    if role == "manager":
        default_page = "console"
    else:
        default_page = "node"

    return render_template('index.html', default_page=default_page, current_user=current_user)



@bp.route('/console')
@login_required
@role_required("manager")
def console():
    return render_template('admin/console.html')



@bp.route('/user')
@login_required
@role_required("manager")
def user():
    return render_template('admin/user.html')





@bp.route('/node')
@login_required
def node():
    print(request.url)
    return render_template('admin/node.html',current_user=current_user )


@bp.route('/route')
@login_required
def route():
    return render_template('admin/route.html')


@bp.route('/deploy')
@login_required
def deploy():
    server_url = current_app.config['SERVER_URL']
    return render_template('admin/deploy.html',server_url = server_url)


@bp.route('/help')
@login_required
def help():
    return render_template('admin/help.html')



@bp.route('/acl')
@login_required
@role_required("manager")
def acl():
    return render_template('admin/acl.html')


@bp.route('/preauthkey')
@login_required
def preauthkey():
    return render_template('admin/preauthkey.html')


@bp.route('/log')
@login_required
def log():
    return render_template('admin/log.html')


@bp.route('/info')
@login_required
def info():
    name = current_user.name
    cellphone = current_user.cellphone
    email = current_user.email
    node = current_user.node
    route = current_user.route
    expire = current_user.expire

    if (route == "1"):
        route = "checked"
    else:
        route = ""

    return render_template('admin/info.html', name = name,
                            cellphone = cellphone,
                            email = email,
                            node = node,
                            route = route,
                            expire = expire
                           )




@bp.route('/set')
@login_required
def set():
    apikey = current_app.config['BEARER_TOKEN']
    server_url = current_app.config['SERVER_URL']
    server_net = current_app.config['SERVER_NET']
    default_reg_days = current_app.config['DEFAULT_REG_DAYS']
    default_node_count = current_app.config['DEFAULT_NODE_COUNT']
    open_user_reg = current_app.config['OPEN_USER_REG']

    options_html = ""
    for interface in get_server_net()["network_interfaces"]:
        if interface == server_net:
            options_html += f'<option value="{interface}" selected>{interface}</option>\n'
        else:
            options_html += f'<option value="{interface}">{interface}</option>\n'





    if get_headscale_pid():
        headscale_status = "checked"
    else:
        headscale_status = ""


    if open_user_reg == 'on':
        open_user_reg = "checked"
    else:
        open_user_reg = ""


    return render_template('admin/set.html',apikey = apikey,
                               server_url = server_url,
                               server_net = options_html,
                               headscale_status = headscale_status,
                               default_reg_days = default_reg_days,
                               default_node_count = default_node_count,
                               open_user_reg = open_user_reg,
                               version = get_headscale_version(),

                           )



@bp.route('/password')
@login_required
def password():
    return render_template('admin/password.html')


