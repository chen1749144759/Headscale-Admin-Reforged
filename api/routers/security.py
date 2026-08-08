"""
安全审计路由
提供安全事件、IP定位历史和可信网络配置接口。
"""
import os
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .dependencies import (
    CFG,
    CurrentUser,
    get_current_user,
    get_db_conn,
    record_log,
    require_manager,
    trusted_service_url,
)

router = APIRouter(prefix="/api/security", tags=["安全审计"])


class SecurityEventReq(BaseModel):
    level: str = 'info'
    event_type: str
    title: str
    description: str = ''
    group_id: Optional[int] = None
    group_name: str = ''
    machine_id: Optional[int] = None
    machine_name: str = ''
    ip: str = ''
    country: str = ''
    city: str = ''
    asn: str = ''
    evidence: dict[str, Any] = Field(default_factory=dict)


class EventStatusReq(BaseModel):
    status: str
    note: str = ''


class TrustedNetworkReq(BaseModel):
    kind: str
    value: str
    description: str = ''
    enabled: bool = True


class RiskRuleReq(BaseModel):
    name: str
    level: str = 'medium'
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


DEFAULT_RISK_RULES = [
    {
        'rule_key': 'sensitive_ports',
        'name': '敏感公网端口访问',
        'level': 'medium',
        'enabled': True,
        'config': {'ports': [22, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 6379, 9200, 11211]},
    },
    {
        'rule_key': 'destination_churn',
        'name': '短时间访问大量目标地址',
        'level': 'high',
        'enabled': True,
        'config': {'threshold': 80, 'window_hours': 1},
    },
]


@router.get('/summary')
def security_summary(user: CurrentUser = Depends(require_manager)):
    geo_template = os.environ.get('IP_GEOLOOKUP_URL') or str(CFG.get('ip_geolookup_url') or '')
    geo_probe = geo_template.replace('{ip}', '192.0.2.1') if geo_template else ''
    if geo_probe and '{ip}' not in geo_template:
        geo_probe = geo_probe.rstrip('/') + '/192.0.2.1'
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT level, COUNT(*) AS count
            FROM security_events
            WHERE status = 'open'
            GROUP BY level
        """)
        levels = {row['level']: row['count'] for row in cur.fetchall()}
        cur.execute("SELECT COUNT(*) AS count FROM node_ip_observations")
        ip_count = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) AS count FROM trusted_networks WHERE enabled = TRUE")
        trusted_count = cur.fetchone()['count']
        return {
            'code': 0,
            'data': {
                'levels': levels,
                'ip_observations': ip_count,
                'trusted_networks': trusted_count,
                'geo_lookup_enabled': bool(trusted_service_url(geo_probe)),
            }
        }
    finally:
        conn.close()


@router.get('/events')
def list_events(
    page: int = 1,
    size: int = 20,
    level: str = '',
    status: str = '',
    event_type: str = '',
    user: CurrentUser = Depends(require_manager),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    where = []
    params = []
    if level:
        where.append("level = %s")
        params.append(level)
    if status:
        where.append("status = %s")
        params.append(status)
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM security_events {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                id, level, event_type, title, description,
                group_name, machine_name, ip, country, city, asn,
                status, evidence,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(handled_at, 'YYYY-MM-DD HH24:MI:SS') AS handled_at
            FROM security_events
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, [*params, size, offset])
        return {'code': 0, 'data': cur.fetchall(), 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()


@router.post('/events')
def create_event(req: SecurityEventReq, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO security_events (
                level, event_type, title, description, group_id, group_name,
                machine_id, machine_name, ip, country, city, asn, evidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            req.level, req.event_type, req.title, req.description, req.group_id, req.group_name,
            req.machine_id, req.machine_name, req.ip, req.country, req.city, req.asn,
            psycopg2.extras.Json(req.evidence),
        ))
        row = cur.fetchone()
        record_log(conn, user.id, f'创建安全事件 #{row["id"]}: {req.title}')
        conn.commit()
        return {'code': 0, 'msg': '安全事件已创建', 'data': row}
    finally:
        conn.close()


@router.patch('/events/{event_id}')
def update_event_status(event_id: int, req: EventStatusReq, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE security_events
            SET status=%s, handled_by_account_id=%s, handled_at=NOW()
            WHERE id=%s
        """, (req.status, user.id, event_id))
        record_log(conn, user.id, f'处理安全事件 #{event_id}: {req.status}')
        conn.commit()
        return {'code': 0, 'msg': '事件状态已更新'}
    finally:
        conn.close()


@router.get('/ip-observations')
def ip_observations(
    machine_id: int | None = None,
    page: int = 1,
    size: int = 20,
    user: CurrentUser = Depends(require_manager),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    where = []
    params = []
    if machine_id:
        where.append("machine_id = %s")
        params.append(machine_id)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM node_ip_observations {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                id, machine_id, machine_name, group_name, ip, country, region, city, asn, isp,
                risk_flags, seen_count,
                TO_CHAR(first_seen, 'YYYY-MM-DD HH24:MI:SS') AS first_seen,
                TO_CHAR(last_seen, 'YYYY-MM-DD HH24:MI:SS') AS last_seen
            FROM node_ip_observations
            {where_sql}
            ORDER BY last_seen DESC
            LIMIT %s OFFSET %s
        """, [*params, size, offset])
        return {'code': 0, 'data': cur.fetchall(), 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()


@router.get('/trusted-networks')
def list_trusted_networks(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, kind, value, description, enabled,
                   TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM trusted_networks
            ORDER BY id DESC
        """)
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()


@router.post('/trusted-networks')
def create_trusted_network(req: TrustedNetworkReq, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO trusted_networks (kind, value, description, enabled, created_by_account_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (req.kind, req.value, req.description, req.enabled, user.id))
        row = cur.fetchone()
        record_log(conn, user.id, f'新增可信网络 {req.kind}:{req.value}')
        conn.commit()
        return {'code': 0, 'msg': '可信网络已创建', 'data': row}
    finally:
        conn.close()


@router.delete('/trusted-networks/{item_id}')
def delete_trusted_network(item_id: int, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM trusted_networks WHERE id=%s", (item_id,))
        record_log(conn, user.id, f'删除可信网络 #{item_id}')
        conn.commit()
        return {'code': 0, 'msg': '可信网络已删除'}
    finally:
        conn.close()


@router.get('/risk-rules')
def list_risk_rules(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT rule_key, name, level, enabled, config,
                   TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM risk_rules
        """)
        rows = {row['rule_key']: row for row in cur.fetchall()}
        data = []
        for rule in DEFAULT_RISK_RULES:
            merged = {**rule, **rows.get(rule['rule_key'], {})}
            data.append(merged)
        for key, row in rows.items():
            if key not in {rule['rule_key'] for rule in DEFAULT_RISK_RULES}:
                data.append(row)
        return {'code': 0, 'data': data}
    finally:
        conn.close()


@router.put('/risk-rules/{rule_key}')
def update_risk_rule(rule_key: str, req: RiskRuleReq, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO risk_rules (rule_key, name, level, enabled, config, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (rule_key) DO UPDATE SET
                name=EXCLUDED.name,
                level=EXCLUDED.level,
                enabled=EXCLUDED.enabled,
                config=EXCLUDED.config,
                updated_at=NOW()
        """, (rule_key, req.name, req.level, req.enabled, psycopg2.extras.Json(req.config)))
        record_log(conn, user.id, f'更新风险规则 {rule_key}: {req.name}')
        conn.commit()
        return {'code': 0, 'msg': '风险规则已更新'}
    finally:
        conn.close()
