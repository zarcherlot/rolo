from __future__ import annotations

import hashlib
import json
import re
import threading
from base64 import b64decode, b64encode
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.bootstrap_execution import (
    TargetBootstrapDeploymentResult,
    TargetBootstrapOperator,
)
from rolo.targets.credentials import CredentialResolver, FileCredentialProvider
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationKeyPin,
    build_deployment_authorization_key_pin,
)
from rolo.targets.deployment_jobs import (
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
)
from rolo.targets.executor import (
    TargetExecutionStatus,
    TargetExecutor,
    TargetExecutorKind,
)
from rolo.targets.models import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
    TargetProfile,
)
from rolo.targets.package_installer import load_target_package, verify_target_package
from rolo.targets.package_registry import TargetPackageRegistry
from rolo.targets.package_signing import (
    Ed25519TargetPackageVerifier,
    ed25519_public_key_sha256,
)
from rolo.targets.package_transfer import TargetPackageUploadError
from rolo.targets.platform_detector import target_executor_for_profile
from rolo.targets.registration import (
    TargetRegistrationRequest,
    TargetRegistrationService,
    target_connection_binding_sha256,
)

_SHA256 = r"^[0-9a-f]{64}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class TargetBootstrapJobSpec(BaseModel):
    """Secret-free immutable Controller inputs for one approved Bootstrap Job."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-job-spec/v1"] = (
        "rolo-target-bootstrap-job-spec/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    target_registration_sha256: str = Field(pattern=_SHA256)
    workspace_root: str = Field(min_length=1, max_length=4096)
    package_root: str = Field(min_length=1, max_length=4096)
    package_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    manifest_sha256: str = Field(pattern=_SHA256)
    release_signing_key_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
    )
    release_signing_public_key_base64: str = Field(max_length=32_768)
    release_signing_public_key_sha256: str = Field(pattern=_SHA256)
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    approval_action: Literal[
        ApprovalAction.INSTALL_TARGET_RUNTIME,
        ApprovalAction.UPGRADE_TARGET_RUNTIME,
    ]
    approver_principal: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
    )
    approval_expires_at: datetime
    expect_current_present: bool | None = None
    expected_current_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )
    authorization_key_pin: DeploymentAuthorizationKeyPin | None = None
    expected_authorization_key_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )
    timeout_s: float = Field(default=300.0, ge=10.0, le=1800.0)

    @field_validator("package_root")
    @classmethod
    def validate_package_root(cls, value: str) -> str:
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise ValueError("bootstrap package root contains control characters")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("bootstrap package root must be a Controller absolute path")
        return str(path.absolute())

    @field_validator("release_signing_public_key_base64")
    @classmethod
    def validate_release_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("bootstrap release public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("bootstrap release public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def bind_spec(self) -> TargetBootstrapJobSpec:
        if self.approval_expires_at.tzinfo is None:
            raise ValueError("bootstrap approval expiry must be timezone-aware")
        if (
            ed25519_public_key_sha256(self.release_public_key_bytes())
            != self.release_signing_public_key_sha256
        ):
            raise ValueError("bootstrap release public key digest mismatch")
        expected_action = (
            ApprovalAction.UPGRADE_TARGET_RUNTIME
            if self.expect_current_present is True
            or self.expected_current_manifest_sha256 is not None
            else ApprovalAction.INSTALL_TARGET_RUNTIME
        )
        if self.approval_action != expected_action:
            raise ValueError("bootstrap approval action does not match install CAS")
        if self.authorization_key_pin is None:
            if self.expected_authorization_key_sha256 is not None:
                raise ValueError("bootstrap authorization-key CAS requires a pin")
        elif (
            self.authorization_key_pin.target_id != self.target_id
            or self.authorization_key_pin.installed_by_approval_id != self.approval_id
        ):
            raise ValueError("bootstrap authorization-key pin binding mismatch")
        return self

    def release_public_key_bytes(self) -> bytes:
        return b64decode(self.release_signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetBootstrapJobSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-job-submission-result/v1"] = (
        "rolo-target-bootstrap-job-submission-result/v1"
    )
    job: DeploymentJobRecord
    spec: TargetBootstrapJobSpec
    approval: ApprovalRequest


class TargetBootstrapJobSubmission(BaseModel):
    """Strict public request; package bytes are addressed only through the registry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-job-submission/v1"] = (
        "rolo-target-bootstrap-job-submission/v1"
    )
    package_ref: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}@[0-9a-f]{64}$"
    )
    approver_principal: str = Field(pattern=_PRINCIPAL)
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    expect_current_present: bool | None = False
    expected_current_manifest_sha256: str | None = Field(default=None, pattern=_SHA256)
    install_authorization_key: bool = True
    expected_authorization_key_sha256: str | None = Field(default=None, pattern=_SHA256)
    timeout_s: float = Field(default=300.0, ge=10.0, le=1800.0)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()

    @model_validator(mode="after")
    def bind_compare_and_swap(self) -> TargetBootstrapJobSubmission:
        if self.expect_current_present is False and self.expected_current_manifest_sha256:
            raise ValueError("absent runtime expectation cannot include a current manifest")
        if not self.install_authorization_key and self.expected_authorization_key_sha256:
            raise ValueError("authorization-key CAS requires key installation")
        return self


class TargetBootstrapJobSubmissionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-job-submission-intent/v1"] = (
        "rolo-target-bootstrap-job-submission-intent/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    requested_by: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"
    )
    submission_sha256: str = Field(pattern=_SHA256)
    spec: TargetBootstrapJobSpec


class TargetBootstrapJobSubmissionIntentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("bootstrap submission intent root cannot be a symbolic link")

    def _path(self, target_id: str, idempotency_key: str) -> Path:
        identity = hashlib.sha256(f"{target_id}:{idempotency_key}".encode()).hexdigest()
        return self.root / f"intent-{identity}.json"

    def lock_target(self, target_id: str, idempotency_key: str) -> Path:
        return self._path(target_id, idempotency_key)

    def load(self, target_id: str, idempotency_key: str) -> TargetBootstrapJobSubmissionIntent:
        path = self._path(target_id, idempotency_key)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
            raise FileNotFoundError(path)
        return TargetBootstrapJobSubmissionIntent.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def persist(
        self,
        intent: TargetBootstrapJobSubmissionIntent,
        *,
        acquire_lock: bool = True,
    ) -> TargetBootstrapJobSubmissionIntent:
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
                    "bootstrap submission intent already differs"
                ) from None
            return current
        return intent


class TargetBootstrapJobSpecStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("bootstrap Job spec root cannot be a symbolic link")

    def _path(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid Bootstrap Job ID")
        return self.root / job_id / "bootstrap-spec.json"

    def load(self, job_id: str) -> TargetBootstrapJobSpec:
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
            raise ValueError("bootstrap Job spec is unavailable")
        return TargetBootstrapJobSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def persist(self, job_id: str, spec: TargetBootstrapJobSpec) -> TargetBootstrapJobSpec:
        path = self._path(job_id)
        if path.exists():
            current = self.load(job_id)
            if current != spec:
                raise DeploymentJobStateConflict("bootstrap Job spec already differs")
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
                    "bootstrap Job spec already differs"
                ) from None
            return current
        return spec


def build_target_bootstrap_job_spec(
    registration: TargetRegistrationRequest,
    *,
    package_root: Path,
    approval_id: str,
    approver_principal: str,
    approval_expires_at: datetime,
    authorization_key_pin: DeploymentAuthorizationKeyPin | None = None,
    expected_authorization_key_sha256: str | None = None,
    expect_current_present: bool | None = None,
    expected_current_manifest_sha256: str | None = None,
    timeout_s: float = 300.0,
) -> TargetBootstrapJobSpec:
    profile = registration.target
    if (
        profile.release_signing_key_id is None
        or profile.release_signing_public_key_path is None
        or profile.release_signing_public_key_sha256 is None
    ):
        raise ValueError("TargetProfile requires a complete release-signing key pin")
    public_key_path = Path(profile.release_signing_public_key_path).expanduser().absolute()
    if (
        public_key_path.is_symlink()
        or not public_key_path.is_file()
        or public_key_path.stat().st_size > 16 * 1024
    ):
        raise ValueError("release-signing public key pin path is unavailable")
    public_key = public_key_path.read_bytes()
    if ed25519_public_key_sha256(public_key) != profile.release_signing_public_key_sha256:
        raise ValueError("release-signing public key pin digest mismatch")
    verifier = Ed25519TargetPackageVerifier({profile.release_signing_key_id: public_key})
    root, manifest, signature = load_target_package(package_root)
    if signature.key_id != profile.release_signing_key_id:
        raise ValueError("target package signing key differs from TargetProfile pin")
    verify_target_package(root, manifest, signature, verifier)
    return TargetBootstrapJobSpec(
        target_id=profile.target_id,
        target_registration_sha256=target_connection_binding_sha256(
            profile,
            registration.connection,
        ),
        workspace_root=profile.workspace_root,
        package_root=str(root),
        package_id=manifest.package_id,
        manifest_sha256=manifest.canonical_sha256(),
        release_signing_key_id=profile.release_signing_key_id,
        release_signing_public_key_base64=b64encode(public_key).decode("ascii"),
        release_signing_public_key_sha256=profile.release_signing_public_key_sha256,
        approval_id=approval_id,
        approval_action=(
            ApprovalAction.UPGRADE_TARGET_RUNTIME
            if expect_current_present is True
            or expected_current_manifest_sha256 is not None
            else ApprovalAction.INSTALL_TARGET_RUNTIME
        ),
        approver_principal=approver_principal,
        approval_expires_at=approval_expires_at,
        expect_current_present=expect_current_present,
        expected_current_manifest_sha256=expected_current_manifest_sha256,
        authorization_key_pin=authorization_key_pin,
        expected_authorization_key_sha256=expected_authorization_key_sha256,
        timeout_s=timeout_s,
    )


class TargetBootstrapJobSubmissionService:
    def __init__(self, store: DeploymentJobStore, specs: TargetBootstrapJobSpecStore) -> None:
        self.store = store
        self.specs = specs

    def submit(
        self,
        spec: TargetBootstrapJobSpec,
        *,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetBootstrapJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        command = DeploymentCommand(
            command=DeploymentCommandKind.BOOTSTRAP,
            target_id=spec.target_id,
            workspace_root=spec.workspace_root,
            active_probe="runtime-readonly",
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
                    summary="Install the exact verified target runtime and authorization pin.",
                    expires_at=spec.approval_expires_at,
                    authorization_scope_sha256=spec.canonical_sha256(),
                    now=observed_at,
                    approval_id=spec.approval_id,
                )
            except FileExistsError:
                approval = self.store.load_approval_request(spec.approval_id)
        if (
            approval.job_id != record.job.job_id
            or approval.command_sha256 != record.job.command_sha256
            or approval.authorization_scope_sha256 != spec.canonical_sha256()
            or approval.action != spec.approval_action
            or approval.approver_principal != spec.approver_principal
        ):
            raise DeploymentJobStateConflict("bootstrap Job approval already differs")
        return TargetBootstrapJobSubmissionResult(
            job=self.store.load_job(record.job.job_id),
            spec=spec,
            approval=approval,
        )


class TargetBootstrapPublicSubmissionService:
    """Resolve a package ref and freeze a retry-stable approved Bootstrap spec."""

    def __init__(
        self,
        *,
        store: DeploymentJobStore,
        specs: TargetBootstrapJobSpecStore,
        intents: TargetBootstrapJobSubmissionIntentStore,
        registrations: TargetRegistrationService,
        packages: TargetPackageRegistry,
        authorization_key_id: str | None,
        authorization_public_key_path: Path | None,
    ) -> None:
        self.submissions = TargetBootstrapJobSubmissionService(store, specs)
        self.intents = intents
        self.registrations = registrations
        self.packages = packages
        self.authorization_key_id = authorization_key_id
        self.authorization_public_key_path = authorization_public_key_path

    @staticmethod
    def _validate_intent(
        intent: TargetBootstrapJobSubmissionIntent,
        *,
        submission: TargetBootstrapJobSubmission,
        requested_by: str,
    ) -> None:
        if (
            intent.requested_by != requested_by
            or intent.submission_sha256 != submission.canonical_sha256()
        ):
            raise DeploymentJobStateConflict(
                "bootstrap idempotency key belongs to a different submission"
            )

    def submit(
        self,
        *,
        target_id: str,
        submission: TargetBootstrapJobSubmission,
        requested_by: str,
        interaction_surface: InteractionSurface,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetBootstrapJobSubmissionResult:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("bootstrap submission timestamp must be timezone-aware")
        with interprocess_lock(self.intents.lock_target(target_id, idempotency_key)):
            try:
                intent = self.intents.load(target_id, idempotency_key)
            except FileNotFoundError:
                registration = self.registrations.load(target_id)
                entry = self.packages.resolve(
                    submission.package_ref,
                    profile=registration.target,
                )
                approval_id = "approval-" + hashlib.sha256(
                    f"bootstrap:{target_id}:{idempotency_key}:{requested_by}".encode()
                ).hexdigest()[:32]
                authorization_pin = None
                if submission.install_authorization_key:
                    if (
                        self.authorization_key_id is None
                        or self.authorization_public_key_path is None
                    ):
                        raise ValueError(
                            "Controller deployment authorization public key is not configured"
                        ) from None
                    authorization_pin = build_deployment_authorization_key_pin(
                        target_id=target_id,
                        key_id=self.authorization_key_id,
                        public_key_path=self.authorization_public_key_path,
                        approval_id=approval_id,
                        installed_at=observed_at,
                    )
                spec = build_target_bootstrap_job_spec(
                    registration,
                    package_root=Path(entry.package_root),
                    approval_id=approval_id,
                    approver_principal=submission.approver_principal,
                    approval_expires_at=observed_at
                    + timedelta(seconds=submission.approval_ttl_s),
                    authorization_key_pin=authorization_pin,
                    expected_authorization_key_sha256=(
                        submission.expected_authorization_key_sha256
                    ),
                    expect_current_present=submission.expect_current_present,
                    expected_current_manifest_sha256=(
                        submission.expected_current_manifest_sha256
                    ),
                    timeout_s=submission.timeout_s,
                )
                intent = self.intents.persist(
                    TargetBootstrapJobSubmissionIntent(
                        target_id=target_id,
                        requested_by=requested_by,
                        idempotency_key=idempotency_key,
                        submission_sha256=submission.canonical_sha256(),
                        spec=spec,
                    ),
                    acquire_lock=False,
                )
            else:
                self._validate_intent(
                    intent,
                    submission=submission,
                    requested_by=requested_by,
                )
            return self.submissions.submit(
                intent.spec,
                requested_by=requested_by,
                interaction_surface=interaction_surface,
                idempotency_key=idempotency_key,
                now=observed_at,
            )


class TargetBootstrapJobArtifactStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetBootstrapJobFailureCode(str, Enum):
    TARGET_REGISTRATION_CHANGED = "TARGET_REGISTRATION_CHANGED"
    PACKAGE_INVALID = "PACKAGE_INVALID"
    RUNNER_ERROR = "RUNNER_ERROR"


class TargetBootstrapJobArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-job-artifact/v1"] = (
        "rolo-target-bootstrap-job-artifact/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command_sha256: str = Field(pattern=_SHA256)
    spec_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    status: TargetBootstrapJobArtifactStatus
    failure_code: TargetBootstrapJobFailureCode | None = None
    deployment: TargetBootstrapDeploymentResult | None = None
    completed_at: datetime

    @model_validator(mode="after")
    def bind_outcome(self) -> TargetBootstrapJobArtifact:
        if self.completed_at.tzinfo is None:
            raise ValueError("bootstrap Job artifact timestamp must be timezone-aware")
        if self.deployment is None:
            if self.status != TargetBootstrapJobArtifactStatus.FAILED or self.failure_code is None:
                raise ValueError("bootstrap Job failure artifact is incomplete")
        else:
            expected = (
                TargetBootstrapJobArtifactStatus.SUCCEEDED
                if self.deployment.execution.status == TargetExecutionStatus.SUCCEEDED
                else TargetBootstrapJobArtifactStatus.FAILED
            )
            if self.status != expected or self.failure_code is not None:
                raise ValueError("bootstrap Job deployment status mismatch")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetBootstrapJobRunner:
    def __init__(
        self,
        store: DeploymentJobStore,
        registrations: TargetRegistrationService,
        specs: TargetBootstrapJobSpecStore,
        artifact_root: Path,
        *,
        executor_factory: Callable[[TargetProfile], TargetExecutor] | None = None,
    ) -> None:
        self.store = store
        self.registrations = registrations
        self.specs = specs
        self.artifact_root = artifact_root.expanduser().absolute()
        if self.artifact_root.is_symlink():
            raise ValueError("bootstrap Job artifact root cannot be a symbolic link")
        self._executor_factory = executor_factory

    def _executor(self, profile: TargetProfile) -> TargetExecutor:
        if self._executor_factory is not None:
            return self._executor_factory(profile)
        return target_executor_for_profile(
            profile,
            registry=self.registrations.registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
        )

    def _path(self, job_id: str) -> Path:
        return self.artifact_root / job_id / "bootstrap-result.json"

    @staticmethod
    def _ref(job_id: str) -> str:
        return f"artifact://deployment-jobs/{job_id}/bootstrap-result.json"

    def _load_artifact(self, job_id: str) -> TargetBootstrapJobArtifact | None:
        path = self._path(job_id)
        if path.is_symlink():
            raise ValueError("bootstrap Job artifact cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("bootstrap Job artifact is invalid")
        return TargetBootstrapJobArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    def _persist(self, artifact: TargetBootstrapJobArtifact) -> None:
        path = self._path(artifact.job_id)
        current = self._load_artifact(artifact.job_id)
        if current is not None:
            if current != artifact:
                raise DeploymentJobStateConflict("bootstrap Job artifact already differs")
            return
        atomic_write_text(path, artifact.model_dump_json(indent=2) + "\n", require_absent=True)

    def _finish(
        self,
        record: DeploymentJobRecord,
        spec: TargetBootstrapJobSpec,
        artifact: TargetBootstrapJobArtifact,
    ) -> DeploymentJobRecord:
        if (
            artifact.job_id != record.job.job_id
            or artifact.command_sha256 != record.job.command_sha256
            or artifact.spec_sha256 != spec.canonical_sha256()
            or artifact.target_id != spec.target_id
        ):
            raise DeploymentJobStateConflict("bootstrap Job artifact binding mismatch")
        if artifact.deployment is not None:
            execution = artifact.deployment.execution
            expected_authorization_pin_sha256 = (
                spec.authorization_key_pin.canonical_sha256()
                if spec.authorization_key_pin is not None
                else None
            )
            if (
                artifact.deployment.target_id != spec.target_id
                or execution.package_id != spec.package_id
                or execution.manifest_sha256 != spec.manifest_sha256
                or artifact.deployment.signing_key_id != spec.release_signing_key_id
                or artifact.deployment.signing_public_key_sha256
                != spec.release_signing_public_key_sha256
                or execution.authorization_key_pin_sha256
                != expected_authorization_pin_sha256
            ):
                raise DeploymentJobStateConflict(
                    "bootstrap Job deployment artifact differs from spec"
                )
        checkpoint = next(
            (
                item
                for item in record.checkpoints
                if item.attempt == record.attempt and item.step_id == "bootstrap-runtime"
            ),
            None,
        )
        ref = self._ref(record.job.job_id)
        digest = artifact.canonical_sha256()
        if artifact.status == TargetBootstrapJobArtifactStatus.FAILED:
            if checkpoint is not None and checkpoint.status in {
                DeploymentStepStatus.FAILED,
                DeploymentStepStatus.UNKNOWN,
            }:
                return record
            remote_known = artifact.deployment is None or (
                artifact.deployment.execution.transport_error_code is None
                or artifact.deployment.execution.executor_kind == TargetExecutorKind.LOCAL
            )
            return self.store.fail_step(
                record.job.job_id,
                step_id="bootstrap-runtime",
                remote_state_known=remote_known,
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        if checkpoint is None:
            raise DeploymentJobStateConflict("bootstrap Job artifact has no checkpoint")
        if checkpoint.status == DeploymentStepStatus.RUNNING:
            self.store.complete_step(
                record.job.job_id,
                step_id="bootstrap-runtime",
                outcome_sha256=digest,
                artifact_refs=[ref],
            )
        elif checkpoint.status != DeploymentStepStatus.COMPLETE:
            raise DeploymentJobStateConflict("bootstrap artifact conflicts with checkpoint")
        return self.store.complete_job(record.job.job_id, artifact_refs=[ref])

    def run(
        self,
        job_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DeploymentJobRecord:
        record = self.store.load_job(job_id)
        if record.job.command.command != DeploymentCommandKind.BOOTSTRAP:
            raise DeploymentJobStateConflict("Bootstrap Job handler received another command")
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
            raise DeploymentJobStateConflict("Bootstrap Job spec digest mismatch")
        approval = self.store.load_approval_request(spec.approval_id)
        if approval.authorization_scope_sha256 != spec.canonical_sha256():
            raise DeploymentJobStateConflict("Bootstrap approval scope mismatch")
        with self.store.target_lease(spec.target_id):
            record = self.store.load_job(job_id)
            if record.cancel_requested:
                return self.store.resolve_cancel(
                    job_id,
                    remote_termination_confirmed=True,
                )
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
            registration_sha256 = target_connection_binding_sha256(
                registration.target,
                registration.connection,
            )
            running = any(
                item.attempt == record.attempt
                and item.step_id == "bootstrap-runtime"
                and item.status == DeploymentStepStatus.RUNNING
                for item in record.checkpoints
            )
            if running:
                raise DeploymentJobStateConflict(
                    "Bootstrap remote checkpoint requires reconciliation"
                )
            if registration_sha256 != spec.target_registration_sha256:
                record = self.store.start_step(
                    job_id,
                    step_id="bootstrap-runtime",
                    state=DeploymentJobState.BOOTSTRAPPING,
                    remote=False,
                )
                artifact = TargetBootstrapJobArtifact(
                    job_id=job_id,
                    command_sha256=record.job.command_sha256,
                    spec_sha256=spec.canonical_sha256(),
                    target_id=spec.target_id,
                    status=TargetBootstrapJobArtifactStatus.FAILED,
                    failure_code=TargetBootstrapJobFailureCode.TARGET_REGISTRATION_CHANGED,
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                try:
                    package_root, manifest, signature = load_target_package(
                        Path(spec.package_root)
                    )
                    verifier = Ed25519TargetPackageVerifier(
                        {
                            spec.release_signing_key_id: (
                                spec.release_public_key_bytes()
                            )
                        }
                    )
                    verify_target_package(
                        package_root,
                        manifest,
                        signature,
                        verifier,
                    )
                    if (
                        manifest.package_id != spec.package_id
                        or manifest.canonical_sha256() != spec.manifest_sha256
                    ):
                        raise ValueError("Bootstrap package changed after submission")
                    operator = TargetBootstrapOperator(
                        self._executor(registration.target),
                        signing_key_id=spec.release_signing_key_id,
                        signing_public_key=spec.release_public_key_bytes(),
                    )
                except (OSError, ValueError):
                    record = self.store.start_step(
                        job_id,
                        step_id="bootstrap-runtime",
                        state=DeploymentJobState.BOOTSTRAPPING,
                        remote=False,
                    )
                    artifact = TargetBootstrapJobArtifact(
                        job_id=job_id,
                        command_sha256=record.job.command_sha256,
                        spec_sha256=spec.canonical_sha256(),
                        target_id=spec.target_id,
                        status=TargetBootstrapJobArtifactStatus.FAILED,
                        failure_code=TargetBootstrapJobFailureCode.RUNNER_ERROR,
                        completed_at=datetime.now(timezone.utc),
                    )
                else:
                    record = self.store.start_step(
                        job_id,
                        step_id="bootstrap-runtime",
                        state=DeploymentJobState.BOOTSTRAPPING,
                        remote=True,
                    )
                    try:
                        deployment = operator.install_and_activate(
                            package_root,
                            target_id=spec.target_id,
                            request_id=f"bootstrap-{job_id.removeprefix('deployment-')}",
                            approval_id=spec.approval_id,
                            expect_current_present=spec.expect_current_present,
                            expected_current_manifest_sha256=(
                                spec.expected_current_manifest_sha256
                            ),
                            authorization_key_pin=spec.authorization_key_pin,
                            expected_authorization_key_sha256=(
                                spec.expected_authorization_key_sha256
                            ),
                            timeout_s=spec.timeout_s,
                            cancel_event=cancel_event,
                        )
                    except TargetPackageUploadError:
                        artifact = TargetBootstrapJobArtifact(
                            job_id=job_id,
                            command_sha256=record.job.command_sha256,
                            spec_sha256=spec.canonical_sha256(),
                            target_id=spec.target_id,
                            status=TargetBootstrapJobArtifactStatus.FAILED,
                            failure_code=TargetBootstrapJobFailureCode.PACKAGE_INVALID,
                            completed_at=datetime.now(timezone.utc),
                        )
                    else:
                        artifact = TargetBootstrapJobArtifact(
                            job_id=job_id,
                            command_sha256=record.job.command_sha256,
                            spec_sha256=spec.canonical_sha256(),
                            target_id=spec.target_id,
                            status=(
                                TargetBootstrapJobArtifactStatus.SUCCEEDED
                                if deployment.execution.status
                                == TargetExecutionStatus.SUCCEEDED
                                else TargetBootstrapJobArtifactStatus.FAILED
                            ),
                            deployment=deployment,
                            completed_at=datetime.now(timezone.utc),
                        )
            self._persist(artifact)
            return self._finish(record, spec, artifact)
