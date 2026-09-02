import sys
from datetime import datetime, timedelta, timezone

from rolo.agent_tools.conformance import conform_tool_surface
from rolo.agent_tools.native_tools import AgentNativeToolDescriptor
from rolo.agent_tools.session import (
    NativeToolSessionBudget,
    NativeToolSessionDescriptor,
    native_catalog_sha256,
)


def _descriptor() -> AgentNativeToolDescriptor:
    return AgentNativeToolDescriptor(
        tool_id="test.echo",
        family="application",
        execution_path="DIRECT_RUNNER",
        executable=sys.executable,
        argv_template=[sys.executable, "-c", "print('ok')"],
        access="read",
        risk="R0",
        max_duration_s=2,
        max_output_bytes=128,
        evidence_kind="TEST",
    )


def _session(
    descriptor: AgentNativeToolDescriptor, *, digest: str | None = None
) -> NativeToolSessionDescriptor:
    now = datetime(2026, 9, 2, tzinfo=timezone.utc)
    return NativeToolSessionDescriptor(
        session_id="session-test",
        nonce="nonce_test_123456",
        robot_id="robot-test",
        stage="probe",
        native_catalog_sha256=digest or native_catalog_sha256([descriptor]),
        allowed_tools=[descriptor.tool_id],
        policy_version="rolo-v2-readonly",
        budget=NativeToolSessionBudget(max_calls=1, max_elapsed_s=30, max_result_bytes=4096),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_conformance_accepts_a_frozen_read_only_surface() -> None:
    descriptor = _descriptor()
    report = conform_tool_surface(_session(descriptor), [descriptor])

    assert report.status == "PASS"
    assert report.target_id == "robot-test"
    assert all(item.status == "PASS" for item in report.checks)


def test_conformance_rejects_catalog_digest_drift() -> None:
    descriptor = _descriptor()
    report = conform_tool_surface(_session(descriptor, digest="0" * 64), [descriptor])

    assert report.status == "FAIL"
    assert next(item for item in report.checks if item.name == "catalog_digest").status == "FAIL"
