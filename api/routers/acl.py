"""
ACL路由模块
处理ACL规则的获取、更新、文件读写、重载等
"""
import json
import re
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


# ─── Headscale policy 用户名 @ 后缀适配 ───────────────────────────
# Headscale 要求 ACL 中引用用户名时必须带 @ 后缀（如 "RD@"），
# 否则会被解析器当作 Host 别名导致 "host not defined in policy" 错误。
# 以下工具函数在后端层做透明转换，前端无需感知。

_SPECIAL_PREFIXES = ('group:', 'tag:', 'autogroup:')


def _is_ip_or_cidr(s: str) -> bool:
    """简单判断是否为 IP 地址或 CIDR 网段"""
    return '.' in s or '/' in s


def _ensure_user_suffix(alias: str) -> str:
    """为裸用户名添加 @ 后缀（发送给 Headscale 前）"""
    if not alias or alias == '*' or '@' in alias:
        return alias
    if any(alias.startswith(p) for p in _SPECIAL_PREFIXES):
        return alias

    # dst 格式 "name:port"
    if ':' in alias:
        name, port = alias.split(':', 1)
        if _is_ip_or_cidr(name) or '@' in name:
            return alias
        if any(name.startswith(p.rstrip(':')) for p in _SPECIAL_PREFIXES):
            return alias
        return f"{name}@:{port}"

    if _is_ip_or_cidr(alias):
        return alias

    return f"{alias}@"


def _strip_user_suffix(alias: str) -> str:
    """去掉用户名的 @ 后缀（从 Headscale 读取后）"""
    if not alias:
        return alias
    if any(alias.startswith(p) for p in _SPECIAL_PREFIXES):
        return alias

    # dst 格式 "name@:port"
    if '@:' in alias:
        return alias.replace('@:', ':', 1)

    # src 格式 "name@"
    if alias.endswith('@'):
        return alias[:-1]

    return alias


def _clean_hujson(text: str) -> str:
    """清理 HuJSON 注释和尾随逗号，使其可被 json.loads 解析"""
    text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _transform_acl_aliases(acl_text: str, transform_fn) -> str:
    """对 ACL JSON 中所有用户名引用执行 transform_fn 转换"""
    try:
        cleaned = _clean_hujson(acl_text)
        obj = json.loads(cleaned)
    except Exception:
        return acl_text

    # 转换 acls 中的 src / dst
    for acl in obj.get('acls', []):
        acl['src'] = [transform_fn(s) for s in acl.get('src', [])]
        acl['dst'] = [transform_fn(d) for d in acl.get('dst', [])]

    # 转换 groups 定义中的成员列表
    groups = obj.get('groups', {})
    for key in groups:
        groups[key] = [transform_fn(m) for m in groups[key]]

    # 转换 tagOwners 中的拥有者列表
    tag_owners = obj.get('tagOwners', {})
    for key in tag_owners:
        tag_owners[key] = [transform_fn(o) for o in tag_owners[key]]

    return json.dumps(obj, indent=2, ensure_ascii=False)


def transform_acl_for_headscale(acl_text: str) -> str:
    """发送给 Headscale 前：为裸用户名添加 @ 后缀"""
    return _transform_acl_aliases(acl_text, _ensure_user_suffix)


def transform_acl_from_headscale(acl_text: str) -> str:
    """从 Headscale 读取后：去掉用户名的 @ 后缀"""
    return _transform_acl_aliases(acl_text, _strip_user_suffix)

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
                # 去掉 @ 后缀，返回前端友好的格式
                return {'code': 0, 'data': transform_acl_from_headscale(policy_text)}
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
        # 保存到管理面板数据库（历史记录，保存前端原始格式）
        cur.execute("INSERT INTO acl (acl, user_id) VALUES (%s, %s)", (acl, user.id))

        # 为用户名添加 @ 后缀后再发送给 Headscale
        acl_for_hs = transform_acl_for_headscale(acl)

        # 通过 Headscale API 写入 policy（database 模式直接生效）
        hs_result = hs_request('PUT', '/api/v1/policy', {'policy': acl_for_hs})
        if hs_result.get('code') != 0:
            msg = hs_result.get('msg', '')
            print(f'写入 Headscale policy 失败: {msg}')
            # 不阻断流程，可能 headscale 版本不支持此接口，走文件兜底
            try:
                with open(ACL_FILE_PATH, 'w') as f:
                    f.write(acl_for_hs)
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
                f.write(transform_acl_for_headscale(acl_text))
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
