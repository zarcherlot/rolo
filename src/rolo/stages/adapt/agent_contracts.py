from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.hashing import sha256_bytes
from rolo.core.models import utc_now

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_OPERATION_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
_SKILL_PATTERN = r"^rolo-[a-z0-9]+(?:-[a-z0-9]+)*$"
_SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
_NONCE_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"
_OPERATION_RE = re.compile(_OPERATION_PATTERN)

CanonicalOperationId = Annotated[str, Field(pattern=_OPERATION_PATTERN, max_length=160)]
Sha256Digest = Annotated[str, Field(pattern=_SHA256_PATTERN)]

MAX_REGISTRY_OPERATIONS = 2_048
MAX_PROPOSAL_EVIDENCE_REFS = 64
MAX_PROPOSAL_RESOURCE_REFS = 32
MAX_REQUESTED_VERIFICATIONS = 16
MAX_SESSION_TTL = timedelta(hours=24)


class ProposalConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"


class AgentDisposition(str, Enum):
    """Agent judgment over one deterministic semantic binding.

    This is advisory until Rolo validates the referenced frozen evidence and
    any evidence-tool receipts.
    """

    ACCEPT = "ACCEPT"
    DEFER = "DEFER"
    REJECT = "REJECT"


class AgentEvidenceCondition(str, Enum):
    """Read-only facts that the mapping evidence tool can reproduce."""

    BINDING_MATCH = "BINDING_MATCH"
    ROUTE_OBSERVED = "ROUTE_OBSERVED"
    INTERFACE_SCHEMA_KNOWN = "INTERFACE_SCHEMA_KNOWN"
    PROVIDER_IDENTIFIED = "PROVIDER_IDENTIFIED"
    RUNTIME_REVISION_KNOWN = "RUNTIME_REVISION_KNOWN"


class AgentEvidenceToolReceipt(BaseModel):
    """Agent-returned receipt that Rolo independently recomputes."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: Sha256Digest
    operation: CanonicalOperationId
    route_resource_id: str = Field(min_length=1, max_length=256)
    condition: AgentEvidenceCondition
    satisfied: bool
    result_sha256: Sha256Digest


class AgentRouteDisposition(BaseModel):
    """Agent decision for exactly one route in a deterministic binding."""

    model_config = ConfigDict(extra="forbid")

    route_resource_id: str = Field(min_length=1, max_length=256)
    disposition: AgentDisposition
    rationale: str = Field(min_length=8, max_length=1_000)
    tool_receipt_ids: list[Sha256Digest] = Field(default_factory=list, max_length=16)

    @field_validator("tool_receipt_ids")
    @classmethod
    def require_unique_receipts(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("route disposition tool receipts must be unique")
        return value


class VerificationRequestKind(str, Enum):
    ROUTE_OBSERVATION = "ROUTE_OBSERVATION"
    EXECUTABLE_INSPECTION = "EXECUTABLE_INSPECTION"
    HARDWARE_INSPECTION = "HARDWARE_INSPECTION"
    CONTRACT_REVIEW = "CONTRACT_REVIEW"


class AgentStopReason(str, Enum):
    COMPLETED = "COMPLETED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NO_MORE_ACTIONS = "NO_MORE_ACTIONS"
    BLOCKED = "BLOCKED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


class AgentArtifactProvenance(BaseModel):
    """Bounded, secret-free identity for one Agent-produced artifact."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(pattern=_SKILL_PATTERN, max_length=64)
    skill_version: str = Field(pattern=_SEMVER_PATTERN)
    model_id: str = Field(min_length=1, max_length=160)
    input_artifact_sha256: dict[str, Sha256Digest] = Field(
        default_factory=dict,
        max_length=64,
    )
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("input_artifact_sha256")
    @classmethod
    def validate_input_artifact_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        for name, _digest in value.items():
            if not name or len(name) > 160:
                raise ValueError("input artifact names must contain 1-160 characters")
        return value


class AgentBudgetUsage(BaseModel):
    """Auditable resource use and stopping reason for one bounded Agent run."""

    model_config = ConfigDict(extra="forbid")

    rounds: int = Field(ge=0, le=256)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    result_bytes: int = Field(ge=0)
    stop_reason: AgentStopReason


class VerificationRequest(BaseModel):
    """One deterministic follow-up requested by an untrusted mapping Agent."""

    model_config = ConfigDict(extra="forbid")

    kind: VerificationRequestKind
    subject_ref: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=8, max_length=1_000)


class AgentOperationProposal(BaseModel):
    """Untrusted mapping proposal that only references collected target evidence."""

    model_config = ConfigDict(extra="forbid")

    operation: CanonicalOperationId
    evidence_refs: list[str] = Field(
        min_length=1,
        max_length=MAX_PROPOSAL_EVIDENCE_REFS,
    )
    route_resource_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_PROPOSAL_RESOURCE_REFS,
    )
    executable_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_PROPOSAL_RESOURCE_REFS,
    )
    hardware_resource_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_PROPOSAL_RESOURCE_REFS,
    )
    confidence: ProposalConfidence
    disposition: AgentDisposition = AgentDisposition.ACCEPT
    rationale: str = Field(min_length=8, max_length=2_000)
    route_dispositions: list[AgentRouteDisposition] = Field(default_factory=list, max_length=32)
    tool_receipts: list[AgentEvidenceToolReceipt] = Field(default_factory=list, max_length=128)
    counter_evidence_refs: list[str] = Field(default_factory=list, max_length=16)
    requested_verification: list[VerificationRequest] = Field(
        default_factory=list,
        max_length=MAX_REQUESTED_VERIFICATIONS,
    )

    @field_validator(
        "evidence_refs",
        "route_resource_ids",
        "executable_ids",
        "hardware_resource_ids",
        "counter_evidence_refs",
    )
    @classmethod
    def require_unique_bounded_refs(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 256 for item in value):
            raise ValueError("proposal references must contain 1-256 characters")
        if len(value) != len(set(value)):
            raise ValueError("proposal references must be unique within each field")
        return value

    @model_validator(mode="after")
    def validate_evidence_binding(self) -> AgentOperationProposal:
        if not (self.route_resource_ids or self.executable_ids or self.hardware_resource_ids):
            raise ValueError("operation proposal requires at least one target resource binding")
        overlap = set(self.evidence_refs) & set(self.counter_evidence_refs)
        if overlap:
            raise ValueError("supporting and counter evidence references must be disjoint")
        route_ids = [item.route_resource_id for item in self.route_dispositions]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route dispositions must be unique")
        receipt_ids = [item.receipt_id for item in self.tool_receipts]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("evidence tool receipts must be unique")
        return self


class OperationProposalBundle(BaseModel):
    """Registry-bound Agent proposals awaiting deterministic Rolo validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-operation-proposal-bundle/v1",
        "rolo-operation-proposal-bundle/v2",
    ] = "rolo-operation-proposal-bundle/v2"
    robot_id: str = Field(min_length=1, max_length=128)
    discovery_id: str = Field(min_length=1, max_length=128)
    target_fingerprint_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_version: str = Field(min_length=1, max_length=128)
    registry_sha256: str = Field(pattern=_SHA256_PATTERN)
    contract_catalog_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_operation_count: int = Field(ge=1, le=MAX_REGISTRY_OPERATIONS)
    proposals: list[AgentOperationProposal] = Field(
        default_factory=list,
        max_length=MAX_REGISTRY_OPERATIONS,
    )
    unmapped_capabilities: list[str] = Field(default_factory=list, max_length=128)
    unknowns: list[str] = Field(default_factory=list, max_length=128)
    budget_usage: AgentBudgetUsage
    provenance: AgentArtifactProvenance

    @field_validator("unmapped_capabilities", "unknowns")
    @classmethod
    def validate_bounded_notes(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 1_000 for item in value):
            raise ValueError("bundle notes must contain 1-1000 characters")
        if len(value) != len(set(value)):
            raise ValueError("bundle notes must be unique")
        return value

    @model_validator(mode="after")
    def validate_unique_operations(self) -> OperationProposalBundle:
        operations = [proposal.operation for proposal in self.proposals]
        if len(operations) != len(set(operations)):
            raise ValueError("operation proposal bundle contains duplicate operations")
        return self


class ToolSessionBudget(BaseModel):
    """Hard invocation limits enforced independently of the downstream Agent."""

    model_config = ConfigDict(extra="forbid")

    max_calls: int = Field(ge=1, le=10_000)
    max_elapsed_s: float = Field(gt=0, le=86_400)
    max_result_bytes: int = Field(ge=1, le=1_000_000_000)


class ToolSessionDescriptor(BaseModel):
    """Immutable, release-bound tool authority handed to a downstream Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-session/v1"] = "rolo-tool-session/v1"
    session_id: str = Field(min_length=1, max_length=128)
    nonce: str = Field(pattern=_NONCE_PATTERN)
    robot_id: str = Field(min_length=1, max_length=128)
    release_id: str = Field(min_length=1, max_length=128)
    target_fingerprint_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_version: str = Field(min_length=1, max_length=128)
    registry_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_operation_count: int = Field(ge=1, le=MAX_REGISTRY_OPERATIONS)
    contract_catalog_sha256: str = Field(pattern=_SHA256_PATTERN)
    tool_catalog_sha256: str = Field(pattern=_SHA256_PATTERN)
    state_graph_sha256: str = Field(pattern=_SHA256_PATTERN)
    allowed_operations: list[CanonicalOperationId] = Field(
        min_length=1,
        max_length=MAX_REGISTRY_OPERATIONS,
    )
    contract_sha256: dict[CanonicalOperationId, Sha256Digest] = Field(
        min_length=1,
        max_length=MAX_REGISTRY_OPERATIONS,
    )
    caller: str = Field(min_length=1, max_length=128)
    stage: Literal["diagnose", "verify"]
    max_risk: Literal["R0", "R1"] = "R0"
    policy_version: str = Field(min_length=1, max_length=128)
    budget: ToolSessionBudget
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    @field_validator("allowed_operations")
    @classmethod
    def validate_allowed_operations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("allowed operations must be unique")
        return value

    @model_validator(mode="after")
    def validate_session_bounds(self) -> ToolSessionDescriptor:
        if set(self.allowed_operations) != set(self.contract_sha256):
            raise ValueError("contract hashes must exactly cover allowed operations")
        if self.expires_at <= self.created_at:
            raise ValueError("tool session expiry must be after creation")
        if self.expires_at - self.created_at > MAX_SESSION_TTL:
            raise ValueError("tool session TTL exceeds 24 hours")
        return self


class OperationRegistryResolver(Protocol):
    """Quantity-independent view used by deterministic contract validators."""

    @property
    def registry_version(self) -> str: ...

    @property
    def registry_sha256(self) -> str: ...

    @property
    def contract_catalog_sha256(self) -> str: ...

    @property
    def operation_count(self) -> int: ...

    def contract_sha256_for(self, operation: str) -> str | None: ...


def registry_identity_sha256(
    *,
    registry_version: str,
    contract_catalog_sha256: str,
    contract_sha256: Mapping[str, str],
) -> str:
    """Hash the exact Operation set and contract identities without serializing Registry code."""

    if not registry_version or len(registry_version) > 128:
        raise ValueError("registry version must contain 1-128 characters")
    if len(contract_catalog_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in contract_catalog_sha256
    ):
        raise ValueError("contract catalog digest must be lowercase SHA-256")
    if not contract_sha256 or len(contract_sha256) > MAX_REGISTRY_OPERATIONS:
        raise ValueError("Registry identity requires a bounded, non-empty Operation set")
    for operation, digest in contract_sha256.items():
        if not _OPERATION_RE.fullmatch(operation):
            raise ValueError(f"invalid canonical Operation ID: {operation}")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid contract digest for Operation: {operation}")
    payload = json.dumps(
        {
            "schema_version": "rolo-registry-identity/v1",
            "registry_version": registry_version,
            "contract_catalog_sha256": contract_catalog_sha256,
            "operations": [
                {"operation": operation, "contract_sha256": contract_sha256[operation]}
                for operation in sorted(contract_sha256)
            ],
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256_bytes(payload.encode())


def _validate_registry_identity(
    *,
    registry_version: str,
    registry_sha256: str,
    contract_catalog_sha256: str,
    registry_operation_count: int,
    resolver: OperationRegistryResolver,
) -> None:
    actual = (
        registry_version,
        registry_sha256,
        contract_catalog_sha256,
        registry_operation_count,
    )
    expected = (
        resolver.registry_version,
        resolver.registry_sha256,
        resolver.contract_catalog_sha256,
        resolver.operation_count,
    )
    if actual != expected:
        raise ValueError("artifact Registry identity does not match the active Registry")


def validate_operation_proposal_bundle(
    bundle: OperationProposalBundle,
    resolver: OperationRegistryResolver,
) -> None:
    """Reject stale identities and operations outside the injected Registry."""

    _validate_registry_identity(
        registry_version=bundle.registry_version,
        registry_sha256=bundle.registry_sha256,
        contract_catalog_sha256=bundle.contract_catalog_sha256,
        registry_operation_count=bundle.registry_operation_count,
        resolver=resolver,
    )
    unknown = sorted(
        proposal.operation
        for proposal in bundle.proposals
        if resolver.contract_sha256_for(proposal.operation) is None
    )
    if unknown:
        raise ValueError(f"operation proposals are outside the active Registry: {unknown}")


def validate_tool_session_descriptor(
    session: ToolSessionDescriptor,
    resolver: OperationRegistryResolver,
) -> None:
    """Require exact Registry and contract identity before exposing a tool session."""

    _validate_registry_identity(
        registry_version=session.registry_version,
        registry_sha256=session.registry_sha256,
        contract_catalog_sha256=session.contract_catalog_sha256,
        registry_operation_count=session.registry_operation_count,
        resolver=resolver,
    )
    mismatched: list[str] = []
    for operation in session.allowed_operations:
        expected = resolver.contract_sha256_for(operation)
        if expected is None or session.contract_sha256[operation] != expected:
            mismatched.append(operation)
    if mismatched:
        raise ValueError(f"tool session contract identity mismatch: {sorted(mismatched)}")


def registry_contract_hashes(
    operations: Sequence[str],
    resolver: OperationRegistryResolver,
) -> Mapping[str, str]:
    """Resolve exact hashes for a bounded session without exposing the full Registry."""

    resolved: dict[str, str] = {}
    for operation in operations:
        digest = resolver.contract_sha256_for(operation)
        if digest is None:
            raise ValueError(f"operation is outside the active Registry: {operation}")
        resolved[operation] = digest
    return resolved
