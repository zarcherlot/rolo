from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.agent_contracts import ToolSessionBudget, ToolSessionDescriptor
from rolo.stages.adapt.tool_gateway import (
    ToolInvocationResult,
    ToolSessionAuthorizationError,
    ToolSessionBudgetError,
)
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.diagnose import create_diagnosis_tool_consumer
from rolo.stages.downstream_tools import (
    DownstreamToolConsumer,
    DownstreamToolFailure,
    DownstreamToolHandoff,
    validate_downstream_tool_handoff,
)
from rolo.stages.verify import create_verification_tool_consumer

NOW = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
OPERATION = "app.camera.snapshot"
CONTRACT_SHA256 = sha256_bytes(b"camera-contract")


def _session(
    *,
    stage: str = "diagnose",
    operation: str = OPERATION,
    expires_at: datetime | None = None,
    max_risk: str = "R1",
) -> ToolSessionDescriptor:
    return ToolSessionDescriptor(
        session_id=f"session-{stage}",
        nonce=f"fixture_{stage}_nonce_123456",
        robot_id="robot-1",
        release_id="release-1",
        target_fingerprint_sha256="a" * 64,
        registry_version="robot-canonical-operation-registry/v1",
        registry_sha256="b" * 64,
        registry_operation_count=294,
        contract_catalog_sha256="c" * 64,
        tool_catalog_sha256="d" * 64,
        state_graph_sha256="e" * 64,
        allowed_operations=[operation],
        contract_sha256={operation: CONTRACT_SHA256},
        caller=f"{stage}-agent",
        stage=stage,
        max_risk=max_risk,
        policy_version="policy-v1",
        budget=ToolSessionBudget(
            max_calls=2,
            max_elapsed_s=300,
            max_result_bytes=1_024,
        ),
        created_at=NOW - timedelta(seconds=1),
        expires_at=expires_at or NOW + timedelta(minutes=5),
    )


def _tool(
    *,
    operation: str = OPERATION,
    availability: str = "VERIFIED",
    access: str = "read",
    risk: str = "R0",
) -> ToolDescriptor:
    return ToolDescriptor(
        operation=operation,
        canonical_cli=["robotctl", "tool", "invoke", operation],
        layer="app",
        description="camera fixture",
        availability=availability,
        access=access,
        risk=risk,
        adapter="bundle:fixture#camera",
        contract_lifecycle="RELEASED",
        contract_version="1.0.0",
        contract_sha256=CONTRACT_SHA256,
        data_classification="PUBLIC",
        result_semantics="OBSERVATION",
    )


class _Gateway:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.listed = 0
        self.invoked: list[str] = []
        self.closed = 0
        self.tools = [_tool()]
        self.list_error: Exception | None = None
        self.invoke_error: Exception | None = None

    def open_session(self, descriptor: ToolSessionDescriptor) -> None:
        self.opened.append(descriptor.session_id)

    def list_tools(self, session_id: str, nonce: str) -> list[ToolDescriptor]:
        del session_id, nonce
        self.listed += 1
        if self.list_error:
            raise self.list_error
        return self.tools

    def invoke(
        self,
        session_id: str,
        nonce: str,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_s: float | None = None,
    ) -> ToolInvocationResult:
        del nonce, payload, timeout_s
        self.invoked.append(operation)
        if self.invoke_error:
            raise self.invoke_error
        return ToolInvocationResult(
            session_id=session_id,
            operation=operation,
            call_index=len(self.invoked),
            result={"frame": 7},
            result_bytes=11,
            result_sha256="f" * 64,
            audit_ref="audit:event-1",
        )

    def close_session(self, session_id: str, nonce: str) -> None:
        del session_id, nonce
        self.closed += 1


def _write_handoff(
    artifact_root: Path,
    *,
    stage: str = "diagnose",
    session: ToolSessionDescriptor | None = None,
) -> tuple[Path, Path]:
    descriptor = session or _session(stage=stage)
    layout = ArtifactLayout(artifact_root)
    session_path = layout.stage_file(stage, "robot-1", "tool_session.json")
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(descriptor.model_dump_json(indent=2), encoding="utf-8")
    handoff = DownstreamToolHandoff(
        stage=stage,
        robot_id="robot-1",
        caller=f"{stage}-agent",
        tool_session_ref=layout.ref(session_path),
        tool_session_sha256=sha256_file(session_path),
        session_id=descriptor.session_id,
        release_id=descriptor.release_id,
        tool_catalog_sha256=descriptor.tool_catalog_sha256,
        state_graph_sha256=descriptor.state_graph_sha256,
    )
    handoff_path = layout.stage_file(stage, "robot-1", "tool_handoff.json")
    handoff_path.write_text(handoff.model_dump_json(indent=2), encoding="utf-8")
    return handoff_path, session_path


@pytest.mark.parametrize("stage", ["diagnose", "verify"])
def test_stage_handoff_binds_exact_tool_session_and_consumes_only_gateway_subset(
    tmp_path: Path, stage: str
) -> None:
    _write_handoff(tmp_path, stage=stage)
    gateway = _Gateway()
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage=stage,
        gateway=gateway,
        clock=lambda: NOW,
    )

    assert consumer.open().status == "READY"
    listed = consumer.list_tools()
    invoked = consumer.invoke(OPERATION, {"camera": "front"})

    assert [tool.operation for tool in listed.tools] == [OPERATION]
    assert invoked.status == "SUCCEEDED"
    assert invoked.invocation is not None
    assert invoked.invocation.result == {"frame": 7}
    assert gateway.invoked == [OPERATION]
    assert consumer.handoff.publication_authority == "none"


@pytest.mark.parametrize(
    ("stage", "factory"),
    [
        ("diagnose", create_diagnosis_tool_consumer),
        ("verify", create_verification_tool_consumer),
    ],
)
def test_stage_packages_bind_their_downstream_tool_consumer(
    tmp_path: Path,
    stage: str,
    factory: Any,
) -> None:
    _write_handoff(tmp_path, stage=stage)

    consumer = factory(
        artifact_root=tmp_path,
        robot_id="robot-1",
        gateway=_Gateway(),
        clock=lambda: NOW,
    )

    assert consumer.session.stage == stage
    assert consumer.open().status == "READY"
    assert consumer.list_tools().status == "SUCCEEDED"


def test_handoff_rejects_tampered_session_and_identity_mismatch(tmp_path: Path) -> None:
    handoff_path, session_path = _write_handoff(tmp_path)
    session_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_downstream_tool_handoff(tmp_path, "robot-1", "diagnose")

    handoff_path.unlink()
    _write_handoff(tmp_path, session=_session().model_copy(update={"release_id": "release-2"}))
    payload = DownstreamToolHandoff.model_validate_json(
        handoff_path.read_text(encoding="utf-8")
    ).model_dump()
    payload["release_id"] = "release-1"
    handoff_path.write_text(
        DownstreamToolHandoff.model_validate(payload).model_dump_json(indent=2),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_downstream_tool_handoff(tmp_path, "robot-1", "diagnose")


def test_direct_consumer_construction_cannot_bypass_handoff_identity() -> None:
    session = _session()
    handoff = DownstreamToolHandoff(
        stage="diagnose",
        robot_id="robot-1",
        caller="diagnose-agent",
        tool_session_ref="artifact://diagnose/robot-1/latest/tool_session.json",
        tool_session_sha256="a" * 64,
        session_id=session.session_id,
        release_id="different-release",
        tool_catalog_sha256=session.tool_catalog_sha256,
        state_graph_sha256=session.state_graph_sha256,
    )

    with pytest.raises(ValueError, match="does not match"):
        DownstreamToolConsumer(
            handoff=handoff,
            session=session,
            gateway=_Gateway(),
            clock=lambda: NOW,
        )


def test_expired_session_degrades_without_opening_gateway(tmp_path: Path) -> None:
    session = _session(expires_at=NOW - timedelta(microseconds=1))
    _write_handoff(tmp_path, session=session)
    gateway = _Gateway()
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )

    outcome = consumer.open()

    assert outcome.status == "DEGRADED"
    assert outcome.failure == DownstreamToolFailure.SESSION_EXPIRED
    assert not outcome.retry_allowed
    assert gateway.opened == []


def test_release_identity_drift_latches_fail_closed_state(tmp_path: Path) -> None:
    _write_handoff(tmp_path)
    gateway = _Gateway()
    gateway.list_error = ToolSessionAuthorizationError(
        "active release identity does not match the frozen Tool Session"
    )
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )
    consumer.open()

    drift = consumer.list_tools()
    again = consumer.list_tools()

    assert drift.failure == DownstreamToolFailure.IDENTITY_DRIFT
    assert again.failure == DownstreamToolFailure.IDENTITY_DRIFT
    assert gateway.listed == 1


def test_operation_escalation_is_denied_before_gateway_invocation(tmp_path: Path) -> None:
    _write_handoff(tmp_path)
    gateway = _Gateway()
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )
    consumer.open()

    outcome = consumer.invoke("app.robot.publish", {"value": True})

    assert outcome.failure == DownstreamToolFailure.UNAUTHORIZED
    assert gateway.invoked == []
    assert not outcome.retry_allowed


def test_gateway_budget_failure_degrades_without_retry(tmp_path: Path) -> None:
    _write_handoff(tmp_path)
    gateway = _Gateway()
    gateway.invoke_error = ToolSessionBudgetError("Tool Session call budget is exhausted")
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )
    consumer.open()

    outcome = consumer.invoke(OPERATION, {})

    assert outcome.failure == DownstreamToolFailure.BUDGET_EXHAUSTED
    assert not outcome.retry_allowed
    assert gateway.invoked == [OPERATION]


@pytest.mark.parametrize(
    ("availability", "access", "risk"),
    [
        ("DISCOVERED_UNVERIFIED", "read", "R0"),
        ("VERIFIED", "write", "R1"),
        ("VERIFIED", "read", "R2"),
    ],
)
def test_consumer_defensively_rejects_non_verified_read_only_r0_r1_tools(
    tmp_path: Path, availability: str, access: str, risk: str
) -> None:
    _write_handoff(tmp_path)
    gateway = _Gateway()
    gateway.tools = [_tool(availability=availability, access=access, risk=risk)]
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )
    consumer.open()

    outcome = consumer.list_tools()

    assert outcome.failure == DownstreamToolFailure.IDENTITY_DRIFT
    assert outcome.tools == []


def test_consumer_enforces_the_session_risk_ceiling(tmp_path: Path) -> None:
    _write_handoff(tmp_path, session=_session(max_risk="R0"))
    gateway = _Gateway()
    gateway.tools = [_tool(risk="R1")]
    consumer = DownstreamToolConsumer.from_handoff(
        artifact_root=tmp_path,
        robot_id="robot-1",
        stage="diagnose",
        gateway=gateway,
        clock=lambda: NOW,
    )
    consumer.open()

    outcome = consumer.list_tools()

    assert outcome.failure == DownstreamToolFailure.IDENTITY_DRIFT


def test_handoff_cannot_grant_publication_authority() -> None:
    payload = DownstreamToolHandoff(
        stage="diagnose",
        robot_id="robot-1",
        caller="diagnose-agent",
        tool_session_ref="artifact://diagnose/robot-1/latest/tool_session.json",
        tool_session_sha256="a" * 64,
        session_id="session-1",
        release_id="release-1",
        tool_catalog_sha256="b" * 64,
        state_graph_sha256="c" * 64,
    ).model_dump()
    payload["publication_authority"] = "release"

    with pytest.raises(ValidationError):
        DownstreamToolHandoff.model_validate(payload)
