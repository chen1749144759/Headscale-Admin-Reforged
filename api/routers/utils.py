"""
工具模块
包含Headscale API调用、系统工具函数等
"""
import os
import subprocess
from typing import Optional

import requests as http_requests
import psutil

from . import dependencies as deps

# ─── Headscale API 调用 ─────────────────────────────────
def hs_request(method: str, path: str, data=None) -> dict:
    """调用 Headscale API"""
    headers = {'Authorization': f'Bearer {deps.BEARER_TOKEN}'}
    url = deps.SERVER_HOST + path
    fn = getattr(http_requests, method.lower())
    
    try:
        r = fn(url, headers=headers, json=data, timeout=10)
        if r.text == 'Unauthorized':
            # 自动刷新 API key
            new_key = refresh_apikey()
            headers['Authorization'] = f'Bearer {new_key}'
            r = fn(url, headers=headers, json=data, timeout=10)
        
        if r.status_code >= 400:
            try:
                err_data = r.json()
                msg = err_data.get('message', '') or err_data.get('error', '') or r.text
            except Exception:
                msg = r.text or f'HTTP {r.status_code}'
            return {'code': 1, 'msg': msg}
        
        try:
            return {'code': 0, 'data': r.json()}
        except Exception:
            return {'code': 0, 'data': r.text}
    except Exception as e:
        return {'code': 1, 'msg': str(e)}

def refresh_apikey() -> str:
    """刷新 API Key — 优先从共享文件读取，否则尝试本地 CLI"""
    # Docker 环境：从共享卷文件读取
    api_key_file = os.environ.get('API_KEY_FILE', '/data/headscale/api.key')
    if os.path.isfile(api_key_file):
        try:
            with open(api_key_file, 'r') as f:
                new_token = f.read().strip()
            if new_token and new_token != deps.BEARER_TOKEN:
                deps.BEARER_TOKEN = new_token
                return new_token
        except Exception as e:
            print(f'从文件读取 API key 失败: {e}')

    # 本地部署：通过 headscale CLI 创建
    try:
        result = subprocess.run('headscale apikey create', shell=True, capture_output=True, text=True, check=True)
        new_token = result.stdout.strip()
        deps.BEARER_TOKEN = new_token
        # 保存到配置
        deps.save_config({'bearer_token': new_token})
        return new_token
    except Exception as e:
        print(f'刷新 API key 失败: {e}')
        return deps.BEARER_TOKEN

def check_headscale_health() -> bool:
    """检查 headscale 健康状态"""
    try:
        r = http_requests.get(deps.SERVER_HOST + '/health', timeout=3)
        return r.status_code == 200 and r.json().get('status') == 'pass'
    except Exception:
        return False

def get_headscale_pid() -> Optional[int]:
    """获取 headscale 进程ID"""
    try:
        r = subprocess.run(['pgrep', '-f', 'headscale'], capture_output=True, text=True)
        pids = r.stdout.strip().split('\n')
        return int(pids[0]) if pids and pids[0] else None
    except Exception:
        return None

def get_headscale_version() -> str:
    """获取 headscale 版本"""
    try:
        r = subprocess.run(['headscale', 'version'], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return 'unknown'

def get_server_net() -> dict:
    """获取服务器网络接口"""
    try:
        r = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True, check=True)
        interfaces = []
        for line in r.stdout.split('\n'):
            if ': ' in line and 'lo:' not in line:
                name = line.split(': ')[1].split('@')[0].strip()
                if name and name != 'lo':
                    interfaces.append(name)
        return {'network_interfaces': interfaces}
    except Exception:
        return {'network_interfaces': []}
