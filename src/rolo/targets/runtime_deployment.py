from __future__ import annotations

import hashlib
import hmac
import json
import re
import stat
from base64 import b64decode, b64encode
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.adapter_runner import AdapterRunner, BoundedAdapterRunner
from rolo.adapter_runtime import adapter_command
from rolo.runtime_context import AdapterRuntimeContext
from rolo.stages.adapt.models import AdapterBundleManifest, AdapterReleaseManifest
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.enrollment import CollectorEnrollmentPinV4, TargetEnrollmentService
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)
from rolo.targets.package_signing import ed25519_public_key_sha256

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SIGNATURE_PATTERN = r"^[A-Za-z0-9+/]{86}==$"
_APPROVAL_PATTERN = r"^approval-[0-9a-f]{32}$"
_MAX_WORKSPACE_FILES = 4096
_MAX_WORKSPACE_FILE_BYTES = 64 * 1024 * 1024
_MAX_WORKSPACE_TOTAL_BYTES = 512 * 1024 * 1024
_RUNTIME_PATH_KEYS = {
    "AMENT_PREFIX_PATH",
    "CMAKE_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
    "DYLD_LIBRARY_PATH",
    "LD_LIBRARY_PATH",
    "PATH",
    "PYTHONPATH",
}
_RUNTIME_FILE_KEYS = {"FASTRTPS_DEFAULT_PROFILES_FILE"}
_RUNTIME_SCALAR_KEYS = {
    "CYCLONEDDS_URI",
    "ROS_AUTOMATIC_DISCOVERY_RANGE",
    "ROS_DISCOVERY_SERVER",
    "ROS_DISTRO",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "ROS_STATIC_PEERS",
    "ROS_VERSION",
    "RMW_IMPLEMENTATION",
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _target_absolute_path(value: str) -> str:
    if not value or len(value) > 4096:
        raise ValueError("target path is empty or too long")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("target path contains control characters")
    if PurePosixPath(value).is_absolute():
        return str(PurePosixPath(value))
    if re.fullmatch(r"[A-Za-z]:[\\/].+", value):
        return value.replace("\\", "/")
    raise ValueError("target path must be absolute")


def _workspace_relative_path(value: str) -> str:
    if not value or len(value) > 4096:
        raise ValueError("workspace path is empty or too long")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or "." in path.parts or ".." in path.parts:
        raise ValueError("workspace path must be normalized and relative")
    if any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
        raise ValueError("workspace path contains forbidden characters")
    return str(path)


class TargetWorkspaceRef(BaseModel):
    """A controller-safe reference to a workspace that exists on one target."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-workspace-ref/v1"] = (
        "rolo-target-workspace-ref/v1"
    )
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    root: str = Field(min_length=1, max_length=4096)

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        return _target_absolute_path(value)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetWorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    size_bytes: int = Field(ge=0, le=_MAX_WORKSPACE_FILE_BYTES)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    executable: bool = False
    role: Literal["SOURCE", "ARTIFACT", "RUNTIME"] = "SOURCE"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _workspace_relative_path(value)


class TargetWorkspaceManifest(BaseModel):
    """Bounded target-observed file set; timestamps are excluded from its digest."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-workspace-manifest/v1"] = (
        "rolo-target-workspace-manifest/v1"
    )
    workspace: TargetWorkspaceRef
    files: list[TargetWorkspaceFile] = Field(
        min_length=1,
        max_length=_MAX_WORKSPACE_FILES,
    )
    total_size_bytes: int = Field(ge=0, le=_MAX_WORKSPACE_TOTAL_BYTES)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    observed_at: datetime

    @model_validator(mode="after")
    def require_canonical_manifest(self) -> TargetWorkspaceManifest:
        paths = [item.path for item in self.files]
        if paths != sorted(set(paths)):
            raise ValueError("target workspace files must be unique and sorted")
        if sum(item.size_bytes for item in self.files) != self.total_size_bytes:
            raise ValueError("target workspace total size mismatch")
        if not hmac.compare_digest(self.content_sha256, self.compute_content_sha256()):
            raise ValueError("target workspace content digest mismatch")
        return self

    def digest_payload(self) -> dict[str, object]:
        return {
            "workspace": self.workspace.model_dump(mode="json"),
            "files": [item.model_dump(mode="json") for item in self.files],
            "total_size_bytes": self.total_size_bytes,
        }

    def compute_content_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.digest_payload())).hexdigest()


def observe_target_workspace(
    workspace: TargetWorkspaceRef,
    *,
    selected_paths: Iterable[str],
    roles_by_path: Mapping[str, Literal["SOURCE", "ARTIFACT", "RUNTIME"]] | None = None,
    observed_at: datetime | None = None,
) -> TargetWorkspaceManifest:
    """Build a manifest on the target; never call this for an SSH path on a controller."""

    root = Path(workspace.root)
    try:
        root_lstat = root.lstat()
    except OSError as exc:
        raise ValueError("target workspace root is unavailable") from exc
    if stat.S_ISLNK(root_lstat.st_mode) or not stat.S_ISDIR(root_lstat.st_mode):
        raise ValueError("target workspace root must be a real directory")
    resolved_root = root.resolve(strict=True)
    normalized = sorted({_workspace_relative_path(value) for value in selected_paths})
    normalized_roles = {
        _workspace_relative_path(path): role for path, role in (roles_by_path or {}).items()
    }
    if set(normalized_roles) - set(normalized):
        raise ValueError("target workspace roles contain paths outside the selection")
    if not normalized:
        raise ValueError("target workspace selection is empty")
    if len(normalized) > _MAX_WORKSPACE_FILES:
        raise ValueError("target workspace selection exceeds the file-count limit")
    files: list[TargetWorkspaceFile] = []
    total = 0
    for relative in normalized:
        candidate = root / Path(relative)
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise ValueError(f"target workspace file is unavailable: {relative}") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"target workspace selection is not a regular file: {relative}")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"target workspace file escapes its root: {relative}") from exc
        if metadata.st_size > _MAX_WORKSPACE_FILE_BYTES:
            raise ValueError(f"target workspace file exceeds its size limit: {relative}")
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        total += metadata.st_size
        if total > _MAX_WORKSPACE_TOTAL_BYTES:
            raise ValueError("target workspace selection exceeds its total size limit")
        files.append(
            TargetWorkspaceFile(
                path=relative,
                size_bytes=metadata.st_size,
                sha256=digest.hexdigest(),
                executable=bool(metadata.st_mode & stat.S_IXUSR),
                role=normalized_roles.get(relative, "SOURCE"),
            )
        )
    payload = {
        "workspace": workspace.model_dump(mode="json"),
        "files": [item.model_dump(mode="json") for item in files],
        "total_size_bytes": total,
    }
    return TargetWorkspaceManifest(
        workspace=workspace,
        files=files,
        total_size_bytes=total,
        content_sha256=hashlib.sha256(_canonical_json(payload)).hexdigest(),
        observed_at=observed_at or datetime.now(timezone.utc),
    )


class TargetProjectEvidenceKind(str, Enum):
    BUILD_METADATA = "BUILD_METADATA"
    RUNTIME_METADATA = "RUNTIME_METADATA"
    SOURCE_ENTRYPOINT = "SOURCE_ENTRYPOINT"
    ROS_METADATA = "ROS_METADATA"
    DOCUMENTATION = "DOCUMENTATION"


class TargetProjectEvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    kind: TargetProjectEvidenceKind
    role: Literal["SOURCE", "ARTIFACT", "RUNTIME"] = "SOURCE"
    required: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _workspace_relative_path(value)


class TargetProjectEvidenceRequest(BaseModel):
    """Explicit, bounded target-side project evidence detection request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-request/v1"] = (
        "rolo-target-project-evidence-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace: TargetWorkspaceRef
    candidates: list[TargetProjectEvidenceCandidate] = Field(
        min_length=1,
        max_length=256,
    )
    approval_id: str = Field(pattern=_APPROVAL_PATTERN)
    authorization: DeploymentAuthorizationProof | None = None
    timeout_s: float = Field(default=60.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def require_canonical_candidates(self) -> TargetProjectEvidenceRequest:
        paths = [candidate.path for candidate in self.candidates]
        if paths != sorted(set(paths)):
            raise ValueError("target project evidence candidates must be unique and sorted")
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.workspace.target_id,
            expected_approval_id=self.approval_id,
        )
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetProjectEvidenceHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    kind: TargetProjectEvidenceKind
    role: Literal["SOURCE", "ARTIFACT", "RUNTIME"]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _workspace_relative_path(value)


class TargetProjectEvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NO_EVIDENCE = "NO_EVIDENCE"


class TargetProjectEvidenceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-snapshot/v1"] = (
        "rolo-target-project-evidence-snapshot/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    status: TargetProjectEvidenceStatus
    hits: list[TargetProjectEvidenceHit] = Field(default_factory=list, max_length=256)
    manifest: TargetWorkspaceManifest | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def require_consistent_evidence(self) -> TargetProjectEvidenceSnapshot:
        if self.status == TargetProjectEvidenceStatus.OBSERVED:
            if self.manifest is None or not self.hits:
                raise ValueError("observed target project evidence is incomplete")
            if (
                self.manifest.workspace.target_id != self.target_id
                or self.manifest.workspace.robot_id != self.robot_id
                or self.manifest.workspace.workspace_id != self.workspace_id
            ):
                raise ValueError("target project evidence manifest identity mismatch")
            hit_paths = [hit.path for hit in self.hits]
            if hit_paths != [item.path for item in self.manifest.files]:
                raise ValueError("target project evidence hits differ from its manifest")
            manifest_roles = {item.path: item.role for item in self.manifest.files}
            if any(manifest_roles[hit.path] != hit.role for hit in self.hits):
                raise ValueError("target project evidence roles differ from its manifest")
        elif self.hits or self.manifest is not None:
            raise ValueError("empty target project evidence cannot contain hits or manifest")
        return self


class TargetProjectEvidenceExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-project-evidence-execution-result/v1"] = (
        "rolo-target-project-evidence-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    snapshot: TargetProjectEvidenceSnapshot | None = None

    @model_validator(mode="after")
    def require_consistent_execution(self) -> TargetProjectEvidenceExecutionResult:
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.snapshot is None:
                raise ValueError("successful target project evidence execution is incomplete")
        elif self.error_code is None or self.snapshot is not None:
            raise ValueError("failed target project evidence execution is inconsistent")
        if self.snapshot is not None and (
            self.snapshot.request_id != self.request_id
            or self.snapshot.request_sha256 != self.request_sha256
            or self.snapshot.target_id != self.target_id
            or self.snapshot.robot_id != self.robot_id
            or self.snapshot.workspace_id != self.workspace_id
        ):
            raise ValueError("target project evidence execution binding mismatch")
        return self


def detect_target_project_evidence(
    request: TargetProjectEvidenceRequest,
    *,
    observed_at: datetime | None = None,
) -> TargetProjectEvidenceSnapshot:
    """Detect only explicitly declared candidate files on the target."""

    workspace = request.workspace
    root = Path(workspace.root)
    selected: list[str] = []
    candidate_by_path: dict[str, TargetProjectEvidenceCandidate] = {}
    for candidate in request.candidates:
        path = root / Path(candidate.path)
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            if candidate.required:
                raise ValueError(
                    f"required target project evidence is unavailable: {candidate.path}"
                ) from None
            continue
        except OSError as exc:
            raise ValueError(
                f"target project evidence cannot be inspected: {candidate.path}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError(
                f"target project evidence is not a regular file: {candidate.path}"
            )
        selected.append(candidate.path)
        candidate_by_path[candidate.path] = candidate

    now = observed_at or datetime.now(timezone.utc)
    if not selected:
        return TargetProjectEvidenceSnapshot(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=workspace.target_id,
            robot_id=workspace.robot_id,
            workspace_id=workspace.workspace_id,
            status=TargetProjectEvidenceStatus.NO_EVIDENCE,
            observed_at=now,
        )
    manifest = observe_target_workspace(
        workspace,
        selected_paths=selected,
        roles_by_path={path: candidate_by_path[path].role for path in selected},
        observed_at=now,
    )
    hits = [
        TargetProjectEvidenceHit(
            path=item.path,
            kind=candidate_by_path[item.path].kind,
            role=item.role,
        )
        for item in manifest.files
    ]
    return TargetProjectEvidenceSnapshot(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=workspace.target_id,
        robot_id=workspace.robot_id,
        workspace_id=workspace.workspace_id,
        status=TargetProjectEvidenceStatus.OBSERVED,
        hits=hits,
        manifest=manifest,
        observed_at=now,
    )


class AdapterSandboxBudget(BaseModel):
    """The same address-space/process controls consumed by BoundedAdapterRunner."""

    model_config = ConfigDict(extra="forbid")

    max_address_space_bytes: int = Field(
        default=4 * 1024 * 1024 * 1024,
        ge=512 * 1024 * 1024,
        le=64 * 1024 * 1024 * 1024,
    )
    max_processes: int = Field(default=128, ge=16, le=512)


class TargetObservedRuntimeEnvironment(BaseModel):
    """Secret-closed environment whose paths are validated only on the target."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cyclonedds_uri: str | None = Field(default=None, alias="CYCLONEDDS_URI")
    ros_automatic_discovery_range: str | None = Field(
        default=None, alias="ROS_AUTOMATIC_DISCOVERY_RANGE"
    )
    ros_discovery_server: str | None = Field(default=None, alias="ROS_DISCOVERY_SERVER")
    ros_distro: str | None = Field(default=None, alias="ROS_DISTRO")
    ros_domain_id: str | None = Field(default=None, alias="ROS_DOMAIN_ID")
    ros_localhost_only: str | None = Field(default=None, alias="ROS_LOCALHOST_ONLY")
    ros_static_peers: str | None = Field(default=None, alias="ROS_STATIC_PEERS")
    ros_version: str | None = Field(default=None, alias="ROS_VERSION")
    rmw_implementation: str | None = Field(default=None, alias="RMW_IMPLEMENTATION")
    fastdds_profiles_file: str | None = Field(
        default=None, alias="FASTRTPS_DEFAULT_PROFILES_FILE"
    )
    ament_prefix_path: str | None = Field(default=None, alias="AMENT_PREFIX_PATH")
    cmake_prefix_path: str | None = Field(default=None, alias="CMAKE_PREFIX_PATH")
    colcon_prefix_path: str | None = Field(default=None, alias="COLCON_PREFIX_PATH")
    dyld_library_path: str | None = Field(default=None, alias="DYLD_LIBRARY_PATH")
    ld_library_path: str | None = Field(default=None, alias="LD_LIBRARY_PATH")
    pythonpath: str | None = Field(default=None, alias="PYTHONPATH")
    executable_path: str | None = Field(default=None, alias="PATH")

    @model_validator(mode="after")
    def validate_target_observed_values(self) -> TargetObservedRuntimeEnvironment:
        values = self.model_dump(by_alias=True, exclude_none=True)
        for name, value in values.items():
            if not value or len(value) > 32_768 or "\x00" in value:
                raise ValueError(f"invalid target runtime environment value: {name}")
            if name != "CYCLONEDDS_URI" and any(c in value for c in ("\r", "\n")):
                raise ValueError(f"target runtime environment contains controls: {name}")
            if name in _RUNTIME_FILE_KEYS:
                _target_absolute_path(value)
            elif name in _RUNTIME_PATH_KEYS:
                # W3/W5's first target runtime is Linux.  Parsing must therefore
                # not depend on the controller's os.pathsep (often ';' on Windows).
                entries = [item for item in value.split(":") if item]
                if not entries or len(entries) > 128 or len(entries) != len(set(entries)):
                    raise ValueError(f"invalid target runtime path list: {name}")
                for entry in entries:
                    _target_absolute_path(entry)
        return self

    def as_environment(self) -> dict[str, str]:
        return self.model_dump(by_alias=True, exclude_none=True)

    def materialize_on_target(self) -> AdapterRuntimeContext:
        """Perform PR #17 availability/canonicalization checks on the target host."""

        return AdapterRuntimeContext.model_validate(self.as_environment())


class LocatedRuntimeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-located-runtime-context/v1"] = (
        "rolo-located-runtime-context/v1"
    )
    target_os: Literal["linux"] = "linux"
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_sha256: str = Field(pattern=_SHA256_PATTERN)
    adapter_entrypoint: str = Field(min_length=1, max_length=4096)
    python_interpreter: str | None = Field(default=None, max_length=4096)
    virtualenv_root: str | None = Field(default=None, max_length=4096)
    editable_roots: list[str] = Field(default_factory=list, max_length=16)
    runtime_environment: TargetObservedRuntimeEnvironment = Field(
        default_factory=TargetObservedRuntimeEnvironment
    )
    sandbox_budget: AdapterSandboxBudget = Field(default_factory=AdapterSandboxBudget)

    @field_validator("adapter_entrypoint", "python_interpreter", "virtualenv_root")
    @classmethod
    def validate_absolute_paths(cls, value: str | None) -> str | None:
        return None if value is None else _target_absolute_path(value)

    @field_validator("editable_roots")
    @classmethod
    def validate_editable_roots(cls, values: list[str]) -> list[str]:
        normalized = [_target_absolute_path(value) for value in values]
        if normalized != sorted(set(normalized)):
            raise ValueError("target editable roots must be unique and sorted")
        return normalized

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetDescribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-describe-request/v1"] = (
        "rolo-target-describe-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)
    sandbox_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    timeout_s: float = Field(default=10.0, ge=1.0, le=30.0)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def require_bounded_lifetime(self) -> TargetDescribeRequest:
        if self.expires_at <= self.issued_at:
            raise ValueError("target describe expiry must follow issue time")
        if (self.expires_at - self.issued_at).total_seconds() > 300:
            raise ValueError("target describe request lifetime exceeds five minutes")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetDescribeOutput(BaseModel):
    """The complete allowlisted stdout object returned by adapter `describe`."""

    model_config = ConfigDict(extra="forbid")

    operations: dict[str, str] = Field(min_length=1, max_length=1024)
    runtime_protocol: Literal["robot-adapter-rpc/v1"] | None = None

    @field_validator("operations")
    @classmethod
    def normalize_operations(cls, value: dict[str, str]) -> dict[str, str]:
        for operation, entrypoint in value.items():
            if not operation or not entrypoint or len(operation) > 256 or len(entrypoint) > 4096:
                raise ValueError("target describe operation binding is invalid")
            if any(c in operation + entrypoint for c in ("\x00", "\r", "\n")):
                raise ValueError("target describe operation binding contains controls")
        return dict(sorted(value.items()))

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetDescribeAttestation(BaseModel):
    """Collector-signed result of target-side sandboxed `describe`; never `invoke`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-describe-attestation/v1"] = (
        "rolo-target-describe-attestation/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)
    sandbox_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    output_sha256: str = Field(pattern=_SHA256_PATTERN)
    described_operations: dict[str, str] = Field(max_length=1024)
    described_at: datetime
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_ed25519_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_ed25519_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        try:
            signature = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("target describe signature is invalid base64") from exc
        if len(signature) != 64:
            raise ValueError("target describe signature must contain 64 bytes")
        return value

    @field_validator("described_operations")
    @classmethod
    def validate_operations(cls, value: dict[str, str]) -> dict[str, str]:
        if not value or list(value) != sorted(value):
            raise ValueError("described operations must be non-empty and sorted")
        for operation, entrypoint in value.items():
            if not operation or not entrypoint or len(operation) > 256 or len(entrypoint) > 4096:
                raise ValueError("target describe operation binding is invalid")
            if any(c in operation + entrypoint for c in ("\x00", "\r", "\n")):
                raise ValueError("target describe operation binding contains controls")
        return value

    def unsigned_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude={"payload_sha256", "signature_ed25519_base64"},
        )


class TargetDescribeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-describe-result/v1"] = (
        "rolo-target-describe-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    output: TargetDescribeOutput
    attestation: TargetDescribeAttestation

    @model_validator(mode="after")
    def require_request_and_identity_binding(self) -> TargetDescribeResult:
        if (
            self.attestation.request_id != self.request_id
            or self.attestation.request_sha256 != self.request_sha256
            or self.attestation.target_id != self.target_id
            or self.attestation.robot_id != self.robot_id
            or self.attestation.output_sha256 != self.output.canonical_sha256()
            or self.attestation.described_operations != self.output.operations
        ):
            raise ValueError("target describe result binding mismatch")
        return self


class AdapterReleaseDescribeRequest(BaseModel):
    """Outer executor request binding describe to one signed staged transfer."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-describe-request/v1"] = (
        "rolo-adapter-release-describe-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_base64: str = Field(max_length=32_768)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    describe: TargetDescribeRequest
    authorization: DeploymentAuthorizationProof | None = None

    @field_validator("signing_public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release describe public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("adapter release describe public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def bind_public_key(self) -> AdapterReleaseDescribeRequest:
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.signing_public_key_sha256:
            raise ValueError("adapter release describe public key digest mismatch")
        if self.request_id == self.describe.request_id:
            raise ValueError("adapter release outer and describe request IDs must differ")
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.describe.target_id,
        )
        return self

    def public_key_bytes(self) -> bytes:
        return b64decode(self.signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class AdapterReleaseDescribeExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-describe-execution-result/v1"] = (
        "rolo-adapter-release-describe-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transfer_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    describe: TargetDescribeResult | None = None

    @model_validator(mode="after")
    def require_consistent_execution(
        self,
    ) -> AdapterReleaseDescribeExecutionResult:
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.describe is None:
                raise ValueError("successful adapter release describe is incomplete")
        elif self.error_code is None or self.describe is not None:
            raise ValueError("failed adapter release describe is inconsistent")
        if self.describe is not None and (
            self.describe.target_id != self.target_id
            or self.describe.robot_id != self.robot_id
            or self.describe.attestation.release_id != self.release_id
        ):
            raise ValueError("adapter release describe execution binding mismatch")
        return self


def _target_release_file(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or "." in path.parts or ".." in path.parts:
        raise ValueError("target release file path is unsafe")
    candidate = root.joinpath(*path.parts)
    current = root
    for part in path.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ValueError("target release file is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("target release path contains a symbolic link")
    if not candidate.is_file():
        raise ValueError("target release path is not a regular file")
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("target release file escapes its root") from exc
    return candidate


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_release_json(path: Path, *, label: str) -> str:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError(f"{label} exceeds its size limit")
    return path.read_text(encoding="utf-8")


def _target_release_file_set(root: Path) -> set[str]:
    files: set[str] = set()
    for candidate in root.rglob("*"):
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise ValueError("target release tree is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("target release tree contains a symbolic link")
        if stat.S_ISREG(metadata.st_mode):
            files.add(candidate.relative_to(root).as_posix())
        elif not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("target release tree contains a non-regular entry")
    return files


def target_sandbox_profile_sha256(
    launcher: Path,
    budget: AdapterSandboxBudget,
) -> str:
    """Digest the actual target launcher bytes together with PR #17 runner budgets."""

    try:
        metadata = launcher.lstat()
    except OSError as exc:
        raise ValueError("target sandbox launcher is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("target sandbox launcher must be a real file")
    payload = {
        "schema_version": "rolo-target-sandbox-profile/v1",
        "launcher_sha256": _sha256_path(launcher),
        "budget": budget.model_dump(mode="json"),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def verify_frozen_adapter_release(
    release_root: Path,
    *,
    expected_manifest_sha256: str | None = None,
) -> tuple[Path, AdapterReleaseManifest, AdapterBundleManifest]:
    """Verify the exact immutable release tree without executing its adapter."""

    try:
        root_metadata = release_root.lstat()
    except OSError as exc:
        raise ValueError("target release root is unavailable") from exc
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("target release root must be a real directory")
    root = release_root.resolve(strict=True)
    manifest_path = _target_release_file(root, "manifest.json")
    if (
        expected_manifest_sha256 is not None
        and _sha256_path(manifest_path) != expected_manifest_sha256
    ):
        raise ValueError("target release manifest digest mismatch")
    release = AdapterReleaseManifest.model_validate_json(
        _read_release_json(manifest_path, label="target release manifest")
    )
    declared_items = [
        (release.bundle_manifest, release.bundle_manifest_sha256),
        (release.adapter_package, release.adapter_package_sha256),
        (release.tool_catalog, release.tool_catalog_sha256),
        (release.state_graph, release.state_graph_sha256),
        (release.conformance_report, release.conformance_report_sha256),
        (release.gate_report, release.gate_report_sha256),
        *((item.path, item.sha256) for item in release.adapter_files),
    ]
    declared: dict[str, str] = {}
    for relative, expected_sha256 in declared_items:
        existing = declared.get(relative)
        if existing is not None and existing != expected_sha256:
            raise ValueError("target release has conflicting file declarations")
        declared[relative] = expected_sha256
    for relative, expected_sha256 in declared.items():
        if _sha256_path(_target_release_file(root, relative)) != expected_sha256:
            raise ValueError("target release file digest mismatch")
    if _target_release_file_set(root) != {"manifest.json", *declared}:
        raise ValueError("target release file set differs from frozen manifest")
    bundle_path = _target_release_file(root, release.bundle_manifest)
    bundle = AdapterBundleManifest.model_validate_json(
        _read_release_json(bundle_path, label="target adapter bundle manifest")
    )
    if (
        bundle.robot_id != release.robot_id
        or bundle.discovery_id != release.discovery_id
        or bundle.package_sha256 != release.adapter_package_sha256
    ):
        raise ValueError("target adapter bundle identity or entrypoint digest mismatch")
    try:
        published_files = {
            PurePosixPath(item.path).relative_to("adapter").as_posix(): item
            for item in release.adapter_files
        }
    except ValueError as exc:
        raise ValueError("target adapter file is outside its release directory") from exc
    bundle_files = {item.path: item for item in bundle.declared_files()}
    if set(published_files) != set(bundle_files):
        raise ValueError("target release and adapter bundle file sets differ")
    for path, bundle_file in bundle_files.items():
        release_file = published_files[path]
        if (
            bundle_file.sha256 != release_file.sha256
            or bundle_file.role != release_file.role
        ):
            raise ValueError("target release and adapter bundle file binding differs")
    return root, release, bundle


def execute_target_describe(
    request: TargetDescribeRequest,
    *,
    context: LocatedRuntimeContext,
    release_root: Path,
    sandbox_launcher: Path,
    service: TargetEnrollmentService,
    runner: AdapterRunner,
    now: datetime | None = None,
) -> TargetDescribeResult:
    """Verify one frozen release and execute only `describe` in the target runner."""

    sandbox_profile_sha256 = target_sandbox_profile_sha256(
        sandbox_launcher,
        context.sandbox_budget,
    )
    if request.sandbox_profile_sha256 != sandbox_profile_sha256:
        raise ValueError("target sandbox profile digest mismatch")
    if (
        context.target_id != request.target_id
        or context.robot_id != request.robot_id
        or context.canonical_sha256() != request.runtime_context_sha256
    ):
        raise ValueError("target runtime context binding mismatch")
    root, release, bundle = verify_frozen_adapter_release(
        release_root,
        expected_manifest_sha256=request.release_manifest_sha256,
    )
    if (
        release.release_id != request.release_id
        or release.robot_id != request.robot_id
        or release.bundle_manifest_sha256 != request.bundle_manifest_sha256
    ):
        raise ValueError("target release identity or bundle digest mismatch")
    entrypoint = _target_release_file(root, release.adapter_package).resolve(strict=True)
    if Path(context.adapter_entrypoint).resolve(strict=False) != entrypoint:
        raise ValueError("target runtime entrypoint differs from frozen release")
    runtime, budget = target_runtime_materialization(context)
    if isinstance(runner, BoundedAdapterRunner) and (
        runner.max_address_space_bytes != budget["max_address_space_bytes"]
        or runner.max_processes != budget["max_processes"]
        or runner.sandbox_launcher is None
        or runner.sandbox_launcher.resolve(strict=False)
        != sandbox_launcher.resolve(strict=False)
    ):
        raise ValueError("target adapter runner differs from located sandbox profile")
    completed = runner.run(
        adapter_command(entrypoint) + ["describe"],
        cwd=root,
        timeout_s=request.timeout_s,
        max_stdout_bytes=200_000,
        max_stderr_bytes=200_000,
        runtime_environment=runtime.as_environment(),
    )
    if completed.timed_out:
        raise ValueError("target adapter describe timed out")
    if completed.output_limited:
        raise ValueError("target adapter describe exceeded its output limit")
    if completed.returncode != 0:
        raise ValueError("target adapter describe failed")
    try:
        raw_output = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("target adapter describe returned invalid JSON") from exc
    output = TargetDescribeOutput.model_validate(raw_output)
    expected_operations = {
        item.operation: item.entrypoint for item in bundle.operations
    }
    if output.operations != dict(sorted(expected_operations.items())):
        raise ValueError("target describe operations do not match frozen bundle")
    attestation = attest_target_describe(
        request,
        output=output,
        service=service,
        now=now,
    )
    return TargetDescribeResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.target_id,
        robot_id=request.robot_id,
        output=output,
        attestation=attestation,
    )


def attest_target_describe(
    request: TargetDescribeRequest,
    *,
    output: TargetDescribeOutput | Mapping[str, object],
    service: TargetEnrollmentService,
    now: datetime | None = None,
) -> TargetDescribeAttestation:
    """Sign already-bounded target-side describe output under the active collector."""

    record = service.current_record()
    descriptor = record.descriptor
    if (
        request.target_id != descriptor.target_id
        or request.robot_id != descriptor.robot_id
        or request.collector_id != descriptor.collector_id
    ):
        raise ValueError("target describe request does not match active collector")
    described = TargetDescribeOutput.model_validate(output)
    canonical_operations = described.operations
    output_sha256 = described.canonical_sha256()
    base = {
        "schema_version": "rolo-target-describe-attestation/v1",
        "request_id": request.request_id,
        "request_sha256": request.canonical_sha256(),
        "target_id": request.target_id,
        "robot_id": request.robot_id,
        "collector_id": request.collector_id,
        "descriptor_sha256": descriptor.canonical_sha256(),
        "release_id": request.release_id,
        "release_manifest_sha256": request.release_manifest_sha256,
        "bundle_manifest_sha256": request.bundle_manifest_sha256,
        "runtime_context_sha256": request.runtime_context_sha256,
        "sandbox_profile_sha256": request.sandbox_profile_sha256,
        "output_sha256": output_sha256,
        "described_operations": canonical_operations,
        "described_at": now or datetime.now(timezone.utc),
    }
    draft = TargetDescribeAttestation(
        **base,
        payload_sha256="0" * 64,
        signature_ed25519_base64=b64encode(b"0" * 64).decode("ascii"),
    )
    payload_sha256 = hashlib.sha256(
        _canonical_json(draft.unsigned_payload())
    ).hexdigest()
    signature = service.sign_current(
        descriptor.collector_id,
        payload_sha256.encode("ascii"),
    )
    return TargetDescribeAttestation(
        **base,
        payload_sha256=payload_sha256,
        signature_ed25519_base64=b64encode(signature).decode("ascii"),
    )


def verify_target_describe_attestation(
    attestation: TargetDescribeAttestation,
    *,
    request: TargetDescribeRequest,
    pin: CollectorEnrollmentPinV4,
    expected_operations: Mapping[str, str],
    output: TargetDescribeOutput | Mapping[str, object],
    now: datetime | None = None,
) -> None:
    """Gate-side verification of identity, release, runtime, sandbox, output and freshness."""

    observed_at = now or datetime.now(timezone.utc)
    descriptor = pin.descriptor
    if observed_at < request.issued_at or observed_at > request.expires_at:
        raise ValueError("target describe request is not currently valid")
    bound = (
        attestation.request_id == request.request_id
        and attestation.request_sha256 == request.canonical_sha256()
        and attestation.target_id == request.target_id == descriptor.target_id
        and attestation.robot_id == request.robot_id == descriptor.robot_id
        and attestation.collector_id == request.collector_id == descriptor.collector_id
        and attestation.descriptor_sha256 == descriptor.canonical_sha256()
        and attestation.release_id == request.release_id
        and attestation.release_manifest_sha256 == request.release_manifest_sha256
        and attestation.bundle_manifest_sha256 == request.bundle_manifest_sha256
        and attestation.runtime_context_sha256 == request.runtime_context_sha256
        and attestation.sandbox_profile_sha256 == request.sandbox_profile_sha256
    )
    if not bound:
        raise ValueError("target describe attestation binding mismatch")
    if (
        attestation.described_at < request.issued_at
        or attestation.described_at > request.expires_at
    ):
        raise ValueError("target describe attestation timestamp is outside request lifetime")
    canonical_expected = dict(sorted(expected_operations.items()))
    if attestation.described_operations != canonical_expected:
        raise ValueError("target describe operations do not match the bundle manifest")
    described = TargetDescribeOutput.model_validate(output)
    output_sha256 = described.canonical_sha256()
    if not hmac.compare_digest(output_sha256, attestation.output_sha256):
        raise ValueError("target describe output digest mismatch")
    payload_sha256 = hashlib.sha256(
        _canonical_json(attestation.unsigned_payload())
    ).hexdigest()
    if not hmac.compare_digest(payload_sha256, attestation.payload_sha256):
        raise ValueError("target describe attestation payload digest mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(descriptor.public_key_bytes()).verify(
            b64decode(attestation.signature_ed25519_base64, validate=True),
            attestation.payload_sha256.encode("ascii"),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("target describe attestation signature mismatch") from exc


def target_runtime_materialization(
    context: LocatedRuntimeContext,
) -> tuple[AdapterRuntimeContext, dict[str, int]]:
    """Target-only bridge into PR #17's runtime context and runner budgets."""

    runtime = context.runtime_environment.materialize_on_target()
    return runtime, context.sandbox_budget.model_dump(mode="python")
