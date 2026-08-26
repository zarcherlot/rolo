from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.credentials import CredentialPurpose, CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.host_provisioning import (
    TargetHostProvisioningExecutionResult,
    TargetHostProvisioningExecutionStatus,
    TargetHostProvisioningPlan,
    build_target_host_provisioning_plan,
    canonical_ed25519_ssh_public_key,
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

_SHA256 = r"^[0-9a-f]{64}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_IDEMPOTENCY = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class TargetHostProvisioningJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-job-submission/v1"] = (
        "rolo-target-host-provisioning-job-submission/v1"
    )
    bootstrap_public_key: str = Field(min_length=1, max_length=16_384)
    runtime_public_key: str = Field(min_length=1, max_length=16_384)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    expected_current_plan_sha256: str | None = Field(default=None, pattern=_SHA256)

    @field_validator("bootstrap_public_key", "runtime_public_key")
    @classmethod
    def canonicalize_public_key(cls, value: str) -> str:
        return canonical_ed25519_ssh_public_key(value)

    @model_validator(mode="after")
    def require_distinct_keys(self) -> TargetHostProvisioningJobSubmission:
        if self.bootstrap_public_key == self.runtime_public_key:
            raise ValueError("host provisioning submission requires distinct SSH keys")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode()
        ).hexdigest()


class TargetHostProvisioningJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-job-spec/v1"] = (
        "rolo-target-host-provisioning-job-spec/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    plan: TargetHostProvisioningPlan
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime
    approval_action: Literal[
        ApprovalAction.USE_SUDO,
        ApprovalAction.ROLLBACK_HOST_CONFIGURATION,
    ] = ApprovalAction.USE_SUDO

    @model_validator(mode="after")
    def bind_spec(self) -> TargetHostProvisioningJobSpec:
        if self.target_id != self.plan.target_id:
            raise ValueError("host provisioning Job target mismatch")
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("host provisioning approval expiry must be timezone-aware")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode()
        ).hexdigest()


class TargetHostProvisioningSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-submission-intent/v1"] = (
        "rolo-target-host-provisioning-submission-intent/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetHostProvisioningJobSpec


class TargetHostProvisioningSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host provisioning intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        identity = hashlib.sha256(f"{target_id}:{idempotency_key}".encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def load(
        self,
        target_id: str,
        idempotency_key: str,
    ) -> TargetHostProvisioningSubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise FileNotFoundError(path)
        return TargetHostProvisioningSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetHostProvisioningSubmissionIntent,
        *,
        acquire_lock: bool = True,
    ) -> TargetHostProvisioningSubmissionIntent:
        path = self._path(intent.target_id, intent.idempotency_key)
        try:
            atomic_write_text(
                path,
                intent.model_dump_json(indent=2) + "\n",
                acquire_lock=acquire_lock,
                require_absent=True,
            )
        except FileExistsError:
            current = self.load(intent.target_id, intent.idempotency_key)
            if current != intent:
                raise DeploymentJobStateConflict(
                    "host provisioning submission intent already differs"
                ) from None
            return current
        return intent

    def lock_path(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key)


class TargetHostProvisioningJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host provisioning spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid host provisioning Job ID")
        return self.root / job_id / "host-provisioning-spec.json"

    def contains(self, job_id: str) -> bool:
        return self._path(job_id).is_file()

    def load(self, job_id: str) -> TargetHostProvisioningJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host provisioning Job spec is unavailable")
        return TargetHostProvisioningJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        job_id: str,
        spec: TargetHostProvisioningJobSpec,
    ) -> TargetHostProvisioningJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict(
                    "host provisioning Job spec already differs"
                )
            return current
        try:
            atomic_write_text(
                path,
                spec.model_dump_json(indent=2) + "\n",
                require_absent=True,
            )
        except FileExistsError:
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict(
                    "host provisioning Job spec already differs"
                ) from None
            return current
        return spec


class TargetHostProvisioningJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-provisioning-job-submission-result/v1"
    ] = "rolo-target-host-provisioning-job-submission-result/v1"
    job: DeploymentJobRecord
    spec: TargetHostProvisioningJobSpec
    approval: ApprovalRequest


class TargetHostProvisioningSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetHostProvisioningJobSpecStore,
        intents: TargetHostProvisioningSubmissionIntentStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations

    @staticmethod
    def _validate_intent(
        intent: TargetHostProvisioningSubmissionIntent,
        *,
        submission: TargetHostProvisioningJobSubmission,
        requested_by: str,
    ) -> None:
        if (
            intent.requested_by != requested_by
            or intent.submission_sha256 != submission.canonical_sha256()
        ):
            raise DeploymentJobStateConflict(
                "host provisioning idempotency key was reused"
            )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetHostProvisioningJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetHostProvisioningJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        intent_path = self.intents.lock_path(target_id, idempotency_key)
        with interprocess_lock(intent_path):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                registration = self.registrations.load(target_id)
                if registration.connection is None:
                    raise ValueError(
                        "host provisioning requires a registered SSH connection"
                    ) from None
                plan = build_target_host_provisioning_plan(
                    target_id=target_id,
                    target_registration_sha256=target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    ),
                    connection=registration.connection,
                    bootstrap_public_key=submission.bootstrap_public_key,
                    runtime_public_key=submission.runtime_public_key,
                    expected_current_plan_sha256=(
                        submission.expected_current_plan_sha256
                    ),
                )
                spec = TargetHostProvisioningJobSpec(
                    target_id=target_id,
                    plan=plan,
                    approval_id=f"approval-{uuid4().hex}",
                    approver_principal=submission.approver_principal,
                    approval_expires_at=(
                        observed_at + timedelta(seconds=submission.approval_ttl_s)
                    ),
                )
                intent = self.intents.persist(
                    TargetHostProvisioningSubmissionIntent(
                        target_id=target_id,
                        requested_by=requested_by,
                        idempotency_key=idempotency_key,
                        submission_sha256=submission.canonical_sha256(),
                        spec=spec,
                    ),
                    acquire_lock=False,
                )
            self._validate_intent(
                intent,
                submission=submission,
                requested_by=requested_by,
            )
        spec = intent.spec
        command = DeploymentCommand(
            command=DeploymentCommandKind.PROVISION_HOST,
            target_id=target_id,
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
            try:
                approval = self.store.request_approval(
                    record.job.job_id,
                    action=spec.approval_action,
                    risk="R3",
                    approver_principal=spec.approver_principal,
                    summary=(
                        "Apply nine digest-bound host provisioning effects with sudo; "
                        "install separate bootstrap/runtime forced-command keys."
                    ),
                    expires_at=spec.approval_expires_at,
                    authorization_scope_sha256=spec.canonical_sha256(),
                    now=observed_at,
                    approval_id=spec.approval_id,
                )
            except FileExistsError:
                approval = self.store.load_approval_request(spec.approval_id)
        if (
            approval.job_id != record.job.job_id
            or approval.authorization_scope_sha256 != spec.canonical_sha256()
            or approval.action != spec.approval_action
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict(
                "host provisioning Job approval already differs"
            )
        return TargetHostProvisioningJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )


class TargetHostProvisioningJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-job-artifact/v1"] = (
        "rolo-target-host-provisioning-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    status: Literal["SUCCEEDED", "FAILED"]
    failure_code: Literal["TARGET_REGISTRATION_CHANGED", "RUNNER_ERROR"] | None = None
    execution: TargetHostProvisioningExecutionResult | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_outcome(self) -> TargetHostProvisioningJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("host provisioning artifact time must be timezone-aware")
        if self.execution is None:
            if self.status != "FAILED" or self.failure_code is None:
                raise ValueError("host provisioning failure artifact is incomplete")
        else:
            expected = (
                "SUCCEEDED"
                if self.execution.status
                in {
                    TargetHostProvisioningExecutionStatus.APPLIED,
                    TargetHostProvisioningExecutionStatus.ALREADY_CURRENT,
                }
                else "FAILED"
            )
            if self.status != expected or self.failure_code is not None:
                raise ValueError("host provisioning artifact status mismatch")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode()
        ).hexdigest()


class TargetHostProvisioner(Protocol):
    def provision_host(
        self,
        plan: TargetHostProvisioningPlan,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostProvisioningExecutionResult: ...


class TargetHostProvisioningJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetHostProvisioningJobSpecStore,
        artifact_root: Path,
        *,
        executor_factory: Callable[[TargetProfile], TargetHostProvisioner] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.artifact_root = artifact_root.expanduser().absolute()
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetHostProvisioner:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        if profile.transport != TargetTransport.SSH:
            raise ValueError("host provisioning requires an SSH target")
        executor = target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
            credential_purpose=CredentialPurpose.SSH_PROVISIONING,
        )
        return executor  # type: ignore[return-value]

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "host-provisioning-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/host-provisioning-result.json"

    def _load_artifact(self, job_id: str) -> TargetHostProvisioningJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("host provisioning artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host provisioning artifact is invalid")
        return TargetHostProvisioningJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _persist(self, artifact: TargetHostProvisioningJobArtifact) -> None:
        path = self._path(artifact.job_id)
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict(
                    "host provisioning artifact already differs"
                )
            return
        atomic_write_text(
            path,
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetHostProvisioningJobSpec,
        artifact: TargetHostProvisioningJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
        ):
            raise DeploymentJobStateConflict(
                "host provisioning artifact binding mismatch"
            )
        if artifact.execution is not None and (
            artifact.execution.target_id != spec.target_id
            or artifact.execution.plan_sha256 != spec.plan.canonical_sha256()
        ):
            raise DeploymentJobStateConflict(
                "host provisioning execution differs from spec"
            )
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt
                and item.step_id == "provision-host"
            ),
            None,
        )
        ref = self._ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == "FAILED":
            if checkpoint is not None and checkpoint.status in {
                DeploymentStepStatus.FAILED,
                DeploymentStepStatus.UNKNOWN,
            }:
                return record
            return self.store.fail_step(
                record.job.job_id,
                step_id="provision-host",
                remote_state_known=(
                    artifact.execution is not None
                    or artifact.failure_code == "TARGET_REGISTRATION_CHANGED"
                ),
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        if checkpoint is None:
            raise DeploymentJobStateConflict(
                "host provisioning artifact has no checkpoint"
            )
        if checkpoint.status == DeploymentStepStatus.RUNNING:
            self.store.complete_step(
                record.job.job_id,
                step_id="provision-host",
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        elif checkpoint.status != DeploymentStepStatus.COMPLETE:
            raise DeploymentJobStateConflict(
                "host provisioning artifact conflicts with checkpoint"
            )
        return self.store.complete_job(record.job.job_id, artifact_refs=[ref])

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command not in {
            DeploymentCommandKind.PROVISION_HOST,
            DeploymentCommandKind.ROLLBACK_HOST,
        }:
            raise DeploymentJobStateConflict(
                "Host provisioning handler received another command"
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
            raise DeploymentJobStateConflict("host provisioning spec digest mismatch")
        approval = self.store.load_approval_request(spec.approval_id)
        if approval.authorization_scope_sha256 != spec.canonical_sha256():
            raise DeploymentJobStateConflict("host provisioning approval scope mismatch")
        if record.cancel_requested or (cancel_event is not None and cancel_event.is_set()):
            if not record.cancel_requested:
                self.store.request_cancel(job_id)
            return self.store.resolve_cancel(job_id, remote_termination_confirmed=True)
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            self.store.verify_approval(
                spec.approval_id,
                job_id=job_id,
                target_id=spec.target_id,
                command_sha256=record.job.command_sha256,
                action=spec.approval_action,
            )
            registration = self.registrations.load(spec.target_id)
            observed_registration = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            running = any(
                item.attempt == record.attempt
                and item.step_id == "provision-host"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "host provisioning remote checkpoint requires reconciliation"
                )
            if observed_registration != spec.plan.target_registration_sha256:
                record = self.store.start_step(
                    job_id,
                    step_id="provision-host",
                    state=DeploymentJobState.BOOTSTRAPPING,
                    remote=False,
                )
                artifact = TargetHostProvisioningJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    status="FAILED",
                    failure_code="TARGET_REGISTRATION_CHANGED",
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                record = self.store.start_step(
                    job_id,
                    step_id="provision-host",
                    state=DeploymentJobState.BOOTSTRAPPING,
                    remote=True,
                )
                try:
                    execution = self._executor(registration.target).provision_host(
                        spec.plan,
                        cancel_event=cancel_event,
                    )
                except Exception:
                    artifact = TargetHostProvisioningJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        status="FAILED",
                        failure_code="RUNNER_ERROR",
                        completed_at=datetime.now(timezone.utc),
                    )
                else:
                    artifact = TargetHostProvisioningJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        status=(
                            "SUCCEEDED"
                            if execution.status
                            in {
                                TargetHostProvisioningExecutionStatus.APPLIED,
                                TargetHostProvisioningExecutionStatus.ALREADY_CURRENT,
                            }
                            else "FAILED"
                        ),
                        execution=execution,
                        completed_at=datetime.now(timezone.utc),
                    )
            self._persist(artifact)
            return self._finish(record, spec, artifact)
