from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rolo.adapter_runtime import invoke_adapter
from rolo.core.hashing import sha256_bytes
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.agent_contracts import (
    ToolSessionBudget,
    ToolSessionDescriptor,
    registry_identity_sha256,
)
from rolo.stages.adapt.models import ToolCatalog
from rolo.stages.adapt.tool_gateway import (
    ToolGateway,
    ToolGatewayError,
    ToolGatewayPolicy,
    ToolSessionAuthorizationError,
    ToolSessionBudgetError,
    tool_session_descriptor_sha256,
)


@dataclass(frozen=True)
class _Resolver:
    registry_version: str
    registry_sha256: str
    contract_catalog_sha256: str
    contracts: dict[str, str]

    @property
    def operation_count(self) -> int:
        return len(self.contracts)

    def contract_sha256_for(self, operation: str) -> str | None:
        return self.contracts.get(operation)


def _resolver() -> _Resolver:
    contracts = {
        "app.camera.snapshot": sha256_bytes(b"camera-contract"),
        "app.robot.status": sha256_bytes(b"status-contract"),
    }
    catalog_sha256 = sha256_bytes(b"contract-catalog")
    return _Resolver(
        registry_version="robot-canonical-operation-registry/v1",
        registry_sha256=registry_identity_sha256(
            registry_version="robot-canonical-operation-registry/v1",
            contract_catalog_sha256=catalog_sha256,
            contract_sha256=contracts,
        ),
        contract_catalog_sha256=catalog_sha256,
        contracts=contracts,
    )


def _tool(
    resolver: _Resolver,
    operation: str,
    *,
    availability: str = "VERIFIED",
    risk: str = "R0",
    access: str = "read",
) -> ToolDescriptor:
    return ToolDescriptor(
        operation=operation,
        canonical_cli=["robotctl", "tool", "invoke", operation],
        layer="app",
        description=f"Fixture {operation}",
        risk=risk,
        access=access,
        availability=availability,
        adapter=f"bundle:fixture#{operation.replace('.', '_')}",
        contract_lifecycle="RELEASED",
        contract_version="1.0.0",
        contract_sha256=resolver.contracts[operation],
        data_classification="PUBLIC",
        result_semantics="OBSERVATION",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        max_duration_s=10,
    )


def _release_and_catalog(
    resolver: _Resolver,
    *,
    tools: list[ToolDescriptor] | None = None,
    release_id: str = "release-1",
) -> tuple[SimpleNamespace, ToolCatalog]:
    release = SimpleNamespace(
        release_id=release_id,
        target_fingerprint_sha256="a" * 64,
        tool_catalog_sha256="b" * 64,
        state_graph_sha256="c" * 64,
    )
    catalog = ToolCatalog(
        robot_id="robot-1",
        discovery_id="discovery-1",
        contract_catalog_sha256=resolver.contract_catalog_sha256,
        tools=tools
        or [
            _tool(resolver, "app.camera.snapshot"),
            _tool(resolver, "app.robot.status"),
        ],
    )
    return release, catalog


def _session(
    resolver: _Resolver,
    now: datetime,
    *,
    operations: list[str] | None = None,
    max_calls: int = 2,
    max_result_bytes: int = 1_024,
) -> ToolSessionDescriptor:
    selected = operations or ["app.camera.snapshot"]
    return ToolSessionDescriptor(
        session_id="session-1",
        nonce="fixture_nonce_1234567890",
        robot_id="robot-1",
        release_id="release-1",
        target_fingerprint_sha256="a" * 64,
        registry_version=resolver.registry_version,
        registry_sha256=resolver.registry_sha256,
        registry_operation_count=resolver.operation_count,
        contract_catalog_sha256=resolver.contract_catalog_sha256,
        tool_catalog_sha256="b" * 64,
        state_graph_sha256="c" * 64,
        allowed_operations=selected,
        contract_sha256={operation: resolver.contracts[operation] for operation in selected},
        caller="diagnose-agent",
        stage="diagnose",
        max_risk="R1",
        policy_version="policy-v1",
        budget=ToolSessionBudget(
            max_calls=max_calls,
            max_elapsed_s=300,
            max_result_bytes=max_result_bytes,
        ),
        created_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )


def _gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    tools: list[ToolDescriptor] | None = None,
    invoker: Any = None,
    authorizer: Any = None,
) -> tuple[ToolGateway, _Resolver, datetime, Path]:
    resolver = _resolver()
    now = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    release, catalog = _release_and_catalog(resolver, tools=tools)
    monkeypatch.setattr(
        "rolo.stages.adapt.tool_gateway.load_current_release",
        lambda *_args, **_kwargs: (tmp_path / "release", release, object(), catalog),
    )
    audit = tmp_path / "tool-gateway-audit.jsonl"
    gateway = ToolGateway(
        output_root=tmp_path / "output",
        artifact_root=tmp_path / "artifacts",
        resolver=resolver,
        policy=ToolGatewayPolicy(
            policy_version="policy-v1",
            allowed_callers=["diagnose-agent"],
        ),
        session_authorizer=authorizer or (lambda _descriptor, _digest: True),
        gateway_audit_path=audit,
        runtime_invoker=invoker or (lambda *_args, **_kwargs: {"status": "ok"}),
        clock=lambda: now,
    )
    return gateway, resolver, now, audit


def test_list_exposes_only_the_frozen_verified_subset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway, resolver, now, audit = _gateway(tmp_path, monkeypatch)
    session = _session(resolver, now)

    gateway.open_session(session)
    session.allowed_operations.clear()
    tools = gateway.list_tools(session.session_id, session.nonce)

    assert [tool.operation for tool in tools] == ["app.camera.snapshot"]
    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [(item["action"], item["outcome"]) for item in records] == [
        ("OPEN", "ALLOWED"),
        ("LIST", "ALLOWED"),
    ]
    assert all("nonce" not in item for item in records)


def test_invoke_pins_runtime_identity_and_audits_only_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def invoke(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "ok", "frame": 7}

    gateway, resolver, now, audit = _gateway(
        tmp_path, monkeypatch, invoker=invoke
    )
    session = _session(resolver, now)
    gateway.open_session(session)

    outcome = gateway.invoke(
        session.session_id,
        session.nonce,
        "app.camera.snapshot",
        {"camera": "front"},
    )

    assert outcome.result == {"status": "ok", "frame": 7}
    assert not outcome.truncated
    assert captured["kwargs"]["expected_release_id"] == session.release_id
    assert captured["kwargs"]["expected_target_fingerprint_sha256"] == (
        session.target_fingerprint_sha256
    )
    assert captured["kwargs"]["expected_tool_catalog_sha256"] == (
        session.tool_catalog_sha256
    )
    assert captured["kwargs"]["expected_state_graph_sha256"] == session.state_graph_sha256
    record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert record["action"] == "INVOKE"
    assert record["outcome"] == "ALLOWED"
    assert record["payload_sha256"]
    assert record["result_sha256"] == outcome.result_sha256
    assert "front" not in json.dumps(record)


@pytest.mark.parametrize(
    ("availability", "risk", "access"),
    [("DISCOVERED_UNVERIFIED", "R0", "read"), ("VERIFIED", "R2", "write")],
)
def test_session_rejects_unverified_or_non_read_only_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    availability: str,
    risk: str,
    access: str,
) -> None:
    resolver = _resolver()
    tools = [
        _tool(
            resolver,
            "app.camera.snapshot",
            availability=availability,
            risk=risk,
            access=access,
        )
    ]
    gateway, resolver, now, _ = _gateway(tmp_path, monkeypatch, tools=tools)

    with pytest.raises(ToolSessionAuthorizationError, match="not Verified|read-only"):
        gateway.open_session(_session(resolver, now))


def test_nonce_and_release_drift_are_denied_on_each_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway, resolver, now, _ = _gateway(tmp_path, monkeypatch)
    session = _session(resolver, now)
    gateway.open_session(session)

    with pytest.raises(ToolSessionAuthorizationError, match="nonce"):
        gateway.list_tools(session.session_id, "wrong_nonce_123456")

    release, catalog = _release_and_catalog(resolver, release_id="release-2")
    monkeypatch.setattr(
        "rolo.stages.adapt.tool_gateway.load_current_release",
        lambda *_args, **_kwargs: (tmp_path / "release", release, object(), catalog),
    )
    with pytest.raises(ToolSessionAuthorizationError, match="active release identity"):
        gateway.list_tools(session.session_id, session.nonce)


def test_call_and_result_budgets_are_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway, resolver, now, _ = _gateway(
        tmp_path,
        monkeypatch,
        invoker=lambda *_args, **_kwargs: {"content": "x" * 200},
    )
    session = _session(resolver, now, max_calls=1, max_result_bytes=16)
    gateway.open_session(session)

    outcome = gateway.invoke(
        session.session_id,
        session.nonce,
        "app.camera.snapshot",
        {},
    )
    assert outcome.truncated
    assert outcome.result is None

    with pytest.raises(ToolSessionBudgetError, match="call budget"):
        gateway.invoke(
            session.session_id,
            session.nonce,
            "app.camera.snapshot",
            {},
        )


def test_policy_version_and_expiry_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway, resolver, now, _ = _gateway(tmp_path, monkeypatch)
    stale_policy = _session(resolver, now).model_copy(update={"policy_version": "old"})
    with pytest.raises(ToolSessionAuthorizationError, match="policy version"):
        gateway.open_session(stale_policy)

    expired = _session(resolver, now).model_copy(
        update={
            "created_at": now - timedelta(minutes=10),
            "expires_at": now - timedelta(minutes=1),
        }
    )
    with pytest.raises(ToolSessionAuthorizationError, match="expired"):
        gateway.open_session(expired)


def test_self_minted_session_without_trusted_issuance_is_denied_and_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolver = _resolver()
    now = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    issued = _session(resolver, now)
    issued_digests = {
        issued.session_id: tool_session_descriptor_sha256(issued),
    }

    def authorize(descriptor: ToolSessionDescriptor, digest: str) -> bool:
        return issued_digests.get(descriptor.session_id) == digest

    gateway, resolver, now, audit = _gateway(
        tmp_path,
        monkeypatch,
        authorizer=authorize,
    )
    gateway.open_session(issued)
    issuer_spoof = issued.model_copy(
        update={"nonce": "spoofed_issuer_nonce_1234"}
    )
    with pytest.raises(ToolSessionAuthorizationError, match="trusted.*issuance"):
        gateway.open_session(issuer_spoof)

    self_minted = _session(resolver, now).model_copy(
        update={
            "session_id": "self-minted-session",
            "nonce": "self_minted_nonce_123456",
        }
    )

    with pytest.raises(ToolSessionAuthorizationError, match="trusted.*issuance"):
        gateway.open_session(self_minted)

    record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert record["action"] == "OPEN"
    assert record["outcome"] == "DENIED"
    assert record["session_descriptor_sha256"] == tool_session_descriptor_sha256(
        self_minted
    )


def test_non_json_payload_is_denied_without_breaking_failure_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoked = False

    def invoke(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal invoked
        invoked = True
        return {"status": "unexpected"}

    gateway, resolver, now, audit = _gateway(
        tmp_path,
        monkeypatch,
        invoker=invoke,
    )
    session = _session(resolver, now)
    gateway.open_session(session)

    with pytest.raises(ToolGatewayError, match="JSON-serializable"):
        gateway.invoke(
            session.session_id,
            session.nonce,
            "app.camera.snapshot",
            {"not_json": {"set-member"}},
        )

    assert not invoked
    record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert record["action"] == "INVOKE"
    assert record["outcome"] == "DENIED"
    assert len(record["payload_sha256"]) == 64


def test_adapter_runtime_rejects_a_release_that_differs_from_the_invocation_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = SimpleNamespace(
        release_id="release-2",
        target_fingerprint_sha256="a" * 64,
        tool_catalog_sha256="b" * 64,
        state_graph_sha256="c" * 64,
    )
    monkeypatch.setattr(
        "rolo.adapter_runtime.load_current_release",
        lambda *_args, **_kwargs: (tmp_path, release, object(), object()),
    )

    with pytest.raises(ValueError, match="release ID.*pinned"):
        invoke_adapter(
            tmp_path,
            "robot-1",
            "app.camera.snapshot",
            {},
            artifact_root=tmp_path,
            expected_release_id="release-1",
        )
