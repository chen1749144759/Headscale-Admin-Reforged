"""
ScaleTail 客户端上报接口。

该接口给客户端后台任务使用，不走管理后台 JWT，而是使用共享密钥：
- 环境变量 SCALETAIL_CLIENT_TOKEN
- 或 config.yaml: client_report_token
"""
import hmac
import ipaddress
import json
import os
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote
from urllib.request import urlopen

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .dependencies import CFG, get_db_conn

router = APIRouter(prefix="/api/client-reports", tags=["client-reports"])


class FlowSummary(BaseModel):
    window_start: Optional[str] = None
    window_seconds: int = 60
    dst_ip: str = ""
    dst_port: Optional[int] = None
    protocol: str = ""
    direction: str = ""
    bytes: int = 0
    packets: int = 0
    connection_count: int = 0
    state: str = ""
    process_id: Optional[int] = None
    process_name: str = ""


class TrafficReport(BaseModel):
    machine_id: Optional[int] = None
    machine_name: str = ""
    group_id: Optional[int] = None
    group_name: str = ""
    scaletail_ips: list[str] = Field(default_factory=list)
    rx_bytes_total: int = 0
    tx_bytes_total: int = 0
    derp: bool = False
    endpoint_type: str = ""
    public_ip: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    asn: str = ""
    isp: str = ""
    flows: list[FlowSummary] = Field(default_factory=list)


class PolicyStateReport(BaseModel):
    policy_id: Optional[int] = None
    machine_id: Optional[int] = None
    machine_name: str = ""
    applied: bool = False
    effective_policy: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


def _configured_token() -> str:
    return os.environ.get("SCALETAIL_CLIENT_TOKEN") or str(CFG.get("client_report_token") or "")


def _version_parts(value: str) -> list[int]:
    parts = []
    for item in re.findall(r"\d+", str(value or "")):
        try:
            parts.append(int(item))
        except Exception:
            continue
    return parts


def _version_gt(remote: str, current: str) -> bool:
    remote = str(remote or "").strip()
    current = str(current or "").strip()
    if not remote:
        return False
    remote_parts = _version_parts(remote)
    current_parts = _version_parts(current)
    if remote_parts or current_parts:
        size = max(len(remote_parts), len(current_parts), 3)
        return (remote_parts + [0] * (size - len(remote_parts))) > (current_parts + [0] * (size - len(current_parts)))
    return remote != current


def _same_version(left: str, right: str) -> bool:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts or right_parts:
        size = max(len(left_parts), len(right_parts), 3)
        return (left_parts + [0] * (size - len(left_parts))) == (right_parts + [0] * (size - len(right_parts)))
    return str(left or "").strip() == str(right or "").strip()


def _platform_aliases(platform: str) -> list[str]:
    clean = str(platform or "windows-amd64").strip().lower()
    aliases = [clean, "all"]
    if clean.startswith("windows") or clean == "win32":
        aliases.extend(["windows", "win32"])
    elif clean.startswith("linux"):
        aliases.append("linux")
    elif clean.startswith("macos") or clean.startswith("darwin"):
        aliases.extend(["macos", "darwin"])
    return list(dict.fromkeys(item for item in aliases if item))


def _release_payload(row: dict[str, Any]) -> dict[str, Any]:
    update_type = str(row.get("update_type") or "suggested").lower()
    return {
        "has_update": True,
        "id": row.get("id"),
        "version": row.get("version") or "",
        "platform": row.get("platform") or "",
        "update_type": update_type,
        "forced": update_type == "forced",
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "download_url": row.get("download_url") or "",
        "release_notes": row.get("release_notes") or "",
        "created_at": row.get("created_at") or "",
    }


def require_client_token(request: Request) -> None:
    expected = _configured_token()
    if not expected:
        raise HTTPException(503, "客户端上报密钥未配置，请设置 SCALETAIL_CLIENT_TOKEN 或 config.yaml: client_report_token")
    actual = request.headers.get("X-ScaleTail-Token") or request.query_params.get("token") or ""
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "客户端上报密钥无效")


def _identity_clause(report: TrafficReport):
    clauses = []
    params: list[Any] = []
    if report.machine_id:
        clauses.append("machine_id = %s")
        params.append(report.machine_id)
    if report.machine_name:
        clauses.append("machine_name = %s")
        params.append(report.machine_name)
    if not clauses:
        return "machine_name = %s", ["unknown"]
    return "(" + " OR ".join(clauses) + ")", params


def _policy_state_identity_clause(report: PolicyStateReport):
    clauses = []
    params: list[Any] = []
    if report.machine_id:
        clauses.append("machine_id = %s")
        params.append(report.machine_id)
    if report.machine_name:
        clauses.append("machine_name = %s")
        params.append(report.machine_name)
    if not clauses:
        return "machine_name = %s", ["unknown"]
    return "(" + " OR ".join(clauses) + ")", params


def _resolve_traffic_identity(conn, report: TrafficReport) -> None:
    if report.machine_id or not report.machine_name:
        return
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT n.id, n.given_name, n.hostname, n.user_id, u.name AS group_name
        FROM nodes n
        LEFT JOIN users u ON n.user_id = u.id
        WHERE n.given_name = %s OR n.hostname = %s
        ORDER BY n.id DESC
        LIMIT 1
        """,
        (report.machine_name, report.machine_name),
    )
    row = cur.fetchone()
    if not row:
        return
    report.machine_id = row["id"]
    report.machine_name = row["given_name"] or row["hostname"] or report.machine_name
    report.group_id = report.group_id or row["user_id"]
    report.group_name = report.group_name or row["group_name"] or ""


def _resolve_policy_state_identity(conn, report: PolicyStateReport) -> None:
    if report.machine_id or not report.machine_name:
        return
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, given_name, hostname
        FROM nodes
        WHERE given_name = %s OR hostname = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (report.machine_name, report.machine_name),
    )
    row = cur.fetchone()
    if row:
        report.machine_id = row["id"]
        report.machine_name = row["given_name"] or row["hostname"] or report.machine_name


def _resolve_policy_query_identity(conn, machine_id: Optional[int], machine_name: str, group_id: Optional[int], group_name: str):
    if machine_id or not machine_name:
        return machine_id, machine_name, group_id, group_name
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT n.id, n.given_name, n.hostname, n.user_id, u.name AS group_name
        FROM nodes n
        LEFT JOIN users u ON n.user_id = u.id
        WHERE n.given_name = %s OR n.hostname = %s
        ORDER BY n.id DESC
        LIMIT 1
        """,
        (machine_name, machine_name),
    )
    row = cur.fetchone()
    if not row:
        return machine_id, machine_name, group_id, group_name
    return (
        row["id"],
        row["given_name"] or row["hostname"] or machine_name,
        group_id or row["user_id"],
        group_name or row["group_name"] or "",
    )


def _positive_delta(current: int, previous: Any) -> int:
    prev = int(previous or 0)
    value = int(current or 0)
    if value < prev:
        return 0
    return value - prev


def _rate_bps(delta_bytes: int, seconds: float) -> float:
    if seconds <= 0:
        return 0
    return float(delta_bytes * 8) / seconds


def _insert_or_update_ip_observation(conn, report: TrafficReport) -> None:
    if not report.public_ip:
        return
    _enrich_ip_geo(report)
    risk_flags = _trusted_risk_flags(conn, report)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where, params = _identity_clause(report)
    cur.execute(
        f"SELECT id FROM node_ip_observations WHERE ip=%s AND {where} ORDER BY id DESC LIMIT 1",
        [report.public_ip, *params],
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE node_ip_observations
            SET country=%s, region=%s, city=%s, asn=%s, isp=%s,
                risk_flags=%s, last_seen=NOW(), seen_count=seen_count + 1
            WHERE id=%s
            """,
            (
                report.country,
                report.region,
                report.city,
                report.asn,
                report.isp,
                psycopg2.extras.Json(risk_flags),
                row["id"],
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO node_ip_observations (
                machine_id, machine_name, group_id, group_name, ip,
                country, region, city, asn, isp, risk_flags,
                first_seen, last_seen, seen_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), 1)
            """,
            (
                report.machine_id,
                report.machine_name or "unknown",
                report.group_id,
                report.group_name,
                report.public_ip,
                report.country,
                report.region,
                report.city,
                report.asn,
                report.isp,
                psycopg2.extras.Json(risk_flags),
            ),
        )
    _maybe_create_ip_churn_event(conn, report)


def _trusted_risk_flags(conn, report: TrafficReport) -> dict[str, Any]:
    matched = _matched_trusted_networks(conn, report)
    return {
        "trusted": bool(matched),
        "matched_trusted": matched,
    }


def _matched_trusted_networks(conn, report: TrafficReport) -> list[dict[str, str]]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT kind, value FROM trusted_networks WHERE enabled = TRUE")
    rows = cur.fetchall()
    if not rows:
        return []

    matched: list[dict[str, str]] = []
    public_ip = None
    try:
        public_ip = ipaddress.ip_address(report.public_ip)
    except ValueError:
        public_ip = None

    for row in rows:
        kind = str(row.get("kind") or "").strip().lower()
        value = str(row.get("value") or "").strip()
        if not kind or not value:
            continue
        if kind == "ip" and public_ip and report.public_ip == value:
            matched.append({"kind": kind, "value": value})
        elif kind == "cidr" and public_ip and _ip_in_cidr(public_ip, value):
            matched.append({"kind": kind, "value": value})
        elif kind == "asn" and _normalize_asn(report.asn) == _normalize_asn(value):
            matched.append({"kind": kind, "value": value})
        elif kind == "country" and report.country.strip().lower() == value.lower():
            matched.append({"kind": kind, "value": value})
    return matched


def _ip_in_cidr(public_ip: Any, cidr: str) -> bool:
    try:
        return public_ip in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False


def _normalize_asn(value: str) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("as"):
        text = text[2:]
    return text.split()[0] if text else ""


def _enrich_ip_geo(report: TrafficReport) -> None:
    if report.country or report.city or report.asn:
        return
    template = os.environ.get("IP_GEOLOOKUP_URL") or str(CFG.get("ip_geolookup_url") or "")
    if not template:
        return
    url = template.replace("{ip}", quote(report.public_ip))
    if "{ip}" not in template:
        url = template.rstrip("/") + "/" + quote(report.public_ip)
    try:
        with urlopen(url, timeout=3) as resp:
            raw = resp.read(64 * 1024)
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return

    connection = data.get("connection") if isinstance(data.get("connection"), dict) else {}
    report.country = report.country or str(data.get("country") or data.get("country_name") or "")
    report.region = report.region or str(data.get("region") or data.get("regionName") or "")
    report.city = report.city or str(data.get("city") or "")
    report.asn = report.asn or str(data.get("asn") or connection.get("asn") or data.get("org") or data.get("as") or "")
    report.isp = report.isp or str(data.get("isp") or connection.get("isp") or data.get("org") or "")


def _maybe_create_ip_churn_event(conn, report: TrafficReport) -> None:
    threshold = _safe_int(os.environ.get("SCALETAIL_IP_CHURN_24H", CFG.get("ip_churn_threshold_24h", 5)), 5)
    where, params = _identity_clause(report)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT ip) AS count
        FROM node_ip_observations
        WHERE {where}
          AND last_seen >= NOW() - INTERVAL '24 hours'
          AND COALESCE((risk_flags->>'trusted')::boolean, FALSE) = FALSE
        """,
        params,
    )
    count = int((cur.fetchone() or {}).get("count") or 0)
    if count < threshold:
        return

    cur.execute(
        f"""
        SELECT id
        FROM security_events
        WHERE event_type='ip_churn'
          AND status='open'
          AND {where}
          AND created_at >= NOW() - INTERVAL '24 hours'
        LIMIT 1
        """,
        params,
    )
    if cur.fetchone():
        return

    cur.execute(
        """
        INSERT INTO security_events (
            level, event_type, title, description, group_id, group_name,
            machine_id, machine_name, ip, country, city, asn, evidence, status, created_at
        ) VALUES (%s, 'ip_churn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', NOW())
        """,
        (
            "medium",
            "机器公网 IP 频繁变化",
            f"过去 24 小时观测到 {count} 个不同公网 IP，建议确认是否为正常办公网络切换。",
            report.group_id,
            report.group_name,
            report.machine_id,
            report.machine_name or "unknown",
            report.public_ip,
            report.country,
            report.city,
            report.asn,
            psycopg2.extras.Json({"ip_count_24h": count, "threshold": threshold}),
        ),
    )


def _maybe_create_quota_event(
    conn,
    machine_id: Optional[int],
    machine_name: str,
    group_id: Optional[int],
    group_name: str,
    month_bytes: int,
    quota_gb: float,
) -> None:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = "machine_id = %s" if machine_id else "machine_name = %s"
    value = machine_id if machine_id else (machine_name or "unknown")
    cur.execute(
        f"""
        SELECT id
        FROM security_events
        WHERE event_type='quota_exceeded'
          AND status='open'
          AND {where}
          AND created_at >= date_trunc('month', NOW())
        LIMIT 1
        """,
        (value,),
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO security_events (
            level, event_type, title, description, group_id, group_name,
            machine_id, machine_name, evidence, status, created_at
        ) VALUES (%s, 'quota_exceeded', %s, %s, %s, %s, %s, %s, %s, 'open', NOW())
        """,
        (
            "high",
            "机器月流量配额已超限",
            f"本月已用 {month_bytes} 字节，超过配置配额 {quota_gb} GB。",
            group_id,
            group_name,
            machine_id,
            machine_name or "unknown",
            psycopg2.extras.Json({"month_bytes": month_bytes, "quota_gb": quota_gb}),
        ),
    )


def _insert_flows(conn, report: TrafficReport) -> int:
    if not report.flows:
        return 0
    cur = conn.cursor()
    count = 0
    for flow in report.flows[:500]:
        cur.execute(
            """
            INSERT INTO flow_summaries (
                machine_id, machine_name, group_id, group_name,
                window_start, window_seconds,
                dst_ip, dst_port, protocol, direction, bytes, packets,
                connection_count, state, process_id, process_name
            ) VALUES (%s, %s, %s, %s, COALESCE(%s::timestamp, NOW()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                report.machine_id,
                report.machine_name or "unknown",
                report.group_id,
                report.group_name,
                flow.window_start,
                flow.window_seconds,
                flow.dst_ip,
                flow.dst_port,
                flow.protocol,
                flow.direction,
                flow.bytes,
                flow.packets,
                flow.connection_count or flow.packets or 1,
                flow.state,
                flow.process_id,
                flow.process_name,
            ),
        )
        count += 1
    _maybe_create_flow_risk_events(conn, report)
    return count


def _maybe_create_flow_risk_events(conn, report: TrafficReport) -> None:
    if not report.machine_id and not report.machine_name:
        return
    _maybe_create_sensitive_port_event(conn, report)
    _maybe_create_destination_churn_event(conn, report)


def _maybe_create_sensitive_port_event(conn, report: TrafficReport) -> None:
    ports = _risk_rule_list(conn, "sensitive_ports", [22, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 6379, 9200, 11211])
    if not ports:
        return
    hits = [
        flow for flow in report.flows
        if flow.dst_port in ports and flow.dst_ip and not _is_private_or_loopback(flow.dst_ip)
    ]
    if not hits:
        return
    first = hits[0]
    _insert_dedup_security_event(
        conn,
        report,
        "sensitive_port",
        "medium",
        "访问敏感公网端口",
        f"客户端连接到公网敏感端口 {first.dst_ip}:{first.dst_port}，建议确认是否为正常业务访问。",
        first.dst_ip,
        {"ports": ports, "hits": [_model_dump(flow) for flow in hits[:20]]},
        "24 hours",
    )


def _maybe_create_destination_churn_event(conn, report: TrafficReport) -> None:
    config = _risk_rule_config(conn, "destination_churn", {"threshold": 80, "window_hours": 1})
    if config is None:
        return
    threshold = _safe_int(config.get("threshold"), 80)
    window_hours = _safe_int(config.get("window_hours"), 1, maximum=168)
    where, params = _flow_identity_clause(report)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT dst_ip) AS count
        FROM flow_summaries
        WHERE {where}
          AND window_start >= NOW() - (%s || ' hours')::interval
          AND dst_ip IS NOT NULL
          AND dst_ip <> ''
        """,
        [*params, window_hours],
    )
    count = int((cur.fetchone() or {}).get("count") or 0)
    if count < threshold:
        return
    _insert_dedup_security_event(
        conn,
        report,
        "destination_churn",
        "high",
        "短时间访问大量目标地址",
        f"过去 {window_hours} 小时访问 {count} 个不同目标 IP，超过阈值 {threshold}，可能是扫描、代理滥用或异常程序行为。",
        "",
        {"destination_count": count, "threshold": threshold, "window_hours": window_hours},
        "6 hours",
    )


def _risk_rule_config(conn, rule_key: str, default: dict[str, Any]) -> dict[str, Any] | None:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT enabled, config FROM risk_rules WHERE rule_key=%s", (rule_key,))
    row = cur.fetchone()
    if row and not row.get("enabled"):
        return None
    if not row or not row.get("config"):
        return default
    data = row["config"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    return {**default, **(data or {})}


def _risk_rule_list(conn, rule_key: str, default: list[int]) -> list[int]:
    config = _risk_rule_config(conn, rule_key, {"ports": default})
    if config is None:
        return []
    values = config.get("ports") or []
    if isinstance(values, str):
        values = values.replace("，", ",").split(",")
    result = []
    for value in values:
        try:
            port = int(value)
            if 0 < port <= 65535:
                result.append(port)
        except Exception:
            continue
    return result


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _safe_int(value: Any, default: int, minimum: int = 1, maximum: Optional[int] = None) -> int:
    try:
        number = int(value)
    except Exception:
        return default
    if number < minimum:
        return default
    if maximum is not None and number > maximum:
        return maximum
    return number


def _flow_identity_clause(report: TrafficReport):
    clauses = []
    params: list[Any] = []
    if report.machine_id:
        clauses.append("machine_id = %s")
        params.append(report.machine_id)
    if report.machine_name:
        clauses.append("machine_name = %s")
        params.append(report.machine_name)
    if not clauses:
        return "machine_name = %s", ["unknown"]
    return "(" + " OR ".join(clauses) + ")", params


def _insert_dedup_security_event(
    conn,
    report: TrafficReport,
    event_type: str,
    level: str,
    title: str,
    description: str,
    ip: str,
    evidence: dict[str, Any],
    dedup_window: str,
) -> None:
    where, params = _identity_clause(report)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"""
        SELECT id
        FROM security_events
        WHERE event_type=%s
          AND status='open'
          AND {where}
          AND created_at >= NOW() - %s::interval
        LIMIT 1
        """,
        [event_type, *params, dedup_window],
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO security_events (
            level, event_type, title, description, group_id, group_name,
            machine_id, machine_name, ip, evidence, status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', NOW())
        """,
        (
            level,
            event_type,
            title,
            description,
            report.group_id,
            report.group_name,
            report.machine_id,
            report.machine_name or "unknown",
            ip,
            psycopg2.extras.Json(evidence),
        ),
    )


def _is_private_or_loopback(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
        return parsed.is_private or parsed.is_loopback or parsed.is_link_local
    except ValueError:
        return False


@router.get("/client-update")
def client_update(
    current_version: str = "",
    platform: str = "windows-amd64",
    _: None = Depends(require_client_token),
):
    platform_aliases = _platform_aliases(platform)
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                id, version, platform, update_type, title, description,
                download_url, release_notes,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM client_releases
            WHERE enabled = TRUE
              AND LOWER(platform) = ANY(%s::text[])
            ORDER BY created_at DESC, id DESC
            """,
            (platform_aliases,),
        )
        best: Optional[dict[str, Any]] = None
        for row in cur.fetchall():
            if not _version_gt(str(row.get("version") or ""), current_version):
                continue
            if best is None:
                best = row
                continue
            row_version = str(row.get("version") or "")
            best_version = str(best.get("version") or "")
            if _version_gt(row_version, best_version):
                best = row
                continue
            if _same_version(row_version, best_version) and row.get("update_type") == "forced":
                best = row
        if not best:
            return {"code": 0, "data": {"has_update": False}}
        return {"code": 0, "data": _release_payload(best)}
    finally:
        conn.close()


@router.post("/traffic")
def report_traffic(report: TrafficReport, _: None = Depends(require_client_token)):
    conn = get_db_conn()
    try:
        _resolve_traffic_identity(conn, report)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where, params = _identity_clause(report)
        cur.execute(
            f"""
            SELECT rx_bytes_total, tx_bytes_total, observed_at
            FROM traffic_samples
            WHERE {where}
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            params,
        )
        last = cur.fetchone()
        rx_delta = _positive_delta(report.rx_bytes_total, last["rx_bytes_total"] if last else 0)
        tx_delta = _positive_delta(report.tx_bytes_total, last["tx_bytes_total"] if last else 0)
        seconds = 60.0
        if last and last.get("observed_at"):
            observed_at = last["observed_at"]
            now = datetime.now(observed_at.tzinfo) if getattr(observed_at, "tzinfo", None) else datetime.now()
            seconds = max(1.0, (now - observed_at).total_seconds())
        cur.execute(
            """
            INSERT INTO traffic_samples (
                machine_id, machine_name, group_id, group_name,
                rx_bytes_total, tx_bytes_total, rx_bytes_delta, tx_bytes_delta,
                rx_rate_bps, tx_rate_bps, derp, endpoint_type, observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (
                report.machine_id,
                report.machine_name or "unknown",
                report.group_id,
                report.group_name,
                report.rx_bytes_total,
                report.tx_bytes_total,
                rx_delta,
                tx_delta,
                _rate_bps(rx_delta, seconds),
                _rate_bps(tx_delta, seconds),
                report.derp,
                report.endpoint_type,
            ),
        )
        row = cur.fetchone()
        _insert_or_update_ip_observation(conn, report)
        flow_count = _insert_flows(conn, report)
        conn.commit()
        return {"code": 0, "data": {"sample_id": row["id"], "flow_count": flow_count}}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/policy")
def effective_policy(
    machine_id: Optional[int] = None,
    machine_name: str = "",
    group_id: Optional[int] = None,
    group_name: str = "",
    _: None = Depends(require_client_token),
):
    conn = get_db_conn()
    try:
        machine_id, machine_name, group_id, group_name = _resolve_policy_query_identity(
            conn,
            machine_id,
            machine_name,
            group_id,
            group_name,
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT *
            FROM client_policies
            WHERE enabled = TRUE
              AND (
                scope = 'global'
                OR (scope = 'group' AND ((group_id IS NOT NULL AND group_id = %s) OR (group_name <> '' AND group_name = %s)))
                OR (scope = 'machine' AND ((machine_id IS NOT NULL AND machine_id = %s) OR (machine_name <> '' AND machine_name = %s)))
              )
            ORDER BY
              CASE scope WHEN 'machine' THEN 1 WHEN 'group' THEN 2 ELSE 3 END,
              priority ASC,
              id DESC
            """,
            (group_id, group_name, machine_id, machine_name),
        )
        policies = cur.fetchall()

        def min_positive(field: str):
            values = [float(p[field]) for p in policies if p.get(field) and float(p[field]) > 0]
            return min(values) if values else None

        action_rank = {"alert": 1, "throttle": 2, "block": 3}
        action = "alert"
        for policy in policies:
            candidate = policy.get("exceed_action") or "alert"
            if action_rank.get(candidate, 0) > action_rank.get(action, 0):
                action = candidate
        quota_gb = min_positive("monthly_quota_gb")
        month_bytes = 0
        if machine_id:
            cur.execute(
                """
                SELECT COALESCE(SUM(rx_bytes_delta + tx_bytes_delta), 0) AS bytes
                FROM traffic_samples
                WHERE machine_id=%s
                  AND observed_at >= date_trunc('month', NOW())
                """,
                (machine_id,),
            )
            month_bytes = int((cur.fetchone() or {}).get("bytes") or 0)
        elif machine_name:
            cur.execute(
                """
                SELECT COALESCE(SUM(rx_bytes_delta + tx_bytes_delta), 0) AS bytes
                FROM traffic_samples
                WHERE machine_name=%s
                  AND observed_at >= date_trunc('month', NOW())
                """,
                (machine_name,),
            )
            month_bytes = int((cur.fetchone() or {}).get("bytes") or 0)
        quota_exceeded = bool(quota_gb and month_bytes > quota_gb * 1024 * 1024 * 1024)
        if quota_exceeded:
            _maybe_create_quota_event(conn, machine_id, machine_name, group_id, group_name, month_bytes, quota_gb)
            conn.commit()

        return {
            "code": 0,
            "data": {
                "effective": {
                    "rate_up_mbps": min_positive("rate_up_mbps"),
                    "rate_down_mbps": min_positive("rate_down_mbps"),
                    "monthly_quota_gb": quota_gb,
                    "month_bytes": month_bytes,
                    "quota_exceeded": quota_exceeded,
                    "exceed_action": action,
                },
                "matched_policies": policies,
            },
        }
    finally:
        conn.close()


@router.post("/policy-state")
def report_policy_state(report: PolicyStateReport, _: None = Depends(require_client_token)):
    conn = get_db_conn()
    try:
        _resolve_policy_state_identity(conn, report)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where, params = _policy_state_identity_clause(report)
        cur.execute(
            f"""
            SELECT id
            FROM client_policy_states
            WHERE {where}
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        payload = psycopg2.extras.Json(report.effective_policy or {})
        if row:
            cur.execute(
                """
                UPDATE client_policy_states
                SET policy_id=%s, machine_id=%s, machine_name=%s, applied=%s,
                    effective_policy=%s, error=%s,
                    applied_at=CASE WHEN %s THEN NOW() ELSE applied_at END,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (
                    report.policy_id,
                    report.machine_id,
                    report.machine_name or "unknown",
                    report.applied,
                    payload,
                    report.error,
                    report.applied,
                    row["id"],
                ),
            )
            state_id = row["id"]
        else:
            cur.execute(
                """
                INSERT INTO client_policy_states (
                    policy_id, machine_id, machine_name, applied,
                    effective_policy, error, applied_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END, NOW())
                RETURNING id
                """,
                (
                    report.policy_id,
                    report.machine_id,
                    report.machine_name or "unknown",
                    report.applied,
                    payload,
                    report.error,
                    report.applied,
                ),
            )
            state_id = cur.fetchone()["id"]
        conn.commit()
        return {"code": 0, "data": {"id": state_id}}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
