from __future__ import annotations

import hashlib
import hmac
import json
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.models import ProbeResult
from rolo.stages.adapt.target_evidence import (
    MAX_CLOCK_SKEW,
    MAX_REQUEST_LIFETIME,
    EvidenceDeploymentMode,
    TargetEvidenceRequest,
    TargetExecutableHelpEvidence,
    bind_target_executable_routes,
    collect_target_evidence_payload,
)
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.enrollment import (
    CollectorEnrollmentPinV4,
    TargetEnrollmentService,
)
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SIGNATURE_PATTERN = r"^[A-Za-z0-9+/]{86}==$"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _signature_bytes(value: str) -> bytes:
    try:
        payload = b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("collector v4 bundle signature is invalid base64") from exc
    if len(payload) != 64:
        raise ValueError("collector v4 bundle signature must contain exactly 64 bytes")
    return payload


class TargetEvidenceBundleV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-bundle/v4"] = (
        "robot-target-evidence-bundle/v4"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    robot_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    configuration_sha256: str = Field(pattern=_SHA256_PATTERN)
    key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    request_nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(
        min_length=1,
        max_length=3,
    )
    access: Literal["READ_ONLY"] = "READ_ONLY"
    collected_at: datetime
    probes: dict[str, ProbeResult]
    executable_help: list[TargetExecutableHelpEvidence] = Field(
        default_factory=list,
        max_length=4,
    )
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_ed25519_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_ed25519_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        _signature_bytes(value)
        return value

    @model_validator(mode="after")
    def require_canonical_collections(self) -> TargetEvidenceBundleV4:
        if len(self.requested_layers) != len(set(self.requested_layers)):
            raise ValueError("collector v4 requested layers must be unique")
        identities = [item.executable_id for item in self.executable_help]
        if identities != sorted(set(identities)):
            raise ValueError("collector v4 executable help IDs must be unique and sorted")
        return self

    def unsigned_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude={"payload_sha256", "signature_ed25519_base64"},
        )


class TargetEvidenceCollectionRequestV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-evidence-collection-request/v4"] = (
        "rolo-target-evidence-collection-request/v4"
    )
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    evidence_request: TargetEvidenceRequest
    approval_id: str | None = Field(
        default=None,
        pattern=r"^approval-[0-9a-f]{32}$",
    )
    authorization: DeploymentAuthorizationProof | None = None
    timeout_s: float = Field(default=45.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def bind_runtime_authorization(self) -> TargetEvidenceCollectionRequestV4:
        if self.authorization is not None and self.approval_id is None:
            raise ValueError(
                "runtime evidence authorization requires an approval"
            )
        if self.approval_id is not None:
            validate_deployment_request_authorization_binding(
                self,
                authorization=self.authorization,
                expected_target_id=self.target_id,
                expected_approval_id=self.approval_id,
            )
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetEvidenceCollectionResultV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-evidence-collection-result/v4"] = (
        "rolo-target-evidence-collection-result/v4"
    )
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    robot_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    bundle: TargetEvidenceBundleV4 | None = None

    @model_validator(mode="after")
    def require_consistent_result(self) -> TargetEvidenceCollectionResultV4:
        succeeded = self.execution_status == TargetExecutionStatus.SUCCEEDED
        if succeeded and (self.error_code is not None or self.bundle is None):
            raise ValueError("successful target evidence v4 collection is incomplete")
        if not succeeded and (self.error_code is None or self.bundle is not None):
            raise ValueError("failed target evidence v4 collection result is inconsistent")
        if self.bundle is not None and (
            self.bundle.target_id != self.target_id
            or self.bundle.robot_id != self.robot_id
        ):
            raise ValueError("target evidence v4 collection bundle identity mismatch")
        return self


def collect_target_evidence_v4(
    request: TargetEvidenceRequest,
    service: TargetEnrollmentService,
    *,
    now: datetime | None = None,
    environment: dict[str, str] | None = None,
) -> TargetEvidenceBundleV4:
    """Collect and sign one v4 bundle without loading private key outside target service."""

    record = service.current_record()
    descriptor = record.descriptor
    base = collect_target_evidence_payload(
        request,
        schema_version="robot-target-evidence-bundle/v4",
        robot_id=descriptor.robot_id,
        collector_id=descriptor.collector_id,
        target_host_fingerprint=descriptor.target_host_fingerprint,
        help_executables=record.configuration.help_executables,
        ros_setup_files=record.configuration.ros_setup_files,
        identity_fields={
            "target_id": descriptor.target_id,
            "descriptor_sha256": descriptor.canonical_sha256(),
            "configuration_sha256": descriptor.configuration_sha256,
            "key_id": descriptor.key_id,
        },
        now=now,
        environment=environment,
    )
    payload_sha256 = hashlib.sha256(_canonical_json(base)).hexdigest()
    signature = service.sign_current(
        descriptor.collector_id,
        payload_sha256.encode("ascii"),
    )
    return TargetEvidenceBundleV4(
        **base,
        payload_sha256=payload_sha256,
        signature_ed25519_base64=b64encode(signature).decode("ascii"),
    )


def verify_target_evidence_v4(
    bundle: TargetEvidenceBundleV4,
    *,
    pin: CollectorEnrollmentPinV4,
    request: TargetEvidenceRequest,
    deployment_mode: EvidenceDeploymentMode,
    now: datetime | None = None,
) -> dict[str, ProbeResult]:
    """Verify target, request, freshness, payload and Ed25519 signature before binding probes."""

    observed_at = now or _utc_now()
    descriptor = pin.descriptor
    configuration = pin.configuration
    if (
        bundle.target_id != descriptor.target_id
        or bundle.robot_id != descriptor.robot_id
        or bundle.collector_id != descriptor.collector_id
        or bundle.target_host_fingerprint != descriptor.target_host_fingerprint
        or bundle.descriptor_sha256 != descriptor.canonical_sha256()
        or bundle.configuration_sha256 != configuration.canonical_sha256()
        or bundle.key_id != descriptor.key_id
    ):
        raise ValueError("collector v4 bundle identity or public-key pin mismatch")
    if request.robot_id != bundle.robot_id or request.nonce != bundle.request_nonce:
        raise ValueError("collector v4 bundle does not answer the issued request")
    if bundle.requested_layers != request.requested_layers:
        raise ValueError("collector v4 bundle layer set differs from request")
    if [item.executable_id for item in bundle.executable_help] != (
        request.requested_executable_help_ids
    ):
        raise ValueError("collector v4 executable help differs from request")
    if bundle.collected_at < request.issued_at - MAX_CLOCK_SKEW:
        raise ValueError("collector v4 bundle predates its request")
    if bundle.collected_at > request.expires_at + MAX_CLOCK_SKEW:
        raise ValueError("collector v4 bundle was collected after request expiry")
    if bundle.collected_at > observed_at + MAX_CLOCK_SKEW:
        raise ValueError("collector v4 bundle timestamp is in the future")
    if observed_at - bundle.collected_at > MAX_REQUEST_LIFETIME + MAX_CLOCK_SKEW:
        raise ValueError("collector v4 bundle is stale")
    if set(bundle.probes) != set(bundle.requested_layers):
        raise ValueError("collector v4 bundle probe keys differ from requested layers")
    allowed_help = {item.executable_id: item for item in configuration.help_executables}
    for item in bundle.executable_help:
        allowed = allowed_help.get(item.executable_id)
        if (
            allowed is None
            or item.path != allowed.path
            or item.executable_sha256 != allowed.sha256
        ):
            raise ValueError("collector v4 executable help is outside pinned configuration")
        if hashlib.sha256(item.output_text.encode("utf-8")).hexdigest() != (
            item.output_sha256
        ):
            raise ValueError("collector v4 executable help output digest mismatch")
    actual_payload_sha256 = hashlib.sha256(
        _canonical_json(bundle.unsigned_payload())
    ).hexdigest()
    if not hmac.compare_digest(actual_payload_sha256, bundle.payload_sha256):
        raise ValueError("collector v4 bundle payload digest mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(descriptor.public_key_bytes()).verify(
            _signature_bytes(bundle.signature_ed25519_base64),
            bundle.payload_sha256.encode("ascii"),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("collector v4 bundle signature mismatch") from exc
    bound: dict[str, ProbeResult] = {}
    for layer, probe in bundle.probes.items():
        data = dict(probe.data)
        data["target_evidence"] = {
            "schema_version": "robot-target-evidence-binding/v4",
            "target_id": bundle.target_id,
            "robot_id": bundle.robot_id,
            "collector_id": bundle.collector_id,
            "target_host_fingerprint": bundle.target_host_fingerprint,
            "descriptor_sha256": bundle.descriptor_sha256,
            "configuration_sha256": bundle.configuration_sha256,
            "key_id": bundle.key_id,
            "bundle_payload_sha256": bundle.payload_sha256,
            "access": bundle.access,
            "deployment_mode": deployment_mode.value,
            "collected_at": bundle.collected_at.isoformat(),
        }
        if layer == "linux":
            data["target_evidence"]["executable_help"] = [
                item.model_dump(mode="json") for item in bundle.executable_help
            ]
        verified = probe.model_copy(update={"data": data})
        if layer == "linux":
            verified = bind_target_executable_routes(
                verified,
                bundle.executable_help,
                bundle_payload_sha256=bundle.payload_sha256,
                observed_at=bundle.collected_at,
            )
        bound[layer] = verified
    return bound
