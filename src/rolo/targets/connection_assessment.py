from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text
from rolo.targets.adapt_jobs import TargetAdaptJobRunner
from rolo.targets.bootstrap_jobs import TargetBootstrapJobRunner
from rolo.targets.credentials import CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.executor import (
    TargetExecutionStatus,
    TargetExecutor,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
)
from rolo.targets.host_provisioning_jobs import TargetHostProvisioningJobRunner
from rolo.targets.host_reconciliation_jobs import TargetHostReconciliationJobRunner
from rolo.targets.host_service_jobs import TargetHostServiceJobRunner
from rolo.targets.host_service_reconciliation_jobs import (
    TargetHostServiceReconciliationJobRunner,
)
from rolo.targets.models import DeploymentCommandKind, DeploymentJobState, TargetProfile
from rolo.targets.platform_detector import target_executor_for_profile
from rolo.targets.project_evidence_jobs import TargetProjectEvidenceJobRunner
from rolo.targets.registration import (
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.runtime_evidence_jobs import TargetRuntimeEvidenceJobRunner
from rolo.targets.runtime_rollback_jobs import TargetRuntimeRollbackJobRunner
from rolo.targets.source_discovery_jobs import TargetSourceDiscoveryJobRunner


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class TargetConnectionAssessmentStatus(str, Enum):
    PROFILE_VALIDATED = "PROFILE_VALIDATED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetConnectionAssessmentFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetConnectionAssessmentArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-connection-assessment-artifact/v1"] = (
        "rolo-target-connection-assessment-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_target_registration_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    status: TargetConnectionAssessmentStatus
    failure_code: TargetConnectionAssessmentFailureCode | None = None
    inspection_request: TargetInspectionRequest | None = None
    inspection_result: TargetInspectionResult | None = None
    assessed_at: datetime

    @model_validator(mode="after")
    def bind_inspection(self) -> TargetConnectionAssessmentArtifact:
        if self.assessed_at.tzinfo is None:
            raise ValueError("connection assessment timestamp must be timezone-aware")
        if self.status == TargetConnectionAssessmentStatus.PROFILE_VALIDATED:
            if (
                self.inspection_request is not None
                or self.inspection_result is not None
                or self.failure_code is not None
            ):
                raise ValueError("profile-only assessment cannot contain inspection")
        elif self.status == TargetConnectionAssessmentStatus.SUCCEEDED:
            if self.inspection_request is None or self.inspection_result is None:
                raise ValueError("connection assessment inspection is incomplete")
            if (
                self.inspection_result.request_id != self.inspection_request.request_id
                or self.inspection_result.request_sha256
                != self.inspection_request.canonical_sha256()
            ):
                raise ValueError("connection assessment inspection binding mismatch")
            if self.inspection_result.status != TargetExecutionStatus.SUCCEEDED:
                raise ValueError("connection assessment status mismatch")
            if self.failure_code is not None:
                raise ValueError("successful assessment cannot contain a failure code")
        elif self.inspection_result is not None:
            if self.inspection_request is None:
                raise ValueError("failed inspection is missing its request")
            if (
                self.inspection_result.request_id != self.inspection_request.request_id
                or self.inspection_result.request_sha256
                != self.inspection_request.canonical_sha256()
                or self.inspection_result.status != TargetExecutionStatus.FAILED
            ):
                raise ValueError("failed inspection binding mismatch")
            if self.failure_code is not None:
                raise ValueError("inspection failure must use its executor error code")
        elif self.inspection_request is not None or self.failure_code is None:
            raise ValueError("runner failure requires a bounded failure code")
        if (
            self.failure_code == TargetConnectionAssessmentFailureCode.TARGET_REGISTRATION_CHANGED
        ) != (self.observed_target_registration_sha256 is not None):
            raise ValueError("registration drift failure requires the observed digest")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetDeploymentJobRunner:
    """Execute typed Job handlers; currently implements read-only connection assessment."""

    def __init__(
        self,
        store: DeploymentJobStore,
        registration_service: TargetRegistrationService,
        artifact_root: Path,
        *,
        executor_factory: Callable[[TargetProfile], TargetExecutor] | None = None,
        bootstrap_runner: TargetBootstrapJobRunner | None = None,
        adapt_runner: TargetAdaptJobRunner | None = None,
        rollback_runner: TargetRuntimeRollbackJobRunner | None = None,
        project_evidence_runner: TargetProjectEvidenceJobRunner | None = None,
        source_discovery_runner: TargetSourceDiscoveryJobRunner | None = None,
        runtime_evidence_runner: TargetRuntimeEvidenceJobRunner | None = None,
        host_provisioning_runner: TargetHostProvisioningJobRunner | None = None,
        host_reconciliation_runner: TargetHostReconciliationJobRunner | None = None,
        host_service_runner: TargetHostServiceJobRunner | None = None,
        host_service_reconciliation_runner: TargetHostServiceReconciliationJobRunner
        | None = None,
    ) -> None:
        self.store = store
        self.registrations = registration_service
        self.artifact_root = artifact_root.expanduser().absolute()
        if self.artifact_root.is_symlink():
            raise ValueError("connection assessment artifact root cannot be a symbolic link")
        self._executor_factory = executor_factory
        self._bootstrap_runner = bootstrap_runner
        self._adapt_runner = adapt_runner
        self._rollback_runner = rollback_runner
        self._project_evidence_runner = project_evidence_runner
        self._source_discovery_runner = source_discovery_runner
        self._runtime_evidence_runner = runtime_evidence_runner
        self._host_provisioning_runner = host_provisioning_runner
        self._host_reconciliation_runner = host_reconciliation_runner
        self._host_service_runner = host_service_runner
        self._host_service_reconciliation_runner = host_service_reconciliation_runner

    def _executor(self, profile: TargetProfile) -> TargetExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
        )

    def _artifact_path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "connection-assessment.json"

    @staticmethod
    def _artifact_ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/connection-assessment.json"

    def _load_artifact(self, job_id: str) -> TargetConnectionAssessmentArtifact | None:
        path = self._artifact_path(job_id)
        if path.is_symlink():
            raise ValueError("connection assessment artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 3 * 1024 * 1024:
            raise ValueError("connection assessment artifact is invalid")
        return TargetConnectionAssessmentArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _persist_artifact(
        self,
        artifact: TargetConnectionAssessmentArtifact,
    ) -> None:
        path = self._artifact_path(artifact.job_id)
        existing = self._load_artifact(artifact.job_id)
        if existing is not None:
            if existing != artifact:
                raise DeploymentJobStateConflict("connection assessment artifact already differs")
            return
        atomic_write_text(
            path,
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def _finish_from_artifact(
        self,
        record: DeploymentJobRecord,
        artifact: TargetConnectionAssessmentArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.target_id != record.job.command.target_id
            or artifact.target_registration_sha256 != record.job.command.parameters_sha256
        ):
            raise DeploymentJobStateConflict("connection assessment artifact does not bind the Job")
        artifact_ref = self._artifact_ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "connection-assessment"
            ),
            None,
        )
        if artifact.status == TargetConnectionAssessmentStatus.FAILED:
            if checkpoint is not None and checkpoint.status in {
                DeploymentStepStatus.FAILED,
                DeploymentStepStatus.UNKNOWN,
            }:
                return record
            return self.store.fail_step(
                record.job.job_id,
                step_id="connection-assessment",
                remote_state_known=True,
                outcome_sha256=digest,
                artifact_refs=[artifact_ref],
            )
        if checkpoint is None:
            raise DeploymentJobStateConflict("connection assessment artifact has no checkpoint")
        if checkpoint.status == DeploymentStepStatus.RUNNING:
            self.store.complete_step(
                record.job.job_id,
                step_id="connection-assessment",
                outcome_sha256=digest,
                artifact_refs=[artifact_ref],
            )
        elif checkpoint.status != DeploymentStepStatus.COMPLETE:
            raise DeploymentJobStateConflict(
                "connection assessment artifact conflicts with checkpoint"
            )
        return self.store.complete_job(
            record.job.job_id,
            artifact_refs=[artifact_ref],
        )

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command in {
            DeploymentCommandKind.PROVISION_HOST,
            DeploymentCommandKind.ROLLBACK_HOST,
        }:
            if self._host_provisioning_runner is None:
                raise DeploymentJobStateConflict(
                    "Host provisioning Job handler is unavailable"
                )
            return self._host_provisioning_runner.run(
                job_id,
                cancel_event=cancel_event,
            )
        if record.job.command.command == DeploymentCommandKind.RECONCILE_HOST:
            if self._host_reconciliation_runner is None:
                raise DeploymentJobStateConflict(
                    "Host reconciliation Job handler is unavailable"
                )
            return self._host_reconciliation_runner.run(
                job_id,
                cancel_event=cancel_event,
            )
        if record.job.command.command == DeploymentCommandKind.START_TARGET_SERVICE:
            if self._host_service_runner is None:
                raise DeploymentJobStateConflict(
                    "Host service Job handler is unavailable"
                )
            return self._host_service_runner.run(
                job_id,
                cancel_event=cancel_event,
            )
        if record.job.command.command == DeploymentCommandKind.RECONCILE_TARGET_SERVICE:
            if self._host_service_reconciliation_runner is None:
                raise DeploymentJobStateConflict(
                    "Host service reconciliation Job handler is unavailable"
                )
            return self._host_service_reconciliation_runner.run(
                job_id,
                cancel_event=cancel_event,
            )
        if record.job.command.command == DeploymentCommandKind.BOOTSTRAP:
            if self._bootstrap_runner is None:
                raise DeploymentJobStateConflict("Bootstrap Job handler is unavailable")
            return self._bootstrap_runner.run(job_id, cancel_event=cancel_event)
        if record.job.command.command == DeploymentCommandKind.ADAPT:
            if self._adapt_runner is None:
                raise DeploymentJobStateConflict("Adapt Job handler is unavailable")
            return self._adapt_runner.run(job_id, cancel_event=cancel_event)
        if record.job.command.command == DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME:
            if self._rollback_runner is None:
                raise DeploymentJobStateConflict(
                    "Target runtime rollback Job handler is unavailable"
                )
            return self._rollback_runner.run(job_id, cancel_event=cancel_event)
        if record.job.command.command == DeploymentCommandKind.COLLECT_EVIDENCE:
            project_owned = (
                self._project_evidence_runner is not None
                and self._project_evidence_runner.specs.contains(job_id)
            )
            source_owned = (
                self._source_discovery_runner is not None
                and self._source_discovery_runner.specs.contains(job_id)
            )
            runtime_owned = (
                self._runtime_evidence_runner is not None
                and self._runtime_evidence_runner.specs.contains(job_id)
            )
            if sum((project_owned, source_owned, runtime_owned)) > 1:
                raise DeploymentJobStateConflict(
                    "Evidence Job is claimed by multiple typed handlers"
                )
            if runtime_owned:
                assert self._runtime_evidence_runner is not None
                return self._runtime_evidence_runner.run(job_id, cancel_event=cancel_event)
            if source_owned:
                assert self._source_discovery_runner is not None
                return self._source_discovery_runner.run(job_id, cancel_event=cancel_event)
            if not project_owned:
                raise DeploymentJobStateConflict("Typed evidence Job handler is unavailable")
            assert self._project_evidence_runner is not None
            return self._project_evidence_runner.run(job_id, cancel_event=cancel_event)
        if record.job.command.command != DeploymentCommandKind.ASSESS_CONNECTION:
            raise DeploymentJobStateConflict("deployment Job handler is not implemented")
        if record.job.state in {
            DeploymentJobState.COMPLETE,
            DeploymentJobState.FAILED,
            DeploymentJobState.BLOCKED,
            DeploymentJobState.CANCELLED,
        }:
            return record
        if record.job.state not in {
            DeploymentJobState.CREATED,
            DeploymentJobState.CONNECTING,
        }:
            raise DeploymentJobStateConflict("deployment Job is not runnable")
        if record.cancel_requested:
            return self.store.resolve_cancel(
                job_id,
                remote_termination_confirmed=True,
            )
        if cancel_event is not None and cancel_event.is_set():
            self.store.request_cancel(job_id)
            return self.store.resolve_cancel(
                job_id,
                remote_termination_confirmed=True,
            )
        target_id = record.job.command.target_id
        with self.store.target_lease(target_id):
            record = self.store.load_job(job_id)
            if record.cancel_requested:
                return self.store.resolve_cancel(
                    job_id,
                    remote_termination_confirmed=True,
                )
            running = any(
                item.attempt == record.attempt
                and item.step_id == "connection-assessment"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish_from_artifact(record, artifact)
            registration = self.registrations.load(target_id)
            registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            if registration_sha256 != record.job.command.parameters_sha256:
                if not running:
                    record = self.store.start_step(
                        job_id,
                        step_id="connection-assessment",
                        state=DeploymentJobState.CONNECTING,
                        remote=False,
                    )
                artifact = TargetConnectionAssessmentArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    target_id=target_id,
                    target_registration_sha256=record.job.command.parameters_sha256,
                    observed_target_registration_sha256=registration_sha256,
                    status=TargetConnectionAssessmentStatus.FAILED,
                    failure_code=(
                        TargetConnectionAssessmentFailureCode.TARGET_REGISTRATION_CHANGED
                    ),
                    assessed_at=datetime.now(timezone.utc),
                )
                self._persist_artifact(artifact)
                return self._finish_from_artifact(record, artifact)
            if not running:
                record = self.store.start_step(
                    job_id,
                    step_id="connection-assessment",
                    state=DeploymentJobState.CONNECTING,
                    remote=False,
                )

            probe = record.job.command.active_probe
            inspection_request: TargetInspectionRequest | None = None
            inspection_result: TargetInspectionResult | None = None
            if probe != "none":
                inspection_request = TargetInspectionRequest(
                    request_id=f"assessment-{job_id.removeprefix('deployment-')}",
                    tool=(
                        TargetInspectionTool.PLATFORM
                        if probe == "help"
                        else TargetInspectionTool.RUNTIME_CAPABILITIES
                    ),
                    timeout_s=20.0,
                    max_stdout_bytes=128 * 1024,
                    max_stderr_bytes=32 * 1024,
                )
                try:
                    inspection_result = self._executor(registration.target).inspect(
                        inspection_request,
                        cancel_event=cancel_event,
                    )
                except Exception:
                    artifact = TargetConnectionAssessmentArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        target_id=target_id,
                        target_registration_sha256=registration_sha256,
                        status=TargetConnectionAssessmentStatus.FAILED,
                        failure_code=TargetConnectionAssessmentFailureCode.RUNNER_ERROR,
                        assessed_at=datetime.now(timezone.utc),
                    )
                    self._persist_artifact(artifact)
                    return self._finish_from_artifact(record, artifact)
                current = self.store.load_job(job_id)
                if inspection_result.cancelled or current.cancel_requested:
                    if not current.cancel_requested:
                        self.store.request_cancel(job_id)
                    return self.store.resolve_cancel(
                        job_id,
                        remote_termination_confirmed=True,
                    )
            artifact = TargetConnectionAssessmentArtifact(
                job_id=job_id,
                command_sha256=record.job.command_sha256,
                target_id=target_id,
                target_registration_sha256=registration_sha256,
                status=(
                    TargetConnectionAssessmentStatus.PROFILE_VALIDATED
                    if inspection_result is None
                    else (
                        TargetConnectionAssessmentStatus.SUCCEEDED
                        if inspection_result.status == TargetExecutionStatus.SUCCEEDED
                        else TargetConnectionAssessmentStatus.FAILED
                    )
                ),
                inspection_request=inspection_request,
                inspection_result=inspection_result,
                assessed_at=datetime.now(timezone.utc),
            )
            self._persist_artifact(artifact)
            return self._finish_from_artifact(record, artifact)
