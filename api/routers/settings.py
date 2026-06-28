"""
系统设置路由模块
处理系统配置、Headscale控制、系统状态等
"""
import os
import subprocess
from typing import List, Optional

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
    is_headscale_running, check_headscale_health, get_headscale_version,
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
    dns_magic_dns: Optional[bool] = None
    dns_base_domain: Optional[str] = None
    dns_override_local: Optional[bool] = None
    dns_global_nameservers: Optional[List[str]] = None
    dns_search_domains: Optional[List[str]] = None
    headscale_action: Optional[str] = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ('0', 'false', 'no', 'off')


def _split_csv(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(';', ',').split(',') if item.strip()]


def _clean_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    result = []
    for value in values:
        text = str(value or '').strip()
        if text and text not in result:
            result.append(text)
    return result


def _headscale_config_path() -> str:
    return os.environ.get('HEADSCALE_CONFIG_PATH') or CFG.get('headscale_config_path', '')


def _load_headscale_config() -> dict:
    path = _headscale_config_path()
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.load(f) or {}


def _default_dns_settings() -> dict:
    cfg_dns = (CFG.get('headscale_dns') or {}) if isinstance(CFG, dict) else {}
    env_global = _split_csv(os.environ.get('HEADSCALE_DNS_GLOBAL', ''))
    env_search = _split_csv(os.environ.get('HEADSCALE_DNS_SEARCH_DOMAINS', ''))
    return {
        'dns_magic_dns': bool(cfg_dns['magic_dns']) if 'magic_dns' in cfg_dns else _env_bool('HEADSCALE_MAGIC_DNS', True),
        'dns_base_domain': cfg_dns.get('base_domain') or os.environ.get('HEADSCALE_DNS_DOMAIN') or 'hs.admin.pro',
        'dns_override_local': (
            bool(cfg_dns['override_local_dns'])
            if 'override_local_dns' in cfg_dns
            else _env_bool('HEADSCALE_DNS_OVERRIDE_LOCAL', True)
        ),
        'dns_global_nameservers': cfg_dns.get('global_nameservers') or env_global or ['1.1.1.1', '8.8.8.8'],
        'dns_search_domains': cfg_dns.get('search_domains') or env_search or [],
    }


def _read_dns_settings() -> dict:
    settings = _default_dns_settings()
    hs_cfg = _load_headscale_config()
    dns_cfg = hs_cfg.get('dns') or {}
    if dns_cfg:
        nameservers = dns_cfg.get('nameservers') or {}
        settings.update({
            'dns_magic_dns': bool(dns_cfg.get('magic_dns', settings['dns_magic_dns'])),
            'dns_base_domain': dns_cfg.get('base_domain') or settings['dns_base_domain'],
            'dns_override_local': bool(dns_cfg.get('override_local_dns', settings['dns_override_local'])),
            'dns_global_nameservers': nameservers.get('global') or settings['dns_global_nameservers'],
            'dns_search_domains': dns_cfg.get('search_domains') or settings['dns_search_domains'],
        })
    path = _headscale_config_path()
    settings['headscale_config_path'] = path
    settings['headscale_config_writable'] = bool(path and os.path.exists(path) and os.access(path, os.W_OK))
    return settings


def _dns_payload_from_request(req: SettingsUpdateReq) -> Optional[dict]:
    fields = (
        req.dns_magic_dns,
        req.dns_base_domain,
        req.dns_override_local,
        req.dns_global_nameservers,
        req.dns_search_domains,
    )
    if all(value is None for value in fields):
        return None
    current = _read_dns_settings()
    payload = {
        'magic_dns': current['dns_magic_dns'] if req.dns_magic_dns is None else bool(req.dns_magic_dns),
        'base_domain': (req.dns_base_domain if req.dns_base_domain is not None else current['dns_base_domain']).strip(),
        'override_local_dns': current['dns_override_local'] if req.dns_override_local is None else bool(req.dns_override_local),
        'global_nameservers': _clean_list(
            current['dns_global_nameservers'] if req.dns_global_nameservers is None else req.dns_global_nameservers
        ),
        'search_domains': _clean_list(
            current['dns_search_domains'] if req.dns_search_domains is None else req.dns_search_domains
        ),
    }
    if not payload['base_domain']:
        payload['base_domain'] = 'hs.admin.pro'
    if not payload['global_nameservers']:
        payload['global_nameservers'] = ['1.1.1.1', '8.8.8.8']
    return payload


def _write_headscale_dns_config(dns_payload: dict) -> bool:
    path = _headscale_config_path()
    if not path:
        return False
    config = _load_headscale_config()
    if not config:
        return False
    dns_cfg = config.setdefault('dns', {})
    dns_cfg['magic_dns'] = dns_payload['magic_dns']
    dns_cfg['base_domain'] = dns_payload['base_domain']
    dns_cfg['override_local_dns'] = dns_payload['override_local_dns']
    nameservers = dns_cfg.setdefault('nameservers', {})
    nameservers['global'] = dns_payload['global_nameservers']
    if dns_payload['search_domains']:
        dns_cfg['search_domains'] = dns_payload['search_domains']
    else:
        dns_cfg.pop('search_domains', None)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
    return True

@router.get('/system/status')
def system_status(user: CurrentUser = Depends(get_current_user)):
    """获取系统状态"""
    hs_running = is_headscale_running()
    hs_healthy = check_headscale_health()
    hs_version = get_headscale_version() if hs_running else ''
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'headscale_version': hs_version,
        }
    }

@router.get('/public/status')
def public_status():
    """公开接口，无需登录 — 返回系统初始化状态"""
    hs_running = is_headscale_running()
    hs_healthy = check_headscale_health()
    
    # 查询数据库判断是否已有管理员
    initialized = False
    try:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            initialized = cur.fetchone()[0] > 0
        finally:
            conn.close()
    except Exception:
        pass
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'initialized': initialized,
            'captcha': {
                'enabled': deps.CAPTCHA_ENABLED,
                'widget_src': deps.CAPTCHA_WIDGET_SRC,
                'api_endpoint': deps.CAPTCHA_API_ENDPOINT,
            },
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
    dns_settings = _read_dns_settings()
    
    return {
        'code': 0,
        'data': {
            'server_url': deps.SERVER_URL,
            'server_net': deps.SERVER_NET,
            'bearer_token': deps.BEARER_TOKEN[:8] + '...' if deps.BEARER_TOKEN else '',
            'default_reg_days': deps.DEFAULT_REG_DAYS,
            'default_node_count': deps.DEFAULT_NODE_COUNT,
            'headscale_running': is_headscale_running(),
            'headscale_version': get_headscale_version(),
            'network_interfaces': interfaces,
            **dns_settings,
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
    dns_payload = _dns_payload_from_request(req)
    if dns_payload is not None:
        updates['headscale_dns'] = dns_payload
        CFG['headscale_dns'] = dns_payload
        _write_headscale_dns_config(dns_payload)

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
