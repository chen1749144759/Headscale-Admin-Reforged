"""
ACL路由模块
处理ACL规则的获取、更新、文件读写、重载等
"""
import json
import subprocess

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, get_current_user, require_manager, get_db_conn, record_log

router = APIRouter(prefix="/api/acl", tags=["ACL"])

ACL_FILE_PATH = "/etc/headscale/acl.hujson"

class AclUpdateReq(BaseModel):
    acl: str

@router.get('')
def get_acl(user: CurrentUser = Depends(get_current_user)):
    """获取ACL规则（从数据库）"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT acl FROM acl ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        acl_text = row[0] if row else ''
        return {'code': 0, 'data': acl_text}
    finally:
        conn.close()

@router.put('')
def update_acl(req: AclUpdateReq, user: CurrentUser = Depends(require_manager)):
    """更新ACL规则（保存到数据库并写入文件）"""
    acl = req.acl
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO acl (acl, user_id) VALUES (%s, %s)", (acl, user.id))
        
        # 写入文件
        try:
            with open(ACL_FILE_PATH, 'w') as f:
                f.write(acl)
            subprocess.run(['systemctl', 'reload', 'headscale'], capture_output=True, timeout=10)
        except Exception as e:
            print(f'写入 ACL 文件失败: {e}')
        
        record_log(conn, user.id, '更新 ACL 规则')
        conn.commit()
        return {'code': 0, 'msg': 'ACL 更新成功'}
    finally:
        conn.close()

@router.post('/rewrite')
def rewrite_acl(user: CurrentUser = Depends(require_manager)):
    """重写 ACL 文件（从数据库读取并写入到文件）"""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT acl FROM acl ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        acl_text = row[0] if row else ''
        
        if not acl_text:
            raise HTTPException(400, '数据库中没有 ACL 规则')
        
        try:
            with open(ACL_FILE_PATH, 'w') as f:
                f.write(acl_text)
            record_log(conn, user.id, '重写 ACL 文件')
            conn.commit()
            return {'code': 0, 'msg': 'ACL 文件重写成功'}
        except Exception as e:
            raise HTTPException(500, f'写入 ACL 文件失败: {str(e)}')
    finally:
        conn.close()

@router.get('/read')
def read_acl_file(user: CurrentUser = Depends(require_manager)):
    """读取 /etc/headscale/acl.hujson 文件内容"""
    try:
        with open(ACL_FILE_PATH, 'r') as f:
            acl_data = json.load(f)
        
        acls = acl_data.get('acls', [])
        return {'code': 0, 'data': {'acl_path': ACL_FILE_PATH, 'acls': acls}}
    except FileNotFoundError:
        raise HTTPException(404, f'错误: 文件 {ACL_FILE_PATH} 未找到')
    except json.JSONDecodeError:
        raise HTTPException(500, f'错误: 无法解析 {ACL_FILE_PATH} 中的 JSON 数据')
    except Exception as e:
        raise HTTPException(500, f'发生未知错误: {str(e)}')

@router.post('/reload')
def reload_headscale_api(user: CurrentUser = Depends(require_manager)):
    """重载 headscale 服务"""
    try:
        subprocess.run(['systemctl', 'reload', 'headscale'], capture_output=True, timeout=10)
        conn = get_db_conn()
        try:
            record_log(conn, user.id, '重载 headscale 服务')
            conn.commit()
        finally:
            conn.close()
        return {'code': 0, 'msg': 'headscale 服务重载成功'}
    except Exception as e:
        raise HTTPException(500, f'重载 headscale 服务失败: {str(e)}')
