"""
流量统计路由
提供全局、分组、机器维度的流量查询接口。
"""
import ipaddress
import math
import psycopg2
import psycopg2.extras
import time
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends

from .dependencies import CurrentUser, get_current_user, get_db_conn, require_manager
from .utils import hs_request

router = APIRouter(prefix="/api/traffic", tags=["流量统计"])


_last_maintenance_at = 0.0
_scaletail_network_cache: dict[str, dict[str, Any]] = {}


def _account_scope(user: CurrentUser, table_alias: str) -> tuple[str, list[int]]:
    """Authorize historical rows by the node's current owner, not stale snapshots."""
    if user.is_manager():
        return "", []
    if user.network_user_id is None:
        return " AND 1=0", []
    return f"""
        AND EXISTS (
            SELECT 1
            FROM nodes scope_node
            WHERE scope_node.id = {table_alias}.machine_id
              AND scope_node.user_id = %s
              AND scope_node.deleted_at IS NULL
        )
    """, [user.network_user_id]


def _append_account_scope(
    where: list[str],
    params: list[Any],
    user: CurrentUser,
    table_alias: str,
) -> None:
    if user.is_manager():
        return
    if user.network_user_id is None:
        where.append("1=0")
        return
    where.append(f"""
        EXISTS (
            SELECT 1
            FROM nodes scope_node
            WHERE scope_node.id = {table_alias}.machine_id
              AND scope_node.user_id = %s
              AND scope_node.deleted_at IS NULL
        )
    """)
    params.append(user.network_user_id)


def _extract_hs_nodes(result: Any) -> list[dict]:
    """兼容不同 Headscale API 包装格式，返回节点列表。"""
    if not isinstance(result, dict):
        return result if isinstance(result, list) else []
    data = result.get('data', result)
    if isinstance(data, dict):
        nodes = data.get('nodes') or data.get('node') or []
        return nodes if isinstance(nodes, list) else []
    return data if isinstance(data, list) else []


def _load_scaletail_networks(user: CurrentUser) -> list[ipaddress._BaseNetwork]:
    """用于展示过滤：Tailnet 地址与已批准/已生效宣告路由都视为 ScaleTail 流量目标。"""
    now = time.time()
    cache_key = "manager" if user.is_manager() else f"user:{user.id}"
    cache = _scaletail_network_cache.get(cache_key, {})
    cached = cache.get("networks")
    if cached is not None and now - float(cache.get("loaded_at") or 0) < 60:
        return cached

    networks: list[ipaddress._BaseNetwork] = [
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("fd7a:115c:a1e0::/48"),
    ]
    try:
        for node in _extract_hs_nodes(
            hs_request(
                'GET',
                '/api/v1/node',
                token=user.session_token,
            )
        ):
            addresses = (
                node.get('ipAddresses')
                or node.get('ip_addresses')
                or node.get('ips')
                or []
            )
            for value in addresses:
                try:
                    ip = ipaddress.ip_address(str(value))
                    prefix = 32 if ip.version == 4 else 128
                    networks.append(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
                except ValueError:
                    continue

            routes = set(node.get('approvedRoutes') or node.get('approved_routes') or [])
            routes.update(node.get('subnetRoutes') or node.get('subnet_routes') or [])
            for value in routes:
                try:
                    network = ipaddress.ip_network(str(value), strict=False)
                except ValueError:
                    continue
                if network.prefixlen == 0:
                    continue
                networks.append(network)
    except Exception:
        pass

    dedup = list(dict.fromkeys(networks))
    _scaletail_network_cache[cache_key] = {
        "loaded_at": now,
        "networks": dedup,
    }
    return dedup


def _sample_window(observed_at: list[datetime] | None, hours: int, interval_seconds: int) -> dict:
    """Calculate report completeness only inside continuous active sessions."""
    samples = sorted(value for value in (observed_at or []) if isinstance(value, datetime))
    total = len(samples)
    if total == 0:
        return {
            'samples': 0,
            'expected': 0,
            'normal': 0,
            'failed': 0,
            'normal_percent': 0,
            'samples_per_hour': 0,
            'active_minutes': 0,
            'sessions': 0,
            'first_seen': '',
            'last_seen': '',
        }

    # A long gap means the client was not using ScaleTail. Only short gaps
    # inside an active session can represent missed reports.
    session_gap_seconds = max(60, interval_seconds * 4)
    expected = 1
    active_seconds = float(interval_seconds)
    sessions = 1
    previous = samples[0]
    for current in samples[1:]:
        gap_seconds = max(0.0, (current - previous).total_seconds())
        if gap_seconds > session_gap_seconds:
            sessions += 1
            expected += 1
            active_seconds += interval_seconds
        else:
            expected += max(1, math.ceil(gap_seconds / interval_seconds))
            active_seconds += max(float(interval_seconds), gap_seconds)
        previous = current

    failed = max(0, expected - total)
    return {
        'samples': total,
        'expected': expected,
        'normal': total,
        'failed': failed,
        'normal_percent': round((total / expected) * 100, 1) if expected else 0,
        'samples_per_hour': round(total / max(active_seconds / 3600, interval_seconds / 3600), 1),
        'active_minutes': round(active_seconds / 60, 1),
        'sessions': sessions,
        'first_seen': samples[0].strftime('%Y-%m-%d %H:%M:%S'),
        'last_seen': samples[-1].strftime('%Y-%m-%d %H:%M:%S'),
    }


def _run_traffic_maintenance(conn, force: bool = False) -> dict:
    global _last_maintenance_at
    now = time.time()
    if not force and now - _last_maintenance_at < 600:
        return {'skipped': True}

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO traffic_hourly (
            bucket_start, machine_id, group_id,
            rx_bytes, tx_bytes, peak_rx_rate_bps, peak_tx_rate_bps
        )
        SELECT
            date_trunc('hour', observed_at) AS bucket_start,
            machine_id,
            MAX(group_id) AS group_id,
            COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
            COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes,
            COALESCE(MAX(rx_rate_bps), 0) AS peak_rx_rate_bps,
            COALESCE(MAX(tx_rate_bps), 0) AS peak_tx_rate_bps
        FROM traffic_samples
        WHERE machine_id IS NOT NULL
          AND observed_at >= NOW() - INTERVAL '31 days'
        GROUP BY date_trunc('hour', observed_at), machine_id
        ON CONFLICT (bucket_start, machine_id) DO UPDATE SET
            group_id = EXCLUDED.group_id,
            rx_bytes = EXCLUDED.rx_bytes,
            tx_bytes = EXCLUDED.tx_bytes,
            peak_rx_rate_bps = EXCLUDED.peak_rx_rate_bps,
            peak_tx_rate_bps = EXCLUDED.peak_tx_rate_bps
    """)
    hourly_rows = cur.rowcount

    cur.execute("""
        INSERT INTO traffic_daily (
            bucket_date, machine_id, group_id, rx_bytes, tx_bytes
        )
        SELECT
            observed_at::date AS bucket_date,
            machine_id,
            MAX(group_id) AS group_id,
            COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
            COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes
        FROM traffic_samples
        WHERE machine_id IS NOT NULL
          AND observed_at >= NOW() - INTERVAL '31 days'
        GROUP BY observed_at::date, machine_id
        ON CONFLICT (bucket_date, machine_id) DO UPDATE SET
            group_id = EXCLUDED.group_id,
            rx_bytes = EXCLUDED.rx_bytes,
            tx_bytes = EXCLUDED.tx_bytes
    """)
    daily_rows = cur.rowcount

    cur.execute("DELETE FROM traffic_samples WHERE observed_at < NOW() - INTERVAL '30 days'")
    deleted_samples = cur.rowcount
    cur.execute("DELETE FROM traffic_hourly WHERE bucket_start < NOW() - INTERVAL '180 days'")
    deleted_hourly = cur.rowcount
    cur.execute("DELETE FROM traffic_daily WHERE bucket_date < CURRENT_DATE - INTERVAL '730 days'")
    deleted_daily = cur.rowcount
    cur.execute("DELETE FROM flow_summaries WHERE window_start < NOW() - INTERVAL '30 days'")
    deleted_flows = cur.rowcount

    conn.commit()
    _last_maintenance_at = now
    return {
        'skipped': False,
        'hourly_rows': hourly_rows,
        'daily_rows': daily_rows,
        'deleted_samples': deleted_samples,
        'deleted_hourly': deleted_hourly,
        'deleted_daily': deleted_daily,
        'deleted_flows': deleted_flows,
    }


@router.get('/summary')
def traffic_summary(user: CurrentUser = Depends(get_current_user)):
    """获取流量总览"""
    conn = get_db_conn()
    try:
        _run_traffic_maintenance(conn)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sample_scope_sql, sample_scope_params = _account_scope(user, "ts")
        cur.execute(f"""
            SELECT
                COALESCE(SUM(ts.rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(ts.tx_bytes_delta), 0) AS tx_bytes,
                COALESCE(MAX(ts.rx_rate_bps), 0) AS peak_rx_rate_bps,
                COALESCE(MAX(ts.tx_rate_bps), 0) AS peak_tx_rate_bps,
                COUNT(DISTINCT COALESCE(ts.machine_id::text, ts.machine_name)) AS machines
            FROM traffic_samples ts
            WHERE ts.observed_at >= NOW() - INTERVAL '24 hours'
            {sample_scope_sql}
        """, sample_scope_params)
        day = cur.fetchone()

        cur.execute(f"""
            SELECT
                COALESCE(SUM(ts.rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(ts.tx_bytes_delta), 0) AS tx_bytes
            FROM traffic_samples ts
            WHERE ts.observed_at >= NOW() - INTERVAL '30 days'
            {sample_scope_sql}
        """, sample_scope_params)
        month = cur.fetchone()

        event_scope_sql, event_scope_params = _account_scope(user, "se")
        cur.execute(
            f"SELECT COUNT(*) AS open_events FROM security_events se WHERE se.status = 'open' {event_scope_sql}",
            event_scope_params,
        )
        events = cur.fetchone()

        return {
            'code': 0,
            'data': {
                'today_rx_bytes': int(day['rx_bytes'] or 0),
                'today_tx_bytes': int(day['tx_bytes'] or 0),
                'month_rx_bytes': int(month['rx_bytes'] or 0),
                'month_tx_bytes': int(month['tx_bytes'] or 0),
                'peak_rx_rate_bps': float(day['peak_rx_rate_bps'] or 0),
                'peak_tx_rate_bps': float(day['peak_tx_rate_bps'] or 0),
                'active_machines': int(day['machines'] or 0),
                'open_security_events': int(events['open_events'] or 0),
            }
        }
    finally:
        conn.close()


@router.post('/maintenance')
def traffic_maintenance(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        result = _run_traffic_maintenance(conn, force=True)
        return {'code': 0, 'data': result}
    finally:
        conn.close()


@router.get('/top-machines')
def top_machines(days: int = 7, user: CurrentUser = Depends(get_current_user)):
    """获取机器流量排行"""
    days = max(1, min(days, 90))
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        scope_sql, scope_params = _account_scope(user, "ts")
        cur.execute(f"""
            SELECT
                ts.machine_id,
                COALESCE(ts.machine_name, CONCAT('机器#', ts.machine_id)) AS machine_name,
                ts.group_name,
                COALESCE(SUM(ts.rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(ts.tx_bytes_delta), 0) AS tx_bytes,
                COALESCE(MAX(ts.rx_rate_bps), 0) AS peak_rx_rate_bps,
                COALESCE(MAX(ts.tx_rate_bps), 0) AS peak_tx_rate_bps
            FROM traffic_samples ts
            WHERE ts.observed_at >= NOW() - (%s || ' days')::interval
            {scope_sql}
            GROUP BY ts.machine_id, ts.machine_name, ts.group_name
            ORDER BY (COALESCE(SUM(ts.rx_bytes_delta), 0) + COALESCE(SUM(ts.tx_bytes_delta), 0)) DESC
            LIMIT 20
        """, [days, *scope_params])
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()


@router.get('/top-groups')
def top_groups(days: int = 7, user: CurrentUser = Depends(get_current_user)):
    """获取分组流量排行"""
    days = max(1, min(days, 90))
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        scope_sql, scope_params = _account_scope(user, "ts")
        cur.execute(f"""
            SELECT
                ts.group_id,
                COALESCE(ts.group_name, CONCAT('分组#', ts.group_id)) AS group_name,
                COALESCE(SUM(ts.rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(ts.tx_bytes_delta), 0) AS tx_bytes,
                COUNT(DISTINCT COALESCE(ts.machine_id::text, ts.machine_name)) AS machines
            FROM traffic_samples ts
            WHERE ts.observed_at >= NOW() - (%s || ' days')::interval
            {scope_sql}
            GROUP BY ts.group_id, ts.group_name
            ORDER BY (COALESCE(SUM(ts.rx_bytes_delta), 0) + COALESCE(SUM(ts.tx_bytes_delta), 0)) DESC
            LIMIT 20
        """, [days, *scope_params])
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()


@router.get('/samples')
def traffic_samples(
    page: int = 1,
    size: int = 20,
    machine_id: int | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """获取原始采样列表"""
    page = max(1, page)
    size = max(1, min(size, 100))
    where = []
    params = []
    if machine_id:
        where.append("ts.machine_id = %s")
        params.append(machine_id)
    _append_account_scope(where, params, user, "ts")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM traffic_samples ts {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                ts.id, ts.machine_id, ts.machine_name, ts.group_name,
                ts.rx_bytes_delta, ts.tx_bytes_delta, ts.rx_rate_bps, ts.tx_rate_bps,
                ts.derp, ts.endpoint_type,
                TO_CHAR(ts.observed_at, 'YYYY-MM-DD HH24:MI:SS') AS observed_at
            FROM traffic_samples ts
            {where_sql}
            ORDER BY ts.observed_at DESC
            LIMIT %s OFFSET %s
        """, [*params, size, offset])
        return {'code': 0, 'data': cur.fetchall(), 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()


@router.get('/sample-health')
def sample_health(
    interval_seconds: int = 15,
    user: CurrentUser = Depends(get_current_user),
):
    """按机器聚合最近 24/12 小时连续活跃时段的上报完整率。"""
    interval_seconds = max(5, min(interval_seconds, 3600))
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        scope_sql, scope_params = _account_scope(user, "ts")
        cur.execute(f"""
            SELECT
                ts.machine_id,
                COALESCE(ts.machine_name, CONCAT('机器#', ts.machine_id)) AS machine_name,
                ts.group_name,
                ARRAY_AGG(ts.observed_at ORDER BY ts.observed_at)
                    FILTER (WHERE ts.observed_at >= NOW() - INTERVAL '24 hours') AS samples_24h,
                ARRAY_AGG(ts.observed_at ORDER BY ts.observed_at)
                    FILTER (WHERE ts.observed_at >= NOW() - INTERVAL '12 hours') AS samples_12h,
                MAX(ts.observed_at) AS last_seen
            FROM traffic_samples ts
            WHERE ts.observed_at >= NOW() - INTERVAL '24 hours'
            {scope_sql}
            GROUP BY ts.machine_id, ts.machine_name, ts.group_name
            ORDER BY COUNT(*) FILTER (WHERE ts.observed_at >= NOW() - INTERVAL '24 hours') DESC,
                     MAX(ts.observed_at) DESC
            LIMIT 50
        """, scope_params)
        rows = []
        for row in cur.fetchall():
            last_seen = row.get('last_seen')
            rows.append({
                'machine_id': row.get('machine_id'),
                'machine_name': row.get('machine_name') or '未知机器',
                'group_name': row.get('group_name') or '',
                'last_seen': last_seen.strftime('%Y-%m-%d %H:%M:%S') if last_seen else '',
                'windows': {
                    'h24': _sample_window(
                        row.get('samples_24h'),
                        24,
                        interval_seconds,
                    ),
                    'h12': _sample_window(
                        row.get('samples_12h'),
                        12,
                        interval_seconds,
                    ),
                },
            })
        return {'code': 0, 'data': rows}
    finally:
        conn.close()


@router.get('/top-destinations')
def top_destinations(days: int = 1, user: CurrentUser = Depends(get_current_user)):
    """获取请求/连接目标排行"""
    days = max(1, min(days, 90))
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        scope_sql, scope_params = _account_scope(user, "fs")
        network_cidrs = [str(network) for network in _load_scaletail_networks(user)]
        cur.execute(f"""
            SELECT
                fs.dst_ip,
                fs.dst_port,
                fs.protocol,
                fs.process_name,
                COALESCE(SUM(fs.bytes), 0) AS bytes,
                COALESCE(SUM(fs.packets), 0) AS packets,
                COALESCE(SUM(fs.connection_count), 0) AS connection_count,
                COUNT(DISTINCT COALESCE(fs.machine_id::text, fs.machine_name)) AS machines,
                TO_CHAR(MAX(fs.window_start), 'YYYY-MM-DD HH24:MI:SS') AS last_seen
            FROM flow_summaries fs
            WHERE fs.window_start >= NOW() - (%s || ' days')::interval
              AND fs.dst_ip IS NOT NULL
              AND fs.dst_ip <> ''
              AND CASE
                    WHEN pg_input_is_valid(fs.dst_ip, 'inet')
                    THEN fs.dst_ip::inet <<= ANY(%s::cidr[])
                    ELSE FALSE
                  END
              {scope_sql}
            GROUP BY fs.dst_ip, fs.dst_port, fs.protocol, fs.process_name
            ORDER BY COALESCE(SUM(fs.connection_count), 0) DESC, COALESCE(SUM(fs.packets), 0) DESC
            LIMIT 20
        """, [days, network_cidrs, *scope_params])
        return {'code': 0, 'data': cur.fetchall()}
    finally:
        conn.close()


@router.get('/flows')
def traffic_flows(
    page: int = 1,
    size: int = 20,
    machine_id: int | None = None,
    dst_ip: str = '',
    user: CurrentUser = Depends(get_current_user),
):
    """获取请求/连接明细"""
    page = max(1, page)
    size = max(1, min(size, 100))
    where = []
    params = []
    if machine_id:
        where.append("fs.machine_id = %s")
        params.append(machine_id)
    if dst_ip:
        where.append("fs.dst_ip = %s")
        params.append(dst_ip)
    _append_account_scope(where, params, user, "fs")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM flow_summaries fs {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                fs.id, fs.machine_id, fs.machine_name, fs.group_name,
                fs.dst_ip, fs.dst_port, fs.protocol, fs.direction, fs.bytes, fs.packets,
                fs.connection_count, fs.state, fs.process_id, fs.process_name,
                TO_CHAR(fs.window_start, 'YYYY-MM-DD HH24:MI:SS') AS window_start,
                fs.window_seconds
            FROM flow_summaries fs
            {where_sql}
            ORDER BY fs.window_start DESC, fs.id DESC
            LIMIT %s OFFSET %s
        """, [*params, size, offset])
        return {'code': 0, 'data': cur.fetchall(), 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()
