"""Approval-bound target runtime evidence Jobs.

The public Job freezes the collector pin, requested layers and short collection
window.  The Controller signs the exact request only after an independent R2
decision; the target verifies that proof against its local authorization pin
before the runtime forced credential can collect hw/linux/ROS evidence.
"""

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
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode, TargetEvidenceRequest
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
from rolo.targets.enrollment import CollectorEnrollmentPinRegistry, CollectorEnrollmentPinV4
from rolo.targets.evidence_v4 import (
    TargetEvidenceCollectionRequestV4,
    TargetEvidenceCollectionResultV4,
    verify_target_evidence_v4,
)
from rolo.targets.executor import TargetExecutionErrorCode, TargetExecutionStatus, TargetExecutor
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


class TargetRuntimeEvidenceJobSubmission(BaseModel):
    """Public request for all discovery-required runtime evidence layers."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-evidence-job-submission/v1"] = (
        "rolo-target-runtime-evidence-job-submission/v1"
    )
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(
        default_factory=lambda: ["hw", "linux", "ros"],
        min_length=3,
        max_length=3,
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=300, ge=60, le=300)
    timeout_s: float = Field(default=45.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def require_complete_layer_set(self) -> TargetRuntimeEvidenceJobSubmission:
        if self.requested_layers != ["hw", "linux", "ros"]:
            raise ValueError("runtime evidence layers must be exactly hw, linux, ros")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetRuntimeEvidenceJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-evidence-job-spec/v1"] = (
        "rolo-target-runtime-evidence-job-spec/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    target_transport: TargetTransport
    target_registration_sha256: str = Field(pattern=_SHA256)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    collector_descriptor_sha256: str = Field(pattern=_SHA256)
    collector_configuration_sha256: str = Field(pattern=_SHA256)
    collector_key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    collection_request: TargetEvidenceCollectionRequestV4
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approval_action: Literal[ApprovalAction.COLLECT_RUNTIME_EVIDENCE] = (
        ApprovalAction.COLLECT_RUNTIME_EVIDENCE
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_expires_at: datetime

    @model_validator(mode="after")
    def bind_spec(self) -> TargetRuntimeEvidenceJobSpec:
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("runtime evidence approval expiry must be timezone-aware")
        request = self.collection_request
        if (
            request.target_id != self.target_id
            or request.evidence_request.robot_id != self.target_id
            or request.approval_id != self.approval_id
            or request.authorization is not None
            or request.evidence_request.requested_layers != ["hw", "linux", "ros"]
            or request.evidence_request.expires_at != self.approval_expires_at
        ):
            raise ValueError("runtime evidence collection request differs from frozen scope")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetRuntimeEvidenceSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-evidence-intent/v1"] = (
        "rolo-target-runtime-evidence-intent/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetRuntimeEvidenceJobSpec


class TargetRuntimeEvidenceJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-evidence-submission-result/v1"] = (
        "rolo-target-runtime-evidence-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetRuntimeEvidenceJobSpec
    approval: ApprovalRequest


class TargetRuntimeEvidenceJobArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetRuntimeEvidenceJobFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    COLLECTOR_PIN_CHANGED = "COLLECTOR_PIN_CHANGED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetRuntimeEvidenceJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-evidence-job-artifact/v1"] = (
        "rolo-target-runtime-evidence-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=_IDENTIFIER)
    target_registration_sha256: str = Field(pattern=_SHA256)
    observed_target_registration_sha256: str | None = Field(default=None, pattern=_SHA256)
    collector_descriptor_sha256: str = Field(pattern=_SHA256)
    observed_collector_descriptor_sha256: str | None = Field(default=None, pattern=_SHA256)
    evidence_request: TargetEvidenceRequest
    authorized_request_sha256: str | None = Field(default=None, pattern=_SHA256)
    status: TargetRuntimeEvidenceJobArtifactStatus
    failure_code: TargetRuntimeEvidenceJobFailureCode | None = None
    execution: TargetEvidenceCollectionResultV4 | None = None
    verified_at: datetime | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_status(self) -> TargetRuntimeEvidenceJobArtifact:
        if self.completed_at.tzinfo is None or (
            self.verified_at is not None and self.verified_at.tzinfo is None
        ):
            raise ValueError("runtime evidence artifact timestamps must be timezone-aware")
        succeeded = self.status == TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED
        if succeeded:
            if (
                self.failure_code is not None
                or self.execution is None
                or self.execution.execution_status != TargetExecutionStatus.SUCCEEDED
                or self.execution.bundle is None
                or self.authorized_request_sha256 is None
                or self.execution.request_sha256 != self.authorized_request_sha256
                or self.verified_at is None
            ):
                raise ValueError("successful runtime evidence artifact is incomplete")
        elif self.failure_code is None:
            raise ValueError("failed runtime evidence artifact requires a failure code")
        registration_drift = (
            self.failure_code == TargetRuntimeEvidenceJobFailureCode.TARGET_REGISTRATION_CHANGED
        )
        collector_drift = (
            self.failure_code == TargetRuntimeEvidenceJobFailureCode.COLLECTOR_PIN_CHANGED
        )
        if registration_drift != (self.observed_target_registration_sha256 is not None):
            raise ValueError("runtime evidence registration drift binding is inconsistent")
        if collector_drift != (self.observed_collector_descriptor_sha256 is not None):
            raise ValueError("runtime evidence collector drift binding is inconsistent")
        if self.execution is not None and (
            self.execution.target_id != self.target_id or self.execution.robot_id != self.target_id
        ):
            raise ValueError("runtime evidence execution target binding mismatch")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetRuntimeEvidenceArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("runtime evidence artifact root cannot be a symbolic link")

    def path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid runtime evidence Job id")
        return self.root / job_id / "runtime-evidence-result.json"

    def load_optional(self, job_id: str) -> TargetRuntimeEvidenceJobArtifact | None:
        path = self.path(job_id)
        if path.is_symlink():
            raise ValueError("runtime evidence artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("runtime evidence artifact is invalid")
        return TargetRuntimeEvidenceJobArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def load(self, job_id: str) -> TargetRuntimeEvidenceJobArtifact:
        artifact = self.load_optional(job_id)
        if artifact is None:
            raise FileNotFoundError(self.path(job_id))
        return artifact

    def persist(self, artifact: TargetRuntimeEvidenceJobArtifact) -> None:
        path = self.path(artifact.job_id)
        current = self.load_optional(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("runtime evidence artifact already differs")
            return
        atomic_write_text(path, artifact.model_dump_json(indent=2) + "\n", require_absent=True)


def build_target_runtime_evidence_job_spec(
    registration: TargetRegistrationRequest,
    submission: TargetRuntimeEvidenceJobSubmission,
    pin: CollectorEnrollmentPinV4,
    *,
    approval_id: str,
    request_id: str,
    nonce: str,
    issued_at: datetime,
    approval_expires_at: datetime,
) -> TargetRuntimeEvidenceJobSpec:
    profile = registration.target
    descriptor = pin.descriptor
    if descriptor.target_id != profile.target_id or descriptor.robot_id != profile.target_id:
        raise ValueError("runtime evidence collector pin differs from target identity")
    evidence_request = TargetEvidenceRequest(
        robot_id=profile.target_id,
        nonce=nonce,
        requested_layers=submission.requested_layers,
        requested_executable_help_ids=[
            item.executable_id for item in pin.configuration.help_executables
        ],
        issued_at=issued_at,
        expires_at=approval_expires_at,
    )
    return TargetRuntimeEvidenceJobSpec(
        target_id=profile.target_id,
        target_transport=profile.transport,
        target_registration_sha256=target_connection_binding_sha256(
            profile,
            registration.connection,
        ),
        collector_id=descriptor.collector_id,
        collector_descriptor_sha256=descriptor.canonical_sha256(),
        collector_configuration_sha256=pin.configuration.canonical_sha256(),
        collector_key_id=descriptor.key_id,
        collection_request=TargetEvidenceCollectionRequestV4(
            request_id=request_id,
            target_id=profile.target_id,
            evidence_request=evidence_request,
            approval_id=approval_id,
            timeout_s=submission.timeout_s,
        ),
        approval_id=approval_id,
        approver_principal=submission.approver_principal,
        approval_expires_at=approval_expires_at,
    )


class TargetRuntimeEvidenceJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("runtime evidence Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid runtime evidence Job id")
        return self.root / job_id / "runtime-evidence-spec.json"

    def contains(self, job_id: str) -> bool:
        path = self._path(job_id)
        return path.is_file() and not path.is_symlink()

    def load(self, job_id: str) -> TargetRuntimeEvidenceJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise ValueError("runtime evidence Job spec is unavailable")
        return TargetRuntimeEvidenceJobSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def persist(self, job_id: str, spec: TargetRuntimeEvidenceJobSpec) -> None:
        path = self._path(job_id)
        try:
            atomic_write_text(path, spec.model_dump_json(indent=2) + "\n", require_absent=True)
        except FileExistsError:
            if self.load(job_id) != spec:
                raise DeploymentJobStateConflict(
                    "runtime evidence Job spec already differs"
                ) from None


class TargetRuntimeEvidenceIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("runtime evidence intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        if (
            re.fullmatch(_IDENTIFIER, target_id) is None
            or re.fullmatch(_IDEMPOTENCY, idempotency_key) is None
        ):
            raise ValueError("invalid runtime evidence intent identity")
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self.root / target_id / f"{digest}.json"

    def lock_target(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key).with_suffix(".intent-lock")

    def load(self, target_id: str, idempotency_key: str) -> TargetRuntimeEvidenceSubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 768 * 1024:
            raise FileNotFoundError(path)
        return TargetRuntimeEvidenceSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self, intent: TargetRuntimeEvidenceSubmissionIntent
    ) -> TargetRuntimeEvidenceSubmissionIntent:
        path = self._path(intent.target_id, intent.idempotency_key)
        try:
            atomic_write_text(path, intent.model_dump_json(indent=2) + "\n", require_absent=True)
        except FileExistsError:
            current = self.load(intent.target_id, intent.idempotency_key)
            if current != intent:
                raise DeploymentJobStateConflict(
                    "runtime evidence submission intent already differs"
                ) from None
            return current
        return intent


class TargetRuntimeEvidenceSubmissionService:
    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetRuntimeEvidenceJobSpecStore,
        intents: TargetRuntimeEvidenceIntentStore,
        registrations: TargetRegistrationService,
        pins: CollectorEnrollmentPinRegistry,
    ) -> None:
        self.store = store
        self.specs = specs
        self.intents = intents
        self.registrations = registrations
        self.pins = pins

    def _submit_spec(
        self,
        spec: TargetRuntimeEvidenceJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime,
    ) -> TargetRuntimeEvidenceJobSubmissionResult:
        command = DeploymentCommand(
            command=DeploymentCommandKind.COLLECT_EVIDENCE,
            target_id=spec.target_id,
            active_probe="runtime-readonly",
            run_adapter_agent=False,
            requested_by=requested_by,
            interaction_surface=interaction_surface,
            idempotency_key=idempotency_key,
            parameters_sha256=spec.canonical_sha256(),
        )
        record = self.store.create_job(command, now=now)
        self.specs.persist(record.job.job_id, spec)
        scope_sha256 = deployment_request_payload_sha256(spec.collection_request)
        try:
            approval = self.store.load_approval_request(spec.approval_id)
        except ValueError:
            try:
                approval = self.store.request_approval(
                    record.job.job_id,
                    action=ApprovalAction.COLLECT_RUNTIME_EVIDENCE,
                    risk="R2",
                    approver_principal=spec.approver_principal,
                    summary=(
                        "Collect the exact read-only hw, linux and ROS layers from the "
                        "pinned target collector within a five-minute window."
                    ),
                    expires_at=spec.approval_expires_at,
                    authorization_scope_sha256=scope_sha256,
                    now=now,
                    approval_id=spec.approval_id,
                )
            except FileExistsError:
                approval = self.store.load_approval_request(spec.approval_id)
        if (
            approval.job_id != record.job.job_id
            or approval.command_sha256 != record.job.command_sha256
            or approval.authorization_scope_sha256 != scope_sha256
            or approval.action != ApprovalAction.COLLECT_RUNTIME_EVIDENCE
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict("runtime evidence Job approval already differs")
        return TargetRuntimeEvidenceJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetRuntimeEvidenceJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetRuntimeEvidenceJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("runtime evidence submission timestamp must be timezone-aware")
        with interprocess_lock(self.intents.lock_target(target_id, idempotency_key)):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                seed = hashlib.sha256(
                    f"runtime-evidence:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()
                approval_id = "approval-" + seed[:32]
                expires_at = observed_at + timedelta(seconds=submission.approval_ttl_s)
                spec = build_target_runtime_evidence_job_spec(
                    self.registrations.load(target_id),
                    submission,
                    self.pins.get(target_id),
                    approval_id=approval_id,
                    request_id="runtime-evidence-" + seed[:32],
                    nonce=seed[32:64],
                    issued_at=observed_at,
                    approval_expires_at=expires_at,
                )
                intent = self.intents.persist(
                    TargetRuntimeEvidenceSubmissionIntent(
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
                        "runtime evidence idempotency key already binds another request"
                    )
            return self._submit_spec(
                intent.spec,
                requested_by=requested_by,
                interaction_surface=interaction_surface,
                idempotency_key=idempotency_key,
                now=observed_at,
            )


class TargetRuntimeEvidenceJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetRuntimeEvidenceJobSpecStore,
        artifact_root: Path,
        pins: CollectorEnrollmentPinRegistry,
        *,
        authorization_signing_key_id: str | None = None,
        authorization_public_key_path: Path | None = None,
        authorization_private_key_path: Path | None = None,
        executor_factory: Callable[[TargetProfile], TargetExecutor] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.artifacts = TargetRuntimeEvidenceArtifactStore(artifact_root)
        self.pins = pins
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
        return f"artifact://deployment-jobs/{job_id}/runtime-evidence-result.json"

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetRuntimeEvidenceJobSpec,
        artifact: TargetRuntimeEvidenceJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
            or artifact.target_registration_sha256 != spec.target_registration_sha256
            or artifact.collector_descriptor_sha256 != spec.collector_descriptor_sha256
            or artifact.evidence_request != spec.collection_request.evidence_request
        ):
            raise DeploymentJobStateConflict("runtime evidence artifact binding mismatch")
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "runtime-evidence"
            ),
            None,
        )
        if checkpoint is None:
            raise DeploymentJobStateConflict("runtime evidence artifact has no checkpoint")
        artifact_ref = self._artifact_ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED:
            if checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    record.job.job_id,
                    step_id="runtime-evidence",
                    outcome_sha256=digest,
                    artifact_refs=[artifact_ref],
                )
            elif checkpoint.status != DeploymentStepStatus.COMPLETE:
                raise DeploymentJobStateConflict(
                    "runtime evidence artifact conflicts with checkpoint"
                )
            return self.store.complete_job(record.job.job_id, artifact_refs=[artifact_ref])
        if record.job.state == DeploymentJobState.FAILED:
            return record
        return self.store.fail_step(
            record.job.job_id,
            step_id="runtime-evidence",
            remote_state_known=True,
            outcome_sha256=digest,
            artifact_refs=[artifact_ref],
        )

    def _failure(
        self,
        record: DeploymentJobRecord,
        spec: TargetRuntimeEvidenceJobSpec,
        code: TargetRuntimeEvidenceJobFailureCode,
        *,
        observed_registration: str | None = None,
        observed_collector: str | None = None,
        execution: TargetEvidenceCollectionResultV4 | None = None,
        authorized_request_sha256: str | None = None,
    ) -> TargetRuntimeEvidenceJobArtifact:
        return TargetRuntimeEvidenceJobArtifact(
            job_id=record.job.job_id,
            command_sha256=record.job.command_sha256,
            spec_sha256=spec.canonical_sha256(),
            target_id=spec.target_id,
            target_registration_sha256=spec.target_registration_sha256,
            observed_target_registration_sha256=observed_registration,
            collector_descriptor_sha256=spec.collector_descriptor_sha256,
            observed_collector_descriptor_sha256=observed_collector,
            evidence_request=spec.collection_request.evidence_request,
            authorized_request_sha256=authorized_request_sha256,
            status=TargetRuntimeEvidenceJobArtifactStatus.FAILED,
            failure_code=code,
            execution=execution,
            completed_at=datetime.now(timezone.utc),
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
                "runtime evidence Job handler received another command"
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
            raise DeploymentJobStateConflict("runtime evidence Job spec digest mismatch")
        self.store.verify_approval(
            spec.approval_id,
            job_id=job_id,
            target_id=spec.target_id,
            command_sha256=record.job.command_sha256,
            action=ApprovalAction.COLLECT_RUNTIME_EVIDENCE,
        )
        if (
            self._authorization_signing_key_id is None
            or self._authorization_public_key_path is None
            or self._authorization_private_key_path is None
        ):
            raise DeploymentJobStateConflict("runtime evidence authorization signer is unavailable")
        try:
            verify_deployment_authorization_signing_key_pair(
                public_key_path=self._authorization_public_key_path,
                private_key_path=self._authorization_private_key_path,
            )
            authorized_request = authorize_deployment_request(
                spec.collection_request,
                self.store,
                approval_id=spec.approval_id,
                signing_key_id=self._authorization_signing_key_id,
                private_key_path=self._authorization_private_key_path,
                lifetime_s=min(300, max(1, int(spec.collection_request.timeout_s))),
                authorization_id=(
                    "authorization-"
                    + hashlib.sha256(
                        f"runtime-evidence:{job_id}:{record.attempt}".encode()
                    ).hexdigest()[:32]
                ),
            )
        except (OSError, ValueError) as exc:
            raise DeploymentJobStateConflict(
                "runtime evidence authorization proof could not be issued"
            ) from exc

        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self.artifacts.load_optional(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            if any(
                item.attempt == record.attempt
                and item.step_id == "runtime-evidence"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            ):
                raise DeploymentJobStateConflict(
                    "runtime evidence execution checkpoint requires reconciliation"
                )
            registration = self.registrations.load(spec.target_id)
            observed_registration = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            current_pin = self.pins.get(spec.target_id)
            observed_collector = current_pin.descriptor.canonical_sha256()
            record = self.store.start_step(
                job_id,
                step_id="runtime-evidence",
                state=DeploymentJobState.COLLECTING_EVIDENCE,
                remote=spec.target_transport == TargetTransport.SSH,
            )
            if observed_registration != spec.target_registration_sha256:
                artifact = self._failure(
                    record,
                    spec,
                    TargetRuntimeEvidenceJobFailureCode.TARGET_REGISTRATION_CHANGED,
                    observed_registration=observed_registration,
                )
            elif (
                observed_collector != spec.collector_descriptor_sha256
                or current_pin.configuration.canonical_sha256()
                != spec.collector_configuration_sha256
            ):
                artifact = self._failure(
                    record,
                    spec,
                    TargetRuntimeEvidenceJobFailureCode.COLLECTOR_PIN_CHANGED,
                    observed_collector=observed_collector,
                )
            else:
                authorized_sha256 = authorized_request.canonical_sha256()
                try:
                    execution = self._executor(registration.target).collect_evidence_v4(
                        authorized_request,
                        cancel_event=cancel_event,
                    )
                except Exception:
                    artifact = self._failure(
                        record,
                        spec,
                        TargetRuntimeEvidenceJobFailureCode.RUNNER_ERROR,
                        authorized_request_sha256=authorized_sha256,
                    )
                else:
                    current = self.store.load_job(job_id)
                    if (
                        execution.error_code == TargetExecutionErrorCode.CANCELLED
                        or current.cancel_requested
                    ):
                        if not current.cancel_requested:
                            self.store.request_cancel(job_id)
                        return self.store.resolve_cancel(
                            job_id,
                            remote_termination_confirmed=(
                                spec.target_transport != TargetTransport.SSH
                            ),
                        )
                    if (
                        execution.execution_status != TargetExecutionStatus.SUCCEEDED
                        or execution.bundle is None
                        or execution.request_sha256 != authorized_sha256
                    ):
                        artifact = self._failure(
                            record,
                            spec,
                            TargetRuntimeEvidenceJobFailureCode.EXECUTION_FAILED,
                            execution=execution,
                            authorized_request_sha256=authorized_sha256,
                        )
                    else:
                        verified_at = datetime.now(timezone.utc)
                        try:
                            verify_target_evidence_v4(
                                execution.bundle,
                                pin=current_pin,
                                request=spec.collection_request.evidence_request,
                                deployment_mode=(
                                    EvidenceDeploymentMode.LOCAL
                                    if spec.target_transport == TargetTransport.LOCAL
                                    else EvidenceDeploymentMode.REMOTE
                                ),
                                now=verified_at,
                            )
                        except ValueError:
                            artifact = self._failure(
                                record,
                                spec,
                                TargetRuntimeEvidenceJobFailureCode.VERIFICATION_FAILED,
                                execution=execution,
                                authorized_request_sha256=authorized_sha256,
                            )
                        else:
                            artifact = TargetRuntimeEvidenceJobArtifact(
                                job_id=job_id,
                                command_sha256=record.job.command_sha256,
                                spec_sha256=spec.canonical_sha256(),
                                target_id=spec.target_id,
                                target_registration_sha256=spec.target_registration_sha256,
                                collector_descriptor_sha256=spec.collector_descriptor_sha256,
                                evidence_request=spec.collection_request.evidence_request,
                                authorized_request_sha256=authorized_sha256,
                                status=TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED,
                                execution=execution,
                                verified_at=verified_at,
                                completed_at=verified_at,
                            )
            self.artifacts.persist(artifact)
            return self._finish(record, spec, artifact)
