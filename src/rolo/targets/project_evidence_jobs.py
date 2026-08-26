from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.credentials import CredentialPurpose, CredentialResolver, FileCredentialProvider
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
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
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
    TargetRegistrationRequest,
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.runtime_deployment import (
    TargetProjectEvidenceCandidate,
    TargetProjectEvidenceExecutionResult,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceRequest,
    TargetWorkspaceRef,
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


def default_project_evidence_candidates() -> list[TargetProjectEvidenceCandidate]:
    """Return a conservative root-level set; callers may explicitly replace it."""

    return [
        TargetProjectEvidenceCandidate(
            path="CMakeLists.txt",
            kind=TargetProjectEvidenceKind.BUILD_METADATA,
        ),
        TargetProjectEvidenceCandidate(
            path="README.md",
            kind=TargetProjectEvidenceKind.DOCUMENTATION,
        ),
        TargetProjectEvidenceCandidate(
            path="package.xml",
            kind=TargetProjectEvidenceKind.ROS_METADATA,
        ),
        TargetProjectEvidenceCandidate(
            path="pyproject.toml",
            kind=TargetProjectEvidenceKind.BUILD_METADATA,
        ),
        TargetProjectEvidenceCandidate(
            path="setup.cfg",
            kind=TargetProjectEvidenceKind.BUILD_METADATA,
        ),
        TargetProjectEvidenceCandidate(
            path="setup.py",
            kind=TargetProjectEvidenceKind.BUILD_METADATA,
        ),
    ]


class TargetProjectEvidenceJobSubmission(BaseModel):
    """Public bounded request for target-side project metadata observation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-job-submission/v1"] = (
        "rolo-target-project-evidence-job-submission/v1"
    )
    candidates: list[TargetProjectEvidenceCandidate] = Field(
        default_factory=default_project_evidence_candidates,
        min_length=1,
        max_length=256,
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    timeout_s: float = Field(default=60.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def require_canonical_candidates(self) -> TargetProjectEvidenceJobSubmission:
        paths = [item.path for item in self.candidates]
        if paths != sorted(set(paths)):
            raise ValueError("project evidence candidates must be unique and sorted")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetProjectEvidenceJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-job-spec/v1"] = (
        "rolo-target-project-evidence-job-spec/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    target_transport: TargetTransport
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace: TargetWorkspaceRef
    candidates: list[TargetProjectEvidenceCandidate] = Field(
        min_length=1,
        max_length=256,
    )
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approval_action: Literal[ApprovalAction.READ_PROJECT_EVIDENCE] = (
        ApprovalAction.READ_PROJECT_EVIDENCE
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime
    timeout_s: float = Field(default=60.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def bind_spec(self) -> TargetProjectEvidenceJobSpec:
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("project evidence approval expiry must be timezone-aware")
        if (
            self.workspace.target_id != self.target_id
            or self.workspace.robot_id != self.target_id
        ):
            raise ValueError("project evidence workspace identity mismatch")
        paths = [item.path for item in self.candidates]
        if paths != sorted(set(paths)):
            raise ValueError("project evidence candidates must be unique and sorted")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetProjectEvidenceSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-intent/v1"] = (
        "rolo-target-project-evidence-intent/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetProjectEvidenceJobSpec


class TargetProjectEvidenceJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-submission-result/v1"] = (
        "rolo-target-project-evidence-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetProjectEvidenceJobSpec
    approval: ApprovalRequest


class TargetProjectEvidenceJobArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetProjectEvidenceJobFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetProjectEvidenceJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-job-artifact/v1"] = (
        "rolo-target-project-evidence-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=_IDENTIFIER)
    target_registration_sha256: str = Field(pattern=_SHA256)
    observed_target_registration_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )
    status: TargetProjectEvidenceJobArtifactStatus
    failure_code: TargetProjectEvidenceJobFailureCode | None = None
    execution: TargetProjectEvidenceExecutionResult | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_status(self) -> TargetProjectEvidenceJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("project evidence artifact timestamp must be timezone-aware")
        if self.status == TargetProjectEvidenceJobArtifactStatus.SUCCEEDED:
            if (
                self.failure_code is not None
                or self.execution is None
                or self.execution.execution_status != TargetExecutionStatus.SUCCEEDED
            ):
                raise ValueError("successful project evidence artifact is incomplete")
        elif self.failure_code is None:
            raise ValueError("failed project evidence artifact requires a failure code")
        if (
            self.failure_code
            == TargetProjectEvidenceJobFailureCode.TARGET_REGISTRATION_CHANGED
        ) != (self.observed_target_registration_sha256 is not None):
            raise ValueError("registration drift artifact binding is inconsistent")
        if self.execution is not None and (
            self.execution.target_id != self.target_id
            or self.execution.robot_id != self.target_id
        ):
            raise ValueError("project evidence execution target binding mismatch")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetProjectEvidenceArtifactStore:
    """Read and publish immutable project-evidence artifacts for downstream Jobs."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("project evidence artifact root cannot be a symbolic link")

    def path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid project evidence Job id")
        return self.root / job_id / "project-evidence-result.json"

    def load_optional(self, job_id: str) -> TargetProjectEvidenceJobArtifact | None:
        path = self.path(job_id)
        if path.is_symlink():
            raise ValueError("project evidence artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("project evidence artifact is invalid")
        return TargetProjectEvidenceJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def load(self, job_id: str) -> TargetProjectEvidenceJobArtifact:
        artifact = self.load_optional(job_id)
        if artifact is None:
            raise FileNotFoundError(self.path(job_id))
        return artifact

    def persist(self, artifact: TargetProjectEvidenceJobArtifact) -> None:
        path = self.path(artifact.job_id)
        current = self.load_optional(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict(
                    "project evidence artifact already differs"
                )
            return
        atomic_write_text(
            path,
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


def build_target_project_evidence_job_spec(
    registration: TargetRegistrationRequest,
    submission: TargetProjectEvidenceJobSubmission,
    *,
    approval_id: str,
    approval_expires_at: datetime,
) -> TargetProjectEvidenceJobSpec:
    profile = registration.target
    workspace_digest = hashlib.sha256(
        f"{profile.target_id}\0{profile.workspace_root}".encode()
    ).hexdigest()[:32]
    return TargetProjectEvidenceJobSpec(
        target_id=profile.target_id,
        target_transport=profile.transport,
        target_registration_sha256=target_connection_binding_sha256(
            profile,
            registration.connection,
        ),
        workspace=TargetWorkspaceRef(
            workspace_id=f"workspace-{workspace_digest}",
            target_id=profile.target_id,
            robot_id=profile.target_id,
            root=profile.workspace_root,
        ),
        candidates=submission.candidates,
        approval_id=approval_id,
        approver_principal=submission.approver_principal,
        approval_expires_at=approval_expires_at,
        timeout_s=submission.timeout_s,
    )


def build_target_project_evidence_execution_request(
    spec: TargetProjectEvidenceJobSpec,
    *,
    job_id: str,
) -> TargetProjectEvidenceRequest:
    if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
        raise ValueError("invalid project evidence Job id")
    return TargetProjectEvidenceRequest(
        request_id=f"project-evidence-{job_id.removeprefix('deployment-')}",
        workspace=spec.workspace,
        candidates=spec.candidates,
        approval_id=spec.approval_id,
        timeout_s=spec.timeout_s,
    )


class TargetProjectEvidenceJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("project evidence Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid project evidence Job id")
        return self.root / job_id / "project-evidence-spec.json"

    def load(self, job_id: str) -> TargetProjectEvidenceJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise ValueError("project evidence Job spec is unavailable")
        return TargetProjectEvidenceJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def contains(self, job_id: str) -> bool:
        path = self._path(job_id)
        return path.is_file() and not path.is_symlink()

    def persist(self, job_id: str, spec: TargetProjectEvidenceJobSpec) -> None:
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
                    "project evidence Job spec already differs"
                ) from None


class TargetProjectEvidenceIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("project evidence intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        if re.fullmatch(_IDENTIFIER, target_id) is None or re.fullmatch(
            _IDEMPOTENCY, idempotency_key
        ) is None:
            raise ValueError("invalid project evidence intent identity")
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self.root / target_id / f"{digest}.json"

    def lock_target(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key).with_suffix(".intent-lock")

    def load(
        self,
        target_id: str,
        idempotency_key: str,
    ) -> TargetProjectEvidenceSubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 768 * 1024:
            raise FileNotFoundError(path)
        return TargetProjectEvidenceSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetProjectEvidenceSubmissionIntent,
    ) -> TargetProjectEvidenceSubmissionIntent:
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
                    "project evidence submission intent already differs"
                ) from None
            return current
        return intent


class TargetProjectEvidenceSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetProjectEvidenceJobSpecStore,
        intents: TargetProjectEvidenceIntentStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations

    def _submit_spec(
        self,
        spec: TargetProjectEvidenceJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime,
    ) -> TargetProjectEvidenceJobSubmissionResult:
        command = DeploymentCommand(
            command=DeploymentCommandKind.COLLECT_EVIDENCE,
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
            build_target_project_evidence_execution_request(
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
                    action=ApprovalAction.READ_PROJECT_EVIDENCE,
                    risk="R2",
                    approver_principal=spec.approver_principal,
                    summary=(
                        "Read only the explicitly listed project evidence files and "
                        "return their metadata digests."
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
            or approval.action != ApprovalAction.READ_PROJECT_EVIDENCE
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict(
                "project evidence Job approval already differs"
            )
        return TargetProjectEvidenceJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetProjectEvidenceJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetProjectEvidenceJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("project evidence submission timestamp must be timezone-aware")
        with interprocess_lock(self.intents.lock_target(target_id, idempotency_key)):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                approval_id = "approval-" + hashlib.sha256(
                    (
                        f"project-evidence:{target_id}:{idempotency_key}:"
                        f"{requested_by}"
                    ).encode()
                ).hexdigest()[:32]
                spec = build_target_project_evidence_job_spec(
                    self.registrations.load(target_id),
                    submission,
                    approval_id=approval_id,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetProjectEvidenceSubmissionIntent(
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
                        "project evidence idempotency key already binds another request"
                    )
            return self._submit_spec(
                intent.spec,
                requested_by=requested_by,
                interaction_surface=interaction_surface,
                idempotency_key=idempotency_key,
                now=observed_at,
            )


class TargetProjectEvidenceJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetProjectEvidenceJobSpecStore,
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
        self.artifacts = TargetProjectEvidenceArtifactStore(artifact_root)
        self.artifact_root = self.artifacts.root
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
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
            credential_purpose=CredentialPurpose.SSH_RUNTIME,
        )

    def _artifact_path(self, job_id: str) -> Path:
        return self.artifacts.path(job_id)

    @staticmethod
    def _artifact_ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/project-evidence-result.json"

    def _load_artifact(self, job_id: str) -> TargetProjectEvidenceJobArtifact | None:
        return self.artifacts.load_optional(job_id)

    def _persist_artifact(self, artifact: TargetProjectEvidenceJobArtifact) -> None:
        self.artifacts.persist(artifact)

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetProjectEvidenceJobSpec,
        artifact: TargetProjectEvidenceJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
            or artifact.target_registration_sha256
            != spec.target_registration_sha256
        ):
            raise DeploymentJobStateConflict("project evidence artifact binding mismatch")
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt
                and item.step_id == "project-evidence"
            ),
            None,
        )
        if checkpoint is None:
            raise DeploymentJobStateConflict(
                "project evidence artifact has no checkpoint"
            )
        artifact_ref = self._artifact_ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == TargetProjectEvidenceJobArtifactStatus.SUCCEEDED:
            if checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    record.job.job_id,
                    step_id="project-evidence",
                    outcome_sha256=digest,
                    artifact_refs=[artifact_ref],
                )
            elif checkpoint.status != DeploymentStepStatus.COMPLETE:
                raise DeploymentJobStateConflict(
                    "project evidence artifact conflicts with checkpoint"
                )
            return self.store.complete_job(
                record.job.job_id,
                artifact_refs=[artifact_ref],
            )
        if record.job.state == DeploymentJobState.FAILED:
            return record
        return self.store.fail_step(
            record.job.job_id,
            step_id="project-evidence",
            remote_state_known=True,
            outcome_sha256=digest,
            artifact_refs=[artifact_ref],
        )

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.COLLECT_EVIDENCE:
            raise DeploymentJobStateConflict(
                "project evidence Job handler received another command"
            )
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
            raise DeploymentJobStateConflict("project evidence Job spec digest mismatch")
        unsigned_request = build_target_project_evidence_execution_request(
            spec,
            job_id=job_id,
        )
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.READ_PROJECT_EVIDENCE,
        )
        if (
            self._authorization_signing_key_id is None
            or self._authorization_public_key_path is None
            or self._authorization_private_key_path is None
        ):
            raise DeploymentJobStateConflict(
                "project evidence authorization signer is unavailable"
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
                        f"project-evidence:{job_id}:{record.attempt}".encode()
                    ).hexdigest()[:32]
                ),
            )
        except (OSError, ValueError) as exc:
            raise DeploymentJobStateConflict(
                "project evidence authorization proof could not be issued"
            ) from exc

        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            running = any(
                item.attempt == record.attempt
                and item.step_id == "project-evidence"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "project evidence execution checkpoint requires reconciliation"
                )
            registration = self.registrations.load(spec.target_id)
            observed_registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            record = self.store.start_step(
                job_id,
                step_id="project-evidence",
                state=DeploymentJobState.COLLECTING_EVIDENCE,
                remote=spec.target_transport == TargetTransport.SSH,
            )
            if observed_registration_sha256 != spec.target_registration_sha256:
                artifact = TargetProjectEvidenceJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    target_registration_sha256=spec.target_registration_sha256,
                    observed_target_registration_sha256=observed_registration_sha256,
                    status=TargetProjectEvidenceJobArtifactStatus.FAILED,
                    failure_code=(
                        TargetProjectEvidenceJobFailureCode.TARGET_REGISTRATION_CHANGED
                    ),
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                try:
                    execution = self._executor(
                        registration.target
                    ).detect_project_evidence(
                        authorized_request,
                        cancel_event=cancel_event,
                    )
                except Exception:
                    artifact = TargetProjectEvidenceJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        target_registration_sha256=spec.target_registration_sha256,
                        status=TargetProjectEvidenceJobArtifactStatus.FAILED,
                        failure_code=TargetProjectEvidenceJobFailureCode.RUNNER_ERROR,
                        completed_at=datetime.now(timezone.utc),
                    )
                else:
                    current = self.store.load_job(job_id)
                    if execution.error_code == TargetExecutionErrorCode.CANCELLED or (
                        current.cancel_requested
                    ):
                        if not current.cancel_requested:
                            self.store.request_cancel(job_id)
                        return self.store.resolve_cancel(
                            job_id,
                            remote_termination_confirmed=(
                                spec.target_transport != TargetTransport.SSH
                            ),
                        )
                    artifact = TargetProjectEvidenceJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        target_registration_sha256=spec.target_registration_sha256,
                        status=(
                            TargetProjectEvidenceJobArtifactStatus.SUCCEEDED
                            if execution.execution_status
                            == TargetExecutionStatus.SUCCEEDED
                            else TargetProjectEvidenceJobArtifactStatus.FAILED
                        ),
                        failure_code=(
                            None
                            if execution.execution_status
                            == TargetExecutionStatus.SUCCEEDED
                            else TargetProjectEvidenceJobFailureCode.EXECUTION_FAILED
                        ),
                        execution=execution,
                        completed_at=datetime.now(timezone.utc),
                    )
            self._persist_artifact(artifact)
            return self._finish(record, spec, artifact)
