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
_scaletail_network_cache: dict[str, Any] = {"loaded_at": 0.0, "networks": None}


def _extract_hs_nodes(result: Any) -> list[dict]:
    """兼容不同 Headscale API 包装格式，返回节点列表。"""
    if not isinstance(result, dict):
        return result if isinstance(result, list) else []
    data = result.get('data', result)
    if isinstance(data, dict):
        nodes = data.get('nodes') or data.get('node') or []
        return nodes if isinstance(nodes, list) else []
    return data if isinstance(data, list) else []


def _load_scaletail_networks() -> list[ipaddress._BaseNetwork]:
    """用于展示过滤：Tailnet 地址与已批准/已生效宣告路由都视为 ScaleTail 流量目标。"""
    now = time.time()
    cached = _scaletail_network_cache.get("networks")
    if cached is not None and now - float(_scaletail_network_cache.get("loaded_at") or 0) < 60:
        return cached

    networks: list[ipaddress._BaseNetwork] = [
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("fd7a:115c:a1e0::/48"),
    ]
    try:
        for node in _extract_hs_nodes(hs_request('GET', '/api/v1/node')):
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
    _scaletail_network_cache["loaded_at"] = now
    _scaletail_network_cache["networks"] = dedup
    return dedup


def _is_scaletail_destination(value: Any) -> bool:
    try:
        ip = ipaddress.ip_address(str(value or "").strip())
    except ValueError:
        return False
    return any(ip in network for network in _load_scaletail_networks())


def _sample_window(total: int, first_seen: datetime | None, last_seen: datetime | None, hours: int, interval_seconds: int) -> dict:
    if total <= 0:
        expected = max(1, math.ceil(hours * 3600 / interval_seconds))
    else:
        now = datetime.now(first_seen.tzinfo) if first_seen and first_seen.tzinfo else datetime.now()
        if first_seen:
            seconds = max(interval_seconds, min(hours * 3600, (now - first_seen).total_seconds()))
        else:
            seconds = hours * 3600
        expected = max(total, math.ceil(seconds / interval_seconds))
    failed = max(0, expected - total)
    return {
        'samples': total,
        'expected': expected,
        'normal': total,
        'failed': failed,
        'normal_percent': round((total / expected) * 100, 1) if expected else 0,
        'samples_per_hour': round(total / hours, 1),
        'first_seen': first_seen.strftime('%Y-%m-%d %H:%M:%S') if first_seen else '',
        'last_seen': last_seen.strftime('%Y-%m-%d %H:%M:%S') if last_seen else '',
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

    conn.commit()
    _last_maintenance_at = now
    return {
        'skipped': False,
        'hourly_rows': hourly_rows,
        'daily_rows': daily_rows,
        'deleted_samples': deleted_samples,
        'deleted_hourly': deleted_hourly,
    }


@router.get('/summary')
def traffic_summary(user: CurrentUser = Depends(get_current_user)):
    """获取流量总览"""
    conn = get_db_conn()
    try:
        _run_traffic_maintenance(conn)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes,
                COALESCE(MAX(rx_rate_bps), 0) AS peak_rx_rate_bps,
                COALESCE(MAX(tx_rate_bps), 0) AS peak_tx_rate_bps,
                COUNT(DISTINCT COALESCE(machine_id::text, machine_name)) AS machines
            FROM traffic_samples
            WHERE observed_at >= NOW() - INTERVAL '24 hours'
        """)
        day = cur.fetchone()

        cur.execute("""
            SELECT
                COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes
            FROM traffic_samples
            WHERE observed_at >= NOW() - INTERVAL '30 days'
        """)
        month = cur.fetchone()

        cur.execute("SELECT COUNT(*) AS open_events FROM security_events WHERE status = 'open'")
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
        cur.execute("""
            SELECT
                machine_id,
                COALESCE(machine_name, CONCAT('机器#', machine_id)) AS machine_name,
                group_name,
                COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes,
                COALESCE(MAX(rx_rate_bps), 0) AS peak_rx_rate_bps,
                COALESCE(MAX(tx_rate_bps), 0) AS peak_tx_rate_bps
            FROM traffic_samples
            WHERE observed_at >= NOW() - (%s || ' days')::interval
            GROUP BY machine_id, machine_name, group_name
            ORDER BY (COALESCE(SUM(rx_bytes_delta), 0) + COALESCE(SUM(tx_bytes_delta), 0)) DESC
            LIMIT 20
        """, (days,))
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
        cur.execute("""
            SELECT
                group_id,
                COALESCE(group_name, CONCAT('分组#', group_id)) AS group_name,
                COALESCE(SUM(rx_bytes_delta), 0) AS rx_bytes,
                COALESCE(SUM(tx_bytes_delta), 0) AS tx_bytes,
                COUNT(DISTINCT COALESCE(machine_id::text, machine_name)) AS machines
            FROM traffic_samples
            WHERE observed_at >= NOW() - (%s || ' days')::interval
            GROUP BY group_id, group_name
            ORDER BY (COALESCE(SUM(rx_bytes_delta), 0) + COALESCE(SUM(tx_bytes_delta), 0)) DESC
            LIMIT 20
        """, (days,))
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
        where.append("machine_id = %s")
        params.append(machine_id)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM traffic_samples {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                id, machine_id, machine_name, group_name,
                rx_bytes_delta, tx_bytes_delta, rx_rate_bps, tx_rate_bps,
                derp, endpoint_type,
                TO_CHAR(observed_at, 'YYYY-MM-DD HH24:MI:SS') AS observed_at
            FROM traffic_samples
            {where_sql}
            ORDER BY observed_at DESC
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
    """按机器聚合最近 24/12 小时采样频率。失败数为按客户端上报间隔估算的缺失采样数。"""
    interval_seconds = max(5, min(interval_seconds, 3600))
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                machine_id,
                COALESCE(machine_name, CONCAT('机器#', machine_id)) AS machine_name,
                group_name,
                COUNT(*) FILTER (WHERE observed_at >= NOW() - INTERVAL '24 hours') AS samples_24h,
                MIN(observed_at) FILTER (WHERE observed_at >= NOW() - INTERVAL '24 hours') AS first_24h,
                MAX(observed_at) FILTER (WHERE observed_at >= NOW() - INTERVAL '24 hours') AS last_24h,
                COUNT(*) FILTER (WHERE observed_at >= NOW() - INTERVAL '12 hours') AS samples_12h,
                MIN(observed_at) FILTER (WHERE observed_at >= NOW() - INTERVAL '12 hours') AS first_12h,
                MAX(observed_at) FILTER (WHERE observed_at >= NOW() - INTERVAL '12 hours') AS last_12h,
                MAX(observed_at) AS last_seen
            FROM traffic_samples
            WHERE observed_at >= NOW() - INTERVAL '24 hours'
            GROUP BY machine_id, machine_name, group_name
            ORDER BY COUNT(*) FILTER (WHERE observed_at >= NOW() - INTERVAL '24 hours') DESC,
                     MAX(observed_at) DESC
            LIMIT 50
        """)
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
                        int(row.get('samples_24h') or 0),
                        row.get('first_24h'),
                        row.get('last_24h'),
                        24,
                        interval_seconds,
                    ),
                    'h12': _sample_window(
                        int(row.get('samples_12h') or 0),
                        row.get('first_12h'),
                        row.get('last_12h'),
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
        cur.execute("""
            SELECT
                dst_ip,
                dst_port,
                protocol,
                process_name,
                COALESCE(SUM(bytes), 0) AS bytes,
                COALESCE(SUM(packets), 0) AS packets,
                COALESCE(SUM(connection_count), 0) AS connection_count,
                COUNT(DISTINCT COALESCE(machine_id::text, machine_name)) AS machines,
                TO_CHAR(MAX(window_start), 'YYYY-MM-DD HH24:MI:SS') AS last_seen
            FROM flow_summaries
            WHERE window_start >= NOW() - (%s || ' days')::interval
              AND dst_ip IS NOT NULL
              AND dst_ip <> ''
            GROUP BY dst_ip, dst_port, protocol, process_name
            ORDER BY COALESCE(SUM(connection_count), 0) DESC, COALESCE(SUM(packets), 0) DESC
        """, (days,))
        rows = [row for row in cur.fetchall() if _is_scaletail_destination(row.get('dst_ip'))]
        return {'code': 0, 'data': rows[:20]}
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
        where.append("machine_id = %s")
        params.append(machine_id)
    if dst_ip:
        where.append("dst_ip = %s")
        params.append(dst_ip)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * size

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) AS count FROM flow_summaries {where_sql}", params)
        total = cur.fetchone()['count']
        cur.execute(f"""
            SELECT
                id, machine_id, machine_name, group_name,
                dst_ip, dst_port, protocol, direction, bytes, packets,
                connection_count, state, process_id, process_name,
                TO_CHAR(window_start, 'YYYY-MM-DD HH24:MI:SS') AS window_start,
                window_seconds
            FROM flow_summaries
            {where_sql}
            ORDER BY window_start DESC, id DESC
            LIMIT %s OFFSET %s
        """, [*params, size, offset])
        return {'code': 0, 'data': cur.fetchall(), 'total': total, 'page': page, 'size': size}
    finally:
        conn.close()
