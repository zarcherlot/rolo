from __future__ import annotations

import hashlib
import json
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.stages.adapt.models import AdapterReleaseIndex
from rolo.targets.adapter_release_activation import (
    AdapterReleaseActiveIndex,
    AdapterReleaseActiveRecord,
)
from rolo.targets.adapter_release_transfer import (
    AdapterReleaseSignatureVerifier,
    AdapterReleaseTransferManifest,
    Ed25519AdapterReleaseVerifier,
    load_verified_adapter_release_transfer,
)
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)
from rolo.targets.package_signing import ed25519_public_key_sha256

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_MAX_ACTIVE_INDEX_BYTES = 1024 * 1024


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class AdapterReleaseDesiredState(BaseModel):
    """Controller authority projected onto one target deployment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-desired-state/v1"] = (
        "rolo-adapter-release-desired-state/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    controller_release_index_sha256: str = Field(pattern=_SHA256_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


def build_adapter_release_desired_state(
    *,
    target_id: str,
    controller_index: AdapterReleaseIndex,
    transfer_manifest: AdapterReleaseTransferManifest,
) -> AdapterReleaseDesiredState:
    """Bind the controller's published index to the exact target transfer."""

    if (
        transfer_manifest.target_id != target_id
        or transfer_manifest.robot_id != controller_index.robot_id
        or transfer_manifest.release_id != controller_index.release_id
        or transfer_manifest.release_manifest_sha256 != controller_index.manifest_sha256
    ):
        raise ValueError("controller release index and target transfer do not match")
    return AdapterReleaseDesiredState(
        target_id=target_id,
        robot_id=controller_index.robot_id,
        release_id=controller_index.release_id,
        controller_release_index_sha256=_canonical_sha256(
            controller_index.model_dump(mode="json")
        ),
        transfer_manifest_sha256=transfer_manifest.canonical_sha256(),
        release_manifest_sha256=transfer_manifest.release_manifest_sha256,
        bundle_manifest_sha256=transfer_manifest.bundle_manifest_sha256,
        runtime_context_sha256=transfer_manifest.runtime_context_sha256,
    )


class AdapterReleaseStatusRequest(BaseModel):
    """Read-only query binding target observation to one controller desired state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-status-request/v1"] = (
        "rolo-adapter-release-status-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    desired: AdapterReleaseDesiredState
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_base64: str = Field(max_length=32_768)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    timeout_s: float = Field(default=60.0, ge=1.0, le=300.0)

    @field_validator("signing_public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release status public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("adapter release status public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def require_public_key_digest(self) -> AdapterReleaseStatusRequest:
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.signing_public_key_sha256:
            raise ValueError("adapter release status public key digest mismatch")
        return self

    def public_key_bytes(self) -> bytes:
        return b64decode(self.signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


def build_adapter_release_status_request(
    *,
    request_id: str,
    desired: AdapterReleaseDesiredState,
    signing_key_id: str,
    signing_public_key: bytes,
    timeout_s: float = 60.0,
) -> AdapterReleaseStatusRequest:
    return AdapterReleaseStatusRequest(
        request_id=request_id,
        desired=desired,
        signing_key_id=signing_key_id,
        signing_public_key_base64=b64encode(signing_public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(signing_public_key),
        timeout_s=timeout_s,
    )


class AdapterReleaseObservedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)
    gate_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    activated_at: datetime


class AdapterReleaseDesiredStageStatus(str, Enum):
    ABSENT = "ABSENT"
    VERIFIED = "VERIFIED"


class AdapterReleaseStatusSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-status-snapshot/v1"] = (
        "rolo-adapter-release-status-snapshot/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    active_index_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    current: AdapterReleaseObservedRecord | None = None
    previous: AdapterReleaseObservedRecord | None = None
    desired_stage_status: AdapterReleaseDesiredStageStatus
    observed_at: datetime

    @model_validator(mode="after")
    def require_index_shape(self) -> AdapterReleaseStatusSnapshot:
        if self.current is None:
            if self.previous is not None or self.active_index_sha256 is not None:
                raise ValueError("absent adapter release current has inconsistent index data")
        elif self.active_index_sha256 is None:
            raise ValueError("present adapter release current requires an index digest")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class AdapterReleaseStatusExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-status-execution-result/v1"] = (
        "rolo-adapter-release-status-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    snapshot: AdapterReleaseStatusSnapshot | None = None

    @model_validator(mode="after")
    def require_consistent_execution(self) -> AdapterReleaseStatusExecutionResult:
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.snapshot is None:
                raise ValueError("successful adapter release status is incomplete")
        elif self.error_code is None or self.snapshot is not None:
            raise ValueError("failed adapter release status is inconsistent")
        if self.snapshot is not None and (
            self.snapshot.request_id != self.request_id
            or self.snapshot.request_sha256 != self.request_sha256
            or self.snapshot.target_id != self.target_id
            or self.snapshot.robot_id != self.robot_id
        ):
            raise ValueError("adapter release status execution binding mismatch")
        return self


class AdapterReleaseStatusService:
    """Read and verify target state without mutating staging or the active index."""

    def __init__(self, install_root: Path) -> None:
        self.install_root = install_root.expanduser().absolute()
        if self.install_root.is_symlink():
            raise ValueError("adapter release install root cannot be a symbolic link")

    def _stage_root(self, robot_id: str, release_id: str, manifest_sha256: str) -> Path:
        return (
            self.install_root
            / "robots"
            / robot_id
            / "staged"
            / f"{release_id}-{manifest_sha256[:16]}"
        )

    @staticmethod
    def _load_index(path: Path) -> AdapterReleaseActiveIndex:
        if path.stat().st_size > _MAX_ACTIVE_INDEX_BYTES:
            raise ValueError("adapter release active index exceeds its size limit")
        return AdapterReleaseActiveIndex.model_validate_json(path.read_text(encoding="utf-8"))

    def _verify_record(
        self,
        record: AdapterReleaseActiveRecord,
        *,
        target_id: str,
        robot_id: str,
        verifier: AdapterReleaseSignatureVerifier,
        signing_key_id: str,
    ) -> AdapterReleaseObservedRecord:
        expected = self._stage_root(
            robot_id,
            record.release_id,
            record.release_manifest_sha256,
        )
        actual = Path(record.staged_root)
        if actual.is_symlink() or actual.resolve(strict=False) != expected.resolve(strict=False):
            raise ValueError("adapter release status staged path mismatch")
        _, manifest, signature, _ = load_verified_adapter_release_transfer(expected, verifier)
        if (
            record.target_id != target_id
            or record.robot_id != robot_id
            or manifest.target_id != target_id
            or manifest.robot_id != robot_id
            or manifest.release_id != record.release_id
            or manifest.release_manifest_sha256 != record.release_manifest_sha256
            or manifest.canonical_sha256() != record.transfer_manifest_sha256
            or signature.key_id != signing_key_id
        ):
            raise ValueError("adapter release status active record mismatch")
        return AdapterReleaseObservedRecord(
            release_id=record.release_id,
            transfer_manifest_sha256=manifest.canonical_sha256(),
            release_manifest_sha256=manifest.release_manifest_sha256,
            bundle_manifest_sha256=manifest.bundle_manifest_sha256,
            runtime_context_sha256=manifest.runtime_context_sha256,
            gate_receipt_sha256=record.gate_receipt_sha256,
            activated_at=record.activated_at,
        )

    def observe(
        self,
        request: AdapterReleaseStatusRequest,
        *,
        verifier: AdapterReleaseSignatureVerifier | None = None,
        now: datetime | None = None,
    ) -> AdapterReleaseStatusSnapshot:
        desired = request.desired
        release_verifier = verifier or Ed25519AdapterReleaseVerifier(
            {request.signing_key_id: request.public_key_bytes()}
        )
        current_path = self.install_root / "robots" / desired.robot_id / "current.json"
        if current_path.is_symlink():
            raise ValueError("adapter release current index cannot be a symbolic link")
        index = self._load_index(current_path) if current_path.is_file() else None
        current: AdapterReleaseObservedRecord | None = None
        previous: AdapterReleaseObservedRecord | None = None
        index_sha256: str | None = None
        if index is not None:
            if index.target_id != desired.target_id or index.robot_id != desired.robot_id:
                raise ValueError("adapter release status active index identity mismatch")
            current = self._verify_record(
                index.current,
                target_id=desired.target_id,
                robot_id=desired.robot_id,
                verifier=release_verifier,
                signing_key_id=request.signing_key_id,
            )
            if index.previous is not None:
                previous = self._verify_record(
                    index.previous,
                    target_id=desired.target_id,
                    robot_id=desired.robot_id,
                    verifier=release_verifier,
                    signing_key_id=request.signing_key_id,
                )
            index_sha256 = _canonical_sha256(index.model_dump(mode="json"))

        desired_root = self._stage_root(
            desired.robot_id,
            desired.release_id,
            desired.release_manifest_sha256,
        )
        desired_stage_status = AdapterReleaseDesiredStageStatus.ABSENT
        if desired_root.is_symlink():
            raise ValueError("adapter release desired stage cannot be a symbolic link")
        if desired_root.exists():
            _, manifest, signature, _ = load_verified_adapter_release_transfer(
                desired_root,
                release_verifier,
            )
            if (
                manifest.target_id != desired.target_id
                or manifest.robot_id != desired.robot_id
                or manifest.release_id != desired.release_id
                or manifest.canonical_sha256() != desired.transfer_manifest_sha256
                or manifest.release_manifest_sha256 != desired.release_manifest_sha256
                or manifest.bundle_manifest_sha256 != desired.bundle_manifest_sha256
                or manifest.runtime_context_sha256 != desired.runtime_context_sha256
                or signature.key_id != request.signing_key_id
            ):
                raise ValueError("adapter release desired stage differs from controller authority")
            desired_stage_status = AdapterReleaseDesiredStageStatus.VERIFIED

        return AdapterReleaseStatusSnapshot(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=desired.target_id,
            robot_id=desired.robot_id,
            active_index_sha256=index_sha256,
            current=current,
            previous=previous,
            desired_stage_status=desired_stage_status,
            observed_at=now or datetime.now(timezone.utc),
        )


class AdapterReleaseConsistencyStatus(str, Enum):
    IN_SYNC = "IN_SYNC"
    TARGET_EMPTY = "TARGET_EMPTY"
    TARGET_DIVERGED = "TARGET_DIVERGED"
    DESIRED_IS_PREVIOUS = "DESIRED_IS_PREVIOUS"
    BLOCKED = "BLOCKED"


class AdapterReleaseReconciliationAction(str, Enum):
    NONE = "NONE"
    DEPLOY_AND_ACTIVATE_DESIRED = "DEPLOY_AND_ACTIVATE_DESIRED"
    ACTIVATE_STAGED_DESIRED = "ACTIVATE_STAGED_DESIRED"
    ROLLBACK_TO_DESIRED = "ROLLBACK_TO_DESIRED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AdapterReleaseReconciliationReport(BaseModel):
    """Controller-only plan. It never performs the proposed mutation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-reconciliation-report/v1"] = (
        "rolo-adapter-release-reconciliation-report/v1"
    )
    desired: AdapterReleaseDesiredState
    status: AdapterReleaseConsistencyStatus
    action: AdapterReleaseReconciliationAction
    requires_reconciliation: bool
    requires_approval: bool
    target_snapshot_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    expect_current_present: bool | None = None
    expected_current_transfer_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    reason: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def require_action_shape(self) -> AdapterReleaseReconciliationReport:
        if self.action == AdapterReleaseReconciliationAction.NONE:
            if self.status != AdapterReleaseConsistencyStatus.IN_SYNC or self.requires_approval:
                raise ValueError("no-op reconciliation must be an unapproved in-sync result")
        elif not self.requires_reconciliation:
            raise ValueError("nontrivial reconciliation action must require reconciliation")
        if self.action == AdapterReleaseReconciliationAction.MANUAL_REVIEW:
            if self.status != AdapterReleaseConsistencyStatus.BLOCKED:
                raise ValueError("manual review reconciliation must be blocked")
        elif self.status == AdapterReleaseConsistencyStatus.BLOCKED:
            raise ValueError("blocked reconciliation must require manual review")
        if (
            self.expect_current_present is False
            and self.expected_current_transfer_manifest_sha256 is not None
        ):
            raise ValueError("absent current expectation cannot include a current digest")
        return self


def reconcile_adapter_release(
    request: AdapterReleaseStatusRequest,
    execution: AdapterReleaseStatusExecutionResult,
) -> AdapterReleaseReconciliationReport:
    """Compare controller authority with one request-bound, target-verified snapshot."""

    desired = request.desired
    if (
        execution.request_id != request.request_id
        or execution.request_sha256 != request.canonical_sha256()
        or execution.target_id != desired.target_id
        or execution.robot_id != desired.robot_id
    ):
        raise ValueError("adapter release status execution is not bound to its request")
    if execution.execution_status != TargetExecutionStatus.SUCCEEDED:
        return AdapterReleaseReconciliationReport(
            desired=desired,
            status=AdapterReleaseConsistencyStatus.BLOCKED,
            action=AdapterReleaseReconciliationAction.MANUAL_REVIEW,
            requires_reconciliation=True,
            requires_approval=True,
            reason=(
                "target status could not be verified; retain unknown state and inspect "
                "before mutation"
            ),
        )
    snapshot = execution.snapshot
    assert snapshot is not None
    snapshot_digest = snapshot.canonical_sha256()
    current = snapshot.current
    if current is not None and (
        current.release_id == desired.release_id
        and current.transfer_manifest_sha256 == desired.transfer_manifest_sha256
        and current.release_manifest_sha256 == desired.release_manifest_sha256
        and current.bundle_manifest_sha256 == desired.bundle_manifest_sha256
        and current.runtime_context_sha256 == desired.runtime_context_sha256
    ):
        return AdapterReleaseReconciliationReport(
            desired=desired,
            status=AdapterReleaseConsistencyStatus.IN_SYNC,
            action=AdapterReleaseReconciliationAction.NONE,
            requires_reconciliation=False,
            requires_approval=False,
            target_snapshot_sha256=snapshot_digest,
            expect_current_present=True,
            expected_current_transfer_manifest_sha256=current.transfer_manifest_sha256,
            reason="target current exactly matches the controller desired release",
        )

    current_digest = current.transfer_manifest_sha256 if current is not None else None
    if snapshot.previous is not None and (
        snapshot.previous.release_id == desired.release_id
        and snapshot.previous.transfer_manifest_sha256 == desired.transfer_manifest_sha256
        and snapshot.previous.release_manifest_sha256 == desired.release_manifest_sha256
    ):
        return AdapterReleaseReconciliationReport(
            desired=desired,
            status=AdapterReleaseConsistencyStatus.DESIRED_IS_PREVIOUS,
            action=AdapterReleaseReconciliationAction.ROLLBACK_TO_DESIRED,
            requires_reconciliation=True,
            requires_approval=True,
            target_snapshot_sha256=snapshot_digest,
            expect_current_present=True,
            expected_current_transfer_manifest_sha256=current_digest,
            reason="controller desired release is the target's verified previous release",
        )

    status = (
        AdapterReleaseConsistencyStatus.TARGET_EMPTY
        if current is None
        else AdapterReleaseConsistencyStatus.TARGET_DIVERGED
    )
    if snapshot.desired_stage_status == AdapterReleaseDesiredStageStatus.VERIFIED:
        action = AdapterReleaseReconciliationAction.ACTIVATE_STAGED_DESIRED
        reason = "controller desired release is staged and verified but is not current"
    else:
        action = AdapterReleaseReconciliationAction.DEPLOY_AND_ACTIVATE_DESIRED
        reason = "controller desired release is not present as a verified target stage"
    return AdapterReleaseReconciliationReport(
        desired=desired,
        status=status,
        action=action,
        requires_reconciliation=True,
        requires_approval=True,
        target_snapshot_sha256=snapshot_digest,
        expect_current_present=current is not None,
        expected_current_transfer_manifest_sha256=current_digest,
        reason=reason,
    )
