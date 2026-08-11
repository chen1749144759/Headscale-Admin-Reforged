"""数据库、平台会话与权限公共依赖。"""
import ipaddress
import os
from urllib.parse import urlsplit

import psycopg2
import psycopg2.extras
from typing import Any

from fastapi import Depends, HTTPException, Request

from .headscale_client import HeadscaleUnavailable, request as headscale_request, response_error

# ─── 配置加载 ─────────────────────────────────────────────
from ruamel.yaml import YAML
yaml = YAML()

# 尝试多个可能的配置路径
_current_dir = os.path.dirname(os.path.abspath(__file__))  # /api/routers
_api_dir = os.path.dirname(_current_dir)  # /api
_project_dir = os.path.dirname(_api_dir)  # 项目根目录

def _find_config_path():
    """查找配置文件路径"""
    # 优先使用环境变量
    env_path = os.environ.get('HS_CONFIG')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 尝试多个可能的路径
    candidates = [
        os.path.join(_project_dir, 'config.yaml'),
        os.path.join(_api_dir, 'config.yaml'),
        os.path.join(_current_dir, 'config.yaml'),
        '/etc/headscale-admin/config.yaml',
    ]
    
    for path in candidates:
        if os.path.exists(path):
            return path
    
    # 如果都不存在，返回项目根目录的路径（即使不存在也返回）
    return os.path.join(_project_dir, 'config.yaml')

CONFIG_PATH = _find_config_path()

def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        print(f'警告: 配置文件 {CONFIG_PATH} 不存在，使用默认配置')
        return {}
    with open(CONFIG_PATH, 'r') as f:
        return yaml.load(f) or {}

CFG = load_config()

# 全局配置 — 环境变量优先，config.yaml 兜底
def _build_database_dsn():
    """构建数据库 DSN，支持分离参数或完整 URL"""
    # 优先使用完整 URL
    url = os.environ.get('DATABASE_URL')
    if url:
        return url
    # 尝试从分离的环境变量构建
    host = os.environ.get('DB_HOST')
    if host:
        port = os.environ.get('DB_PORT', '5432')
        name = os.environ.get('DB_NAME', 'headscale_admin')
        user = os.environ.get('DB_USER', 'headscale_admin')
        password = os.environ.get('DB_PASS', '')
        return f"host={host} port={port} dbname={name} user={user} password={password}"
    # 兜底到 config.yaml
    return CFG.get('database', {}).get('postgresql', {}).get('dsn', '')

DATABASE_DSN = _build_database_dsn()
SERVER_URL = (
    os.environ.get('HEADSCALE_PUBLIC_URL')
    or CFG.get('server_url', {}).get('headscale', '')
)
SESSION_COOKIE_NAME = 'scaleforge_session'
SESSION_COOKIE_SECURE = os.environ.get(
    'SESSION_COOKIE_SECURE',
    'true',
).strip().lower() not in ('0', 'false', 'no', 'off')
TRUSTED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get('TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
)
_CAPTCHA_CFG = CFG.get('captcha', {}) or {}
_CAPTCHA_ENABLED_RAW = os.environ.get(
    'CAPTCHA_ENABLED',
    str(_CAPTCHA_CFG.get('enabled', 'true'))
)
CAPTCHA_ENABLED = str(_CAPTCHA_ENABLED_RAW).lower() not in ('0', 'false', 'no', 'off')


def trusted_service_url(value: str) -> str:
    value = str(value or '').strip()
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        hostname = parsed.hostname or ''
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            return ''
        if parsed.scheme == 'https' and hostname:
            return value
        if parsed.scheme != 'http' or not hostname:
            return ''
        if hostname.lower() == 'localhost' or ipaddress.ip_address(hostname).is_loopback:
            return value
    except ValueError:
        return ''
    return ''


CAPTCHA_API_ENDPOINT = trusted_service_url(
    os.environ.get('CAPTCHA_API_ENDPOINT')
    or _CAPTCHA_CFG.get('api_endpoint')
    or ''
)
CAPTCHA_SITEVERIFY_URL = trusted_service_url(
    os.environ.get('CAPTCHA_SITEVERIFY_URL')
    or _CAPTCHA_CFG.get('siteverify_url')
    or ''
)
CAPTCHA_SECRET_KEY = (
    os.environ.get('CAPTCHA_SECRET_KEY')
    or _CAPTCHA_CFG.get('secret_key')
    or ''
)

# ─── 数据库 ───────────────────────────────────────────
def get_db():
    """获取数据库连接（生成器）"""
    conn = psycopg2.connect(DATABASE_DSN)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db_conn():
    """获取数据库连接（直接返回）"""
    conn = psycopg2.connect(DATABASE_DSN)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn

# ─── 日志记录 ─────────────────────────────────────────
def record_log(conn, user_id: int, content: str):
    """记录用户操作日志。"""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO log (account_id, content, created_at) VALUES (%s, %s, NOW())",
        (user_id, content),
    )

# ─── 当前用户依赖 ─────────────────────────────────────
class CurrentUser:
    """Headscale account session projected into ScaleForge."""

    def __init__(self, account: dict[str, Any], token: str, must_change_password: bool):
        self.id = int(account['id'])
        self.name = str(account.get('username') or '')
        self.username = self.name
        self.role = str(account.get('role') or 'user')
        self.enabled = bool(account.get('enabled', True))
        self.enable = 1 if self.enabled else 0
        self.expires_at = account.get('expiresAt')
        self.expire = self.expires_at or ''
        self.password_changed_at = account.get('passwordChangedAt')
        self.must_change_password = bool(
            must_change_password or account.get('mustChangePassword', False)
        )
        self.network_user_id = _optional_int(account.get('userId'))
        self.network_name = str(account.get('networkName') or '')
        self.group_id = _optional_int(account.get('groupId'))
        self.group_name = str(account.get('groupName') or '')
        self.session_token = token
        self.raw_account = account

    def is_manager(self):
        """是否为管理员"""
        return self.role == 'manager'

def get_current_user(request: Request) -> CurrentUser:
    """只从安全 Cookie 读取 opaque token，并通过 UDS 验证会话。"""
    token = request.cookies.get(SESSION_COOKIE_NAME, '')
    if not token:
        raise HTTPException(401, '未登录')

    try:
        response = headscale_request('GET', '/v1/session', token=token)
    except HeadscaleUnavailable as exc:
        raise HTTPException(503, '认证服务暂不可用') from exc
    if response.status_code != 200:
        _, message = response_error(response)
        raise HTTPException(401, message or '登录已过期，请重新登录')

    payload = response.json()
    account = payload.get('account') if isinstance(payload, dict) else None
    if not isinstance(account, dict) or not account.get('id'):
        raise HTTPException(502, '认证服务返回了无效账户信息')

    current = CurrentUser(account, token, bool(payload.get('mustChangePassword')))
    allowed_when_restricted = {
        '/api/auth/me',
        '/api/auth/password',
        '/api/auth/logout',
    }
    if current.must_change_password and request.url.path not in allowed_when_restricted:
        raise HTTPException(
            403,
            detail={
                'code': 'password_change_required',
                'message': '密码已过期，请先修改密码',
            },
        )
    return current

def require_manager(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """要求管理员权限"""
    if not user.is_manager():
        raise HTTPException(403, '需要管理员权限')
    return user


def _optional_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def require_node_access(node_id: int | str, user: CurrentUser) -> None:
    """Manager can access all nodes; users are confined to their network UserID."""
    if user.is_manager():
        return
    if user.network_user_id is None:
        raise HTTPException(403, '当前用户没有可用的内部网络身份')

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT user_id FROM nodes WHERE id=%s', (node_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, '节点不存在')
    if _optional_int(row.get('user_id')) != user.network_user_id:
        raise HTTPException(403, '无权操作该节点')
