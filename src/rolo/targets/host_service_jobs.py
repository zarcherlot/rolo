from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.bootstrap_jobs import TargetBootstrapJobSpecStore
from rolo.targets.credentials import CredentialPurpose, CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.host_provisioning_jobs import TargetHostProvisioningJobSpecStore
from rolo.targets.host_service import (
    TargetHostServiceError,
    TargetHostServiceExecutionResult,
    TargetHostServiceOperation,
    TargetHostServiceRequest,
    TargetHostServiceStatus,
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


class TargetHostServiceJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-job-submission/v1"] = (
        "rolo-target-host-service-job-submission/v1"
    )
    host_configuration_job_id: str = Field(pattern=_JOB_ID)
    bootstrap_job_id: str = Field(pattern=_JOB_ID)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-job-spec/v1"] = (
        "rolo-target-host-service-job-spec/v1"
    )
    target_id: str
    target_registration_sha256: str = Field(pattern=_SHA256)
    host_configuration_job_id: str = Field(pattern=_JOB_ID)
    host_configuration_command_sha256: str = Field(pattern=_SHA256)
    host_configuration_spec_sha256: str = Field(pattern=_SHA256)
    bootstrap_job_id: str = Field(pattern=_JOB_ID)
    bootstrap_command_sha256: str = Field(pattern=_SHA256)
    bootstrap_spec_sha256: str = Field(pattern=_SHA256)
    request: TargetHostServiceRequest
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime

    @model_validator(mode="after")
    def bind_spec(self) -> TargetHostServiceJobSpec:
        if self.target_id != self.request.target_id:
            raise ValueError("host service Job target differs from request")
        if self.request.operation != TargetHostServiceOperation.START:
            raise ValueError("host service Job requires a START request")
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("host service approval expiry must be timezone-aware")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-submission-intent/v1"] = (
        "rolo-target-host-service-submission-intent/v1"
    )
    requested_by: str = Field(pattern=_PRINCIPAL)
    interaction_surface: InteractionSurface
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetHostServiceJobSpec


class TargetHostServiceSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host service intent root cannot be a symbolic link")

    def _path(self, idempotency_key: str) -> Path:
        identity = hashlib.sha256(idempotency_key.encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def lock_path(self, idempotency_key: str) -> Path:
        return self._path(idempotency_key)

    def load(self, idempotency_key: str) -> TargetHostServiceSubmissionIntent:
        path = self._path(idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise FileNotFoundError(path)
        return TargetHostServiceSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetHostServiceSubmissionIntent,
    ) -> TargetHostServiceSubmissionIntent:
        atomic_write_text(
            self._path(intent.idempotency_key),
            intent.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
            require_absent=True,
        )
        return intent


class TargetHostServiceJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host service spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(_JOB_ID, job_id) is None:
            raise ValueError("invalid host service Job ID")
        return self.root / job_id / "host-service-spec.json"

    def load(self, job_id: str) -> TargetHostServiceJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host service Job spec is unavailable")
        return TargetHostServiceJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        job_id: str,
        spec: TargetHostServiceJobSpec,
    ) -> TargetHostServiceJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict("host service Job spec already differs")
            return current
        atomic_write_text(
            path,
            spec.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        return spec


class TargetHostServiceJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-job-submission-result/v1"] = (
        "rolo-target-host-service-job-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetHostServiceJobSpec
    approval: ApprovalRequest


class TargetHostServiceSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetHostServiceJobSpecStore,
        intents: TargetHostServiceSubmissionIntentStore,
        host_specs: TargetHostProvisioningJobSpecStore,
        bootstrap_specs: TargetBootstrapJobSpecStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.host_specs = host_specs
        self.bootstrap_specs = bootstrap_specs
        self.registrations = registrations

    def submit(
        self,
        *,
        submission: TargetHostServiceJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetHostServiceJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        with interprocess_lock(self.intents.lock_path(idempotency_key)):
            try:
                intent = self.intents.load(idempotency_key)
            except FileNotFoundError:
                host_job = self.store.load_job(submission.host_configuration_job_id)
                bootstrap_job = self.store.load_job(submission.bootstrap_job_id)
                if host_job.job.command.command not in {
                    DeploymentCommandKind.PROVISION_HOST,
                    DeploymentCommandKind.ROLLBACK_HOST,
                } or host_job.job.state != DeploymentJobState.COMPLETE:
                    raise DeploymentJobStateConflict(
                        "host service requires a completed host configuration Job"
                    ) from None
                if (
                    bootstrap_job.job.command.command != DeploymentCommandKind.BOOTSTRAP
                    or bootstrap_job.job.state != DeploymentJobState.COMPLETE
                ):
                    raise DeploymentJobStateConflict(
                        "host service requires a completed Bootstrap Job"
                    ) from None
                if host_job.job.command.target_id != bootstrap_job.job.command.target_id:
                    raise ValueError(
                        "host service source Jobs belong to different targets"
                    ) from None
                target_id = host_job.job.command.target_id
                host_spec = self.host_specs.load(host_job.job.job_id)
                bootstrap_spec = self.bootstrap_specs.load(bootstrap_job.job.job_id)
                if host_spec.target_id != target_id or bootstrap_spec.target_id != target_id:
                    raise DeploymentJobStateConflict(
                        "host service source specs differ from target"
                    ) from None
                registration = self.registrations.load(target_id)
                if registration.connection is None:
                    raise ValueError("host service requires an SSH target") from None
                registration_sha256 = target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                )
                request = TargetHostServiceRequest(
                    request_id="host-service-"
                    + hashlib.sha256(
                        f"{target_id}:{idempotency_key}".encode()
                    ).hexdigest()[:24],
                    operation=TargetHostServiceOperation.START,
                    target_id=target_id,
                    expected_host_plan_sha256=host_spec.plan.canonical_sha256(),
                    expected_runtime_manifest_sha256=bootstrap_spec.manifest_sha256,
                    unit_name=host_spec.plan.template_bundle.systemd_unit_name,
                )
                approval_id = "approval-" + hashlib.sha256(
                    f"host-service:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()[:32]
                spec = TargetHostServiceJobSpec(
                    target_id=target_id,
                    target_registration_sha256=registration_sha256,
                    host_configuration_job_id=host_job.job.job_id,
                    host_configuration_command_sha256=host_job.job.command_sha256,
                    host_configuration_spec_sha256=host_spec.canonical_sha256(),
                    bootstrap_job_id=bootstrap_job.job.job_id,
                    bootstrap_command_sha256=bootstrap_job.job.command_sha256,
                    bootstrap_spec_sha256=bootstrap_spec.canonical_sha256(),
                    request=request,
                    approval_id=approval_id,
                    approver_principal=submission.approver_principal,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetHostServiceSubmissionIntent(
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
                    "host service idempotency key was reused"
                )
        spec = intent.spec
        command = DeploymentCommand(
            command=DeploymentCommandKind.START_TARGET_SERVICE,
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
                action=ApprovalAction.START_TARGET_SERVICE,
                risk="R2",
                approver_principal=spec.approver_principal,
                summary=(
                    "Start the installed loopback-only target service after verifying "
                    "the host plan and active runtime manifest digests."
                ),
                expires_at=spec.approval_expires_at,
                authorization_scope_sha256=spec.canonical_sha256(),
                now=observed_at,
                approval_id=spec.approval_id,
            )
        if (
            approval.job_id != record.job.job_id
            or approval.action != ApprovalAction.START_TARGET_SERVICE
            or approval.authorization_scope_sha256 != spec.canonical_sha256()
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict("host service approval already differs")
        return TargetHostServiceJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )


class TargetHostServiceJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-job-artifact/v1"] = (
        "rolo-target-host-service-job-artifact/v1"
    )
    job_id: str = Field(pattern=_JOB_ID)
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str
    execution: TargetHostServiceExecutionResult
    completed_at: datetime

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceExecutor(Protocol):
    def execute_host_service(
        self,
        request: TargetHostServiceRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostServiceExecutionResult: ...


class TargetHostServiceJobRunner:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetHostServiceJobSpecStore,
        host_specs: TargetHostProvisioningJobSpecStore,
        bootstrap_specs: TargetBootstrapJobSpecStore,
        artifact_root: Path,
        executor_factory: Callable[[TargetProfile], TargetHostServiceExecutor] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.host_specs = host_specs
        self.bootstrap_specs = bootstrap_specs
        self.artifact_root = artifact_root.expanduser().absolute()
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetHostServiceExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        if profile.transport != TargetTransport.SSH:
            raise ValueError("host service requires an SSH target")
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
            credential_purpose=CredentialPurpose.SSH_PROVISIONING,
        )  # type: ignore[return-value]

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "host-service-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/host-service-result.json"

    def _load_artifact(self, job_id: str) -> TargetHostServiceJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("host service artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host service artifact is invalid")
        return TargetHostServiceJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _persist(self, artifact: TargetHostServiceJobArtifact) -> None:
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("host service artifact already differs")
            return
        atomic_write_text(
            self._path(artifact.job_id),
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetHostServiceJobSpec,
        artifact: TargetHostServiceJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
            or artifact.execution.request_sha256 != spec.request.canonical_sha256()
            or artifact.execution.request_id != spec.request.request_id
            or artifact.execution.target_id != spec.target_id
            or artifact.execution.operation != TargetHostServiceOperation.START
        ):
            raise DeploymentJobStateConflict("host service artifact binding mismatch")
        if artifact.execution.status != TargetHostServiceStatus.FAILED and (
            artifact.execution.observed_host_plan_sha256
            != spec.request.expected_host_plan_sha256
            or artifact.execution.observed_runtime_manifest_sha256
            != spec.request.expected_runtime_manifest_sha256
        ):
            raise DeploymentJobStateConflict(
                "host service observed state differs from approved digests"
            )
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "start-target-service"
            ),
            None,
        )
        ref = self._ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.execution.status == TargetHostServiceStatus.FAILED:
            if checkpoint is not None and checkpoint.status in {
                DeploymentStepStatus.FAILED,
                DeploymentStepStatus.UNKNOWN,
            }:
                return record
            remote_known = artifact.execution.error_code not in {
                TargetHostServiceError.CANCELLED,
                TargetHostServiceError.CONNECTION_FAILED,
                TargetHostServiceError.PROTOCOL_ERROR,
            }
            return self.store.fail_step(
                record.job.job_id,
                step_id="start-target-service",
                remote_state_known=remote_known,
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        if checkpoint is None:
            raise DeploymentJobStateConflict("host service artifact has no checkpoint")
        if checkpoint.status == DeploymentStepStatus.RUNNING:
            self.store.complete_step(
                record.job.job_id,
                step_id="start-target-service",
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        elif checkpoint.status != DeploymentStepStatus.COMPLETE:
            raise DeploymentJobStateConflict(
                "host service artifact conflicts with checkpoint"
            )
        return self.store.complete_job(record.job.job_id, artifact_refs=[ref])

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.START_TARGET_SERVICE:
            raise DeploymentJobStateConflict("Host service handler received another command")
        if record.job.state in {
            DeploymentJobState.COMPLETE,
            DeploymentJobState.FAILED,
            DeploymentJobState.BLOCKED,
            DeploymentJobState.CANCELLED,
        }:
            return record
        spec = self.specs.load(job_id)
        if record.job.command.parameters_sha256 != spec.canonical_sha256():
            raise DeploymentJobStateConflict("host service spec digest mismatch")
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.START_TARGET_SERVICE,
        )
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            host_job = self.store.load_job(spec.host_configuration_job_id)
            bootstrap_job = self.store.load_job(spec.bootstrap_job_id)
            host_spec = self.host_specs.load(spec.host_configuration_job_id)
            bootstrap_spec = self.bootstrap_specs.load(spec.bootstrap_job_id)
            registration = self.registrations.load(spec.target_id)
            if registration.connection is None:
                raise DeploymentJobStateConflict(
                    "host service target no longer has an SSH connection"
                )
            registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            source_changed = (
                host_job.job.state != DeploymentJobState.COMPLETE
                or bootstrap_job.job.state != DeploymentJobState.COMPLETE
                or host_job.job.command_sha256
                != spec.host_configuration_command_sha256
                or bootstrap_job.job.command_sha256 != spec.bootstrap_command_sha256
                or host_spec.canonical_sha256()
                != spec.host_configuration_spec_sha256
                or bootstrap_spec.canonical_sha256() != spec.bootstrap_spec_sha256
                or registration_sha256 != spec.target_registration_sha256
            )
            record = self.store.start_step(
                job_id,
                step_id="start-target-service",
                state=DeploymentJobState.BOOTSTRAPPING,
                remote=not source_changed,
            )
            if source_changed:
                now = datetime.now(timezone.utc)
                execution = TargetHostServiceExecutionResult(
                    request_id=spec.request.request_id,
                    request_sha256=spec.request.canonical_sha256(),
                    target_id=spec.target_id,
                    operation=TargetHostServiceOperation.START,
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
                        operation=TargetHostServiceOperation.START,
                        status=TargetHostServiceStatus.FAILED,
                        error_code=TargetHostServiceError.PROTOCOL_ERROR,
                        started_at=now,
                        finished_at=now,
                    )
            artifact = TargetHostServiceJobArtifact(
                job_id=job_id,
                command_sha256=record.job.command_sha256,
                spec_sha256=spec.canonical_sha256(),
                target_id=spec.target_id,
                execution=execution,
                completed_at=datetime.now(timezone.utc),
            )
            self._persist(artifact)
            return self._finish(record, spec, artifact)
