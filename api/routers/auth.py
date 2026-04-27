"""
认证路由模块
处理登录、注册、登出、密码修改等
"""
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
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

@router.post('/login')
def login(req: LoginReq, response: Response):
    """用户登录"""
    username = req.username
    password = req.password
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
    """用户注册"""
    username = req.username
    password = req.password
    confirmPassword = req.confirmPassword
    if deps.OPEN_USER_REG != 'on':
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            if count > 0:
                raise HTTPException(403, '注册已关闭')
        finally:
            conn.close()

    if password != confirmPassword:
        raise HTTPException(400, '两次密码不一致')

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # 检查用户名是否已存在
        cur.execute("SELECT id FROM users WHERE name=%s", (username,))
        if cur.fetchone():
            raise HTTPException(400, '用户名已存在')

        # 第一个注册的用户自动成为管理员
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()['count']
        role = 'manager' if count == 0 else 'user'

        hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (name, password, role, node, route, enable, expire, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW() + INTERVAL '%s days', NOW(), NOW()) RETURNING id",
            (username, hashed, role, deps.DEFAULT_NODE_COUNT, 0, 1, deps.DEFAULT_REG_DAYS)
        )
        user_id = cur.fetchone()['id']
        conn.commit()
        
        return {'code': 0, 'msg': '注册成功', 'data': {'id': user_id, 'role': role}}
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
