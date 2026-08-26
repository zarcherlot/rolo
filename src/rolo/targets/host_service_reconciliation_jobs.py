from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.credentials import CredentialPurpose, CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentRemoteReconciliationOutcome,
    DeploymentStepStatus,
)
from rolo.targets.host_service import (
    TargetHostServiceError,
    TargetHostServiceExecutionResult,
    TargetHostServiceOperation,
    TargetHostServiceRequest,
    TargetHostServiceStatus,
)
from rolo.targets.host_service_jobs import (
    TargetHostServiceExecutor,
    TargetHostServiceJobSpecStore,
)
from rolo.targets.models import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
    TargetProfile,
    TargetTransport,
)
from rolo.targets.platform_detector import target_executor_for_profile
from rolo.targets.registration import (
    TargetRegistrationService,
    target_connection_binding_sha256,
)

_JOB_ID = r"^deployment-[0-9a-f]{32}$"
_SHA256 = r"^[0-9a-f]{64}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_IDEMPOTENCY = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def target_service_reconciliation_outcome(
    execution: TargetHostServiceExecutionResult,
) -> DeploymentRemoteReconciliationOutcome | None:
    if execution.operation != TargetHostServiceOperation.STATUS:
        raise ValueError("service reconciliation outcome requires STATUS")
    if execution.status == TargetHostServiceStatus.ACTIVE:
        return DeploymentRemoteReconciliationOutcome.EXACT
    if execution.status == TargetHostServiceStatus.INACTIVE:
        return DeploymentRemoteReconciliationOutcome.NOT_COMMITTED
    if execution.error_code in {
        TargetHostServiceError.HOST_PLAN_MISMATCH,
        TargetHostServiceError.RUNTIME_MISMATCH,
    }:
        return DeploymentRemoteReconciliationOutcome.DIVERGED
    return None


class TargetHostServiceReconciliationJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-job-submission/v1"
    ] = "rolo-target-host-service-reconciliation-job-submission/v1"
    original_job_id: str = Field(pattern=_JOB_ID)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceReconciliationJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-job-spec/v1"
    ] = "rolo-target-host-service-reconciliation-job-spec/v1"
    target_id: str
    target_registration_sha256: str = Field(pattern=_SHA256)
    original_job_id: str = Field(pattern=_JOB_ID)
    original_command_sha256: str = Field(pattern=_SHA256)
    original_spec_sha256: str = Field(pattern=_SHA256)
    request: TargetHostServiceRequest
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime

    @model_validator(mode="after")
    def bind_spec(self) -> TargetHostServiceReconciliationJobSpec:
        if self.target_id != self.request.target_id:
            raise ValueError("service reconciliation target differs from request")
        if self.request.operation != TargetHostServiceOperation.STATUS:
            raise ValueError("service reconciliation requires STATUS")
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("service reconciliation approval expiry must be timezone-aware")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceReconciliationSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-submission-intent/v1"
    ] = "rolo-target-host-service-reconciliation-submission-intent/v1"
    requested_by: str = Field(pattern=_PRINCIPAL)
    interaction_surface: InteractionSurface
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetHostServiceReconciliationJobSpec


class TargetHostServiceReconciliationSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("service reconciliation intent root cannot be a symbolic link")

    def _path(self, idempotency_key: str) -> Path:
        identity = hashlib.sha256(idempotency_key.encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def lock_path(self, idempotency_key: str) -> Path:
        return self._path(idempotency_key)

    def load(
        self,
        idempotency_key: str,
    ) -> TargetHostServiceReconciliationSubmissionIntent:
        path = self._path(idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise FileNotFoundError(path)
        return TargetHostServiceReconciliationSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetHostServiceReconciliationSubmissionIntent,
    ) -> TargetHostServiceReconciliationSubmissionIntent:
        atomic_write_text(
            self._path(intent.idempotency_key),
            intent.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
            require_absent=True,
        )
        return intent


class TargetHostServiceReconciliationJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("service reconciliation spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(_JOB_ID, job_id) is None:
            raise ValueError("invalid service reconciliation Job ID")
        return self.root / job_id / "host-service-reconciliation-spec.json"

    def load(self, job_id: str) -> TargetHostServiceReconciliationJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("service reconciliation Job spec is unavailable")
        return TargetHostServiceReconciliationJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        job_id: str,
        spec: TargetHostServiceReconciliationJobSpec,
    ) -> TargetHostServiceReconciliationJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict(
                    "service reconciliation Job spec already differs"
                )
            return current
        atomic_write_text(
            path,
            spec.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        return spec


class TargetHostServiceReconciliationJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-job-submission-result/v1"
    ] = "rolo-target-host-service-reconciliation-job-submission-result/v1"
    job: DeploymentJobRecord
    spec: TargetHostServiceReconciliationJobSpec
    approval: ApprovalRequest


class TargetHostServiceReconciliationSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetHostServiceReconciliationJobSpecStore,
        intents: TargetHostServiceReconciliationSubmissionIntentStore,
        service_specs: TargetHostServiceJobSpecStore,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.service_specs = service_specs

    def submit(
        self,
        *,
        submission: TargetHostServiceReconciliationJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetHostServiceReconciliationJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        with interprocess_lock(self.intents.lock_path(idempotency_key)):
            try:
                intent = self.intents.load(idempotency_key)
            except FileNotFoundError:
                original = self.store.load_job(submission.original_job_id)
                if (
                    original.job.command.command
                    != DeploymentCommandKind.START_TARGET_SERVICE
                    or original.job.state != DeploymentJobState.BLOCKED
                    or original.recovery_disposition.value
                    != "REQUIRES_RECONCILIATION"
                ):
                    raise DeploymentJobStateConflict(
                        "target service Job does not require reconciliation"
                    ) from None
                original_spec = self.service_specs.load(original.job.job_id)
                request = original_spec.request.model_copy(
                    update={
                        "request_id": "service-status-"
                        + hashlib.sha256(idempotency_key.encode()).hexdigest()[:24],
                        "operation": TargetHostServiceOperation.STATUS,
                    }
                )
                approval_id = "approval-" + hashlib.sha256(
                    f"service-reconcile:{original.job.job_id}:{idempotency_key}".encode()
                ).hexdigest()[:32]
                spec = TargetHostServiceReconciliationJobSpec(
                    target_id=original_spec.target_id,
                    target_registration_sha256=(
                        original_spec.target_registration_sha256
                    ),
                    original_job_id=original.job.job_id,
                    original_command_sha256=original.job.command_sha256,
                    original_spec_sha256=original_spec.canonical_sha256(),
                    request=request,
                    approval_id=approval_id,
                    approver_principal=submission.approver_principal,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetHostServiceReconciliationSubmissionIntent(
                        requested_by=requested_by,
                        interaction_surface=interaction_surface,
                        idempotency_key=idempotency_key,
                        submission_sha256=submission.canonical_sha256(),
                        spec=spec,
                    )
                )
            if (
                intent.requested_by != requested_by
                or intent.interaction_surface != interaction_surface
                or intent.submission_sha256 != submission.canonical_sha256()
            ):
                raise DeploymentJobStateConflict(
                    "service reconciliation idempotency key was reused"
                )
        spec = intent.spec
        command = DeploymentCommand(
            command=DeploymentCommandKind.RECONCILE_TARGET_SERVICE,
            target_id=spec.target_id,
            active_probe="none",
            run_adapter_agent=False,
            requested_by=requested_by,
            interaction_surface=interaction_surface,
            idempotency_key=idempotency_key,
            parameters_sha256=spec.canonical_sha256(),
        )
        record = self.store.create_job(command, now=observed_at)
        self.specs.persist(record.job.job_id, spec)
        try:
            approval = self.store.load_approval_request(spec.approval_id)
        except ValueError:
            approval = self.store.request_approval(
                record.job.job_id,
                action=ApprovalAction.RECONCILE_TARGET_SERVICE,
                risk="R2",
                approver_principal=spec.approver_principal,
                summary=(
                    "Read the digest-bound systemd service status without starting, "
                    "stopping, or restarting the target service."
                ),
                expires_at=spec.approval_expires_at,
                authorization_scope_sha256=spec.canonical_sha256(),
                now=observed_at,
                approval_id=spec.approval_id,
            )
        if (
            approval.job_id != record.job.job_id
            or approval.action != ApprovalAction.RECONCILE_TARGET_SERVICE
            or approval.authorization_scope_sha256 != spec.canonical_sha256()
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict(
                "service reconciliation approval already differs"
            )
        return TargetHostServiceReconciliationJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )


class TargetHostServiceReconciliationJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-job-artifact/v1"
    ] = "rolo-target-host-service-reconciliation-job-artifact/v1"
    job_id: str = Field(pattern=_JOB_ID)
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    original_job_id: str = Field(pattern=_JOB_ID)
    target_id: str
    execution: TargetHostServiceExecutionResult
    completed_at: datetime

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceReconciliationJobRunner:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetHostServiceReconciliationJobSpecStore,
        service_specs: TargetHostServiceJobSpecStore,
        artifact_root: Path,
        executor_factory: Callable[[TargetProfile], TargetHostServiceExecutor] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.service_specs = service_specs
        self.artifact_root = artifact_root.expanduser().absolute()
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetHostServiceExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        if profile.transport != TargetTransport.SSH:
            raise ValueError("service reconciliation requires an SSH target")
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
            credential_purpose=CredentialPurpose.SSH_PROVISIONING,
        )  # type: ignore[return-value]

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "host-service-reconciliation-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return (
            f"artifact://deployment-jobs/{job_id}/"
            "host-service-reconciliation-result.json"
        )

    def _load_artifact(
        self,
        job_id: str,
    ) -> TargetHostServiceReconciliationJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("service reconciliation artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("service reconciliation artifact is invalid")
        return TargetHostServiceReconciliationJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.RECONCILE_TARGET_SERVICE:
            raise DeploymentJobStateConflict(
                "Service reconciliation handler received another command"
            )
        if record.job.state in {
            DeploymentJobState.COMPLETE,
            DeploymentJobState.FAILED,
            DeploymentJobState.BLOCKED,
            DeploymentJobState.CANCELLED,
        }:
            return record
        spec = self.specs.load(job_id)
        if record.job.command.parameters_sha256 != spec.canonical_sha256():
            raise DeploymentJobStateConflict("service reconciliation spec digest mismatch")
        original = self.store.load_job(spec.original_job_id)
        original_spec = self.service_specs.load(spec.original_job_id)
        if (
            original.job.command_sha256 != spec.original_command_sha256
            or original_spec.canonical_sha256() != spec.original_spec_sha256
        ):
            raise DeploymentJobStateConflict("service reconciliation source changed")
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.RECONCILE_TARGET_SERVICE,
        )
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            ref = self._ref(job_id)
            artifact = self._load_artifact(job_id)
            if artifact is None:
                checkpoint = next(
                    (
                        item
                        for item in record.checkpoints
                        if item.attempt == record.attempt
                        and item.step_id == "observe-target-service"
                    ),
                    None,
                )
                if checkpoint is None:
                    record = self.store.start_step(
                        job_id,
                        step_id="observe-target-service",
                        state=DeploymentJobState.BOOTSTRAPPING,
                        remote=True,
                    )
                elif checkpoint.status != DeploymentStepStatus.RUNNING:
                    raise DeploymentJobStateConflict(
                        "service reconciliation checkpoint conflicts with artifact"
                    )
                registration = self.registrations.load(spec.target_id)
                if registration.connection is None:
                    raise DeploymentJobStateConflict(
                        "service reconciliation target has no SSH connection"
                    )
                if (
                    target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    )
                    != spec.target_registration_sha256
                ):
                    now = datetime.now(timezone.utc)
                    execution = TargetHostServiceExecutionResult(
                        request_id=spec.request.request_id,
                        request_sha256=spec.request.canonical_sha256(),
                        target_id=spec.target_id,
                        operation=TargetHostServiceOperation.STATUS,
                        status=TargetHostServiceStatus.FAILED,
                        error_code=TargetHostServiceError.INVALID_REQUEST,
                        started_at=now,
                        finished_at=now,
                    )
                else:
                    try:
                        execution = self._executor(
                            registration.target
                        ).execute_host_service(
                            spec.request,
                            cancel_event=cancel_event,
                        )
                    except Exception:
                        now = datetime.now(timezone.utc)
                        execution = TargetHostServiceExecutionResult(
                            request_id=spec.request.request_id,
                            request_sha256=spec.request.canonical_sha256(),
                            target_id=spec.target_id,
                            operation=TargetHostServiceOperation.STATUS,
                            status=TargetHostServiceStatus.FAILED,
                            error_code=TargetHostServiceError.PROTOCOL_ERROR,
                            started_at=now,
                            finished_at=now,
                        )
                artifact = TargetHostServiceReconciliationJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    original_job_id=spec.original_job_id,
                    target_id=spec.target_id,
                    execution=execution,
                    completed_at=datetime.now(timezone.utc),
                )
                atomic_write_text(
                    self._path(job_id),
                    artifact.model_dump_json(indent=2) + "\n",
                    require_absent=True,
                )
            elif (
                artifact.command_sha256 != record.job.command_sha256
                or artifact.spec_sha256 != spec.canonical_sha256()
                or artifact.original_job_id != spec.original_job_id
                or artifact.execution.request_sha256
                != spec.request.canonical_sha256()
            ):
                raise DeploymentJobStateConflict(
                    "service reconciliation artifact binding mismatch"
                )
            digest = artifact.canonical_sha256()
            execution = artifact.execution
            outcome = target_service_reconciliation_outcome(execution)
            if outcome is None:
                current = self.store.load_job(job_id)
                checkpoint = next(
                    item
                    for item in current.checkpoints
                    if item.attempt == current.attempt
                    and item.step_id == "observe-target-service"
                )
                if checkpoint.status == DeploymentStepStatus.RUNNING:
                    return self.store.fail_step(
                        job_id,
                        step_id="observe-target-service",
                        remote_state_known=True,
                        outcome_sha256=digest,
                        artifact_refs=[ref],
                    )
                return current
            already_applied = any(
                event.event.step_id == "remote-reconciled"
                and ref in event.event.artifact_refs
                for event in self.store.read_events(spec.original_job_id)
            )
            if not already_applied:
                self.store.reconcile_remote_step(
                    spec.original_job_id,
                    step_id="start-target-service",
                    outcome=outcome,
                    outcome_sha256=digest,
                    artifact_refs=[ref],
                )
            current = self.store.load_job(job_id)
            checkpoint = next(
                item
                for item in current.checkpoints
                if item.attempt == current.attempt
                and item.step_id == "observe-target-service"
            )
            if checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    job_id,
                    step_id="observe-target-service",
                    outcome_sha256=digest,
                    artifact_refs=[ref],
                )
            return self.store.complete_job(job_id, artifact_refs=[ref])
