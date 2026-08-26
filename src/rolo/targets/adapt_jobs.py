from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.models import DiscoveryStatus
from rolo.core.persistence import atomic_write_text
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.targets.adapt_command import AdaptStartParameters
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.enrollment import CollectorEnrollmentPinRegistry
from rolo.targets.evidence_v4 import verify_target_evidence_v4
from rolo.targets.executor import TargetExecutionStatus
from rolo.targets.models import (
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
    TargetTransport,
)
from rolo.targets.project_evidence_jobs import (
    TargetProjectEvidenceArtifactStore,
    TargetProjectEvidenceJobArtifactStatus,
)
from rolo.targets.registration import (
    TargetRegistrationRequest,
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.runtime_deployment import TargetProjectEvidenceStatus
from rolo.targets.runtime_evidence_jobs import (
    TargetRuntimeEvidenceArtifactStore,
    TargetRuntimeEvidenceJobArtifactStatus,
)
from rolo.targets.source_discovery_jobs import (
    TargetSourceDiscoveryArtifactStore,
    TargetSourceDiscoveryJobArtifactStatus,
)

_SHA256 = r"^[0-9a-f]{64}$"
_JOB_ID = r"^deployment-[0-9a-f]{32}$"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class TargetAdaptProjectEvidenceBinding(BaseModel):
    """Immutable reference from one SSH Adapt Job to verified target metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-adapt-project-evidence-binding/v1"] = (
        "rolo-target-adapt-project-evidence-binding/v1"
    )
    job_id: str = Field(pattern=_JOB_ID)
    artifact_sha256: str = Field(pattern=_SHA256)
    command_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace_sha256: str = Field(pattern=_SHA256)
    workspace_manifest_sha256: str = Field(pattern=_SHA256)
    observed_paths: list[str] = Field(min_length=1, max_length=256)
    observed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def bind_observation(self) -> TargetAdaptProjectEvidenceBinding:
        if self.observed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Adapt project evidence timestamps must be timezone-aware")
        if self.expires_at <= self.observed_at:
            raise ValueError("Adapt project evidence expiry must follow observation")
        if self.observed_paths != sorted(set(self.observed_paths)):
            raise ValueError("Adapt project evidence paths must be unique and sorted")
        return self


class TargetAdaptSourceDiscoveryBinding(BaseModel):
    """Immutable reference to separately approved target source-analysis facts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-adapt-source-discovery-binding/v1"] = (
        "rolo-target-adapt-source-discovery-binding/v1"
    )
    job_id: str = Field(pattern=_JOB_ID)
    artifact_sha256: str = Field(pattern=_SHA256)
    command_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    workspace_sha256: str = Field(pattern=_SHA256)
    request_sha256: str = Field(pattern=_SHA256)
    summary_sha256: str = Field(pattern=_SHA256)
    scan_roots: list[str] = Field(min_length=1, max_length=16)
    observed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def bind_observation(self) -> TargetAdaptSourceDiscoveryBinding:
        if self.observed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Adapt source discovery timestamps must be timezone-aware")
        if self.expires_at <= self.observed_at:
            raise ValueError("Adapt source discovery expiry must follow observation")
        if self.scan_roots != sorted(set(self.scan_roots)):
            raise ValueError("Adapt source discovery roots must be unique and sorted")
        return self


class TargetAdaptRuntimeEvidenceBinding(BaseModel):
    """Immutable reference to separately approved, signed runtime facts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-adapt-runtime-evidence-binding/v1"] = (
        "rolo-target-adapt-runtime-evidence-binding/v1"
    )
    job_id: str = Field(pattern=_JOB_ID)
    artifact_sha256: str = Field(pattern=_SHA256)
    command_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=_SHA256)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    collector_descriptor_sha256: str = Field(pattern=_SHA256)
    collector_configuration_sha256: str = Field(pattern=_SHA256)
    collector_key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    evidence_request_sha256: str = Field(pattern=_SHA256)
    bundle_payload_sha256: str = Field(pattern=_SHA256)
    collected_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def bind_observation(self) -> TargetAdaptRuntimeEvidenceBinding:
        if self.collected_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Adapt runtime evidence timestamps must be timezone-aware")
        if self.expires_at <= self.collected_at:
            raise ValueError("Adapt runtime evidence expiry must follow collection")
        return self


class TargetAdaptJobSubmission(BaseModel):
    """Public discovery request; target workspace always comes from registration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-adapt-job-submission/v1"] = (
        "rolo-target-adapt-job-submission/v1"
    )
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly"
    run_adapter_agent: bool = False
    timeout_s: int = Field(default=1800, ge=1, le=86_400)
    evidence_timeout_s: float = Field(default=45.0, ge=1.0, le=300.0)
    urdf_path: str | None = Field(default=None, min_length=1, max_length=4096)
    scratch_root: str | None = Field(default=None, min_length=1, max_length=4096)
    project_evidence_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    project_evidence_max_age_s: int = Field(default=900, ge=60, le=86_400)
    source_discovery_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    source_discovery_max_age_s: int = Field(default=900, ge=60, le=86_400)
    runtime_evidence_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    runtime_evidence_max_age_s: int = Field(default=300, ge=60, le=300)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetAdaptJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-adapt-job-spec/v1",
        "rolo-target-adapt-job-spec/v2",
        "rolo-target-adapt-job-spec/v3",
        "rolo-target-adapt-job-spec/v4",
    ] = "rolo-target-adapt-job-spec/v4"
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace_root: str = Field(min_length=1, max_length=4096)
    target_transport: TargetTransport = TargetTransport.LOCAL
    project_evidence: TargetAdaptProjectEvidenceBinding | None = None
    source_discovery: TargetAdaptSourceDiscoveryBinding | None = None
    runtime_evidence: TargetAdaptRuntimeEvidenceBinding | None = None
    parameters: AdaptStartParameters
    active_probe: Literal["none", "help", "runtime-readonly"]
    run_adapter_agent: Literal[False] = False

    @model_validator(mode="after")
    def bind_parameters(self) -> TargetAdaptJobSpec:
        if self.target_transport == TargetTransport.SSH:
            workspace_matches = self.parameters.project_root == self.workspace_root
        else:
            workspace_matches = (
                self.parameters.project_root.casefold() == self.workspace_root.casefold()
            )
        if not workspace_matches:
            raise ValueError("Adapt Job parameters differ from frozen workspace")
        if self.target_transport == TargetTransport.LOCAL:
            if (
                self.parameters.project_root_location != "CONTROLLER"
                or self.parameters.evidence_mode != "local"
                or self.project_evidence is not None
                or self.source_discovery is not None
                or self.runtime_evidence is not None
            ):
                raise ValueError("Local Adapt Job has remote project evidence state")
        elif self.target_transport == TargetTransport.SSH:
            if (
                self.parameters.project_root_location != "TARGET"
                or self.parameters.evidence_mode != "remote"
                or self.project_evidence is None
            ):
                raise ValueError("SSH Adapt Job requires target project evidence")
            if (
                self.project_evidence.target_id != self.target_id
                or self.project_evidence.target_registration_sha256
                != self.target_registration_sha256
            ):
                raise ValueError("SSH Adapt project evidence identity mismatch")
            if self.source_discovery is not None and (
                self.source_discovery.target_id != self.target_id
                or self.source_discovery.target_registration_sha256
                != self.target_registration_sha256
                or self.source_discovery.workspace_sha256 != self.project_evidence.workspace_sha256
            ):
                raise ValueError("SSH Adapt source discovery identity mismatch")
            if self.runtime_evidence is not None and (
                self.runtime_evidence.target_id != self.target_id
                or self.runtime_evidence.target_registration_sha256
                != self.target_registration_sha256
            ):
                raise ValueError("SSH Adapt runtime evidence identity mismatch")
            if self.active_probe == "none" and self.runtime_evidence is not None:
                raise ValueError("SSH metadata-only Adapt cannot bind runtime evidence")
            if self.active_probe == "runtime-readonly" and self.runtime_evidence is None:
                raise ValueError("SSH runtime-readonly Adapt requires target runtime evidence")
            if self.active_probe == "help":
                raise ValueError("SSH Adapt does not support an unbound help probe")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetAdaptJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("Adapt Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid Adapt Job ID")
        return self.root / job_id / "adapt-spec.json"

    def load(self, job_id: str) -> TargetAdaptJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise ValueError("Adapt Job spec is unavailable")
        return TargetAdaptJobSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def persist(self, job_id: str, spec: TargetAdaptJobSpec) -> TargetAdaptJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict("Adapt Job spec already differs")
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
                raise DeploymentJobStateConflict("Adapt Job spec already differs") from None
            return current
        return spec


def build_target_adapt_job_spec(
    registration: TargetRegistrationRequest,
    submission: TargetAdaptJobSubmission,
    *,
    project_evidence: TargetAdaptProjectEvidenceBinding | None = None,
    source_discovery: TargetAdaptSourceDiscoveryBinding | None = None,
    runtime_evidence: TargetAdaptRuntimeEvidenceBinding | None = None,
) -> TargetAdaptJobSpec:
    profile = registration.target
    if submission.run_adapter_agent:
        raise ValueError(
            "Adapt Job automatic Agent/release activation requires release-scoped approvals"
        )
    if profile.transport == TargetTransport.LOCAL:
        if (
            submission.project_evidence_job_id is not None
            or project_evidence is not None
            or submission.source_discovery_job_id is not None
            or source_discovery is not None
            or submission.runtime_evidence_job_id is not None
            or runtime_evidence is not None
        ):
            raise ValueError("Local Adapt Job does not accept target evidence Jobs")
        if (
            submission.project_evidence_max_age_s != 900
            or submission.source_discovery_max_age_s != 900
            or submission.runtime_evidence_max_age_s != 300
        ):
            raise ValueError("Local Adapt Job does not accept target evidence freshness options")
        project_root_location = "CONTROLLER"
        evidence_mode = "local"
    else:
        if submission.project_evidence_job_id is None or project_evidence is None:
            raise ValueError("SSH Adapt Job requires a completed target project evidence Job")
        if submission.project_evidence_job_id != project_evidence.job_id:
            raise ValueError("SSH Adapt project evidence Job differs from its binding")
        if (submission.source_discovery_job_id is None) != (source_discovery is None):
            raise ValueError("SSH Adapt source discovery Job and binding must be supplied together")
        if (
            source_discovery is not None
            and submission.source_discovery_job_id != source_discovery.job_id
        ):
            raise ValueError("SSH Adapt source discovery Job differs from its binding")
        if (submission.runtime_evidence_job_id is None) != (runtime_evidence is None):
            raise ValueError("SSH Adapt runtime evidence Job and binding must be supplied together")
        if (
            runtime_evidence is not None
            and submission.runtime_evidence_job_id != runtime_evidence.job_id
        ):
            raise ValueError("SSH Adapt runtime evidence Job differs from its binding")
        if submission.active_probe == "runtime-readonly" and runtime_evidence is None:
            raise ValueError("SSH runtime-readonly Adapt requires a completed runtime evidence Job")
        if submission.active_probe == "none" and runtime_evidence is not None:
            raise ValueError("SSH metadata-only Adapt does not accept runtime evidence")
        if submission.active_probe == "help":
            raise ValueError("SSH Adapt does not support an unbound help probe")
        if submission.urdf_path is not None or submission.scratch_root is not None:
            raise ValueError(
                "SSH metadata-only Adapt does not accept controller URDF or scratch paths"
            )
        project_root_location = "TARGET"
        evidence_mode = "remote"
    parameters = AdaptStartParameters(
        project_root_location=project_root_location,
        project_root=profile.workspace_root,
        urdf_path=submission.urdf_path,
        scratch_root=submission.scratch_root,
        timeout_s=submission.timeout_s,
        evidence_mode=evidence_mode,
        evidence_timeout_s=submission.evidence_timeout_s,
    )
    return TargetAdaptJobSpec(
        target_id=profile.target_id,
        target_registration_sha256=target_connection_binding_sha256(
            profile, registration.connection
        ),
        workspace_root=parameters.project_root,
        target_transport=profile.transport,
        project_evidence=project_evidence,
        source_discovery=source_discovery,
        runtime_evidence=runtime_evidence,
        parameters=parameters,
        active_probe=submission.active_probe,
        run_adapter_agent=False,
    )


def resolve_target_adapt_project_evidence_binding(
    *,
    job_id: str,
    target_id: str,
    target_registration_sha256: str,
    jobs: DeploymentJobStore,
    artifacts: TargetProjectEvidenceArtifactStore,
    max_age_s: int,
    now: datetime | None = None,
) -> TargetAdaptProjectEvidenceBinding:
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise ValueError("Adapt project evidence resolution time must be timezone-aware")
    record = jobs.load_job(job_id)
    if (
        record.job.state != DeploymentJobState.COMPLETE
        or record.job.command.command != DeploymentCommandKind.COLLECT_EVIDENCE
        or record.job.command.target_id != target_id
    ):
        raise DeploymentJobStateConflict(
            "Adapt project evidence Job is not a completed Job for this target"
        )
    artifact = artifacts.load(job_id)
    execution = artifact.execution
    snapshot = execution.snapshot if execution is not None else None
    manifest = snapshot.manifest if snapshot is not None else None
    if (
        artifact.status != TargetProjectEvidenceJobArtifactStatus.SUCCEEDED
        or artifact.target_id != target_id
        or artifact.target_registration_sha256 != target_registration_sha256
        or artifact.command_sha256 != record.job.command_sha256
        or execution is None
        or execution.execution_status != TargetExecutionStatus.SUCCEEDED
        or snapshot is None
        or snapshot.status != TargetProjectEvidenceStatus.OBSERVED
        or manifest is None
        or manifest.workspace.target_id != target_id
        or manifest.workspace.robot_id != target_id
    ):
        raise DeploymentJobStateConflict(
            "Adapt project evidence artifact is incomplete or has another identity"
        )
    if snapshot.observed_at > observed_now + timedelta(minutes=2):
        raise DeploymentJobStateConflict("Adapt project evidence timestamp is in the future")
    expires_at = snapshot.observed_at + timedelta(seconds=max_age_s)
    if observed_now >= expires_at:
        raise DeploymentJobStateConflict("Adapt project evidence artifact has expired")
    return TargetAdaptProjectEvidenceBinding(
        job_id=job_id,
        artifact_sha256=artifact.canonical_sha256(),
        command_sha256=record.job.command_sha256,
        target_id=target_id,
        target_registration_sha256=target_registration_sha256,
        workspace_sha256=manifest.workspace.canonical_sha256(),
        workspace_manifest_sha256=manifest.content_sha256,
        observed_paths=[item.path for item in manifest.files],
        observed_at=snapshot.observed_at,
        expires_at=expires_at,
    )


def resolve_target_adapt_source_discovery_binding(
    *,
    job_id: str,
    target_id: str,
    target_registration_sha256: str,
    workspace_sha256: str,
    jobs: DeploymentJobStore,
    artifacts: TargetSourceDiscoveryArtifactStore,
    max_age_s: int,
    now: datetime | None = None,
) -> TargetAdaptSourceDiscoveryBinding:
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise ValueError("Adapt source discovery resolution time must be timezone-aware")
    record = jobs.load_job(job_id)
    if (
        record.job.state != DeploymentJobState.COMPLETE
        or record.job.command.command != DeploymentCommandKind.COLLECT_EVIDENCE
        or record.job.command.target_id != target_id
    ):
        raise DeploymentJobStateConflict(
            "Adapt source discovery Job is not a completed Job for this target"
        )
    artifact = artifacts.load(job_id)
    execution = artifact.execution
    snapshot = execution.snapshot if execution is not None else None
    if (
        artifact.status != TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED
        or artifact.target_id != target_id
        or artifact.target_registration_sha256 != target_registration_sha256
        or artifact.command_sha256 != record.job.command_sha256
        or execution is None
        or execution.execution_status != TargetExecutionStatus.SUCCEEDED
        or snapshot is None
        or snapshot.status == DiscoveryStatus.UNAVAILABLE
        or not snapshot.projects
        or snapshot.target_id != target_id
        or snapshot.robot_id != target_id
        or snapshot.workspace_sha256 != workspace_sha256
    ):
        raise DeploymentJobStateConflict(
            "Adapt source discovery artifact is incomplete or has another identity"
        )
    if snapshot.observed_at > observed_now + timedelta(minutes=2):
        raise DeploymentJobStateConflict("Adapt source discovery timestamp is in the future")
    expires_at = snapshot.observed_at + timedelta(seconds=max_age_s)
    if observed_now >= expires_at:
        raise DeploymentJobStateConflict("Adapt source discovery artifact has expired")
    return TargetAdaptSourceDiscoveryBinding(
        job_id=job_id,
        artifact_sha256=artifact.canonical_sha256(),
        command_sha256=record.job.command_sha256,
        target_id=target_id,
        target_registration_sha256=target_registration_sha256,
        workspace_id=snapshot.workspace_id,
        workspace_sha256=snapshot.workspace_sha256,
        request_sha256=snapshot.request_sha256,
        summary_sha256=snapshot.summary_sha256,
        scan_roots=[project.root for project in snapshot.projects],
        observed_at=snapshot.observed_at,
        expires_at=expires_at,
    )


def resolve_target_adapt_runtime_evidence_binding(
    *,
    job_id: str,
    target_id: str,
    target_registration_sha256: str,
    jobs: DeploymentJobStore,
    artifacts: TargetRuntimeEvidenceArtifactStore,
    pins: CollectorEnrollmentPinRegistry,
    max_age_s: int,
    now: datetime | None = None,
) -> TargetAdaptRuntimeEvidenceBinding:
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise ValueError("Adapt runtime evidence resolution time must be timezone-aware")
    record = jobs.load_job(job_id)
    if (
        record.job.state != DeploymentJobState.COMPLETE
        or record.job.command.command != DeploymentCommandKind.COLLECT_EVIDENCE
        or record.job.command.target_id != target_id
    ):
        raise DeploymentJobStateConflict(
            "Adapt runtime evidence Job is not a completed Job for this target"
        )
    artifact = artifacts.load(job_id)
    execution = artifact.execution
    bundle = execution.bundle if execution is not None else None
    pin = pins.get(target_id)
    if (
        artifact.status != TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED
        or artifact.target_id != target_id
        or artifact.target_registration_sha256 != target_registration_sha256
        or artifact.command_sha256 != record.job.command_sha256
        or execution is None
        or execution.execution_status != TargetExecutionStatus.SUCCEEDED
        or bundle is None
        or artifact.collector_descriptor_sha256 != pin.descriptor.canonical_sha256()
    ):
        raise DeploymentJobStateConflict(
            "Adapt runtime evidence artifact is incomplete or has another identity"
        )
    try:
        verify_target_evidence_v4(
            bundle,
            pin=pin,
            request=artifact.evidence_request,
            deployment_mode=EvidenceDeploymentMode.REMOTE,
            now=observed_now,
        )
    except ValueError as exc:
        raise DeploymentJobStateConflict(
            "Adapt runtime evidence signature or freshness is invalid"
        ) from exc
    expires_at = bundle.collected_at + timedelta(seconds=max_age_s)
    if observed_now >= expires_at:
        raise DeploymentJobStateConflict("Adapt runtime evidence artifact has expired")
    return TargetAdaptRuntimeEvidenceBinding(
        job_id=job_id,
        artifact_sha256=artifact.canonical_sha256(),
        command_sha256=record.job.command_sha256,
        target_id=target_id,
        target_registration_sha256=target_registration_sha256,
        collector_id=bundle.collector_id,
        collector_descriptor_sha256=bundle.descriptor_sha256,
        collector_configuration_sha256=bundle.configuration_sha256,
        collector_key_id=bundle.key_id,
        evidence_request_sha256=hashlib.sha256(
            _canonical_json(artifact.evidence_request.model_dump(mode="json")).encode("utf-8")
        ).hexdigest(),
        bundle_payload_sha256=bundle.payload_sha256,
        collected_at=bundle.collected_at,
        expires_at=expires_at,
    )


class TargetAdaptJobSubmissionService:
    def __init__(self, store: DeploymentJobStore, specs: TargetAdaptJobSpecStore) -> None:
        self.store = store
        self.specs = specs

    def submit(
        self,
        spec: TargetAdaptJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        command = DeploymentCommand(
            command=DeploymentCommandKind.ADAPT,
            target_id=spec.target_id,
            workspace_root=spec.workspace_root,
            active_probe=spec.active_probe,
            run_adapter_agent=False,
            requested_by=requested_by,
            interaction_surface=interaction_surface,
            idempotency_key=idempotency_key,
            parameters_sha256=spec.canonical_sha256(),
        )
        record = self.store.create_job(command, now=now)
        self.specs.persist(record.job.job_id, spec)
        return self.store.load_job(record.job.job_id)


class TargetAdaptJobArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class TargetAdaptJobFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    JOURNEY_BLOCKED = "JOURNEY_BLOCKED"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetAdaptJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-adapt-job-artifact/v1"] = (
        "rolo-target-adapt-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    status: TargetAdaptJobArtifactStatus
    failure_code: TargetAdaptJobFailureCode | None = None
    journey_status: Literal["DISCOVERY_COMPLETE", "BLOCKED"] | None = None
    journey_result_sha256: str | None = Field(default=None, pattern=_SHA256)
    completed_at: datetime

    @model_validator(mode="after")
    def bind_outcome(self) -> TargetAdaptJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("Adapt Job artifact timestamp must be timezone-aware")
        has_result = self.journey_status is not None or self.journey_result_sha256 is not None
        if has_result != (
            self.journey_status is not None and self.journey_result_sha256 is not None
        ):
            raise ValueError("Adapt Job journey result binding is incomplete")
        if self.status == TargetAdaptJobArtifactStatus.SUCCEEDED:
            if self.journey_status != "DISCOVERY_COMPLETE" or self.failure_code is not None:
                raise ValueError("successful Adapt Job artifact is inconsistent")
        elif self.status == TargetAdaptJobArtifactStatus.BLOCKED:
            if (
                self.journey_status != "BLOCKED"
                or self.failure_code != TargetAdaptJobFailureCode.JOURNEY_BLOCKED
            ):
                raise ValueError("blocked Adapt Job artifact is inconsistent")
        elif self.failure_code is None or has_result:
            raise ValueError("failed Adapt Job artifact is incomplete")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class AdaptJourneyResultLike(Protocol):
    status: str
    robot_id: str

    def model_dump_json(self, *, indent: int | None = None) -> str: ...


class TargetAdaptJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetAdaptJobSpecStore,
        artifact_root: Path,
        *,
        settings: object,
        project_evidence_artifacts: TargetProjectEvidenceArtifactStore | None = None,
        source_discovery_artifacts: TargetSourceDiscoveryArtifactStore | None = None,
        runtime_evidence_artifacts: TargetRuntimeEvidenceArtifactStore | None = None,
        collector_pins: CollectorEnrollmentPinRegistry | None = None,
        journey_runner: Callable[[TargetAdaptJobSpec, DeploymentCommand], AdaptJourneyResultLike]
        | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.artifact_root = artifact_root.expanduser().absolute()
        if self.artifact_root.is_symlink():
            raise ValueError("Adapt Job artifact root cannot be a symbolic link")
        self.settings = settings
        self.project_evidence_artifacts = project_evidence_artifacts
        self.source_discovery_artifacts = source_discovery_artifacts
        self.runtime_evidence_artifacts = runtime_evidence_artifacts
        self.collector_pins = collector_pins
        self._journey_runner = journey_runner

    def _directory(self, job_id: str) -> Path:
        return self.artifact_root / job_id

    def _artifact_path(self, job_id: str) -> Path:
        return self._directory(job_id) / "adapt-result.json"

    def _journey_path(self, job_id: str) -> Path:
        return self._directory(job_id) / "adapt-journey.json"

    @staticmethod
    def _artifact_ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/adapt-result.json"

    @staticmethod
    def _journey_ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/adapt-journey.json"

    def _load_artifact(self, job_id: str) -> TargetAdaptJobArtifact | None:
        path = self._artifact_path(job_id)
        if path.is_symlink():
            raise ValueError("Adapt Job artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 512 * 1024:
            raise ValueError("Adapt Job artifact is invalid")
        return TargetAdaptJobArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    def _load_journey(self, job_id: str) -> AdaptJourneyResultLike | None:
        path = self._journey_path(job_id)
        if path.is_symlink():
            raise ValueError("Adapt Journey artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Adapt Journey artifact is invalid")
        from rolo.stages.adapt.journey import AdaptJourneyResult

        return AdaptJourneyResult.model_validate_json(path.read_text(encoding="utf-8"))

    def _execute(
        self, spec: TargetAdaptJobSpec, command: DeploymentCommand
    ) -> AdaptJourneyResultLike:
        bound_project_evidence = self._load_bound_project_evidence(spec)
        bound_source_discovery = self._load_bound_source_discovery(spec)
        bound_runtime_evidence = self._load_bound_runtime_evidence(spec)
        if self._journey_runner is not None:
            return self._journey_runner(spec, command)
        from rolo.commands.lifecycle import run_adapt_start_parameters

        return run_adapt_start_parameters(
            command=command,
            parameters=spec.parameters,
            settings=self.settings,
            project_evidence=bound_project_evidence,
            target_application_probe=(
                bound_source_discovery.to_application_probe()
                if bound_source_discovery is not None
                else None
            ),
            target_runtime_probes=(
                bound_runtime_evidence[0] if bound_runtime_evidence is not None else None
            ),
            target_runtime_evidence=(
                bound_runtime_evidence[1] if bound_runtime_evidence is not None else None
            ),
        )

    def _load_bound_project_evidence(self, spec: TargetAdaptJobSpec):  # type: ignore[no-untyped-def]
        if spec.target_transport == TargetTransport.LOCAL:
            return None
        binding = spec.project_evidence
        if binding is None or self.project_evidence_artifacts is None:
            raise DeploymentJobStateConflict(
                "SSH Adapt project evidence artifact store is unavailable"
            )
        artifact = self.project_evidence_artifacts.load(binding.job_id)
        execution = artifact.execution
        snapshot = execution.snapshot if execution is not None else None
        manifest = snapshot.manifest if snapshot is not None else None
        if (
            artifact.canonical_sha256() != binding.artifact_sha256
            or artifact.command_sha256 != binding.command_sha256
            or artifact.target_id != binding.target_id
            or artifact.target_registration_sha256 != binding.target_registration_sha256
            or artifact.status != TargetProjectEvidenceJobArtifactStatus.SUCCEEDED
            or execution is None
            or execution.execution_status != TargetExecutionStatus.SUCCEEDED
            or snapshot is None
            or snapshot.status != TargetProjectEvidenceStatus.OBSERVED
            or manifest is None
            or manifest.workspace.canonical_sha256() != binding.workspace_sha256
            or manifest.content_sha256 != binding.workspace_manifest_sha256
            or [item.path for item in manifest.files] != binding.observed_paths
        ):
            raise DeploymentJobStateConflict(
                "SSH Adapt project evidence artifact differs from its frozen binding"
            )
        if datetime.now(timezone.utc) >= binding.expires_at:
            raise DeploymentJobStateConflict("SSH Adapt project evidence binding has expired")
        from rolo.stages.adapt.journey import ProjectEvidence

        return ProjectEvidence(
            project_root=Path(manifest.workspace.root),
            observation_mode="TARGET_METADATA",
            target_workspace_manifest_sha256=manifest.content_sha256,
            target_observed_paths=binding.observed_paths,
            target_project_root=manifest.workspace.root,
        )

    def _load_bound_source_discovery(self, spec: TargetAdaptJobSpec):  # type: ignore[no-untyped-def]
        binding = spec.source_discovery
        if binding is None:
            return None
        if self.source_discovery_artifacts is None:
            raise DeploymentJobStateConflict(
                "SSH Adapt source discovery artifact store is unavailable"
            )
        artifact = self.source_discovery_artifacts.load(binding.job_id)
        execution = artifact.execution
        snapshot = execution.snapshot if execution is not None else None
        if (
            artifact.canonical_sha256() != binding.artifact_sha256
            or artifact.command_sha256 != binding.command_sha256
            or artifact.target_id != binding.target_id
            or artifact.target_registration_sha256 != binding.target_registration_sha256
            or artifact.status != TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED
            or execution is None
            or execution.execution_status != TargetExecutionStatus.SUCCEEDED
            or snapshot is None
            or snapshot.status == DiscoveryStatus.UNAVAILABLE
            or snapshot.target_id != binding.target_id
            or snapshot.robot_id != binding.target_id
            or snapshot.workspace_id != binding.workspace_id
            or snapshot.workspace_sha256 != binding.workspace_sha256
            or snapshot.request_sha256 != binding.request_sha256
            or snapshot.summary_sha256 != binding.summary_sha256
            or [project.root for project in snapshot.projects] != binding.scan_roots
        ):
            raise DeploymentJobStateConflict(
                "SSH Adapt source discovery artifact differs from its frozen binding"
            )
        if datetime.now(timezone.utc) >= binding.expires_at:
            raise DeploymentJobStateConflict("SSH Adapt source discovery binding has expired")
        return snapshot

    def _load_bound_runtime_evidence(self, spec: TargetAdaptJobSpec):  # type: ignore[no-untyped-def]
        binding = spec.runtime_evidence
        if binding is None:
            return None
        if self.runtime_evidence_artifacts is None or self.collector_pins is None:
            raise DeploymentJobStateConflict("SSH Adapt runtime evidence stores are unavailable")
        artifact = self.runtime_evidence_artifacts.load(binding.job_id)
        execution = artifact.execution
        bundle = execution.bundle if execution is not None else None
        pin = self.collector_pins.get(binding.target_id)
        request_sha256 = hashlib.sha256(
            _canonical_json(artifact.evidence_request.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()
        if (
            artifact.canonical_sha256() != binding.artifact_sha256
            or artifact.command_sha256 != binding.command_sha256
            or artifact.target_id != binding.target_id
            or artifact.target_registration_sha256 != binding.target_registration_sha256
            or artifact.status != TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED
            or execution is None
            or execution.execution_status != TargetExecutionStatus.SUCCEEDED
            or bundle is None
            or bundle.collector_id != binding.collector_id
            or bundle.descriptor_sha256 != binding.collector_descriptor_sha256
            or bundle.configuration_sha256 != binding.collector_configuration_sha256
            or bundle.key_id != binding.collector_key_id
            or request_sha256 != binding.evidence_request_sha256
            or bundle.payload_sha256 != binding.bundle_payload_sha256
            or bundle.collected_at != binding.collected_at
        ):
            raise DeploymentJobStateConflict(
                "SSH Adapt runtime evidence artifact differs from its frozen binding"
            )
        if datetime.now(timezone.utc) >= binding.expires_at:
            raise DeploymentJobStateConflict("SSH Adapt runtime evidence binding has expired")
        try:
            probes = verify_target_evidence_v4(
                bundle,
                pin=pin,
                request=artifact.evidence_request,
                deployment_mode=EvidenceDeploymentMode.REMOTE,
            )
        except ValueError as exc:
            raise DeploymentJobStateConflict(
                "SSH Adapt runtime evidence failed re-verification"
            ) from exc
        from rolo.stages.adapt.journey import TargetEvidenceJourneySummary

        summary = TargetEvidenceJourneySummary(
            mode=EvidenceDeploymentMode.REMOTE,
            collector_id=bundle.collector_id,
            target_host_fingerprint=bundle.target_host_fingerprint,
            bundle_payload_sha256=bundle.payload_sha256,
            bundle_path=(
                f"artifact://deployment-jobs/{binding.job_id}/runtime-evidence-result.json"
            ),
            collected_at=bundle.collected_at.isoformat(),
            signature_version="ED25519_V4",
            target_id=bundle.target_id,
            descriptor_sha256=bundle.descriptor_sha256,
            key_id=bundle.key_id,
        )
        return probes, summary

    def _persist_journey(self, job_id: str, result: AdaptJourneyResultLike) -> str:
        path = self._journey_path(job_id)
        serialized = result.model_dump_json(indent=2) + "\n"
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if path.exists():
            if path.is_symlink() or path.read_text(encoding="utf-8") != serialized:
                raise DeploymentJobStateConflict("Adapt Journey artifact already differs")
            return digest
        atomic_write_text(path, serialized, require_absent=True)
        return digest

    def _artifact_from_journey(
        self,
        record: DeploymentJobRecord,
        spec: TargetAdaptJobSpec,
        result: AdaptJourneyResultLike,
    ) -> TargetAdaptJobArtifact:
        if result.robot_id != spec.target_id:
            raise DeploymentJobStateConflict("Adapt Journey target differs from spec")
        digest = self._persist_journey(record.job.job_id, result)
        if result.status == "DISCOVERY_COMPLETE":
            status = TargetAdaptJobArtifactStatus.SUCCEEDED
            failure = None
        elif result.status == "BLOCKED":
            status = TargetAdaptJobArtifactStatus.BLOCKED
            failure = TargetAdaptJobFailureCode.JOURNEY_BLOCKED
        else:
            raise DeploymentJobStateConflict(
                "discovery-only Adapt Job returned an unexpected Journey status"
            )
        return TargetAdaptJobArtifact(
            job_id=record.job.job_id,
            command_sha256=record.job.command_sha256,
            spec_sha256=spec.canonical_sha256(),
            target_id=spec.target_id,
            status=status,
            failure_code=failure,
            journey_status=result.status,
            journey_result_sha256=digest,
            completed_at=datetime.now(timezone.utc),
        )

    def _persist_artifact(self, artifact: TargetAdaptJobArtifact) -> None:
        path = self._artifact_path(artifact.job_id)
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("Adapt Job artifact already differs")
            return
        atomic_write_text(
            path,
            artifact.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetAdaptJobSpec,
        artifact: TargetAdaptJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
        ):
            raise DeploymentJobStateConflict("Adapt Job artifact binding mismatch")
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "adapt-discovery"
            ),
            None,
        )
        if checkpoint is None:
            raise DeploymentJobStateConflict("Adapt Job artifact has no checkpoint")
        refs = [self._artifact_ref(record.job.job_id)]
        if artifact.journey_result_sha256 is not None:
            refs.append(self._journey_ref(record.job.job_id))
        digest = artifact.canonical_sha256()
        if artifact.status == TargetAdaptJobArtifactStatus.SUCCEEDED:
            if checkpoint.status == DeploymentStepStatus.RUNNING:
                self.store.complete_step(
                    record.job.job_id,
                    step_id="adapt-discovery",
                    outcome_sha256=digest,
                    artifact_refs=refs,
                )
            elif checkpoint.status != DeploymentStepStatus.COMPLETE:
                raise DeploymentJobStateConflict("Adapt artifact conflicts with checkpoint")
            return self.store.complete_job(record.job.job_id, artifact_refs=refs)
        if artifact.status == TargetAdaptJobArtifactStatus.BLOCKED:
            if record.job.state == DeploymentJobState.BLOCKED:
                return record
            return self.store.block_step(
                record.job.job_id,
                step_id="adapt-discovery",
                blocker_codes=["ADAPT_JOURNEY_BLOCKED"],
                outcome_sha256=digest,
                artifact_refs=refs,
            )
        if record.job.state == DeploymentJobState.FAILED:
            return record
        return self.store.fail_step(
            record.job.job_id,
            step_id="adapt-discovery",
            remote_state_known=True,
            outcome_sha256=digest,
            artifact_refs=refs,
        )

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.ADAPT:
            raise DeploymentJobStateConflict("Adapt Job handler received another command")
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
            raise DeploymentJobStateConflict("Adapt Job spec digest mismatch")
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            artifact = self._load_artifact(job_id)
            if artifact is not None:
                return self._finish(record, spec, artifact)
            journey = self._load_journey(job_id)
            if journey is not None:
                artifact = self._artifact_from_journey(record, spec, journey)
                self._persist_artifact(artifact)
                return self._finish(record, spec, artifact)
            running = any(
                item.attempt == record.attempt
                and item.step_id == "adapt-discovery"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "Adapt execution checkpoint requires reconciliation"
                )
            registration = self.registrations.load(spec.target_id)
            registration_sha256 = target_connection_binding_sha256(
                registration.target, registration.connection
            )
            record = self.store.start_step(
                job_id,
                step_id="adapt-discovery",
                state=DeploymentJobState.DISCOVERING,
                remote=False,
            )
            if registration_sha256 != spec.target_registration_sha256:
                artifact = TargetAdaptJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    status=TargetAdaptJobArtifactStatus.FAILED,
                    failure_code=TargetAdaptJobFailureCode.TARGET_REGISTRATION_CHANGED,
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                result = self._execute(spec, record.job.command)
                artifact = self._artifact_from_journey(record, spec, result)
            self._persist_artifact(artifact)
            return self._finish(record, spec, artifact)
