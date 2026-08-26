from __future__ import annotations

import hashlib
import json
import platform
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.targets.agent_runtime import build_codex_session_agent_command

_SHA256 = r"^[0-9a-f]{64}$"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SessionAgentReadinessStatus(str, Enum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    NOT_VERIFIED = "NOT_VERIFIED"


class SessionAgentReadinessGateId(str, Enum):
    FEATURE_ENABLED = "FEATURE_ENABLED"
    DEDICATED_PROVIDER_CREDENTIAL = "DEDICATED_PROVIDER_CREDENTIAL"
    HTTPS_PROVIDER = "HTTPS_PROVIDER"
    CODEX_EXECUTABLE = "CODEX_EXECUTABLE"
    CODEX_CONTAINMENT_CONTRACT = "CODEX_CONTAINMENT_CONTRACT"
    DEDICATED_OS_ISOLATION = "DEDICATED_OS_ISOLATION"
    REAL_PROVIDER_ACCEPTANCE = "REAL_PROVIDER_ACCEPTANCE"
    REAL_SSH_PROMPT_INJECTION = "REAL_SSH_PROMPT_INJECTION"
    MULTI_WORKER_FAILURE_INJECTION = "MULTI_WORKER_FAILURE_INJECTION"
    LINUX_X86_64_ACCEPTANCE = "LINUX_X86_64_ACCEPTANCE"
    LINUX_ARM64_ACCEPTANCE = "LINUX_ARM64_ACCEPTANCE"


class SessionAgentReadinessEvidenceKind(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    COMMAND_CONTRACT = "COMMAND_CONTRACT"
    EXTERNAL_ACCEPTANCE_REQUIRED = "EXTERNAL_ACCEPTANCE_REQUIRED"


class SessionAgentHostClass(str, Enum):
    LINUX_X86_64 = "LINUX_X86_64"
    LINUX_ARM64 = "LINUX_ARM64"
    WINDOWS_X86_64 = "WINDOWS_X86_64"
    OTHER = "OTHER"


class SessionAgentReadinessGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: SessionAgentReadinessGateId
    status: SessionAgentReadinessStatus
    evidence_kind: SessionAgentReadinessEvidenceKind
    summary: str = Field(min_length=1, max_length=300)
    evidence_sha256: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def bind_evidence(self) -> SessionAgentReadinessGate:
        if self.evidence_kind == SessionAgentReadinessEvidenceKind.EXTERNAL_ACCEPTANCE_REQUIRED:
            if self.status != SessionAgentReadinessStatus.NOT_VERIFIED:
                raise ValueError("external Session Agent gate cannot be self-attested")
            if self.evidence_sha256 is not None:
                raise ValueError("unverified external Session Agent gate has no evidence")
        elif self.status == SessionAgentReadinessStatus.NOT_VERIFIED:
            raise ValueError("static Session Agent gate must pass or block")
        elif self.evidence_sha256 is None:
            raise ValueError("static Session Agent gate requires evidence digest")
        return self


class SessionAgentProductionReadinessReport(BaseModel):
    """Secret-free W10 gate report. It cannot self-attest external acceptance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-production-readiness/v1"] = (
        "rolo-session-agent-production-readiness/v1"
    )
    generated_at: datetime
    host_class: SessionAgentHostClass
    catalog_sha256: str = Field(pattern=_SHA256)
    provider_configuration_sha256: str = Field(pattern=_SHA256)
    gates: list[SessionAgentReadinessGate]
    production_ready: bool

    @model_validator(mode="after")
    def bind_readiness(self) -> SessionAgentProductionReadinessReport:
        gate_ids = [gate.gate_id for gate in self.gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("Session Agent readiness gates must be unique")
        if set(gate_ids) != set(SessionAgentReadinessGateId):
            raise ValueError("Session Agent readiness report must cover every W10 gate")
        expected = all(
            gate.status == SessionAgentReadinessStatus.PASSED for gate in self.gates
        )
        if self.production_ready != expected:
            raise ValueError("Session Agent production readiness contradicts its gates")
        return self


def _host_class() -> SessionAgentHostClass:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return SessionAgentHostClass.LINUX_X86_64
    if system == "linux" and machine in {"aarch64", "arm64"}:
        return SessionAgentHostClass.LINUX_ARM64
    if system == "windows" and machine in {"x86_64", "amd64"}:
        return SessionAgentHostClass.WINDOWS_X86_64
    return SessionAgentHostClass.OTHER


def _static_gate(
    gate_id: SessionAgentReadinessGateId,
    *,
    passed: bool,
    evidence_kind: SessionAgentReadinessEvidenceKind,
    summary: str,
    evidence: object,
) -> SessionAgentReadinessGate:
    return SessionAgentReadinessGate(
        gate_id=gate_id,
        status=(
            SessionAgentReadinessStatus.PASSED
            if passed
            else SessionAgentReadinessStatus.BLOCKED
        ),
        evidence_kind=evidence_kind,
        summary=summary,
        evidence_sha256=_sha256(evidence),
    )


def _external_gate(
    gate_id: SessionAgentReadinessGateId,
    summary: str,
) -> SessionAgentReadinessGate:
    return SessionAgentReadinessGate(
        gate_id=gate_id,
        status=SessionAgentReadinessStatus.NOT_VERIFIED,
        evidence_kind=SessionAgentReadinessEvidenceKind.EXTERNAL_ACCEPTANCE_REQUIRED,
        summary=summary,
    )


def build_session_agent_production_readiness(
    *,
    enabled: bool,
    provider_api_key_configured: bool,
    base_url: str,
    executable: str,
    model: str | None,
    provider_timeout_s: int,
    catalog_sha256: str,
    executable_resolver: Callable[[str], str | None] = shutil.which,
    now: Callable[[], datetime] = _utc_now,
) -> SessionAgentProductionReadinessReport:
    """Evaluate local static controls while leaving real-environment gates unverified."""
    provider_configuration = {
        "enabled": enabled,
        "provider_api_key_configured": provider_api_key_configured,
        "base_url": base_url,
        "executable": executable,
        "model": model,
        "provider_timeout_s": provider_timeout_s,
    }
    parsed = urlparse(base_url)
    https_provider = parsed.scheme == "https" and bool(parsed.netloc)
    resolved = executable_resolver(executable) is not None
    command = build_codex_session_agent_command(
        executable=executable,
        workspace=Path("/session-agent-workspace"),
        schema_path=Path("/session-agent-schema.json"),
        final_message_path=Path("/session-agent-result.json"),
        model=model,
        base_url=base_url,
    )
    required_tokens = {
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "read-only",
        'shell_environment_policy.inherit="none"',
    }
    containment_contract = required_tokens.issubset(set(command)) and (
        "--dangerously-bypass-approvals-and-sandbox" not in command
    )
    gates = [
        _static_gate(
            SessionAgentReadinessGateId.FEATURE_ENABLED,
            passed=enabled,
            evidence_kind=SessionAgentReadinessEvidenceKind.CONFIGURATION,
            summary=(
                "Session Agent feature flag is enabled."
                if enabled
                else "Session Agent feature flag is disabled."
            ),
            evidence={"enabled": enabled},
        ),
        _static_gate(
            SessionAgentReadinessGateId.DEDICATED_PROVIDER_CREDENTIAL,
            passed=provider_api_key_configured,
            evidence_kind=SessionAgentReadinessEvidenceKind.CONFIGURATION,
            summary=(
                "A dedicated provider credential is configured."
                if provider_api_key_configured
                else "A dedicated provider credential is not configured."
            ),
            evidence={"configured": provider_api_key_configured},
        ),
        _static_gate(
            SessionAgentReadinessGateId.HTTPS_PROVIDER,
            passed=https_provider,
            evidence_kind=SessionAgentReadinessEvidenceKind.CONFIGURATION,
            summary=(
                "The provider uses an absolute HTTPS endpoint."
                if https_provider
                else "The provider endpoint is not absolute HTTPS."
            ),
            evidence={"absolute_https": https_provider},
        ),
        _static_gate(
            SessionAgentReadinessGateId.CODEX_EXECUTABLE,
            passed=resolved,
            evidence_kind=SessionAgentReadinessEvidenceKind.CONFIGURATION,
            summary=(
                "The Codex executable is resolvable."
                if resolved
                else "The Codex executable is not resolvable."
            ),
            evidence={"resolved": resolved},
        ),
        _static_gate(
            SessionAgentReadinessGateId.CODEX_CONTAINMENT_CONTRACT,
            passed=containment_contract,
            evidence_kind=SessionAgentReadinessEvidenceKind.COMMAND_CONTRACT,
            summary=(
                "The Codex command enforces ephemeral, read-only, and clean-env controls."
                if containment_contract
                else "The Codex command is missing required containment controls."
            ),
            evidence={"command_sha256": _sha256(command)},
        ),
        _external_gate(
            SessionAgentReadinessGateId.DEDICATED_OS_ISOLATION,
            "Requires real ACL evidence from a dedicated OS user or container.",
        ),
        _external_gate(
            SessionAgentReadinessGateId.REAL_PROVIDER_ACCEPTANCE,
            "Requires real Codex acceptance with a dedicated provider credential.",
        ),
        _external_gate(
            SessionAgentReadinessGateId.REAL_SSH_PROMPT_INJECTION,
            "Requires prompt-injection acceptance against a real sshd and hostile target output.",
        ),
        _external_gate(
            SessionAgentReadinessGateId.MULTI_WORKER_FAILURE_INJECTION,
            "Requires multi-worker crash, retry, and cancellation failure injection.",
        ),
        _external_gate(
            SessionAgentReadinessGateId.LINUX_X86_64_ACCEPTANCE,
            "Requires Ubuntu or Debian x86_64 host acceptance.",
        ),
        _external_gate(
            SessionAgentReadinessGateId.LINUX_ARM64_ACCEPTANCE,
            "Requires Ubuntu or Debian ARM64 host acceptance.",
        ),
    ]
    return SessionAgentProductionReadinessReport(
        generated_at=now(),
        host_class=_host_class(),
        catalog_sha256=catalog_sha256,
        provider_configuration_sha256=_sha256(provider_configuration),
        gates=gates,
        production_ready=all(
            gate.status == SessionAgentReadinessStatus.PASSED for gate in gates
        ),
    )
