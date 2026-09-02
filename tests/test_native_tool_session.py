import json
from datetime import datetime, timedelta, timezone

import pytest

from rolo.agent_tools import (
    AgentNativeRunner,
    NativeToolBroker,
    NativeToolSession,
    NativeToolSessionAuthorizationError,
    NativeToolSessionBudget,
    NativeToolSessionDescriptor,
    ToolPlanStep,
    build_tool_plan,
    default_agent_native_catalog,
    native_broker_request,
    native_catalog_sha256,
)
from rolo.core.artifacts import ArtifactStore


def _session(tmp_path, *, max_calls: int = 2) -> NativeToolSession:
    catalog = default_agent_native_catalog()[:1]
    now = datetime.now(timezone.utc)
    descriptor = NativeToolSessionDescriptor(
        session_id="native-session-1",
        nonce="native_nonce_123456",
        robot_id="demo",
        stage="probe",
        native_catalog_sha256=native_catalog_sha256(default_agent_native_catalog()),
        allowed_tools=[catalog[0].tool_id],
        policy_version="native-policy-v1",
        budget=NativeToolSessionBudget(
            max_calls=max_calls,
            max_elapsed_s=60,
            max_result_bytes=100_000,
        ),
        created_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    return NativeToolSession(
        descriptor=descriptor,
        runner=AgentNativeRunner(
            default_agent_native_catalog(),
            executor=lambda *args, **kwargs: type(
                "Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""}
            )(),
        ),
        artifacts=ArtifactStore(tmp_path / "artifacts"),
        clock=lambda: now,
    )


def test_native_session_writes_evidence_artifact_and_audit(tmp_path) -> None:
    session = _session(tmp_path)

    result = session.invoke("native.hw.inventory.scan")

    assert result.status.value in {"SUCCEEDED", "UNAVAILABLE"}
    assert result.evidence_refs == [
        "artifact://native/demo/sessions/native-session-1/calls/0001-native.hw.inventory.scan.json"
    ]
    assert (
        tmp_path
        / "artifacts/native/demo/sessions/native-session-1/calls/0001-native.hw.inventory.scan.json"
    ).is_file()
    assert (
        tmp_path / "artifacts/native/demo/sessions/native-session-1/audit.jsonl"
    ).is_file()


def test_native_session_rejects_unknown_tool_and_enforces_budget(tmp_path) -> None:
    session = _session(tmp_path, max_calls=1)

    with pytest.raises(NativeToolSessionAuthorizationError):
        session.invoke("native.ros.node.list")
    session.invoke("native.hw.inventory.scan")
    with pytest.raises(ValueError, match="call budget"):
        session.invoke("native.hw.inventory.scan")


def test_native_session_catalog_identity_is_bound(tmp_path) -> None:
    catalog = default_agent_native_catalog()[:1]
    now = datetime.now(timezone.utc)
    descriptor = NativeToolSessionDescriptor(
        session_id="native-session-2",
        nonce="native_nonce_123456",
        robot_id="demo",
        stage="probe",
        native_catalog_sha256="0" * 64,
        allowed_tools=[catalog[0].tool_id],
        policy_version="native-policy-v1",
        budget=NativeToolSessionBudget(max_calls=1, max_elapsed_s=60, max_result_bytes=100_000),
        created_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    with pytest.raises(NativeToolSessionAuthorizationError, match="catalog identity"):
        NativeToolSession(
            descriptor=descriptor,
            runner=AgentNativeRunner(default_agent_native_catalog()),
            artifacts=ArtifactStore(tmp_path / "artifacts"),
            clock=lambda: now,
        )


def test_native_session_executes_validated_tool_plan(tmp_path) -> None:
    session = _session(tmp_path)
    plan = build_tool_plan(
        goal="inspect hardware",
        target_id="demo",
        session_id="native-session-1",
        session_nonce="native_nonce_123456",
        surface_digest=native_catalog_sha256(default_agent_native_catalog()),
        steps=[
            ToolPlanStep(
                tool_id="native.hw.inventory.scan",
                expected_observation="hardware inventory",
            )
        ],
    )

    results = session.execute_plan(plan)

    assert len(results) == 1
    assert results[0].evidence_refs


def test_native_session_rejects_a_plan_from_another_nonce(tmp_path) -> None:
    session = _session(tmp_path)
    plan = build_tool_plan(
        goal="inspect hardware",
        target_id="demo",
        session_id="native-session-1",
        session_nonce="other_nonce_123456",
        surface_digest=native_catalog_sha256(default_agent_native_catalog()),
        steps=[
            ToolPlanStep(
                tool_id="native.hw.inventory.scan",
                expected_observation="hardware inventory",
            )
        ],
    )

    with pytest.raises(NativeToolSessionAuthorizationError, match="nonce"):
        session.execute_plan(plan)


def test_native_session_close_is_idempotent_and_audits_once(tmp_path) -> None:
    session = _session(tmp_path)

    session.close()
    session.close()

    records = [
        json.loads(line)
        for line in (
            tmp_path / "artifacts/native/demo/sessions/native-session-1/audit.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert [item["outcome"] for item in records] == ["CLOSED"]


def test_native_broker_keeps_runner_outside_agent_workspace(tmp_path) -> None:
    session = _session(tmp_path)
    broker = NativeToolBroker(session)
    broker.start()
    try:
        host, port = broker.address
        listed = native_broker_request(host, port, broker.token, {"action": "list"})
        assert listed["status"] == "SUCCEEDED"
        result = native_broker_request(
            host,
            port,
            broker.token,
            {"action": "run", "tool_id": "native.hw.inventory.scan"},
        )
        assert result["result"]["tool_id"] == "native.hw.inventory.scan"
        with pytest.raises(ValueError, match="authorization"):
            native_broker_request(host, port, "wrong-token", {"action": "list"})
    finally:
        broker.stop()
