"""仅供 Headscale 经私有 UDS 转发的 ScaleTail 客户端接口。"""
import hashlib
import ipaddress
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional
from urllib.parse import quote

import httpx
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .dependencies import CFG, get_db_conn, trusted_service_url
from .ota import MAX_POLICY_REVISION, release_signature_valid
from .versioning import compare_versions, parse_semver

router = APIRouter(prefix="/internal/v1/client", tags=["internal-client"])


MAX_DATABASE_INTEGER = 2**63 - 1
MAX_PROCESS_ID = 2**32 - 1
MAX_FLOW_SUMMARIES = 500
MAX_SCALETAIL_IPS = 16
MAX_MATCHED_POLICY_IDS = 128
MAX_EFFECTIVE_POLICY_BYTES = 32 * 1024
MAX_EFFECTIVE_POLICY_ITEMS = 128
MAX_EFFECTIVE_POLICY_DEPTH = 8

NonNegativeInteger = Annotated[
    int,
    Field(strict=True, ge=0, le=MAX_DATABASE_INTEGER),
]
PositiveIdentifier = Annotated[
    int,
    Field(strict=True, ge=1, le=MAX_DATABASE_INTEGER),
]
ProcessIdentifier = Annotated[
    int,
    Field(strict=True, ge=0, le=MAX_PROCESS_ID),
]
NetworkPort = Annotated[int, Field(strict=True, ge=1, le=65535)]
WindowSeconds = Annotated[int, Field(strict=True, ge=1, le=86400)]
IPAddressText = Annotated[str, Field(strict=True, min_length=1, max_length=45)]


def _normalized_ip(value: str, *, allow_empty: bool = False) -> str:
    if allow_empty and not value:
        return ""
    if "%" in value:
        raise ValueError("IP 地址不能包含作用域标识")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise ValueError("IP 地址格式无效") from exc


def _validate_plain_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("文本不能包含 NUL 字符")
    return value


def _validate_policy_value(value: Any, depth: int = 0) -> None:
    if depth > MAX_EFFECTIVE_POLICY_DEPTH:
        raise ValueError("生效策略嵌套层级过深")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > MAX_DATABASE_INTEGER:
            raise ValueError("生效策略整数超出允许范围")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > MAX_DATABASE_INTEGER:
            raise ValueError("生效策略数值无效")
        return
    if isinstance(value, str):
        if len(value) > 2048 or "\x00" in value:
            raise ValueError("生效策略文本超出允许范围")
        return
    if isinstance(value, list):
        if len(value) > MAX_EFFECTIVE_POLICY_ITEMS:
            raise ValueError("生效策略列表过长")
        for item in value:
            _validate_policy_value(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_EFFECTIVE_POLICY_ITEMS:
            raise ValueError("生效策略字段过多")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 128 or "\x00" in key:
                raise ValueError("生效策略字段名无效")
            _validate_policy_value(item, depth + 1)
        return
    raise ValueError("生效策略包含不支持的数据类型")


class ClientReportModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class FlowSummary(ClientReportModel):
    window_start: Optional[str] = Field(default=None, strict=True, min_length=1, max_length=64)
    window_seconds: WindowSeconds = 60
    dst_ip: IPAddressText
    dst_port: Optional[NetworkPort] = None
    protocol: str = Field(default="", strict=True, max_length=16)
    direction: str = Field(default="", strict=True, max_length=16)
    bytes: NonNegativeInteger = 0
    packets: NonNegativeInteger = 0
    connection_count: NonNegativeInteger = 0
    state: str = Field(default="", strict=True, max_length=64)
    process_id: Optional[ProcessIdentifier] = None
    process_name: str = Field(default="", strict=True, max_length=260)

    @field_validator("window_start")
    @classmethod
    def validate_window_start(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("采样窗口开始时间格式无效") from exc
        return value

    @field_validator("dst_ip")
    @classmethod
    def validate_dst_ip(cls, value: str) -> str:
        return _normalized_ip(value)

    @field_validator("protocol", "direction", "state", "process_name")
    @classmethod
    def validate_flow_text(cls, value: str) -> str:
        return _validate_plain_text(value)


class TrafficReport(ClientReportModel):
    machine_id: Optional[PositiveIdentifier] = None
    machine_name: str = Field(default="", strict=True, max_length=255)
    group_id: Optional[PositiveIdentifier] = None
    group_name: str = Field(default="", strict=True, max_length=255)
    scaletail_ips: list[IPAddressText] = Field(default_factory=list, max_length=MAX_SCALETAIL_IPS)
    rx_bytes_total: NonNegativeInteger = 0
    tx_bytes_total: NonNegativeInteger = 0
    derp: bool = False
    endpoint_type: str = Field(default="", strict=True, max_length=32)
    public_ip: str = Field(default="", strict=True, max_length=45)
    country: str = Field(default="", strict=True, max_length=128)
    region: str = Field(default="", strict=True, max_length=128)
    city: str = Field(default="", strict=True, max_length=128)
    asn: str = Field(default="", strict=True, max_length=128)
    isp: str = Field(default="", strict=True, max_length=255)
    flows: list[FlowSummary] = Field(default_factory=list, max_length=MAX_FLOW_SUMMARIES)

    @field_validator("scaletail_ips")
    @classmethod
    def validate_scaletail_ips(cls, values: list[str]) -> list[str]:
        return [_normalized_ip(value) for value in values]

    @field_validator("public_ip")
    @classmethod
    def validate_public_ip(cls, value: str) -> str:
        return _normalized_ip(value, allow_empty=True)

    @field_validator(
        "machine_name",
        "group_name",
        "endpoint_type",
        "country",
        "region",
        "city",
        "asn",
        "isp",
    )
    @classmethod
    def validate_traffic_text(cls, value: str) -> str:
        return _validate_plain_text(value)


class PolicyStateReport(ClientReportModel):
    machine_id: Optional[PositiveIdentifier] = None
    machine_name: str = Field(default="", strict=True, max_length=255)
    policy_revision: str = Field(
        default="",
        strict=True,
        max_length=64,
        pattern=r"^(?:|[0-9a-f]{64})$",
    )
    matched_policy_ids: list[PositiveIdentifier] = Field(
        default_factory=list,
        max_length=MAX_MATCHED_POLICY_IDS,
    )
    applied: bool = False
    effective_policy: dict[str, Any] = Field(default_factory=dict)
    error: str = Field(default="", strict=True, max_length=2048)

    @field_validator("machine_name", "error")
    @classmethod
    def validate_policy_text(cls, value: str) -> str:
        return _validate_plain_text(value)

    @field_validator("effective_policy")
    @classmethod
    def validate_effective_policy(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_policy_value(value)
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("生效策略不是有效 JSON") from exc
        if len(encoded) > MAX_EFFECTIVE_POLICY_BYTES:
            raise ValueError("生效策略内容过大")
        return value


@dataclass(frozen=True)
class TrustedNode:
    id: int
    user_id: int
    machine_name: str
    group_name: str
    scaletail_ips: list[str]
    source_ip: str


def require_trusted_node(request: Request) -> TrustedNode:
    """Resolve the node identity injected by Headscale after Noise validation."""
    try:
        node_id = int(request.headers.get("X-ScaleForge-Node-ID", ""))
        user_id = int(request.headers.get("X-ScaleForge-User-ID", ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "缺少可信节点身份") from exc
    if node_id <= 0 or user_id <= 0:
        raise HTTPException(401, "缺少可信节点身份")

    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                n.id,
                n.user_id,
                COALESCE(NULLIF(n.given_name, ''), NULLIF(n.hostname, ''), CONCAT('机器#', n.id)) AS machine_name,
                COALESCE(u.name, '') AS group_name,
                n.ipv4,
                n.ipv6
            FROM nodes n
            JOIN users u ON u.id = n.user_id
            JOIN accounts a ON a.user_id = n.user_id
            WHERE n.id = %s
              AND n.user_id = %s
              AND n.deleted_at IS NULL
              AND (n.expiry IS NULL OR n.expiry > NOW())
              AND a.enabled = TRUE
              AND (a.expires_at IS NULL OR a.expires_at > NOW())
              AND a.must_change_password = FALSE
              AND a.password_changed_at > NOW() - INTERVAL '90 days'
            LIMIT 1
            """,
            (node_id, user_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(401, "节点身份已失效")

    source_ip = ""
    try:
        observed_ip = ipaddress.ip_address(
            request.headers.get("X-ScaleForge-Source-IP", "").strip()
        )
        if not (observed_ip.is_private or observed_ip.is_loopback or observed_ip.is_link_local):
            source_ip = str(observed_ip)
    except ValueError:
        pass

    return TrustedNode(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        machine_name=str(row.get("machine_name") or ""),
        group_name=str(row.get("group_name") or ""),
        scaletail_ips=[str(value) for value in (row.get("ipv4"), row.get("ipv6")) if value],
        source_ip=source_ip,
    )


def _bind_traffic_identity(report: TrafficReport, node: TrustedNode) -> None:
    report.machine_id = node.id
    report.machine_name = node.machine_name
    report.group_id = node.user_id
    report.group_name = node.group_name
    report.scaletail_ips = node.scaletail_ips
    report.public_ip = node.source_ip
    report.country = ""
    report.region = ""
    report.city = ""
    report.asn = ""
    report.isp = ""


def _bind_policy_state_identity(report: PolicyStateReport, node: TrustedNode) -> None:
    report.machine_id = node.id
    report.machine_name = node.machine_name


def _version_gt(remote: str, current: str) -> bool:
    return compare_versions(remote, current) == 1


def _release_payload(row: dict[str, Any], has_update: bool) -> dict[str, Any]:
    update_type = str(row.get("update_type") or "suggested").lower()
    return {
        "has_update": has_update,
        "id": row.get("id"),
        "policy_revision": int(row.get("policy_revision") or 0),
        "version": row.get("version") or "",
        "platform": row.get("platform") or "",
        "update_type": update_type,
        "forced": has_update and update_type == "forced",
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "download_url": row.get("download_url") or "",
        "sha256": row.get("sha256") or "",
        "signature": row.get("signature") or "",
        "file_size": int(row.get("file_size") or 0),
        "release_notes": row.get("release_notes") or "",
        "created_at": row.get("created_at") or "",
    }


def _policy_revision(policies: list[dict[str, Any]], effective: dict[str, Any]) -> str:
    source = {
        "policies": [
            {
                "id": int(policy["id"]),
                "updated_at": str(policy.get("updated_at") or ""),
            }
            for policy in policies
            if policy.get("id") is not None
        ],
        "effective": effective,
    }
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _identity_clause(report: TrafficReport):
    if not report.machine_id:
        raise HTTPException(401, "缺少可信节点身份")
    return "machine_id = %s", [report.machine_id]


def _policy_state_identity_clause(report: PolicyStateReport):
    if not report.machine_id:
        raise HTTPException(401, "缺少可信节点身份")
    return "machine_id = %s", [report.machine_id]


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

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where, params = _identity_clause(report)
    cur.execute(
        f"""
        SELECT id, country, region, city, asn, isp, last_seen
        FROM node_ip_observations
        WHERE ip=%s AND {where}
        ORDER BY id DESC
        LIMIT 1
        """,
        [report.public_ip, *params],
    )
    row = cur.fetchone()
    if row:
        report.country = str(row.get("country") or "")
        report.region = str(row.get("region") or "")
        report.city = str(row.get("city") or "")
        report.asn = str(row.get("asn") or "")
        report.isp = str(row.get("isp") or "")
        last_seen = row.get("last_seen")
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if not (report.country or report.city or report.asn) and (
            last_seen is None or last_seen <= datetime.now(timezone.utc) - timedelta(hours=24)
        ):
            _enrich_ip_geo(report)
        risk_flags = _trusted_risk_flags(conn, report)
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
        _enrich_ip_geo(report)
        risk_flags = _trusted_risk_flags(conn, report)
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


def _geo_lookup_url(public_ip: str) -> str:
    try:
        normalized_ip = ipaddress.ip_address(public_ip).compressed
    except ValueError:
        return ""
    template = os.environ.get("IP_GEOLOOKUP_URL") or str(CFG.get("ip_geolookup_url") or "")
    if not template:
        return ""
    url = template.replace("{ip}", quote(normalized_ip))
    if "{ip}" not in template:
        url = template.rstrip("/") + "/" + quote(normalized_ip)
    return trusted_service_url(url)


def _enrich_ip_geo(report: TrafficReport) -> None:
    if report.country or report.city or report.asn:
        return
    url = _geo_lookup_url(report.public_ip)
    if not url:
        return
    try:
        with httpx.Client(timeout=3.0, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
                response.raise_for_status()
                chunks = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 64 * 1024:
                        return
                    chunks.append(chunk)
                raw = b"".join(chunks)
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except (httpx.HTTPError, ValueError, UnicodeError):
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
    values = [
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
        )
        for flow in report.flows
    ]
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO flow_summaries (
            machine_id, machine_name, group_id, group_name,
            window_start, window_seconds,
            dst_ip, dst_port, protocol, direction, bytes, packets,
            connection_count, state, process_id, process_name
        ) VALUES %s
        """,
        values,
        template=(
            "(%s, %s, %s, %s, COALESCE(%s::timestamp, NOW()), %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s)"
        ),
        page_size=MAX_FLOW_SUMMARIES,
    )
    _maybe_create_flow_risk_events(conn, report)
    return len(values)


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
    return _identity_clause(report)


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


def _client_update_response(current_version: str, platform: str, current_revision: int = 0) -> dict[str, Any]:
    current_version = str(current_version or "").strip()
    platform = str(platform or "windows-amd64").strip().lower()
    try:
        current_revision = int(current_revision)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "客户端更新策略修订号无效") from exc
    if (
        parse_semver(current_version) is None
        or not platform
        or len(platform) > 64
        or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in platform)
        or current_revision < 0
        or current_revision > MAX_POLICY_REVISION
    ):
        raise HTTPException(400, "客户端版本查询参数无效")
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                id, policy_revision, version, platform, update_type, title, description,
                download_url, sha256, signature, file_size, release_notes,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM client_releases
            WHERE enabled = TRUE
              AND LOWER(platform) = ANY(%s::text[])
            ORDER BY policy_revision DESC, id DESC
            LIMIT 1
            """,
            ([platform],),
        )
        rows = cur.fetchall()
        if not rows:
            return {"code": 0, "data": {"has_update": False}}
        authoritative = rows[0]
        if not release_signature_valid(authoritative):
            raise HTTPException(503, "最新客户端更新策略签名无效")
        if int(authoritative.get("policy_revision") or 0) < current_revision:
            raise HTTPException(409, "服务端更新策略修订落后于客户端")
        action = str(authoritative.get("update_type") or "").lower()
        has_update = action != "clear" and _version_gt(
            str(authoritative.get("version") or ""),
            current_version,
        )
        return {"code": 0, "data": _release_payload(authoritative, has_update)}
    finally:
        conn.close()


@router.get("/client-update")
def client_update(
    current_version: str = "",
    platform: str = "windows-amd64",
    current_revision: int = 0,
    _: TrustedNode = Depends(require_trusted_node),
):
    return _client_update_response(current_version, platform, current_revision)


@router.get("/public-client-update")
def public_client_update(
    current_version: str = "",
    platform: str = "windows-amd64",
    current_revision: int = 0,
):
    """Serve only signed, non-secret release metadata to Headscale's public update endpoint."""
    return _client_update_response(current_version, platform, current_revision)


@router.post("/traffic")
def report_traffic(report: TrafficReport, node: TrustedNode = Depends(require_trusted_node)):
    conn = get_db_conn()
    try:
        _bind_traffic_identity(report, node)
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
    node: TrustedNode = Depends(require_trusted_node),
):
    conn = get_db_conn()
    try:
        machine_id = node.id
        machine_name = node.machine_name
        group_id = node.user_id
        group_name = node.group_name
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

        effective = {
            "rate_up_mbps": min_positive("rate_up_mbps"),
            "rate_down_mbps": min_positive("rate_down_mbps"),
            "monthly_quota_gb": quota_gb,
            "month_bytes": month_bytes,
            "quota_exceeded": quota_exceeded,
            "exceed_action": action,
        }
        matched_policy_ids = [int(policy["id"]) for policy in policies if policy.get("id") is not None]

        return {
            "code": 0,
            "data": {
                "effective": effective,
                "matched_policies": policies,
                "matched_policy_ids": matched_policy_ids,
                "policy_revision": _policy_revision(policies, effective),
            },
        }
    finally:
        conn.close()


@router.post("/policy-state")
def report_policy_state(report: PolicyStateReport, node: TrustedNode = Depends(require_trusted_node)):
    conn = get_db_conn()
    try:
        _bind_policy_state_identity(report, node)
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
                SET machine_id=%s, machine_name=%s, policy_revision=%s,
                    matched_policy_ids=%s, applied=%s, effective_policy=%s, error=%s,
                    applied_at=CASE WHEN %s THEN NOW() ELSE applied_at END,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (
                    report.machine_id,
                    report.machine_name or "unknown",
                    report.policy_revision,
                    psycopg2.extras.Json(report.matched_policy_ids),
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
                    machine_id, machine_name, policy_revision, matched_policy_ids, applied,
                    effective_policy, error, applied_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END, NOW())
                RETURNING id
                """,
                (
                    report.machine_id,
                    report.machine_name or "unknown",
                    report.policy_revision,
                    psycopg2.extras.Json(report.matched_policy_ids),
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
