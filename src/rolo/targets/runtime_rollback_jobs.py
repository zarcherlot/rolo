from __future__ import annotations

import hashlib
import json
import re
import threading
from base64 import b64decode, b64encode
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.bootstrap import BootstrapInstallStatus
from rolo.targets.bootstrap_execution import (
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetBootstrapExecutionResult,
)
from rolo.targets.credentials import (
    CredentialResolver,
    FileCredentialProvider,
)
from rolo.targets.deployment_authorization import (
    authorize_deployment_request,
    deployment_request_payload_sha256,
    verify_deployment_authorization_signing_key_pair,
)
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.executor import (
    TargetExecutionStatus,
    TargetExecutor,
    TargetExecutorKind,
)
from rolo.targets.models import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
    TargetProfile,
)
from rolo.targets.package_signing import ed25519_public_key_sha256
from rolo.targets.platform_detector import target_executor_for_profile
from rolo.targets.registration import (
    TargetRegistrationRequest,
    TargetRegistrationService,
    target_connection_binding_sha256,
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_IDEMPOTENCY = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class TargetRuntimeRollbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-submission/v1"] = (
        "rolo-target-runtime-rollback-submission/v1"
    )
    package_id: str = Field(pattern=_IDENTIFIER)
    expected_current_manifest_sha256: str = Field(pattern=_SHA256)
    expected_previous_manifest_sha256: str = Field(pattern=_SHA256)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    timeout_s: float = Field(default=300.0, ge=10.0, le=1800.0)

    @model_validator(mode="after")
    def reject_noop(self) -> TargetRuntimeRollbackSubmission:
        if (
            self.expected_current_manifest_sha256
            == self.expected_previous_manifest_sha256
        ):
            raise ValueError("target runtime rollback requires two different digests")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetRuntimeRollbackJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-job-spec/v1"] = (
        "rolo-target-runtime-rollback-job-spec/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    target_registration_sha256: str = Field(pattern=_SHA256)
    package_id: str = Field(pattern=_IDENTIFIER)
    expected_current_manifest_sha256: str = Field(pattern=_SHA256)
    expected_previous_manifest_sha256: str = Field(pattern=_SHA256)
    release_signing_key_id: str = Field(pattern=_IDENTIFIER)
    release_signing_public_key_base64: str = Field(max_length=32_768)
    release_signing_public_key_sha256: str = Field(pattern=_SHA256)
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approval_action: Literal[ApprovalAction.ROLLBACK_TARGET_RUNTIME] = (
        ApprovalAction.ROLLBACK_TARGET_RUNTIME
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime
    timeout_s: float = Field(default=300.0, ge=10.0, le=1800.0)

    @field_validator("release_signing_public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("rollback release public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("rollback release public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def bind_spec(self) -> TargetRuntimeRollbackJobSpec:
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("rollback approval expiry must be timezone-aware")
        if (
            self.expected_current_manifest_sha256
            == self.expected_previous_manifest_sha256
        ):
            raise ValueError("rollback current and previous digests must differ")
        if (
            ed25519_public_key_sha256(self.release_public_key_bytes())
            != self.release_signing_public_key_sha256
        ):
            raise ValueError("rollback release public key digest mismatch")
        return self

    def release_public_key_bytes(self) -> bytes:
        return b64decode(self.release_signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetRuntimeRollbackSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-intent/v1"] = (
        "rolo-target-runtime-rollback-intent/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetRuntimeRollbackJobSpec


class TargetRuntimeRollbackJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-submission-result/v1"] = (
        "rolo-target-runtime-rollback-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetRuntimeRollbackJobSpec
    approval: ApprovalRequest


class TargetRuntimeRollbackArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetRuntimeRollbackFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    REMOTE_OUTCOME_UNKNOWN = "REMOTE_OUTCOME_UNKNOWN"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetRuntimeRollbackJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-job-artifact/v1"] = (
        "rolo-target-runtime-rollback-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=_IDENTIFIER)
    status: TargetRuntimeRollbackArtifactStatus
    failure_code: TargetRuntimeRollbackFailureCode | None = None
    execution: TargetBootstrapExecutionResult | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_status(self) -> TargetRuntimeRollbackJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("rollback artifact timestamp must be timezone-aware")
        if self.status == TargetRuntimeRollbackArtifactStatus.SUCCEEDED:
            if self.failure_code is not None or self.execution is None:
                raise ValueError("successful rollback artifact is incomplete")
            if (
                self.execution.status != TargetExecutionStatus.SUCCEEDED
                or self.execution.operation
                != TargetBootstrapExecutionOperation.ROLLBACK
                or self.execution.install_result is None
                or self.execution.install_result.status
                != BootstrapInstallStatus.ROLLED_BACK
                or self.execution.install_result.active is None
                or self.execution.install_result.active.package_id
                != self.execution.package_id
                or self.execution.install_result.active.manifest_sha256
                != self.execution.manifest_sha256
                or not self.execution.install_result.previous_preserved
            ):
                raise ValueError("successful rollback artifact has invalid execution")
        elif self.failure_code is None:
            raise ValueError("failed rollback artifact requires a failure code")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


def build_target_runtime_rollback_job_spec(
    registration: TargetRegistrationRequest,
    submission: TargetRuntimeRollbackSubmission,
    *,
    approval_id: str,
    approval_expires_at: datetime,
) -> TargetRuntimeRollbackJobSpec:
    profile = registration.target
    if (
        profile.release_signing_key_id is None
        or profile.release_signing_public_key_path is None
        or profile.release_signing_public_key_sha256 is None
    ):
        raise ValueError("TargetProfile requires a complete release-signing key pin")
    public_key_path = Path(
        profile.release_signing_public_key_path
    ).expanduser().absolute()
    if (
        public_key_path.is_symlink()
        or not public_key_path.is_file()
        or public_key_path.stat().st_size > 16 * 1024
    ):
        raise ValueError("release-signing public key pin path is unavailable")
    public_key = public_key_path.read_bytes()
    if ed25519_public_key_sha256(public_key) != profile.release_signing_public_key_sha256:
        raise ValueError("release-signing public key pin digest mismatch")
    return TargetRuntimeRollbackJobSpec(
        target_id=profile.target_id,
        target_registration_sha256=target_connection_binding_sha256(
            profile,
            registration.connection,
        ),
        package_id=submission.package_id,
        expected_current_manifest_sha256=(
            submission.expected_current_manifest_sha256
        ),
        expected_previous_manifest_sha256=(
            submission.expected_previous_manifest_sha256
        ),
        release_signing_key_id=profile.release_signing_key_id,
        release_signing_public_key_base64=b64encode(public_key).decode("ascii"),
        release_signing_public_key_sha256=(
            profile.release_signing_public_key_sha256
        ),
        approval_id=approval_id,
        approver_principal=submission.approver_principal,
        approval_expires_at=approval_expires_at,
        timeout_s=submission.timeout_s,
    )


def build_target_runtime_rollback_execution_request(
    spec: TargetRuntimeRollbackJobSpec,
    *,
    job_id: str,
) -> TargetBootstrapExecutionRequest:
    if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
        raise ValueError("invalid rollback Job id")
    return TargetBootstrapExecutionRequest(
        request_id=f"rollback-{job_id.removeprefix('deployment-')}",
        operation=TargetBootstrapExecutionOperation.ROLLBACK,
        target_id=spec.target_id,
        package_id=spec.package_id,
        manifest_sha256=spec.expected_previous_manifest_sha256,
        signing_key_id=spec.release_signing_key_id,
        signing_public_key_base64=spec.release_signing_public_key_base64,
        signing_public_key_sha256=spec.release_signing_public_key_sha256,
        approval_id=spec.approval_id,
        expected_current_manifest_sha256=(
            spec.expected_current_manifest_sha256
        ),
        timeout_s=spec.timeout_s,
    )


class TargetRuntimeRollbackJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("rollback Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid rollback Job id")
        return self.root / job_id / "runtime-rollback-spec.json"

    def load(self, job_id: str) -> TargetRuntimeRollbackJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
            raise ValueError("rollback Job spec is unavailable")
        return TargetRuntimeRollbackJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(self, job_id: str, spec: TargetRuntimeRollbackJobSpec) -> None:
        path = self._path(job_id)
        try:
            atomic_write_text(
                path,
                spec.model_dump_json(indent=2) + "\n",
                require_absent=True,
            )
        except FileExistsError:
            if self.load(job_id) != spec:
                raise DeploymentJobStateConflict(
                    "rollback Job spec already differs"
                ) from None


class TargetRuntimeRollbackIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("rollback intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        if re.fullmatch(_IDENTIFIER, target_id) is None or re.fullmatch(
            _IDEMPOTENCY, idempotency_key
        ) is None:
            raise ValueError("invalid rollback intent identity")
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self.root / target_id / f"{digest}.json"

    def lock_target(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key).with_suffix(".intent-lock")

    def load(
        self,
        target_id: str,
        idempotency_key: str,
    ) -> TargetRuntimeRollbackSubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise FileNotFoundError(path)
        return TargetRuntimeRollbackSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetRuntimeRollbackSubmissionIntent,
    ) -> TargetRuntimeRollbackSubmissionIntent:
        path = self._path(intent.target_id, intent.idempotency_key)
        try:
            atomic_write_text(
                path,
                intent.model_dump_json(indent=2) + "\n",
                require_absent=True,
            )
        except FileExistsError:
            current = self.load(intent.target_id, intent.idempotency_key)
            if current != intent:
                raise DeploymentJobStateConflict(
                    "rollback submission intent already differs"
                ) from None
            return current
        return intent


class TargetRuntimeRollbackSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetRuntimeRollbackJobSpecStore,
        intents: TargetRuntimeRollbackIntentStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations

    def _submit_spec(
        self,
        spec: TargetRuntimeRollbackJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime,
    ) -> TargetRuntimeRollbackJobSubmissionResult:
        command = DeploymentCommand(
            command=DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME,
            target_id=spec.target_id,
            active_probe="none",
            run_adapter_agent=False,
            requested_by=requested_by,
            interaction_surface=interaction_surface,
            idempotency_key=idempotency_key,
            parameters_sha256=spec.canonical_sha256(),
        )
        record = self.store.create_job(command, now=now)
        self.specs.persist(record.job.job_id, spec)
        request_scope_sha256 = deployment_request_payload_sha256(
            build_target_runtime_rollback_execution_request(
                spec,
                job_id=record.job.job_id,
            )
        )
        try:
            approval = self.store.load_approval_request(spec.approval_id)
        except ValueError:
            try:
                approval = self.store.request_approval(
                    record.job.job_id,
                    action=ApprovalAction.ROLLBACK_TARGET_RUNTIME,
                    risk="R3",
                    approver_principal=spec.approver_principal,
                    summary=(
                        "Rollback the exact target runtime current digest to the "
                        "bound previous digest."
                    ),
                    expires_at=spec.approval_expires_at,
                    authorization_scope_sha256=request_scope_sha256,
                    now=now,
                    approval_id=spec.approval_id,
                )
            except FileExistsError:
                approval = self.store.load_approval_request(spec.approval_id)
        if (
            approval.job_id != record.job.job_id
            or approval.command_sha256 != record.job.command_sha256
            or approval.authorization_scope_sha256 != request_scope_sha256
            or approval.action != ApprovalAction.ROLLBACK_TARGET_RUNTIME
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict("rollback Job approval already differs")
        return TargetRuntimeRollbackJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetRuntimeRollbackSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetRuntimeRollbackJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("rollback submission timestamp must be timezone-aware")
        with interprocess_lock(self.intents.lock_target(target_id, idempotency_key)):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                approval_id = "approval-" + hashlib.sha256(
                    f"runtime-rollback:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()[:32]
                spec = build_target_runtime_rollback_job_spec(
                    self.registrations.load(target_id),
                    submission,
                    approval_id=approval_id,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetRuntimeRollbackSubmissionIntent(
                        target_id=target_id,
                        requested_by=requested_by,
                        idempotency_key=idempotency_key,
                        submission_sha256=submission.canonical_sha256(),
                        spec=spec,
                    )
                )
            else:
                if (
                    intent.requested_by != requested_by
                    or intent.submission_sha256 != submission.canonical_sha256()
                ):
                    raise DeploymentJobStateConflict(
                        "rollback idempotency key belongs to a different submission"
                    )
            return self._submit_spec(
                intent.spec,
                requested_by=requested_by,
                interaction_surface=interaction_surface,
                idempotency_key=idempotency_key,
                now=observed_at,
            )


class TargetRuntimeRollbackJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetRuntimeRollbackJobSpecStore,
        artifact_root: Path,
        *,
        authorization_signing_key_id: str | None = None,
        authorization_public_key_path: Path | None = None,
        authorization_private_key_path: Path | None = None,
        executor_factory: Callable[[TargetProfile], TargetExecutor] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.artifact_root = artifact_root.expanduser().absolute()
        if self.artifact_root.is_symlink():
            raise ValueError("rollback artifact root cannot be a symbolic link")
        self._executor_factory = executor_factory
        self._authorization_signing_key_id = authorization_signing_key_id
        self._authorization_public_key_path = (
            authorization_public_key_path.expanduser().absolute()
            if authorization_public_key_path is not None
            else None
        )
        self._authorization_private_key_path = (
            authorization_private_key_path.expanduser().absolute()
            if authorization_private_key_path is not None
            else None
        )
    def _executor(self, profile: TargetProfile) -> TargetExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
        )

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "runtime-rollback-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/runtime-rollback-result.json"

    def _load_artifact(self, job_id: str) -> TargetRuntimeRollbackJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("rollback artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("rollback artifact is invalid")
        return TargetRuntimeRollbackJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _persist(self, artifact: TargetRuntimeRollbackJobArtifact) -> None:
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("rollback artifact already differs")
            return
        atomic_write_text(
            self._path(artifact.job_id),
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetRuntimeRollbackJobSpec,
        artifact: TargetRuntimeRollbackJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
        ):
            raise DeploymentJobStateConflict("rollback artifact binding mismatch")
        if artifact.execution is not None:
            execution = artifact.execution
            if (
                execution.target_id != spec.target_id
                or execution.package_id != spec.package_id
                or execution.manifest_sha256
                != spec.expected_previous_manifest_sha256
                or execution.signing_key_id != spec.release_signing_key_id
                or execution.signing_public_key_sha256
                != spec.release_signing_public_key_sha256
                or execution.operation != TargetBootstrapExecutionOperation.ROLLBACK
            ):
                raise DeploymentJobStateConflict("rollback execution differs from spec")
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt
                and item.step_id == "target-runtime-rollback"
            ),
            None,
        )
        ref = self._ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == TargetRuntimeRollbackArtifactStatus.FAILED:
            if checkpoint is not None and checkpoint.status in {
                DeploymentStepStatus.FAILED,
                DeploymentStepStatus.UNKNOWN,
            }:
                return record
            execution = artifact.execution
            remote_known = artifact.failure_code != (
                TargetRuntimeRollbackFailureCode.REMOTE_OUTCOME_UNKNOWN
            ) and (
                execution is None
                or execution.transport_error_code is None
                or execution.executor_kind == TargetExecutorKind.LOCAL
            )
            return self.store.fail_step(
                record.job.job_id,
                step_id="target-runtime-rollback",
                remote_state_known=remote_known,
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        if checkpoint is None:
            raise DeploymentJobStateConflict("rollback artifact has no checkpoint")
        if checkpoint.status == DeploymentStepStatus.RUNNING:
            self.store.complete_step(
                record.job.job_id,
                step_id="target-runtime-rollback",
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        elif checkpoint.status != DeploymentStepStatus.COMPLETE:
            raise DeploymentJobStateConflict("rollback artifact conflicts with checkpoint")
        return self.store.complete_job(record.job.job_id, artifact_refs=[ref])

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME:
            raise DeploymentJobStateConflict("rollback handler received another command")
        if record.job.state in {
            DeploymentJobState.COMPLETE,
            DeploymentJobState.FAILED,
            DeploymentJobState.BLOCKED,
            DeploymentJobState.CANCELLED,
        }:
            return record
        if record.cancel_requested or (cancel_event is not None and cancel_event.is_set()):
            if not record.cancel_requested:
                self.store.request_cancel(job_id)
            return self.store.resolve_cancel(job_id, remote_termination_confirmed=True)
        spec = self.specs.load(job_id)
        if record.job.command.parameters_sha256 != spec.canonical_sha256():
            raise DeploymentJobStateConflict("rollback Job spec digest mismatch")
        approval = self.store.load_approval_request(spec.approval_id)
        unsigned_request = build_target_runtime_rollback_execution_request(
            spec,
            job_id=job_id,
        )
        request_scope_sha256 = deployment_request_payload_sha256(unsigned_request)
        if approval.authorization_scope_sha256 != request_scope_sha256:
            raise DeploymentJobStateConflict("rollback approval scope mismatch")
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.ROLLBACK_TARGET_RUNTIME,
        )
        if (
            self._authorization_signing_key_id is None
            or self._authorization_public_key_path is None
            or self._authorization_private_key_path is None
        ):
            raise DeploymentJobStateConflict(
                "rollback authorization signer is unavailable"
            )
        try:
            verify_deployment_authorization_signing_key_pair(
                public_key_path=self._authorization_public_key_path,
                private_key_path=self._authorization_private_key_path,
            )
            authorized_request = authorize_deployment_request(
                unsigned_request,
                self.store,
                approval_id=spec.approval_id,
                signing_key_id=self._authorization_signing_key_id,
                private_key_path=self._authorization_private_key_path,
                lifetime_s=min(300, max(1, int(spec.timeout_s))),
                authorization_id=(
                    "authorization-"
                    + hashlib.sha256(
                        f"runtime-rollback:{job_id}:{record.attempt}".encode()
                    ).hexdigest()[:32]
                ),
            )
        except (OSError, ValueError) as exc:
            raise DeploymentJobStateConflict(
                "rollback authorization proof could not be issued"
            ) from exc
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            if record.cancel_requested:
                return self.store.resolve_cancel(
                    job_id,
                    remote_termination_confirmed=True,
                )
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            registration = self.registrations.load(spec.target_id)
            registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            running = any(
                item.attempt == record.attempt
                and item.step_id == "target-runtime-rollback"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "rollback remote checkpoint requires reconciliation"
                )
            if registration_sha256 != spec.target_registration_sha256:
                record = self.store.start_step(
                    job_id,
                    step_id="target-runtime-rollback",
                    state=DeploymentJobState.ROLLING_BACK,
                    remote=False,
                )
                artifact = TargetRuntimeRollbackJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    status=TargetRuntimeRollbackArtifactStatus.FAILED,
                    failure_code=(
                        TargetRuntimeRollbackFailureCode.TARGET_REGISTRATION_CHANGED
                    ),
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                try:
                    executor = self._executor(registration.target)
                except (OSError, ValueError):
                    record = self.store.start_step(
                        job_id,
                        step_id="target-runtime-rollback",
                        state=DeploymentJobState.ROLLING_BACK,
                        remote=False,
                    )
                    artifact = TargetRuntimeRollbackJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        status=TargetRuntimeRollbackArtifactStatus.FAILED,
                        failure_code=TargetRuntimeRollbackFailureCode.RUNNER_ERROR,
                        completed_at=datetime.now(timezone.utc),
                    )
                else:
                    record = self.store.start_step(
                        job_id,
                        step_id="target-runtime-rollback",
                        state=DeploymentJobState.ROLLING_BACK,
                        remote=True,
                    )
                    try:
                        execution = executor.execute_bootstrap(
                            authorized_request,
                            cancel_event=cancel_event,
                        )
                    except Exception:
                        artifact = TargetRuntimeRollbackJobArtifact(
                            job_id=job_id,
                            command_sha256=record.job.command_sha256,
                            spec_sha256=spec.canonical_sha256(),
                            target_id=spec.target_id,
                            status=TargetRuntimeRollbackArtifactStatus.FAILED,
                            failure_code=(
                                TargetRuntimeRollbackFailureCode.REMOTE_OUTCOME_UNKNOWN
                            ),
                            completed_at=datetime.now(timezone.utc),
                        )
                    else:
                        succeeded = (
                            execution.status == TargetExecutionStatus.SUCCEEDED
                            and execution.install_result is not None
                            and execution.install_result.status
                            == BootstrapInstallStatus.ROLLED_BACK
                            and execution.install_result.active is not None
                            and execution.install_result.active.package_id
                            == spec.package_id
                            and execution.install_result.active.manifest_sha256
                            == spec.expected_previous_manifest_sha256
                            and execution.install_result.previous_preserved
                        )
                        artifact = TargetRuntimeRollbackJobArtifact(
                            job_id=job_id,
                            command_sha256=record.job.command_sha256,
                            spec_sha256=spec.canonical_sha256(),
                            target_id=spec.target_id,
                            status=(
                                TargetRuntimeRollbackArtifactStatus.SUCCEEDED
                                if succeeded
                                else TargetRuntimeRollbackArtifactStatus.FAILED
                            ),
                            failure_code=(
                                None
                                if succeeded
                                else TargetRuntimeRollbackFailureCode.EXECUTION_FAILED
                            ),
                            execution=execution,
                            completed_at=datetime.now(timezone.utc),
                        )
            self._persist(artifact)
            return self._finish(record, spec, artifact)
