"""
ACL路由模块
处理 ACL 规则的获取和热更新
"""
import json
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, require_manager, get_db_conn, record_log
from .utils import hs_request

router = APIRouter(prefix="/api/acl", tags=["ACL"])

class AclUpdateReq(BaseModel):
    acl: str


# ─── Headscale policy 用户名 @ 后缀适配 ───────────────────────────
# Headscale 要求 ACL 中引用用户名时必须带 @ 后缀（如 "RD@"），
# 否则会被解析器当作 Host 别名导致 "host not defined in policy" 错误。
# 以下工具函数在后端层做透明转换，前端无需感知。

_SPECIAL_PREFIXES = ('group:', 'autogroup:')
_MANAGED_GROUP_PREFIX = 'group:scaleforge-'


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


def _parse_policy(acl_text: str) -> dict:
    try:
        policy = json.loads(_clean_hujson(acl_text))
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f'ACL 不是有效的 HuJSON/JSON: {exc}') from exc

    if not isinstance(policy, dict):
        raise HTTPException(400, 'ACL 根节点必须是对象')

    return policy


def _reject_identity_tags(policy: dict) -> None:
    """账户密码节点不支持身份标签，拒绝保存永远无法生效的规则。"""
    if policy.get('tagOwners'):
        raise HTTPException(400, '账户密码节点不支持身份标签，请删除 tagOwners')

    def contains_tag(value) -> bool:
        if isinstance(value, str):
            return value.startswith('tag:')
        if isinstance(value, list):
            return any(contains_tag(item) for item in value)
        if isinstance(value, dict):
            return any(
                (isinstance(key, str) and key.startswith('tag:')) or contains_tag(item)
                for key, item in value.items()
            )
        return False

    if contains_tag(policy):
        raise HTTPException(400, '账户密码节点不支持 tag: 身份标签引用，请改用账户、分组或 IP')
    def contains_managed_group(value) -> bool:
        if isinstance(value, str):
            return value.startswith(_MANAGED_GROUP_PREFIX)
        if isinstance(value, list):
            return any(contains_managed_group(item) for item in value)
        if isinstance(value, dict):
            return any(
                contains_managed_group(key) or contains_managed_group(item)
                for key, item in value.items()
            )
        return False

    if contains_managed_group(policy):
        raise HTTPException(400, 'group:scaleforge-* 为系统保留分组名称')


def _account_is_active(account: dict, now: datetime | None = None) -> bool:
    if not bool(account.get('enabled')) or str(account.get('role') or '') != 'user':
        return False
    expires_at = str(account.get('expiresAt') or '').strip()
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    except ValueError:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > (now or datetime.now(timezone.utc))


def _load_business_groups(user: CurrentUser) -> list[dict]:
    groups_result = hs_request('GET', '/v1/groups', token=user.session_token)
    accounts_result = hs_request('GET', '/v1/accounts', token=user.session_token)
    if groups_result.get('code') != 0 or accounts_result.get('code') != 0:
        raise HTTPException(502, '账户分组服务请求失败')
    groups = groups_result.get('data') or []
    accounts = accounts_result.get('data') or []
    if not isinstance(groups, list) or not isinstance(accounts, list):
        raise HTTPException(502, '账户分组服务返回了无效数据')

    accounts_by_group: dict[int, list[dict]] = {}
    for account in accounts:
        if not isinstance(account, dict):
            raise HTTPException(502, '账户分组服务返回了无效账户')
        raw_group_id = account.get('groupId')
        if raw_group_id is None:
            continue
        try:
            account_group_id = int(raw_group_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(502, '账户分组服务返回了无效账户分组 ID') from exc
        if account_group_id <= 0:
            raise HTTPException(502, '账户分组服务返回了无效账户分组 ID')
        if str(account.get('role') or '') == 'user':
            accounts_by_group.setdefault(account_group_id, []).append(account)

    result = []
    for group in groups:
        if not isinstance(group, dict):
            raise HTTPException(502, '账户分组服务返回了无效分组')
        try:
            group_id = int(group.get('id') or 0)
        except (TypeError, ValueError) as exc:
            raise HTTPException(502, '账户分组服务返回了无效分组 ID') from exc
        if group_id <= 0 or not str(group.get('name') or '').strip():
            raise HTTPException(502, '账户分组服务返回了无效分组')
        group_accounts = accounts_by_group.get(group_id, [])
        result.append({
            'id': group_id,
            'name': str(group.get('name') or ''),
            'managed_account_exists': bool(group_accounts),
            'members': [
                str(account.get('networkName') or '')
                for account in group_accounts
                if _account_is_active(account) and str(account.get('networkName') or '').strip()
            ],
        })
    return result


def _business_group_index(business_groups: list[dict] | None) -> dict[str, dict]:
    return {
        str(group.get('name') or '').strip().casefold(): group
        for group in (business_groups or [])
        if str(group.get('name') or '').strip()
        and bool(group.get('managed_account_exists'))
    }


def _managed_group_name(group: dict) -> str:
    return f"{_MANAGED_GROUP_PREFIX}{int(group['id'])}"


def _split_alias_port(alias: str) -> tuple[str, str]:
    if ':' not in alias:
        return alias, ''
    if alias.startswith(_SPECIAL_PREFIXES) and alias.count(':') == 1:
        return alias, ''
    return tuple(alias.rsplit(':', 1))


def _compile_business_group_alias(alias: str, index: dict[str, dict]) -> str:
    if not alias or alias == '*' or alias.startswith(_SPECIAL_PREFIXES):
        return alias

    name, port = _split_alias_port(alias)
    group = index.get(name.strip().casefold())
    if group is None:
        return _ensure_user_suffix(alias)

    compiled = _managed_group_name(group)
    return f'{compiled}:{port}' if port else compiled


def transform_acl_for_headscale(
    acl_text: str,
    business_groups: list[dict] | None = None,
) -> str:
    """Compile business-group aliases and Headscale account identities."""
    try:
        obj = json.loads(_clean_hujson(acl_text))
    except Exception:
        return acl_text

    index = _business_group_index(business_groups)
    referenced_groups: set[str] = set()

    def compile_alias(value: str) -> str:
        compiled = _compile_business_group_alias(value, index)
        name, _ = _split_alias_port(compiled)
        if name.startswith(_MANAGED_GROUP_PREFIX):
            referenced_groups.add(name)
        return compiled

    for acl in obj.get('acls', []):
        acl['src'] = [compile_alias(value) for value in acl.get('src', [])]
        acl['dst'] = [compile_alias(value) for value in acl.get('dst', [])]
    for grant in obj.get('grants', []):
        grant['src'] = [compile_alias(value) for value in grant.get('src', [])]
        grant['dst'] = [compile_alias(value) for value in grant.get('dst', [])]
    for ssh_rule in obj.get('ssh', []):
        ssh_rule['src'] = [compile_alias(value) for value in ssh_rule.get('src', [])]
        ssh_rule['dst'] = [_ensure_user_suffix(value) for value in ssh_rule.get('dst', [])]
    auto_approvers = obj.get('autoApprovers') or {}
    routes = auto_approvers.get('routes') or {}
    for prefix, approvers in routes.items():
        values = approvers if isinstance(approvers, list) else [approvers]
        routes[prefix] = [compile_alias(value) for value in values]
    if auto_approvers.get('exitNode') is not None:
        auto_approvers['exitNode'] = [
            compile_alias(value)
            for value in (auto_approvers.get('exitNode') or [])
        ]

    groups = obj.setdefault('groups', {})
    for key in list(groups):
        if key.startswith(_MANAGED_GROUP_PREFIX):
            del groups[key]
        else:
            groups[key] = [_ensure_user_suffix(member) for member in groups[key]]
    for group in index.values():
        managed_name = _managed_group_name(group)
        if managed_name not in referenced_groups:
            continue
        groups[managed_name] = [
            _ensure_user_suffix(str(member))
            for member in group.get('members') or []
            if str(member).strip()
        ]

    if not groups:
        obj.pop('groups', None)
    return json.dumps(obj, indent=2, ensure_ascii=False)


def transform_acl_from_headscale(
    acl_text: str,
    business_groups: list[dict] | None = None,
) -> str:
    """Restore managed Headscale groups to ScaleForge business-group aliases."""
    try:
        obj = json.loads(_clean_hujson(acl_text))
    except Exception:
        return acl_text

    reverse = {
        _managed_group_name(group): str(group.get('name') or '').strip()
        for group in (business_groups or [])
        if str(group.get('name') or '').strip()
    }

    def restore(alias: str) -> str:
        name, port = _split_alias_port(alias)
        restored = reverse.get(name)
        if restored:
            return f'{restored}:{port}' if port else restored
        return _strip_user_suffix(alias)

    for acl in obj.get('acls', []):
        acl['src'] = [restore(value) for value in acl.get('src', [])]
        acl['dst'] = [restore(value) for value in acl.get('dst', [])]
    for grant in obj.get('grants', []):
        grant['src'] = [restore(value) for value in grant.get('src', [])]
        grant['dst'] = [restore(value) for value in grant.get('dst', [])]
    for ssh_rule in obj.get('ssh', []):
        ssh_rule['src'] = [restore(value) for value in ssh_rule.get('src', [])]
        ssh_rule['dst'] = [_strip_user_suffix(value) for value in ssh_rule.get('dst', [])]
    auto_approvers = obj.get('autoApprovers') or {}
    routes = auto_approvers.get('routes') or {}
    for prefix, approvers in routes.items():
        values = approvers if isinstance(approvers, list) else [approvers]
        routes[prefix] = [restore(value) for value in values]
    if auto_approvers.get('exitNode') is not None:
        auto_approvers['exitNode'] = [
            restore(value)
            for value in (auto_approvers.get('exitNode') or [])
        ]
    groups = obj.get('groups', {})
    for key in list(groups):
        if key.startswith(_MANAGED_GROUP_PREFIX):
            del groups[key]
        else:
            groups[key] = [_strip_user_suffix(member) for member in groups[key]]
    if not groups:
        obj.pop('groups', None)
    return json.dumps(obj, indent=2, ensure_ascii=False)


def refresh_acl_business_groups(user: CurrentUser) -> None:
    """Recompile the latest operator-authored ACL after membership changes."""
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT acl FROM acl ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row or not row.get('acl'):
            return
        acl_text = row['acl']
    finally:
        conn.close()

    compiled = transform_acl_for_headscale(acl_text, _load_business_groups(user))
    result = hs_request('PUT', '/api/v1/policy', {'policy': compiled}, token=user.session_token)
    if result.get('code') != 0:
        raise HTTPException(502, result.get('msg', '刷新 Headscale ACL 分组失败'))

@router.get('')
def get_acl(user: CurrentUser = Depends(require_manager)):
    """获取ACL规则（优先从 Headscale API 读取，兜底读管理数据库）"""
    # 优先从 Headscale policy API 读取（database 模式）
    try:
        result = hs_request('GET', '/api/v1/policy', token=user.session_token)
        if result.get('code') == 0:
            data = result.get('data', {})
            policy_text = data.get('policy', '') if isinstance(data, dict) else ''
            if policy_text:
                groups = _load_business_groups(user)
                return {'code': 0, 'data': transform_acl_from_headscale(policy_text, groups)}
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
    policy = _parse_policy(acl)
    _reject_identity_tags(policy)
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        # 保存到管理面板数据库（历史记录，保存前端原始格式）
        cur.execute("INSERT INTO acl (acl, account_id) VALUES (%s, %s)", (acl, user.id))

        acl_for_hs = transform_acl_for_headscale(acl, _load_business_groups(user))

        # 通过 Headscale API 写入 policy（database 模式直接生效）
        hs_result = hs_request(
            'PUT',
            '/api/v1/policy',
            {'policy': acl_for_hs},
            token=user.session_token,
        )
        if hs_result.get('code') != 0:
            conn.rollback()
            raise HTTPException(502, hs_result.get('msg', '写入 Headscale policy 失败'))

        record_log(conn, user.id, '更新 ACL 规则')
        conn.commit()
        return {'code': 0, 'msg': 'ACL 更新成功'}
    finally:
        conn.close()
