"""
认证路由模块
处理登录、注册、登出、密码修改等
"""
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import requests
from fastapi import APIRouter, Depends, HTTPException, Response
import bcrypt as _bcrypt
from pydantic import BaseModel

from .dependencies import (
    CurrentUser, get_current_user, get_db_conn, create_token,
    record_log
)
from . import dependencies as deps
from .utils import get_headscale_pid, check_headscale_health

router = APIRouter(prefix="/api/auth", tags=["认证"])

class LoginReq(BaseModel):
    username: str
    password: str
    captchaToken: str = ''

class RegisterReq(BaseModel):
    username: str
    password: str
    confirmPassword: str

class ChangePasswordReq(BaseModel):
    old_password: str
    new_password: str

class ProfileReq(BaseModel):
    email: str = ''
    cellphone: str = ''

def _captcha_siteverify_url() -> str:
    if deps.CAPTCHA_SITEVERIFY_URL:
        return deps.CAPTCHA_SITEVERIFY_URL

    endpoint = deps.CAPTCHA_API_ENDPOINT.rstrip('/')
    if endpoint.startswith('http://') or endpoint.startswith('https://'):
        return f'{endpoint}/siteverify'
    return ''

def verify_captcha(token: str):
    if not deps.CAPTCHA_ENABLED:
        return

    if not token:
        raise HTTPException(400, '请先完成验证码')

    siteverify_url = _captcha_siteverify_url()
    if not siteverify_url or not deps.CAPTCHA_SECRET_KEY:
        raise HTTPException(500, '验证码服务未配置')

    try:
        resp = requests.post(
            siteverify_url,
            json={'secret': deps.CAPTCHA_SECRET_KEY, 'response': token},
            timeout=5,
        )
        data = resp.json()
    except requests.RequestException as exc:
        raise HTTPException(502, '验证码服务不可用') from exc
    except ValueError as exc:
        raise HTTPException(502, '验证码服务响应异常') from exc

    if not resp.ok or not data.get('success'):
        raise HTTPException(400, '验证码校验失败，请重试')

@router.post('/login')
def login(req: LoginReq, response: Response):
    """用户登录"""
    username = req.username
    password = req.password
    verify_captcha(req.captchaToken)
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, password, role FROM users WHERE name=%s", (username,))
        user = cur.fetchone()
        
        if not user or not user['password']:
            raise HTTPException(400, '用户名或密码错误')
        
        # 兼容多种密码格式
        pwd_ok = False
        stored = user['password']
        if stored.startswith('$2b$') or stored.startswith('$2a$'):
            pwd_ok = _bcrypt.checkpw(password.encode(), stored.encode())
        elif stored.startswith('scrypt:') or stored.startswith('pbkdf2:'):
            from werkzeug.security import check_password_hash
            pwd_ok = check_password_hash(stored, password)
        else:
            pwd_ok = (stored == password)
        
        if not pwd_ok:
            raise HTTPException(400, '用户名或密码错误')
        
        token = create_token(user['id'], user['role'])
        response.set_cookie('token', token, httponly=True, max_age=86400, path='/')
        record_log(conn, user['id'], '登录系统')
        conn.commit()
        
        return {
            'code': 0,
            'msg': '登录成功',
            'data': {
                'token': token,
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'role': user['role']
                }
            }
        }
    finally:
        conn.close()

@router.post('/register')
def register(req: RegisterReq):
    """用户注册（仅允许首次初始化时注册管理员）"""
    username = req.username
    password = req.password
    confirmPassword = req.confirmPassword

    if password != confirmPassword:
        raise HTTPException(400, '两次密码不一致')

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 检查系统是否已初始化（已有管理员）
        cur.execute("SELECT COUNT(*) as count FROM users")
        count = cur.fetchone()['count']
        if count > 0:
            raise HTTPException(403, '系统已完成初始化，无法注册新账户')

        hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (name, password, role, node, route, enable, expire, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW() + INTERVAL '%s days', NOW(), NOW()) RETURNING id",
            (username, hashed, 'manager', deps.DEFAULT_NODE_COUNT, 0, 1, deps.DEFAULT_REG_DAYS)
        )
        user_id = cur.fetchone()['id']
        conn.commit()
        
        return {'code': 0, 'msg': '注册成功', 'data': {'id': user_id, 'role': 'manager'}}
    finally:
        conn.close()

@router.post('/logout')
def logout(response: Response):
    """用户登出"""
    response.delete_cookie('token', path='/')
    return {'code': 0, 'msg': '已退出'}

@router.get('/me')
def me(user: CurrentUser = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        'code': 0,
        'data': {
            'id': user.id, 'name': user.name, 'role': user.role,
            'email': user.email, 'cellphone': user.cellphone,
            'node': user.node, 'route': user.route, 'enable': user.enable,
            'expire': user.expire, 'created_at': user.created_at,
        }
    }

@router.post('/password')
def change_password(req: ChangePasswordReq, user: CurrentUser = Depends(get_current_user)):
    """修改密码"""
    old_password = req.old_password
    new_password = req.new_password
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT password FROM users WHERE id=%s", (user.id,))
        row = cur.fetchone()
        
        if not row or not row['password'] or not _bcrypt.checkpw(old_password.encode(), row['password'].encode()):
            raise HTTPException(400, '原密码错误')
        
        hashed = _bcrypt.hashpw(new_password.encode(), _bcrypt.gensalt()).decode()
        cur.execute("UPDATE users SET password=%s, updated_at=NOW() WHERE id=%s", (hashed, user.id))
        record_log(conn, user.id, '修改密码')
        conn.commit()
        return {'code': 0, 'msg': '密码修改成功'}
    finally:
        conn.close()

@router.post('/profile')
def update_profile(req: ProfileReq, user: CurrentUser = Depends(get_current_user)):
    """更新个人资料"""
    email = req.email
    cellphone = req.cellphone
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET email=%s, cellphone=%s, updated_at=NOW() WHERE id=%s", (email, cellphone, user.id))
        record_log(conn, user.id, '更新个人资料')
        conn.commit()
        return {'code': 0, 'msg': '更新成功'}
    finally:
        conn.close()
