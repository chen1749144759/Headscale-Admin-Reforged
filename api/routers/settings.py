"""
系统设置路由模块
处理系统配置、Headscale控制、系统状态等
"""
import subprocess
from typing import Optional

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ruamel.yaml import YAML

from .dependencies import (
    CurrentUser, get_current_user, require_manager, get_db_conn,
    record_log, CFG, CONFIG_PATH
)
from . import dependencies as deps
from .utils import (
    get_headscale_pid, check_headscale_health, get_headscale_version,
    get_server_net, refresh_apikey
)

yaml = YAML()

router = APIRouter(prefix="/api", tags=["系统"])

# 请求模型
class SettingsUpdateReq(BaseModel):
    server_url: Optional[str] = None
    server_net: Optional[str] = None
    bearer_token: Optional[str] = None
    default_reg_days: Optional[int] = None
    default_node_count: Optional[int] = None
    open_user_reg: Optional[str] = None
    headscale_action: Optional[str] = None

@router.get('/system/status')
def system_status(user: CurrentUser = Depends(get_current_user)):
    """获取系统状态"""
    hs_running = get_headscale_pid() is not None
    hs_healthy = check_headscale_health() if hs_running else False
    hs_version = get_headscale_version() if hs_running else ''
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'headscale_version': hs_version,
            'open_user_reg': deps.OPEN_USER_REG,
        }
    }

@router.get('/public/status')
def public_status():
    """公开接口，无需登录"""
    hs_running = get_headscale_pid() is not None
    hs_healthy = check_headscale_health() if hs_running else False
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'open_user_reg': deps.OPEN_USER_REG,
        }
    }

@router.get('/system/info')
def system_info(user: CurrentUser = Depends(get_current_user)):
    """获取系统信息（CPU、内存、内网IP）"""
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory()

    # 获取所有非 loopback 的 IPv4 内网地址
    internal_ips = []
    try:
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET (IPv4)
                    ip = addr.address
                    if ip and not ip.startswith('127.'):
                        internal_ips.append({'iface': name, 'ip': ip})
    except Exception:
        pass

    return {
        'code': 0,
        'data': {
            'cpu_usage': cpu,
            'memory_percent': mem.percent,
            'memory_total': mem.total,
            'memory_used': mem.used,
            'internal_ips': internal_ips,
        }
    }

@router.get('/system/traffic')
def system_traffic(user: CurrentUser = Depends(get_current_user)):
    """获取系统流量"""
    try:
        net = psutil.net_io_counters()
        return {'code': 0, 'data': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv}}
    except Exception:
        return {'code': 0, 'data': {'bytes_sent': 0, 'bytes_recv': 0}}

@router.get('/settings')
def get_settings(user: CurrentUser = Depends(get_current_user)):
    """获取系统设置"""
    interfaces = get_server_net().get('network_interfaces', [])
    
    return {
        'code': 0,
        'data': {
            'server_url': deps.SERVER_URL,
            'server_net': deps.SERVER_NET,
            'bearer_token': deps.BEARER_TOKEN[:8] + '...' if deps.BEARER_TOKEN else '',
            'default_reg_days': deps.DEFAULT_REG_DAYS,
            'default_node_count': deps.DEFAULT_NODE_COUNT,
            'open_user_reg': deps.OPEN_USER_REG,
            'headscale_running': get_headscale_pid() is not None,
            'headscale_version': get_headscale_version(),
            'network_interfaces': interfaces,
        }
    }

@router.put('/settings')
def update_settings(req: SettingsUpdateReq, user: CurrentUser = Depends(get_current_user)):
    """更新系统设置"""
    updates = {}
    if req.server_url is not None:
        deps.SERVER_URL = req.server_url
        updates['server_url'] = {'headscale': req.server_url}
    if req.server_net is not None:
        deps.SERVER_NET = req.server_net
        updates['server_net'] = req.server_net
    if req.bearer_token is not None:
        deps.BEARER_TOKEN = req.bearer_token
        updates['bearer_token'] = req.bearer_token
    if req.default_reg_days is not None:
        deps.DEFAULT_REG_DAYS = req.default_reg_days
        updates['default_reg_days'] = req.default_reg_days
    if req.default_node_count is not None:
        deps.DEFAULT_NODE_COUNT = req.default_node_count
        updates['default_node_count'] = req.default_node_count
    if req.open_user_reg is not None:
        deps.OPEN_USER_REG = req.open_user_reg
        updates['open_user_reg'] = req.open_user_reg

    if updates:
        for k, v in updates.items():
            CFG[k] = v
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(CFG, f)

    # headscale start/stop
    if req.headscale_action == 'start':
        subprocess.Popen(['headscale', 'serve'], start_new_session=True)
    elif req.headscale_action == 'stop':
        subprocess.run(['pkill', '-f', 'headscale'], capture_output=True)

    conn = get_db_conn()
    try:
        record_log(conn, user.id, '更新系统设置')
        conn.commit()
    finally:
        conn.close()

    return {'code': 0, 'msg': '设置已保存'}

@router.post('/settings/refresh-apikey')
def refresh_apikey_endpoint(user: CurrentUser = Depends(get_current_user)):
    """刷新 API Key"""
    key = refresh_apikey()
    conn = get_db_conn()
    try:
        record_log(conn, user.id, '刷新 API Key')
        conn.commit()
    finally:
        conn.close()
    return {'code': 0, 'data': key}

@router.get('/deploy')
def deploy_info(user: CurrentUser = Depends(get_current_user)):
    """获取部署信息"""
    return {'code': 0, 'data': {'server_url': deps.SERVER_URL}}
