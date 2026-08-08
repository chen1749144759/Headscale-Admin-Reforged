from unittest.mock import patch

import pytest
from pydantic import ValidationError

from api.routers.client_reports import (
    FlowSummary,
    PolicyStateReport,
    TrafficReport,
    _insert_flows,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (FlowSummary, {"dst_ip": "203.0.113.10", "bytes": -1}),
        (FlowSummary, {"dst_ip": "203.0.113.10", "packets": -1}),
        (FlowSummary, {"dst_ip": "203.0.113.10", "connection_count": -1}),
        (FlowSummary, {"dst_ip": "203.0.113.10", "process_id": -1}),
        (TrafficReport, {"rx_bytes_total": -1}),
        (TrafficReport, {"tx_bytes_total": -1}),
        (PolicyStateReport, {"machine_id": -1}),
        (PolicyStateReport, {"matched_policy_ids": [-1]}),
    ],
)
def test_negative_counters_and_identifiers_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (FlowSummary, {"dst_ip": "203.0.113.10", "process_name": "x" * 261}),
        (TrafficReport, {"machine_name": "x" * 256}),
        (TrafficReport, {"endpoint_type": "x" * 33}),
        (PolicyStateReport, {"error": "x" * 2049}),
    ],
)
def test_oversized_strings_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (TrafficReport, {"flows": [{"dst_ip": "203.0.113.10"}] * 501}),
        (TrafficReport, {"scaletail_ips": ["100.64.0.1"] * 17}),
        (PolicyStateReport, {"matched_policy_ids": list(range(1, 130))}),
        (PolicyStateReport, {"effective_policy": {"values": list(range(129))}}),
    ],
)
def test_oversized_lists_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (FlowSummary, {"dst_ip": "not-an-ip"}),
        (FlowSummary, {"dst_ip": "203.0.113.10", "dst_port": 0}),
        (FlowSummary, {"dst_ip": "203.0.113.10", "dst_port": 65536}),
        (TrafficReport, {"public_ip": "999.1.1.1"}),
        (TrafficReport, {"scaletail_ips": ["invalid"]}),
    ],
)
def test_invalid_ip_addresses_and_ports_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


def test_invalid_flow_window_timestamp_is_rejected_before_database_use():
    with pytest.raises(ValidationError):
        FlowSummary(dst_ip="203.0.113.10", window_start="not-a-timestamp")


def test_normal_reports_are_accepted_and_ip_addresses_are_normalized():
    flow = FlowSummary(
        window_start="2026-08-09T12:00:00Z",
        window_seconds=60,
        dst_ip="2001:0db8:0:0:0:0:0:1",
        dst_port=443,
        protocol="tcp",
        direction="outbound",
        bytes=4096,
        packets=8,
        connection_count=2,
        process_id=1234,
        process_name="browser.exe",
    )
    report = TrafficReport(
        machine_id=7,
        machine_name="workstation-7",
        group_id=3,
        group_name="engineering",
        scaletail_ips=["100.64.0.7", "fd7a:115c:a1e0::7"],
        rx_bytes_total=123456,
        tx_bytes_total=654321,
        endpoint_type="direct",
        public_ip="203.0.113.7",
        flows=[flow],
    )
    state = PolicyStateReport(
        machine_id=7,
        machine_name="workstation-7",
        policy_revision="a" * 64,
        matched_policy_ids=[1, 2],
        applied=True,
        effective_policy={
            "rate_up_mbps": 2.5,
            "quota_exceeded": False,
            "sources": ["global", "machine"],
        },
    )

    assert report.flows[0].dst_ip == "2001:db8::1"
    assert report.scaletail_ips == ["100.64.0.7", "fd7a:115c:a1e0::7"]
    assert report.flows[0].dst_port == 443
    assert state.matched_policy_ids == [1, 2]


class FakeConnection:
    def __init__(self):
        self.cursor_instance = object()

    def cursor(self):
        return self.cursor_instance


def test_insert_flows_uses_one_execute_values_batch():
    report = TrafficReport(
        machine_id=7,
        machine_name="workstation-7",
        group_id=3,
        group_name="engineering",
        flows=[
            FlowSummary(
                window_start="2026-08-09T12:00:00Z",
                dst_ip="203.0.113.10",
                dst_port=443,
                packets=4,
            ),
            FlowSummary(
                window_start="2026-08-09T12:00:00Z",
                dst_ip="2001:db8::10",
                dst_port=8443,
            ),
        ],
    )
    conn = FakeConnection()

    with (
        patch("api.routers.client_reports.psycopg2.extras.execute_values") as execute_values,
        patch("api.routers.client_reports._maybe_create_flow_risk_events") as risk_events,
    ):
        count = _insert_flows(conn, report)

    assert count == 2
    execute_values.assert_called_once()
    args, kwargs = execute_values.call_args
    assert args[0] is conn.cursor_instance
    assert "VALUES %s" in args[1]
    assert len(args[2]) == 2
    assert args[2][0][6] == "203.0.113.10"
    assert args[2][0][12] == 4
    assert args[2][1][12] == 1
    assert kwargs["page_size"] == 500
    risk_events.assert_called_once_with(conn, report)
