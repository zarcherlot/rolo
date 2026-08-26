from __future__ import annotations

import hashlib
import json
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.adapter_release_transfer import (
    AdapterReleaseSignatureVerifier,
    AdapterReleaseTransferManifest,
    Ed25519AdapterReleaseVerifier,
    load_verified_adapter_release_transfer,
)
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.enrollment import CollectorEnrollmentPinV4
from rolo.targets.evidence_v4 import MAX_CLOCK_SKEW
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)
from rolo.targets.package_signing import _read_bounded_key, ed25519_public_key_sha256
from rolo.targets.runtime_deployment import (
    TargetDescribeAttestation,
    TargetDescribeOutput,
    TargetDescribeRequest,
    verify_target_describe_attestation,
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_APPROVAL_PATTERN = r"^approval-[0-9a-f]{32}$"
_SIGNATURE_PATTERN = r"^[A-Za-z0-9+/]{86}==$"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class AdapterReleaseGateReceipt(BaseModel):
    """Controller Gate proof that one target-side `describe` matched a frozen release."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-gate-receipt/v1"] = (
        "rolo-adapter-release-gate-receipt/v1"
    )
    gate_status: Literal["PASSED"] = "PASSED"
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)
    sandbox_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    describe_request_sha256: str = Field(pattern=_SHA256_PATTERN)
    describe_attestation_sha256: str = Field(pattern=_SHA256_PATTERN)
    describe_payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    describe_output_sha256: str = Field(pattern=_SHA256_PATTERN)
    gate_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    verified_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def require_bounded_lifetime(self) -> AdapterReleaseGateReceipt:
        if self.expires_at <= self.verified_at:
            raise ValueError("adapter release gate receipt expiry must follow verification")
        if (self.expires_at - self.verified_at).total_seconds() > 600:
            raise ValueError("adapter release gate receipt lifetime exceeds ten minutes")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class AdapterReleaseGateSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-gate-signature/v1"] = (
        "rolo-adapter-release-gate-signature/v1"
    )
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        try:
            signature = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release gate signature is invalid base64") from exc
        if len(signature) != 64:
            raise ValueError("adapter release gate signature must be 64 bytes")
        return value


def _attestation_sha256(attestation: TargetDescribeAttestation) -> str:
    return hashlib.sha256(
        _canonical_json(attestation.model_dump(mode="json")).encode("utf-8")
    ).hexdigest()


def issue_adapter_release_gate_receipt(
    *,
    request: TargetDescribeRequest,
    attestation: TargetDescribeAttestation,
    pin: CollectorEnrollmentPinV4,
    expected_operations: dict[str, str],
    output: TargetDescribeOutput,
    transfer_manifest: AdapterReleaseTransferManifest,
    gate_report_sha256: str,
    signing_key_id: str,
    private_key_path: Path,
    now: datetime | None = None,
    lifetime_s: int = 300,
) -> tuple[AdapterReleaseGateReceipt, AdapterReleaseGateSignature]:
    """Verify target evidence first, then sign the controller's PASSED receipt."""

    observed_at = now or _utc_now()
    if not 1 <= lifetime_s <= 600:
        raise ValueError("adapter release gate receipt lifetime is out of bounds")
    verify_target_describe_attestation(
        attestation,
        request=request,
        pin=pin,
        expected_operations=expected_operations,
        output=output,
        now=observed_at,
    )
    if (
        transfer_manifest.target_id != request.target_id
        or transfer_manifest.robot_id != request.robot_id
        or transfer_manifest.release_id != request.release_id
        or transfer_manifest.release_manifest_sha256
        != request.release_manifest_sha256
        or transfer_manifest.bundle_manifest_sha256 != request.bundle_manifest_sha256
        or transfer_manifest.runtime_context_sha256 != request.runtime_context_sha256
    ):
        raise ValueError("adapter release Gate transfer binding mismatch")
    receipt = AdapterReleaseGateReceipt(
        target_id=request.target_id,
        robot_id=request.robot_id,
        collector_id=request.collector_id,
        descriptor_sha256=pin.descriptor_sha256,
        release_id=request.release_id,
        transfer_manifest_sha256=transfer_manifest.canonical_sha256(),
        release_manifest_sha256=request.release_manifest_sha256,
        bundle_manifest_sha256=request.bundle_manifest_sha256,
        runtime_context_sha256=request.runtime_context_sha256,
        sandbox_profile_sha256=request.sandbox_profile_sha256,
        describe_request_sha256=request.canonical_sha256(),
        describe_attestation_sha256=_attestation_sha256(attestation),
        describe_payload_sha256=attestation.payload_sha256,
        describe_output_sha256=attestation.output_sha256,
        gate_report_sha256=gate_report_sha256,
        verified_at=observed_at,
        expires_at=observed_at + timedelta(seconds=lifetime_s),
    )
    try:
        key = serialization.load_pem_private_key(
            _read_bounded_key(private_key_path, private=True),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("adapter release gate private signing key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("adapter release gate private signing key must be Ed25519")
    signature = key.sign(receipt.canonical_json().encode("utf-8"))
    return receipt, AdapterReleaseGateSignature(
        key_id=signing_key_id,
        receipt_sha256=receipt.canonical_sha256(),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def verify_adapter_release_gate_receipt(
    receipt: AdapterReleaseGateReceipt,
    signature: AdapterReleaseGateSignature,
    *,
    verifier: AdapterReleaseSignatureVerifier,
    now: datetime | None = None,
) -> None:
    observed_at = now or _utc_now()
    if signature.receipt_sha256 != receipt.canonical_sha256():
        raise ValueError("adapter release gate receipt digest mismatch")
    if observed_at < receipt.verified_at - MAX_CLOCK_SKEW:
        raise ValueError("adapter release gate receipt is from the future")
    if observed_at > receipt.expires_at + MAX_CLOCK_SKEW:
        raise ValueError("adapter release gate receipt is expired")
    verifier.verify_payload(
        signature.key_id,
        receipt.canonical_json().encode("utf-8"),
        b64decode(signature.signature_base64, validate=True),
    )


class AdapterReleaseActivationOperation(str, Enum):
    ACTIVATE = "ACTIVATE"
    ROLLBACK = "ROLLBACK"


class AdapterReleaseActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-activation-request/v1"] = (
        "rolo-adapter-release-activation-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    operation: AdapterReleaseActivationOperation
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_base64: str = Field(max_length=32_768)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    approval_id: str = Field(pattern=_APPROVAL_PATTERN)
    authorization: DeploymentAuthorizationProof | None = None
    gate_receipt: AdapterReleaseGateReceipt | None = None
    gate_signature: AdapterReleaseGateSignature | None = None
    expect_current_present: bool | None = None
    expected_current_transfer_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )

    @field_validator("signing_public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release activation public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("adapter release activation public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def require_operation_inputs(self) -> AdapterReleaseActivationRequest:
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.signing_public_key_sha256:
            raise ValueError("adapter release activation public key digest mismatch")
        if self.operation == AdapterReleaseActivationOperation.ACTIVATE:
            if self.gate_receipt is None or self.gate_signature is None:
                raise ValueError("adapter release activation requires a Gate receipt")
            if (
                self.gate_receipt.target_id != self.target_id
                or self.gate_receipt.robot_id != self.robot_id
                or self.gate_receipt.release_id != self.release_id
                or self.gate_receipt.transfer_manifest_sha256
                != self.transfer_manifest_sha256
            ):
                raise ValueError("adapter release activation Gate receipt binding mismatch")
        elif self.gate_receipt is not None or self.gate_signature is not None:
            raise ValueError("adapter release rollback does not accept a new Gate receipt")
        if self.operation == AdapterReleaseActivationOperation.ROLLBACK:
            if self.expected_current_transfer_manifest_sha256 is None:
                raise ValueError("adapter release rollback requires current CAS digest")
            if self.expect_current_present is not None:
                raise ValueError("adapter release rollback rejects current presence input")
        elif (
            self.expect_current_present is False
            and self.expected_current_transfer_manifest_sha256 is not None
        ):
            raise ValueError("absent current expectation cannot include a current digest")
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.target_id,
            expected_approval_id=self.approval_id,
        )
        return self

    def public_key_bytes(self) -> bytes:
        return b64decode(self.signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class AdapterReleaseActiveRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    staged_root: str = Field(min_length=1, max_length=4096)
    gate_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    activated_at: datetime


class AdapterReleaseActiveIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-active-index/v1"] = (
        "rolo-adapter-release-active-index/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    current: AdapterReleaseActiveRecord
    previous: AdapterReleaseActiveRecord | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def require_identity_binding(self) -> AdapterReleaseActiveIndex:
        records = [self.current, *([self.previous] if self.previous is not None else [])]
        if any(
            item.target_id != self.target_id or item.robot_id != self.robot_id
            for item in records
        ):
            raise ValueError("adapter release active index identity mismatch")
        if self.previous is not None and (
            self.previous.transfer_manifest_sha256
            == self.current.transfer_manifest_sha256
        ):
            raise ValueError("adapter release active index current and previous must differ")
        return self


class AdapterReleaseActivationStatus(str, Enum):
    ACTIVATED = "ACTIVATED"
    ALREADY_ACTIVE = "ALREADY_ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"


class AdapterReleaseActivationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-activation-result/v1"] = (
        "rolo-adapter-release-activation-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation: AdapterReleaseActivationOperation
    status: AdapterReleaseActivationStatus
    index: AdapterReleaseActiveIndex


class AdapterReleaseActivationErrorCode(str, Enum):
    INVALID_GATE = "INVALID_GATE"
    INVALID_STAGE = "INVALID_STAGE"
    STATE_CONFLICT = "STATE_CONFLICT"
    IO_ERROR = "IO_ERROR"


class AdapterReleaseActivationExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-activation-execution-result/v1"] = (
        "rolo-adapter-release-activation-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation: AdapterReleaseActivationOperation
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    transport_error_code: TargetExecutionErrorCode | None = None
    activation_error_code: AdapterReleaseActivationErrorCode | None = None
    result: AdapterReleaseActivationResult | None = None

    @model_validator(mode="after")
    def require_consistent_execution(
        self,
    ) -> AdapterReleaseActivationExecutionResult:
        errors = int(self.transport_error_code is not None) + int(
            self.activation_error_code is not None
        )
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if errors or self.result is None:
                raise ValueError("successful adapter release activation is incomplete")
        elif errors != 1 or self.result is not None:
            raise ValueError("failed adapter release activation is inconsistent")
        if self.result is not None and (
            self.result.request_id != self.request_id
            or self.result.request_sha256 != self.request_sha256
            or self.result.operation != self.operation
        ):
            raise ValueError("adapter release activation execution binding mismatch")
        return self


class AdapterReleaseActivationStateConflict(ValueError):
    pass


class AdapterReleaseActivator:
    """Atomically switch the current index only after a signed PASSED Gate receipt."""

    def __init__(self, install_root: Path) -> None:
        self.install_root = install_root.expanduser().absolute()
        if self.install_root.is_symlink():
            raise ValueError("adapter release install root cannot be a symbolic link")

    def _current_path(self, robot_id: str) -> Path:
        return self.install_root / "robots" / robot_id / "current.json"

    @staticmethod
    def _load_index(path: Path) -> AdapterReleaseActiveIndex:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("adapter release active index exceeds its size limit")
        return AdapterReleaseActiveIndex.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _stage_root(
        self,
        *,
        robot_id: str,
        release_id: str,
        release_manifest_sha256: str,
    ) -> Path:
        return (
            self.install_root
            / "robots"
            / robot_id
            / "staged"
            / f"{release_id}-{release_manifest_sha256[:16]}"
        )

    def _validate_index_paths(self, index: AdapterReleaseActiveIndex) -> None:
        records = [index.current, *([index.previous] if index.previous is not None else [])]
        for record in records:
            expected = self._stage_root(
                robot_id=record.robot_id,
                release_id=record.release_id,
                release_manifest_sha256=record.release_manifest_sha256,
            )
            actual = Path(record.staged_root)
            if actual.is_symlink() or actual.resolve(strict=False) != expected.resolve(
                strict=False
            ):
                raise ValueError("adapter release active index staged path mismatch")

    def execute(
        self,
        request: AdapterReleaseActivationRequest,
        *,
        now: datetime | None = None,
    ) -> AdapterReleaseActivationResult:
        observed_at = now or _utc_now()
        verifier = Ed25519AdapterReleaseVerifier(
            {request.signing_key_id: request.public_key_bytes()}
        )
        current_path = self._current_path(request.robot_id)
        if current_path.is_symlink():
            raise ValueError("adapter release current index cannot be a symbolic link")
        with interprocess_lock(current_path):
            existing = self._load_index(current_path) if current_path.is_file() else None
            if existing is not None:
                self._validate_index_paths(existing)
            if existing is not None and (
                existing.target_id != request.target_id
                or existing.robot_id != request.robot_id
            ):
                raise AdapterReleaseActivationStateConflict(
                    "adapter release current index identity mismatch"
                )
            if request.operation == AdapterReleaseActivationOperation.ROLLBACK:
                return self._rollback(
                    request,
                    existing=existing,
                    verifier=verifier,
                    current_path=current_path,
                    now=observed_at,
                )
            assert request.gate_receipt is not None
            assert request.gate_signature is not None
            verify_adapter_release_gate_receipt(
                request.gate_receipt,
                request.gate_signature,
                verifier=verifier,
                now=observed_at,
            )
            if request.gate_signature.key_id != request.signing_key_id:
                raise ValueError("adapter release activation Gate signing key mismatch")
            if (
                existing is not None
                and existing.current.transfer_manifest_sha256
                == request.transfer_manifest_sha256
            ):
                return AdapterReleaseActivationResult(
                    request_id=request.request_id,
                    request_sha256=request.canonical_sha256(),
                    operation=request.operation,
                    status=AdapterReleaseActivationStatus.ALREADY_ACTIVE,
                    index=existing,
                )
            self._check_activation_cas(request, existing)
            receipt = request.gate_receipt
            stage_root = self._stage_root(
                robot_id=request.robot_id,
                release_id=request.release_id,
                release_manifest_sha256=receipt.release_manifest_sha256,
            )
            _, transfer, signature, _ = load_verified_adapter_release_transfer(
                stage_root,
                verifier,
            )
            if (
                transfer.canonical_sha256() != request.transfer_manifest_sha256
                or transfer.release_manifest_sha256 != receipt.release_manifest_sha256
                or transfer.bundle_manifest_sha256 != receipt.bundle_manifest_sha256
                or transfer.runtime_context_sha256 != receipt.runtime_context_sha256
                or signature.key_id != request.signing_key_id
            ):
                raise ValueError("adapter release activation staged release mismatch")
            record = AdapterReleaseActiveRecord(
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                release_manifest_sha256=transfer.release_manifest_sha256,
                staged_root=str(stage_root),
                gate_receipt_sha256=receipt.canonical_sha256(),
                activated_at=observed_at,
            )
            index = AdapterReleaseActiveIndex(
                target_id=request.target_id,
                robot_id=request.robot_id,
                current=record,
                previous=existing.current if existing is not None else None,
                updated_at=observed_at,
            )
            atomic_write_text(
                current_path,
                index.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
            return AdapterReleaseActivationResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                status=AdapterReleaseActivationStatus.ACTIVATED,
                index=index,
            )

    @staticmethod
    def _check_activation_cas(
        request: AdapterReleaseActivationRequest,
        existing: AdapterReleaseActiveIndex | None,
    ) -> None:
        if request.expect_current_present is True and existing is None:
            raise AdapterReleaseActivationStateConflict(
                "adapter release activation expected an active release"
            )
        if request.expect_current_present is False and existing is not None:
            raise AdapterReleaseActivationStateConflict(
                "adapter release activation expected no active release"
            )
        if request.expected_current_transfer_manifest_sha256 is not None and (
            existing is None
            or existing.current.transfer_manifest_sha256
            != request.expected_current_transfer_manifest_sha256
        ):
            raise AdapterReleaseActivationStateConflict(
                "adapter release activation current digest CAS mismatch"
            )

    def _rollback(
        self,
        request: AdapterReleaseActivationRequest,
        *,
        existing: AdapterReleaseActiveIndex | None,
        verifier: AdapterReleaseSignatureVerifier,
        current_path: Path,
        now: datetime,
    ) -> AdapterReleaseActivationResult:
        if existing is None or existing.previous is None:
            raise AdapterReleaseActivationStateConflict(
                "adapter release rollback has no previous release"
            )
        if (
            existing.current.transfer_manifest_sha256
            != request.expected_current_transfer_manifest_sha256
            or existing.previous.release_id != request.release_id
            or existing.previous.transfer_manifest_sha256
            != request.transfer_manifest_sha256
        ):
            raise AdapterReleaseActivationStateConflict(
                "adapter release rollback CAS or target mismatch"
            )
        previous_root = Path(existing.previous.staged_root)
        expected_previous_root = self._stage_root(
            robot_id=request.robot_id,
            release_id=existing.previous.release_id,
            release_manifest_sha256=existing.previous.release_manifest_sha256,
        )
        if (
            previous_root.is_symlink()
            or previous_root.resolve(strict=False)
            != expected_previous_root.resolve(strict=False)
        ):
            raise ValueError("adapter release rollback staged path mismatch")
        _, transfer, signature, _ = load_verified_adapter_release_transfer(
            previous_root,
            verifier,
        )
        if (
            transfer.canonical_sha256() != request.transfer_manifest_sha256
            or signature.key_id != request.signing_key_id
        ):
            raise ValueError("adapter release rollback staged release mismatch")
        index = AdapterReleaseActiveIndex(
            target_id=request.target_id,
            robot_id=request.robot_id,
            current=existing.previous.model_copy(update={"activated_at": now}),
            previous=existing.current,
            updated_at=now,
        )
        atomic_write_text(
            current_path,
            index.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
        )
        return AdapterReleaseActivationResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            operation=request.operation,
            status=AdapterReleaseActivationStatus.ROLLED_BACK,
            index=index,
        )
