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
from rolo.targets.credentials import CredentialPurpose, CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentRemoteReconciliationOutcome,
    DeploymentStepStatus,
)
from rolo.targets.host_provisioning import (
    TargetHostProvisioningObservation,
    TargetHostProvisioningObservationStatus,
    TargetHostProvisioningPlan,
)
from rolo.targets.host_provisioning_jobs import TargetHostProvisioningJobSpecStore
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
from rolo.targets.registration import TargetRegistrationService

_SHA256 = r"^[0-9a-f]{64}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_JOB_ID = r"^deployment-[0-9a-f]{32}$"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


class TargetHostReconciliationJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-job-submission/v1"] = (
        "rolo-target-host-reconciliation-job-submission/v1"
    )
    original_job_id: str = Field(pattern=_JOB_ID)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostReconciliationJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-job-spec/v1"] = (
        "rolo-target-host-reconciliation-job-spec/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    original_job_id: str = Field(pattern=_JOB_ID)
    original_command_sha256: str = Field(pattern=_SHA256)
    original_spec_sha256: str = Field(pattern=_SHA256)
    plan: TargetHostProvisioningPlan
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime

    @model_validator(mode="after")
    def bind_spec(self) -> TargetHostReconciliationJobSpec:
        if self.target_id != self.plan.target_id:
            raise ValueError("host reconciliation target differs from the frozen plan")
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("host reconciliation approval expiry must be timezone-aware")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostReconciliationJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host reconciliation spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(_JOB_ID, job_id) is None:
            raise ValueError("invalid host reconciliation Job ID")
        return self.root / job_id / "host-reconciliation-spec.json"

    def load(self, job_id: str) -> TargetHostReconciliationJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host reconciliation Job spec is unavailable")
        return TargetHostReconciliationJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        job_id: str,
        spec: TargetHostReconciliationJobSpec,
    ) -> TargetHostReconciliationJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict(
                    "host reconciliation Job spec already differs"
                )
            return current
        atomic_write_text(
            path,
            spec.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        return spec


class TargetHostReconciliationSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-submission-intent/v1"] = (
        "rolo-target-host-reconciliation-submission-intent/v1"
    )
    requested_by: str = Field(pattern=_PRINCIPAL)
    interaction_surface: InteractionSurface
    idempotency_key: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"
    )
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetHostReconciliationJobSpec


class TargetHostReconciliationSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host reconciliation intent root cannot be a symbolic link")

    def _path(self, idempotency_key: str) -> Path:
        identity = hashlib.sha256(idempotency_key.encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def lock_path(self, idempotency_key: str) -> Path:
        return self._path(idempotency_key)

    def load(self, idempotency_key: str) -> TargetHostReconciliationSubmissionIntent:
        path = self._path(idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise FileNotFoundError(path)
        return TargetHostReconciliationSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetHostReconciliationSubmissionIntent,
    ) -> TargetHostReconciliationSubmissionIntent:
        atomic_write_text(
            self._path(intent.idempotency_key),
            intent.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
            require_absent=True,
        )
        return intent


class TargetHostReconciliationJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-reconciliation-job-submission-result/v1"
    ] = "rolo-target-host-reconciliation-job-submission-result/v1"
    job: DeploymentJobRecord
    spec: TargetHostReconciliationJobSpec
    approval: ApprovalRequest


class TargetHostReconciliationSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetHostReconciliationJobSpecStore,
        provisioning_specs: TargetHostProvisioningJobSpecStore,
        intents: TargetHostReconciliationSubmissionIntentStore,
    ) -> None:
        self.store = store
        self.specs = specs
        self.provisioning_specs = provisioning_specs
        self.intents = intents

    def submit(
        self,
        *,
        submission: TargetHostReconciliationJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetHostReconciliationJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        intent_path = self.intents.lock_path(idempotency_key)
        with interprocess_lock(intent_path):
            try:
                intent = self.intents.load(idempotency_key)
            except FileNotFoundError:
                original = self.store.load_job(submission.original_job_id)
                if original.job.command.command != DeploymentCommandKind.PROVISION_HOST:
                    raise ValueError(
                        "host reconciliation requires a host provisioning Job"
                    ) from None
                if (
                    original.job.state != DeploymentJobState.BLOCKED
                    or original.recovery_disposition.value
                    != "REQUIRES_RECONCILIATION"
                ):
                    raise DeploymentJobStateConflict(
                        "host provisioning Job does not require reconciliation"
                    ) from None
                provisioning_spec = self.provisioning_specs.load(
                    submission.original_job_id
                )
                approval_seed = hashlib.sha256(
                    f"{original.job.job_id}:{idempotency_key}".encode()
                ).hexdigest()[:32]
                spec = TargetHostReconciliationJobSpec(
                    target_id=original.job.command.target_id,
                    original_job_id=original.job.job_id,
                    original_command_sha256=original.job.command_sha256,
                    original_spec_sha256=provisioning_spec.canonical_sha256(),
                    plan=provisioning_spec.plan,
                    approval_id=f"approval-{approval_seed}",
                    approver_principal=submission.approver_principal,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetHostReconciliationSubmissionIntent(
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
                    "host reconciliation idempotency key was reused"
                )
        spec = intent.spec
        command = DeploymentCommand(
            command=DeploymentCommandKind.RECONCILE_HOST,
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
                action=ApprovalAction.USE_SUDO,
                risk="R2",
                approver_principal=spec.approver_principal,
                summary=(
                    "Read and compare digest-bound privileged host state; no host "
                    "provisioning write is replayed."
                ),
                expires_at=spec.approval_expires_at,
                authorization_scope_sha256=spec.canonical_sha256(),
                now=observed_at,
                approval_id=spec.approval_id,
            )
        return TargetHostReconciliationJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )


class TargetHostReconciliationJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-job-artifact/v1"] = (
        "rolo-target-host-reconciliation-job-artifact/v1"
    )
    job_id: str = Field(pattern=_JOB_ID)
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    original_job_id: str = Field(pattern=_JOB_ID)
    target_id: str
    observation: TargetHostProvisioningObservation
    completed_at: datetime

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostProvisioningObserver(Protocol):
    def observe_host_provisioning(
        self,
        plan: TargetHostProvisioningPlan,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostProvisioningObservation: ...


class TargetHostReconciliationJobRunner:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetHostReconciliationJobSpecStore,
        provisioning_specs: TargetHostProvisioningJobSpecStore,
        artifact_root: Path,
        executor_factory: Callable[[TargetProfile], TargetHostProvisioningObserver]
        | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.provisioning_specs = provisioning_specs
        self.artifact_root = artifact_root.expanduser().absolute()
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetHostProvisioningObserver:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        if profile.transport != TargetTransport.SSH:
            raise ValueError("host reconciliation requires an SSH target")
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
            credential_purpose=CredentialPurpose.SSH_PROVISIONING,
        )  # type: ignore[return-value]

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "host-reconciliation-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/host-reconciliation-result.json"

    def _load_artifact(
        self,
        job_id: str,
    ) -> TargetHostReconciliationJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("host reconciliation artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("host reconciliation artifact is invalid")
        return TargetHostReconciliationJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _persist(self, artifact: TargetHostReconciliationJobArtifact) -> None:
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict(
                    "host reconciliation artifact already differs"
                )
            return
        try:
            atomic_write_text(
                self._path(artifact.job_id),
                artifact.model_dump_json(indent=2) + "\n",
                require_absent=True,
            )
        except FileExistsError:
            if self._load_artifact(artifact.job_id) != artifact:
                raise DeploymentJobStateConflict(
                    "host reconciliation artifact already differs"
                ) from None

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.RECONCILE_HOST:
            raise DeploymentJobStateConflict(
                "Host reconciliation handler received another command"
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
            raise DeploymentJobStateConflict("host reconciliation spec digest mismatch")
        original = self.store.load_job(spec.original_job_id)
        original_spec = self.provisioning_specs.load(spec.original_job_id)
        if (
            original.job.command_sha256 != spec.original_command_sha256
            or original_spec.canonical_sha256() != spec.original_spec_sha256
            or original_spec.plan != spec.plan
        ):
            raise DeploymentJobStateConflict("host reconciliation source binding changed")
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.USE_SUDO,
        )
        with self.store.target_lease(spec.target_id):
            ref = self._ref(job_id)
            artifact = self._load_artifact(job_id)
            checkpoint = next(
                (
                    item
                    for item in record.checkpoints
                    if item.attempt == record.attempt
                    and item.step_id == "observe-host-provisioning"
                ),
                None,
            )
            if artifact is None:
                if checkpoint is None:
                    record = self.store.start_step(
                        job_id,
                        step_id="observe-host-provisioning",
                        state=DeploymentJobState.BOOTSTRAPPING,
                        remote=True,
                    )
                elif checkpoint.status != DeploymentStepStatus.RUNNING:
                    raise DeploymentJobStateConflict(
                        "host reconciliation checkpoint conflicts with its artifact"
                    )
                registration = self.registrations.load(spec.target_id)
                observation = self._executor(
                    registration.target
                ).observe_host_provisioning(spec.plan, cancel_event=cancel_event)
                artifact = TargetHostReconciliationJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    original_job_id=spec.original_job_id,
                    target_id=spec.target_id,
                    observation=observation,
                    completed_at=datetime.now(timezone.utc),
                )
                self._persist(artifact)
            elif (
                artifact.command_sha256 != record.job.command_sha256
                or artifact.spec_sha256 != spec.canonical_sha256()
                or artifact.original_job_id != spec.original_job_id
                or artifact.target_id != spec.target_id
                or artifact.observation.target_id != spec.target_id
                or artifact.observation.expected_plan_sha256
                != spec.plan.canonical_sha256()
            ):
                raise DeploymentJobStateConflict(
                    "host reconciliation artifact binding mismatch"
                )
            observation = artifact.observation
            digest = artifact.canonical_sha256()
            if observation.status == TargetHostProvisioningObservationStatus.FAILED:
                if checkpoint is not None and checkpoint.status == DeploymentStepStatus.FAILED:
                    return self.store.load_job(job_id)
                return self.store.fail_step(
                    job_id,
                    step_id="observe-host-provisioning",
                    remote_state_known=True,
                    outcome_sha256=digest,
                    artifact_refs=[ref],
                )
            outcome = (
                DeploymentRemoteReconciliationOutcome.EXACT
                if observation.status == TargetHostProvisioningObservationStatus.EXACT
                else DeploymentRemoteReconciliationOutcome.NOT_COMMITTED
                if observation.status
                == TargetHostProvisioningObservationStatus.NOT_COMMITTED
                else DeploymentRemoteReconciliationOutcome.DIVERGED
            )
            already_applied = any(
                event.event.step_id == "remote-reconciled"
                and ref in event.event.artifact_refs
                for event in self.store.read_events(spec.original_job_id)
            )
            if not already_applied:
                self.store.reconcile_remote_step(
                    spec.original_job_id,
                    step_id="provision-host",
                    outcome=outcome,
                    outcome_sha256=digest,
                    artifact_refs=[ref],
                )
            current = self.store.load_job(job_id)
            checkpoint = next(
                (
                    item
                    for item in current.checkpoints
                    if item.attempt == current.attempt
                    and item.step_id == "observe-host-provisioning"
                ),
                None,
            )
            if checkpoint is not None and checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    job_id,
                    step_id="observe-host-provisioning",
                    outcome_sha256=digest,
                    artifact_refs=[ref],
                )
            return self.store.complete_job(job_id, artifact_refs=[ref])
