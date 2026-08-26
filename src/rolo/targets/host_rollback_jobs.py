from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
)
from rolo.targets.host_provisioning import build_target_host_provisioning_plan
from rolo.targets.host_provisioning_jobs import (
    TargetHostProvisioningJobSpec,
    TargetHostProvisioningJobSpecStore,
)
from rolo.targets.models import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
)
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


class TargetHostRollbackJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-rollback-job-submission/v1"] = (
        "rolo-target-host-rollback-job-submission/v1"
    )
    current_host_job_id: str = Field(pattern=_JOB_ID)
    rollback_to_host_job_id: str = Field(pattern=_JOB_ID)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostRollbackSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-rollback-submission-intent/v1"] = (
        "rolo-target-host-rollback-submission-intent/v1"
    )
    requested_by: str = Field(pattern=_PRINCIPAL)
    interaction_surface: InteractionSurface
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetHostProvisioningJobSpec


class TargetHostRollbackSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("host rollback intent root cannot be a symbolic link")

    def _path(self, idempotency_key: str) -> Path:
        identity = hashlib.sha256(idempotency_key.encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def lock_path(self, idempotency_key: str) -> Path:
        return self._path(idempotency_key)

    def load(self, idempotency_key: str) -> TargetHostRollbackSubmissionIntent:
        path = self._path(idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise FileNotFoundError(path)
        return TargetHostRollbackSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetHostRollbackSubmissionIntent,
    ) -> TargetHostRollbackSubmissionIntent:
        atomic_write_text(
            self._path(intent.idempotency_key),
            intent.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
            require_absent=True,
        )
        return intent


class TargetHostRollbackJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-rollback-job-submission-result/v1"] = (
        "rolo-target-host-rollback-job-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetHostProvisioningJobSpec
    approval: ApprovalRequest
    current_host_job_id: str = Field(pattern=_JOB_ID)
    rollback_to_host_job_id: str = Field(pattern=_JOB_ID)


class TargetHostRollbackSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetHostProvisioningJobSpecStore,
        intents: TargetHostRollbackSubmissionIntentStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations

    @staticmethod
    def _require_completed_host_job(record: DeploymentJobRecord, *, role: str) -> None:
        if record.job.command.command not in {
            DeploymentCommandKind.PROVISION_HOST,
            DeploymentCommandKind.ROLLBACK_HOST,
        }:
            raise ValueError(f"{role} is not a host configuration Job")
        if record.job.state != DeploymentJobState.COMPLETE:
            raise DeploymentJobStateConflict(f"{role} is not complete")

    def submit(
        self,
        *,
        submission: TargetHostRollbackJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetHostRollbackJobSubmissionResult:
        if submission.current_host_job_id == submission.rollback_to_host_job_id:
            raise ValueError("host rollback requires two different configuration Jobs")
        observed_at = now or datetime.now(timezone.utc)
        with interprocess_lock(self.intents.lock_path(idempotency_key)):
            try:
                intent = self.intents.load(idempotency_key)
            except FileNotFoundError:
                current = self.store.load_job(submission.current_host_job_id)
                previous = self.store.load_job(submission.rollback_to_host_job_id)
                self._require_completed_host_job(current, role="current host Job")
                self._require_completed_host_job(previous, role="rollback target Job")
                if current.job.command.target_id != previous.job.command.target_id:
                    raise ValueError("host rollback Jobs belong to different targets") from None
                current_spec = self.specs.load(current.job.job_id)
                previous_spec = self.specs.load(previous.job.job_id)
                target_id = current.job.command.target_id
                if (
                    current_spec.target_id != target_id
                    or previous_spec.target_id != target_id
                ):
                    raise DeploymentJobStateConflict(
                        "host rollback Job specs differ from their target"
                    ) from None
                registration = self.registrations.load(target_id)
                if registration.connection is None:
                    raise ValueError("host rollback requires an SSH target") from None
                plan = build_target_host_provisioning_plan(
                    target_id=target_id,
                    target_registration_sha256=target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    ),
                    connection=registration.connection,
                    bootstrap_public_key=previous_spec.plan.bootstrap_public_key,
                    runtime_public_key=previous_spec.plan.runtime_public_key,
                    expected_current_plan_sha256=current_spec.plan.canonical_sha256(),
                )
                approval_id = "approval-" + hashlib.sha256(
                    f"host-rollback:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()[:32]
                spec = TargetHostProvisioningJobSpec(
                    target_id=target_id,
                    plan=plan,
                    approval_id=approval_id,
                    approver_principal=submission.approver_principal,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                    approval_action=ApprovalAction.ROLLBACK_HOST_CONFIGURATION,
                )
                intent = self.intents.persist(
                    TargetHostRollbackSubmissionIntent(
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
                    "host rollback idempotency key was reused"
                )
        spec = intent.spec
        command = DeploymentCommand(
            command=DeploymentCommandKind.ROLLBACK_HOST,
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
                action=ApprovalAction.ROLLBACK_HOST_CONFIGURATION,
                risk="R3",
                approver_principal=spec.approver_principal,
                summary=(
                    "Restore a prior digest-bound host key/template configuration using "
                    "compare-and-swap; runtime data and the runtime account are preserved."
                ),
                expires_at=spec.approval_expires_at,
                authorization_scope_sha256=spec.canonical_sha256(),
                now=observed_at,
                approval_id=spec.approval_id,
            )
        if (
            approval.job_id != record.job.job_id
            or approval.action != ApprovalAction.ROLLBACK_HOST_CONFIGURATION
            or approval.authorization_scope_sha256 != spec.canonical_sha256()
        ):
            raise DeploymentJobStateConflict("host rollback approval already differs")
        return TargetHostRollbackJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
            current_host_job_id=submission.current_host_job_id,
            rollback_to_host_job_id=submission.rollback_to_host_job_id,
        )
