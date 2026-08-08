"""
系统设置路由模块
处理系统配置、Headscale控制、系统状态等
"""
from typing import Optional

import psutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import (
    CurrentUser, get_current_user, require_manager, get_db_conn,
    record_log,
)
from . import dependencies as deps
from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error
from .utils import (
    is_headscale_running, check_headscale_health, get_headscale_version,
)

router = APIRouter(prefix="/api", tags=["系统"])

# 请求模型
class SettingsUpdateReq(BaseModel):
    dns_magic_dns: Optional[bool] = None
    dns_override_local: Optional[bool] = None
    dns_global_nameservers: Optional[list[str]] = None
    dns_search_domains: Optional[list[str]] = None


def _clean_list(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    result = []
    for value in values:
        text = str(value or '').strip()
        if text and text not in result:
            result.append(text)
    return result


def _read_dns_settings(user: CurrentUser) -> dict:
    try:
        response = headscale_request('GET', '/v1/dns', token=user.session_token)
    except HeadscaleUnavailable as exc:
        raise HTTPException(503, 'Headscale DNS 管理接口暂不可用') from exc
    if response.status_code != 200:
        _, message = response_error(response)
        raise HTTPException(response.status_code, message or '读取 Headscale DNS 配置失败')
    data = response.json()
    if not isinstance(data, dict):
        raise HTTPException(502, 'Headscale DNS 管理接口返回无效数据')
    return {
        'dns_magic_dns': bool(data.get('magicDNS')),
        'dns_base_domain': str(data.get('baseDomain') or ''),
        'dns_override_local': bool(data.get('overrideLocalDNS')),
        'dns_global_nameservers': list(data.get('globalNameservers') or []),
        'dns_search_domains': list(data.get('searchDomains') or []),
        'dns_hot_reload': True,
    }


def _dns_payload_from_request(req: SettingsUpdateReq, current: dict) -> Optional[dict]:
    fields = (
        req.dns_magic_dns,
        req.dns_override_local,
        req.dns_global_nameservers,
        req.dns_search_domains,
    )
    if all(value is None for value in fields):
        return None
    payload = {
        'magicDNS': current['dns_magic_dns'] if req.dns_magic_dns is None else bool(req.dns_magic_dns),
        'overrideLocalDNS': current['dns_override_local'] if req.dns_override_local is None else bool(req.dns_override_local),
        'globalNameservers': _clean_list(
            current['dns_global_nameservers'] if req.dns_global_nameservers is None else req.dns_global_nameservers
        ),
        'searchDomains': _clean_list(
            current['dns_search_domains'] if req.dns_search_domains is None else req.dns_search_domains
        ),
    }
    return payload

@router.get('/system/status')
def system_status(user: CurrentUser = Depends(get_current_user)):
    """获取系统状态"""
    hs_running = is_headscale_running()
    hs_healthy = check_headscale_health()
    hs_version = get_headscale_version(user.session_token) if hs_running else ''
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'headscale_version': hs_version,
            'server_url': deps.SERVER_URL,
        }
    }

@router.get('/public/status')
def public_status():
    """公开接口只返回登录页所需的服务与 CAPTCHA 配置。"""
    hs_running = is_headscale_running()
    hs_healthy = check_headscale_health()
    
    return {
        'code': 0,
        'data': {
            'headscale_running': hs_running,
            'headscale_healthy': hs_healthy,
            'captcha': {
                'enabled': deps.CAPTCHA_ENABLED,
                'api_endpoint': deps.CAPTCHA_API_ENDPOINT,
            },
        }
    }

@router.get('/system/info')
def system_info(user: CurrentUser = Depends(require_manager)):
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
def system_traffic(user: CurrentUser = Depends(require_manager)):
    """获取系统流量"""
    try:
        net = psutil.net_io_counters()
        return {'code': 0, 'data': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv}}
    except Exception:
        return {'code': 0, 'data': {'bytes_sent': 0, 'bytes_recv': 0}}

@router.get('/settings')
def get_settings(user: CurrentUser = Depends(require_manager)):
    """获取系统设置"""
    dns_settings = _read_dns_settings(user)
    
    return {
        'code': 0,
        'data': {
            'server_url': deps.SERVER_URL,
            'headscale_running': is_headscale_running(),
            'headscale_version': get_headscale_version(user.session_token),
            **dns_settings,
        }
    }

@router.put('/settings')
def update_settings(req: SettingsUpdateReq, user: CurrentUser = Depends(require_manager)):
    """热更新 Headscale DNS 设置。部署地址只能通过环境变量修改。"""
    current_dns = _read_dns_settings(user)
    dns_payload = _dns_payload_from_request(req, current_dns)
    dns_settings = current_dns
    if dns_payload is not None:
        try:
            response = headscale_request('PUT', '/v1/dns', token=user.session_token, json=dns_payload)
        except HeadscaleUnavailable as exc:
            raise HTTPException(503, 'Headscale DNS 管理接口暂不可用') from exc
        if response.status_code != 200:
            _, message = response_error(response)
            raise HTTPException(response.status_code, message or '更新 Headscale DNS 配置失败')
        data = response.json()
        dns_settings = {
            'dns_magic_dns': bool(data.get('magicDNS')),
            'dns_base_domain': str(data.get('baseDomain') or ''),
            'dns_override_local': bool(data.get('overrideLocalDNS')),
            'dns_global_nameservers': list(data.get('globalNameservers') or []),
            'dns_search_domains': list(data.get('searchDomains') or []),
            'dns_hot_reload': True,
        }

    conn = get_db_conn()
    try:
        record_log(conn, user.id, '更新系统设置')
        conn.commit()
    finally:
        conn.close()

    return {'code': 0, 'msg': '设置已保存并热下发', 'data': dns_settings}

@router.get('/deploy')
def deploy_info(user: CurrentUser = Depends(require_manager)):
    """获取部署信息"""
    return {'code': 0, 'data': {'server_url': deps.SERVER_URL}}
