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
from rolo.targets.runtime_deployment import TargetWorkspaceRef
from rolo.targets.source_discovery import (
    TargetSourceDiscoveryExecutionResult,
    TargetSourceDiscoveryLimits,
    TargetSourceDiscoveryRequest,
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


class TargetSourceDiscoveryJobSubmission(BaseModel):
    """Public request for separately approved recursive target source analysis."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-job-submission/v1"] = (
        "rolo-target-source-discovery-job-submission/v1"
    )
    scan_roots: list[str] = Field(default_factory=lambda: ["."], min_length=1, max_length=16)
    limits: TargetSourceDiscoveryLimits = Field(default_factory=TargetSourceDiscoveryLimits)
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    timeout_s: float = Field(default=120.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def validate_request_scope(self) -> TargetSourceDiscoveryJobSubmission:
        TargetSourceDiscoveryRequest(
            request_id="source-discovery-scope-validation",
            workspace=TargetWorkspaceRef(
                workspace_id="scope-validation",
                target_id="scope-validation",
                robot_id="scope-validation",
                root="/scope-validation",
            ),
            scan_roots=self.scan_roots,
            limits=self.limits,
            approval_id="approval-" + "0" * 32,
            timeout_s=self.timeout_s,
        )
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetSourceDiscoveryJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-job-spec/v1"] = (
        "rolo-target-source-discovery-job-spec/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    target_transport: TargetTransport
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace: TargetWorkspaceRef
    scan_roots: list[str] = Field(min_length=1, max_length=16)
    limits: TargetSourceDiscoveryLimits
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approval_action: Literal[ApprovalAction.ANALYZE_PROJECT_SOURCE] = (
        ApprovalAction.ANALYZE_PROJECT_SOURCE
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime
    timeout_s: float = Field(default=120.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def bind_spec(self) -> TargetSourceDiscoveryJobSpec:
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("source discovery approval expiry must be timezone-aware")
        if (
            self.workspace.target_id != self.target_id
            or self.workspace.robot_id != self.target_id
        ):
            raise ValueError("source discovery workspace identity mismatch")
        TargetSourceDiscoveryRequest(
            request_id="source-discovery-spec-validation",
            workspace=self.workspace,
            scan_roots=self.scan_roots,
            limits=self.limits,
            approval_id=self.approval_id,
            timeout_s=self.timeout_s,
        )
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetSourceDiscoverySubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-intent/v1"] = (
        "rolo-target-source-discovery-intent/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetSourceDiscoveryJobSpec


class TargetSourceDiscoveryJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-submission-result/v1"] = (
        "rolo-target-source-discovery-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetSourceDiscoveryJobSpec
    approval: ApprovalRequest


class TargetSourceDiscoveryJobArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetSourceDiscoveryJobFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetSourceDiscoveryJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-job-artifact/v1"] = (
        "rolo-target-source-discovery-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=_IDENTIFIER)
    target_registration_sha256: str = Field(pattern=_SHA256)
    observed_target_registration_sha256: str | None = Field(default=None, pattern=_SHA256)
    status: TargetSourceDiscoveryJobArtifactStatus
    failure_code: TargetSourceDiscoveryJobFailureCode | None = None
    execution: TargetSourceDiscoveryExecutionResult | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_status(self) -> TargetSourceDiscoveryJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("source discovery artifact timestamp must be timezone-aware")
        if self.status == TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED:
            if (
                self.failure_code is not None
                or self.execution is None
                or self.execution.execution_status != TargetExecutionStatus.SUCCEEDED
            ):
                raise ValueError("successful source discovery artifact is incomplete")
        elif self.failure_code is None:
            raise ValueError("failed source discovery artifact requires a failure code")
        drift = (
            self.failure_code
            == TargetSourceDiscoveryJobFailureCode.TARGET_REGISTRATION_CHANGED
        )
        if drift != (self.observed_target_registration_sha256 is not None):
            raise ValueError("source discovery registration drift binding is inconsistent")
        if self.execution is not None and (
            self.execution.target_id != self.target_id
            or self.execution.robot_id != self.target_id
        ):
            raise ValueError("source discovery execution target binding mismatch")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetSourceDiscoveryArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("source discovery artifact root cannot be a symbolic link")

    def path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid source discovery Job id")
        return self.root / job_id / "source-discovery-result.json"

    def load_optional(self, job_id: str) -> TargetSourceDiscoveryJobArtifact | None:
        path = self.path(job_id)
        if path.is_symlink():
            raise ValueError("source discovery artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("source discovery artifact is invalid")
        return TargetSourceDiscoveryJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def load(self, job_id: str) -> TargetSourceDiscoveryJobArtifact:
        artifact = self.load_optional(job_id)
        if artifact is None:
            raise FileNotFoundError(self.path(job_id))
        return artifact

    def persist(self, artifact: TargetSourceDiscoveryJobArtifact) -> None:
        path = self.path(artifact.job_id)
        current = self.load_optional(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("source discovery artifact already differs")
            return
        atomic_write_text(path, artifact.model_dump_json(indent=2) + "\n", require_absent=True)


def build_target_source_discovery_job_spec(
    registration: TargetRegistrationRequest,
    submission: TargetSourceDiscoveryJobSubmission,
    *,
    approval_id: str,
    approval_expires_at: datetime,
) -> TargetSourceDiscoveryJobSpec:
    profile = registration.target
    workspace_digest = hashlib.sha256(
        f"{profile.target_id}\0{profile.workspace_root}".encode()
    ).hexdigest()[:32]
    return TargetSourceDiscoveryJobSpec(
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
        scan_roots=submission.scan_roots,
        limits=submission.limits,
        approval_id=approval_id,
        approver_principal=submission.approver_principal,
        approval_expires_at=approval_expires_at,
        timeout_s=submission.timeout_s,
    )


def build_target_source_discovery_execution_request(
    spec: TargetSourceDiscoveryJobSpec,
    *,
    job_id: str,
) -> TargetSourceDiscoveryRequest:
    if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
        raise ValueError("invalid source discovery Job id")
    return TargetSourceDiscoveryRequest(
        request_id=f"source-discovery-{job_id.removeprefix('deployment-')}",
        workspace=spec.workspace,
        scan_roots=spec.scan_roots,
        limits=spec.limits,
        approval_id=spec.approval_id,
        timeout_s=spec.timeout_s,
    )


class TargetSourceDiscoveryJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("source discovery Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid source discovery Job id")
        return self.root / job_id / "source-discovery-spec.json"

    def load(self, job_id: str) -> TargetSourceDiscoveryJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise ValueError("source discovery Job spec is unavailable")
        return TargetSourceDiscoveryJobSpec.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def contains(self, job_id: str) -> bool:
        path = self._path(job_id)
        return path.is_file() and not path.is_symlink()

    def persist(self, job_id: str, spec: TargetSourceDiscoveryJobSpec) -> None:
        path = self._path(job_id)
        try:
            atomic_write_text(path, spec.model_dump_json(indent=2) + "\n", require_absent=True)
        except FileExistsError:
            if self.load(job_id) != spec:
                raise DeploymentJobStateConflict(
                    "source discovery Job spec already differs"
                ) from None


class TargetSourceDiscoveryIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("source discovery intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        if re.fullmatch(_IDENTIFIER, target_id) is None or re.fullmatch(
            _IDEMPOTENCY, idempotency_key
        ) is None:
            raise ValueError("invalid source discovery intent identity")
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self.root / target_id / f"{digest}.json"

    def lock_target(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key).with_suffix(".intent-lock")

    def load(self, target_id: str, idempotency_key: str) -> TargetSourceDiscoverySubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 768 * 1024:
            raise FileNotFoundError(path)
        return TargetSourceDiscoverySubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetSourceDiscoverySubmissionIntent,
    ) -> TargetSourceDiscoverySubmissionIntent:
        path = self._path(intent.target_id, intent.idempotency_key)
        try:
            atomic_write_text(path, intent.model_dump_json(indent=2) + "\n", require_absent=True)
        except FileExistsError:
            current = self.load(intent.target_id, intent.idempotency_key)
            if current != intent:
                raise DeploymentJobStateConflict(
                    "source discovery submission intent already differs"
                ) from None
            return current
        return intent


class TargetSourceDiscoverySubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetSourceDiscoveryJobSpecStore,
        intents: TargetSourceDiscoveryIntentStore,
        registrations: TargetRegistrationService,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations

    def _submit_spec(
        self,
        spec: TargetSourceDiscoveryJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime,
    ) -> TargetSourceDiscoveryJobSubmissionResult:
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
            build_target_source_discovery_execution_request(spec, job_id=record.job.job_id)
        )
        try:
            approval = self.store.load_approval_request(spec.approval_id)
        except ValueError:
            try:
                approval = self.store.request_approval(
                    record.job.job_id,
                    action=ApprovalAction.ANALYZE_PROJECT_SOURCE,
                    risk="R2",
                    approver_principal=spec.approver_principal,
                    summary=(
                        "Recursively parse only the approved target workspace roots and "
                        "return bounded structured facts without source text."
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
            or approval.action != ApprovalAction.ANALYZE_PROJECT_SOURCE
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict("source discovery Job approval already differs")
        return TargetSourceDiscoveryJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetSourceDiscoveryJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetSourceDiscoveryJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("source discovery submission timestamp must be timezone-aware")
        with interprocess_lock(self.intents.lock_target(target_id, idempotency_key)):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                approval_id = "approval-" + hashlib.sha256(
                    f"source-discovery:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()[:32]
                spec = build_target_source_discovery_job_spec(
                    self.registrations.load(target_id),
                    submission,
                    approval_id=approval_id,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                )
                intent = self.intents.persist(
                    TargetSourceDiscoverySubmissionIntent(
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
                        "source discovery idempotency key already binds another request"
                    )
            return self._submit_spec(
                intent.spec,
                requested_by=requested_by,
                interaction_surface=interaction_surface,
                idempotency_key=idempotency_key,
                now=observed_at,
            )


class TargetSourceDiscoveryJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetSourceDiscoveryJobSpecStore,
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
        self.artifacts = TargetSourceDiscoveryArtifactStore(artifact_root)
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

    @staticmethod
    def _artifact_ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/source-discovery-result.json"

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetSourceDiscoveryJobSpec,
        artifact: TargetSourceDiscoveryJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
            or artifact.target_registration_sha256 != spec.target_registration_sha256
        ):
            raise DeploymentJobStateConflict("source discovery artifact binding mismatch")
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "source-discovery"
            ),
            None,
        )
        if checkpoint is None:
            raise DeploymentJobStateConflict("source discovery artifact has no checkpoint")
        artifact_ref = self._artifact_ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED:
            if checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    record.job.job_id,
                    step_id="source-discovery",
                    outcome_sha256=digest,
                    artifact_refs=[artifact_ref],
                )
            elif checkpoint.status != DeploymentStepStatus.COMPLETE:
                raise DeploymentJobStateConflict(
                    "source discovery artifact conflicts with checkpoint"
                )
            return self.store.complete_job(record.job.job_id, artifact_refs=[artifact_ref])
        if record.job.state == DeploymentJobState.FAILED:
            return record
        return self.store.fail_step(
            record.job.job_id,
            step_id="source-discovery",
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
                "source discovery Job handler received another command"
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
            raise DeploymentJobStateConflict("source discovery Job spec digest mismatch")
        unsigned_request = build_target_source_discovery_execution_request(spec, job_id=job_id)
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.ANALYZE_PROJECT_SOURCE,
        )
        if (
            self._authorization_signing_key_id is None
            or self._authorization_public_key_path is None
            or self._authorization_private_key_path is None
        ):
            raise DeploymentJobStateConflict("source discovery authorization signer is unavailable")
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
                        f"source-discovery:{job_id}:{record.attempt}".encode()
                    ).hexdigest()[:32]
                ),
            )
        except (OSError, ValueError) as exc:
            raise DeploymentJobStateConflict(
                "source discovery authorization proof could not be issued"
            ) from exc

        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self.artifacts.load_optional(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            running = any(
                item.attempt == record.attempt
                and item.step_id == "source-discovery"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "source discovery execution checkpoint requires reconciliation"
                )
            registration = self.registrations.load(spec.target_id)
            observed_registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            record = self.store.start_step(
                job_id,
                step_id="source-discovery",
                state=DeploymentJobState.COLLECTING_EVIDENCE,
                remote=spec.target_transport == TargetTransport.SSH,
            )
            if observed_registration_sha256 != spec.target_registration_sha256:
                artifact = TargetSourceDiscoveryJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    target_registration_sha256=spec.target_registration_sha256,
                    observed_target_registration_sha256=observed_registration_sha256,
                    status=TargetSourceDiscoveryJobArtifactStatus.FAILED,
                    failure_code=(
                        TargetSourceDiscoveryJobFailureCode.TARGET_REGISTRATION_CHANGED
                    ),
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                try:
                    execution = self._executor(registration.target).discover_source(
                        authorized_request,
                        cancel_event=cancel_event,
                    )
                except Exception:
                    artifact = TargetSourceDiscoveryJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        target_registration_sha256=spec.target_registration_sha256,
                        status=TargetSourceDiscoveryJobArtifactStatus.FAILED,
                        failure_code=TargetSourceDiscoveryJobFailureCode.RUNNER_ERROR,
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
                    succeeded = (
                        execution.execution_status == TargetExecutionStatus.SUCCEEDED
                    )
                    artifact = TargetSourceDiscoveryJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        target_registration_sha256=spec.target_registration_sha256,
                        status=(
                            TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED
                            if succeeded
                            else TargetSourceDiscoveryJobArtifactStatus.FAILED
                        ),
                        failure_code=(
                            None
                            if succeeded
                            else TargetSourceDiscoveryJobFailureCode.EXECUTION_FAILED
                        ),
                        execution=execution,
                        completed_at=datetime.now(timezone.utc),
                    )
            self.artifacts.persist(artifact)
            return self._finish(record, spec, artifact)
