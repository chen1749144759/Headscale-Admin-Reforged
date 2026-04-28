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
from .utils import hs_request

router = APIRouter(prefix="/api/acl", tags=["ACL"])

ACL_FILE_PATH = "/etc/headscale/acl.hujson"

class AclUpdateReq(BaseModel):
    acl: str

@router.get('')
def get_acl(user: CurrentUser = Depends(get_current_user)):
    """获取ACL规则（优先从 Headscale API 读取，兜底读管理数据库）"""
    # 优先从 Headscale policy API 读取（database 模式）
    try:
        result = hs_request('GET', '/api/v1/policy')
        if result.get('code') == 0:
            data = result.get('data', {})
            policy_text = data.get('policy', '') if isinstance(data, dict) else ''
            if policy_text:
                return {'code': 0, 'data': policy_text}
    except Exception:
        pass

    # 兜底：从管理面板数据库读取
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT acl FROM acl ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        acl_text = row['acl'] if row else ''
        return {'code': 0, 'data': acl_text}
    finally:
        conn.close()

@router.put('')
def update_acl(req: AclUpdateReq, user: CurrentUser = Depends(require_manager)):
    """更新ACL规则（同步写入 Headscale API + 管理数据库）"""
    acl = req.acl
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        # 保存到管理面板数据库（历史记录）
        cur.execute("INSERT INTO acl (acl, user_id) VALUES (%s, %s)", (acl, user.id))

        # 通过 Headscale API 写入 policy（database 模式直接生效）
        hs_result = hs_request('PUT', '/api/v1/policy', {'policy': acl})
        if hs_result.get('code') != 0:
            msg = hs_result.get('msg', '')
            print(f'写入 Headscale policy 失败: {msg}')
            # 不阻断流程，可能 headscale 版本不支持此接口，走文件兜底
            try:
                with open(ACL_FILE_PATH, 'w') as f:
                    f.write(acl)
            except Exception as e:
                print(f'写入 ACL 文件也失败: {e}')

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
        acl_text = row['acl'] if row else ''
        
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
