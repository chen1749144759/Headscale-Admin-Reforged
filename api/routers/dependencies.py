"""
公共依赖模块
包含数据库连接、JWT工具、用户认证等公共功能
"""
import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
# from passlib.hash import bcrypt  # removed: using native bcrypt in auth.py

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

def save_config(updates: dict):
    """保存配置更新"""
    global CFG
    CFG.update(updates)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(CFG, f)

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
SERVER_HOST = os.environ.get('HEADSCALE_URL') or CFG.get('server_url', {}).get('headscale', 'http://127.0.0.1:8080')
BEARER_TOKEN = os.environ.get('HEADSCALE_API_KEY') or CFG.get('bearer_token', '')
SERVER_URL = CFG.get('server_url', {}).get('headscale', '')
SERVER_NET = CFG.get('server_net', '')
DEFAULT_REG_DAYS = int(os.environ.get('DEFAULT_REG_DAYS', 0) or CFG.get('default_reg_days', 7))
DEFAULT_NODE_COUNT = int(os.environ.get('DEFAULT_NODE_COUNT', 0) or CFG.get('default_node_count', 2))
SECRET_KEY = os.environ.get('SECRET_KEY') or CFG.get('secret_key', 'change-me')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_SECONDS = 86400  # 24h

# Docker 环境：尝试从共享卷读取 API Key
_API_KEY_FILE = os.environ.get('API_KEY_FILE', '/data/headscale/api.key')
if not BEARER_TOKEN and os.path.isfile(_API_KEY_FILE):
    try:
        with open(_API_KEY_FILE, 'r') as f:
            BEARER_TOKEN = f.read().strip()
    except Exception:
        pass

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
    """记录操作日志"""
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO log (user_id, content, created_at) VALUES (%s, %s, NOW())", (user_id, content))
    except Exception as e:
        print(f'记录日志失败: {e}')

# ─── JWT 工具 ─────────────────────────────────────────
def create_token(user_id: int, role: str) -> str:
    """创建JWT令牌"""
    expire = datetime.now(timezone.utc) + timedelta(seconds=JWT_EXPIRE_SECONDS)
    payload = {
        'sub': str(user_id),
        'role': role,
        'exp': expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    """解码JWT令牌"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, '登录已过期，请重新登录')

# ─── 当前用户依赖 ─────────────────────────────────────
class CurrentUser:
    """当前用户模型"""
    def __init__(self, id: int, name: str, role: str, email: str = '',
                 cellphone: str = '', node: int = 0, route: int = 0,
                 enable: int = 1, expire: str = '', created_at: str = ''):
        self.id = id
        self.name = name
        self.role = role
        self.email = email
        self.cellphone = cellphone
        self.node = node
        self.route = route
        self.enable = enable
        self.expire = expire
        self.created_at = created_at

    def is_manager(self):
        """是否为管理员"""
        return self.role == 'manager'

def get_current_user(request: Request) -> CurrentUser:
    """获取当前登录用户"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
    else:
        token = request.cookies.get('token', '')
        if not token:
            raise HTTPException(401, '未登录')
    
    payload = decode_token(token)
    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(401, '无效令牌')
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(401, '无效令牌')
    
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, name, role, email, cellphone, node, route, enable, "
            "TO_CHAR(expire, 'YYYY-MM-DD HH24:MI:SS') as expire, "
            "TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at "
            "FROM users WHERE id=%s", 
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(401, '用户不存在')
        return CurrentUser(**row)
    finally:
        conn.close()

def require_manager(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """要求管理员权限"""
    if not user.is_manager():
        raise HTTPException(403, '需要管理员权限')
    return user
