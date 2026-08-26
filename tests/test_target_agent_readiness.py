from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from rolo.targets.agent_broker import build_session_agent_tool_catalog
from rolo.targets.agent_readiness import (
    SessionAgentReadinessEvidenceKind,
    SessionAgentReadinessGate,
    SessionAgentReadinessGateId,
    SessionAgentReadinessStatus,
    build_session_agent_production_readiness,
)


def test_readiness_passes_static_controls_but_never_self_attests_w10() -> None:
    report = build_session_agent_production_readiness(
        enabled=True,
        provider_api_key_configured=True,
        base_url="https://provider.example/v1",
        executable="codex",
        model="gpt-test",
        provider_timeout_s=120,
        catalog_sha256=build_session_agent_tool_catalog().canonical_sha256(),
        executable_resolver=lambda _: "/usr/local/bin/codex",
        now=lambda: datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    by_id = {gate.gate_id: gate for gate in report.gates}
    static = {
        SessionAgentReadinessGateId.FEATURE_ENABLED,
        SessionAgentReadinessGateId.DEDICATED_PROVIDER_CREDENTIAL,
        SessionAgentReadinessGateId.HTTPS_PROVIDER,
        SessionAgentReadinessGateId.CODEX_EXECUTABLE,
        SessionAgentReadinessGateId.CODEX_CONTAINMENT_CONTRACT,
    }
    assert all(by_id[gate_id].status == SessionAgentReadinessStatus.PASSED for gate_id in static)
    assert all(
        gate.status == SessionAgentReadinessStatus.NOT_VERIFIED
        for gate in report.gates
        if gate.gate_id not in static
    )
    assert report.production_ready is False
    assert report.generated_at == datetime(2026, 8, 26, tzinfo=timezone.utc)
    payload = report.model_dump_json()
    assert "provider.example" not in payload
    assert "/usr/local/bin/codex" not in payload


def test_readiness_blocks_insecure_or_missing_local_configuration() -> None:
    report = build_session_agent_production_readiness(
        enabled=False,
        provider_api_key_configured=False,
        base_url="http://provider.example/v1",
        executable="missing-codex",
        model=None,
        provider_timeout_s=120,
        catalog_sha256="a" * 64,
        executable_resolver=lambda _: None,
    )

    by_id = {gate.gate_id: gate for gate in report.gates}
    for gate_id in {
        SessionAgentReadinessGateId.FEATURE_ENABLED,
        SessionAgentReadinessGateId.DEDICATED_PROVIDER_CREDENTIAL,
        SessionAgentReadinessGateId.HTTPS_PROVIDER,
        SessionAgentReadinessGateId.CODEX_EXECUTABLE,
    }:
        assert by_id[gate_id].status == SessionAgentReadinessStatus.BLOCKED
    assert by_id[
        SessionAgentReadinessGateId.CODEX_CONTAINMENT_CONTRACT
    ].status == SessionAgentReadinessStatus.PASSED
    assert report.production_ready is False


def test_external_readiness_gate_cannot_be_self_attested() -> None:
    with pytest.raises(ValidationError, match="cannot be self-attested"):
        SessionAgentReadinessGate(
            gate_id=SessionAgentReadinessGateId.REAL_PROVIDER_ACCEPTANCE,
            status=SessionAgentReadinessStatus.PASSED,
            evidence_kind=(
                SessionAgentReadinessEvidenceKind.EXTERNAL_ACCEPTANCE_REQUIRED
            ),
            summary="untrusted claim",
            evidence_sha256="a" * 64,
        )
