from __future__ import annotations

import hashlib
import json
from base64 import b64decode
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
TARGET_PACKAGE_SBOM_NAME = "target-package.cdx.json"


class TargetArchitecture(str, Enum):
    X86_64 = "x86_64"
    AARCH64 = "aarch64"


class TargetPackageFileRole(str, Enum):
    ENTRYPOINT = "ENTRYPOINT"
    RUNTIME = "RUNTIME"
    CONFIG = "CONFIG"
    SERVICE = "SERVICE"
    LICENSE = "LICENSE"
    SBOM = "SBOM"


def _relative_package_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise ValueError("target package path must be normalized and relative")
    if any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
        raise ValueError("target package path contains forbidden characters")
    return str(path)


class TargetPackageFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    size_bytes: int = Field(ge=0, le=1_000_000_000)
    mode: int = Field(ge=0, le=0o777)
    role: TargetPackageFileRole

    _path = field_validator("path")(_relative_package_path)


class TargetPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package/v1"] = "rolo-target-package/v1"
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    rolo_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    target_os: Literal["linux"] = "linux"
    architecture: TargetArchitecture
    python_requires: str = Field(min_length=1, max_length=128)
    entrypoint: str = Field(min_length=1, max_length=4096)
    files: list[TargetPackageFile] = Field(min_length=1, max_length=4096)
    requires_bubblewrap: bool = True
    requires_user_namespace: bool = True
    requires_mount_namespace: bool = True
    requires_network_namespace: bool = True
    minimum_address_space_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=512 * 1024 * 1024,
        le=16 * 1024 * 1024 * 1024,
    )
    minimum_processes: int = Field(default=16, ge=16, le=512)

    _entrypoint = field_validator("entrypoint")(_relative_package_path)

    @field_validator("python_requires")
    @classmethod
    def validate_python_requires(cls, value: str) -> str:
        try:
            SpecifierSet(value)
        except InvalidSpecifier as exc:
            raise ValueError("target package python_requires is invalid") from exc
        return value

    @model_validator(mode="after")
    def require_canonical_files(self) -> TargetPackageManifest:
        paths = [item.path for item in self.files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("target package files must be unique and canonically sorted")
        entrypoints = [item for item in self.files if item.role == TargetPackageFileRole.ENTRYPOINT]
        if len(entrypoints) != 1 or entrypoints[0].path != self.entrypoint:
            raise ValueError("target package requires one matching entrypoint file")
        if entrypoints[0].mode & 0o111 == 0:
            raise ValueError("target package entrypoint must be executable")
        sboms = [item for item in self.files if item.role == TargetPackageFileRole.SBOM]
        if len(sboms) > 1:
            raise ValueError("target package can contain at most one SBOM")
        if sboms and sboms[0].path != TARGET_PACKAGE_SBOM_NAME:
            raise ValueError("target package SBOM path is not canonical")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class TargetPackageSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-signature/v1"] = (
        "rolo-target-package-signature/v1"
    )
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_base64: str = Field(pattern=r"^[A-Za-z0-9+/]{86}==$")

    @field_validator("signature_base64")
    @classmethod
    def validate_signature_bytes(cls, value: str) -> str:
        try:
            decoded = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("target package signature is invalid base64") from exc
        if len(decoded) != 64:
            raise ValueError("target package Ed25519 signature must be 64 bytes")
        return value

    def validate_manifest(self, manifest: TargetPackageManifest) -> None:
        if self.manifest_sha256 != manifest.canonical_sha256():
            raise ValueError("target package signature manifest digest mismatch")


class TargetPreflightStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class TargetPlatformFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-platform-facts/v1"] = (
        "rolo-target-platform-facts/v1"
    )
    os: str = Field(min_length=1, max_length=64)
    architecture: str = Field(min_length=1, max_length=64)
    python_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    bubblewrap_available: bool
    user_namespace_available: bool
    mount_namespace_available: bool
    network_namespace_available: bool
    available_address_space_bytes: int = Field(ge=0)
    available_processes: int = Field(ge=0)
    runtime_path_available: bool
    explicit_pythonpath_supported: bool
    virtualenv_supported: bool


class TargetPlatformPreflight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-platform-preflight/v1"] = (
        "rolo-target-platform-preflight/v1"
    )
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    status: TargetPreflightStatus
    normalized_architecture: TargetArchitecture | None = None
    facts: TargetPlatformFacts
    blockers: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def bind_status_and_blockers(self) -> TargetPlatformPreflight:
        if self.blockers != sorted(set(self.blockers)):
            raise ValueError("target preflight blockers must be unique and sorted")
        if self.status == TargetPreflightStatus.READY and self.blockers:
            raise ValueError("ready target preflight cannot contain blockers")
        if self.status == TargetPreflightStatus.BLOCKED and not self.blockers:
            raise ValueError("blocked target preflight requires blockers")
        return self


def _normalize_architecture(value: str) -> TargetArchitecture | None:
    normalized = value.casefold().replace("-", "_")
    if normalized in {"amd64", "x86_64"}:
        return TargetArchitecture.X86_64
    if normalized in {"aarch64", "arm64"}:
        return TargetArchitecture.AARCH64
    return None


def build_target_preflight(
    manifest: TargetPackageManifest,
    facts: TargetPlatformFacts,
) -> TargetPlatformPreflight:
    blockers: list[str] = []
    architecture = _normalize_architecture(facts.architecture)
    if facts.os.casefold() != manifest.target_os:
        blockers.append("TARGET_OS_UNSUPPORTED")
    if architecture != manifest.architecture:
        blockers.append("TARGET_ARCHITECTURE_MISMATCH")
    if facts.python_version not in SpecifierSet(manifest.python_requires):
        blockers.append("TARGET_PYTHON_UNSUPPORTED")
    requirements = {
        "TARGET_BUBBLEWRAP_UNAVAILABLE": (
            manifest.requires_bubblewrap,
            facts.bubblewrap_available,
        ),
        "TARGET_USER_NAMESPACE_UNAVAILABLE": (
            manifest.requires_user_namespace,
            facts.user_namespace_available,
        ),
        "TARGET_MOUNT_NAMESPACE_UNAVAILABLE": (
            manifest.requires_mount_namespace,
            facts.mount_namespace_available,
        ),
        "TARGET_NETWORK_NAMESPACE_UNAVAILABLE": (
            manifest.requires_network_namespace,
            facts.network_namespace_available,
        ),
        "TARGET_RUNTIME_PATH_UNAVAILABLE": (True, facts.runtime_path_available),
        "TARGET_EXPLICIT_PYTHONPATH_UNAVAILABLE": (
            True,
            facts.explicit_pythonpath_supported,
        ),
        "TARGET_VIRTUALENV_UNAVAILABLE": (True, facts.virtualenv_supported),
    }
    blockers.extend(
        code for code, (required, available) in requirements.items() if required and not available
    )
    if facts.available_address_space_bytes < manifest.minimum_address_space_bytes:
        blockers.append("TARGET_ADDRESS_SPACE_BUDGET_INSUFFICIENT")
    if facts.available_processes < manifest.minimum_processes:
        blockers.append("TARGET_PROCESS_BUDGET_INSUFFICIENT")
    blockers = sorted(set(blockers))
    return TargetPlatformPreflight(
        package_id=manifest.package_id,
        package_version=manifest.package_version,
        manifest_sha256=manifest.canonical_sha256(),
        status=(TargetPreflightStatus.BLOCKED if blockers else TargetPreflightStatus.READY),
        normalized_architecture=architecture,
        facts=facts,
        blockers=blockers,
    )


class BootstrapStepKind(str, Enum):
    UPLOAD = "UPLOAD"
    VERIFY = "VERIFY"
    INSTALL = "INSTALL"
    ACTIVATE = "ACTIVATE"
    HEALTH_CHECK = "HEALTH_CHECK"
    ROLLBACK = "ROLLBACK"


class BootstrapStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    kind: BootstrapStepKind
    risk: Literal["R1", "R2", "R3"]
    requires_sudo: bool
    sanitized_summary: str = Field(min_length=1, max_length=1000)


class BootstrapPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-bootstrap-plan/v1"] = "rolo-bootstrap-plan/v1"
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    preflight: TargetPlatformPreflight
    current_package_version: str | None = None
    current_manifest_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    idempotent_noop: bool = False
    steps: list[BootstrapStep] = Field(min_length=1, max_length=32)
    approval_actions: list[Literal["INSTALL_TARGET_RUNTIME", "USE_SUDO"]] = Field(
        default_factory=list,
        max_length=2,
    )

    @model_validator(mode="after")
    def require_consistent_plan(self) -> BootstrapPlan:
        if self.preflight.manifest_sha256 != self.manifest_sha256:
            raise ValueError("bootstrap plan preflight digest mismatch")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("bootstrap plan step IDs must be unique")
        if self.approval_actions != sorted(set(self.approval_actions)):
            raise ValueError("bootstrap approval actions must be unique and sorted")
        requires_sudo = any(step.requires_sudo for step in self.steps)
        if requires_sudo != ("USE_SUDO" in self.approval_actions):
            raise ValueError("bootstrap sudo steps and approval actions disagree")
        if self.idempotent_noop:
            if self.current_package_version != self.package_version:
                raise ValueError("bootstrap no-op requires the requested version to be current")
            if self.current_manifest_sha256 != self.manifest_sha256:
                raise ValueError("bootstrap no-op requires the requested digest to be current")
            allowed_noop_steps = {BootstrapStepKind.VERIFY, BootstrapStepKind.HEALTH_CHECK}
            if any(step.kind not in allowed_noop_steps for step in self.steps):
                raise ValueError("bootstrap no-op cannot contain mutation steps")
            if self.approval_actions:
                raise ValueError("bootstrap no-op cannot require mutation approval")
        elif "INSTALL_TARGET_RUNTIME" not in self.approval_actions:
            raise ValueError("bootstrap mutation requires installation approval")
        return self


def build_bootstrap_plan(
    *,
    target_id: str,
    manifest: TargetPackageManifest,
    signature: TargetPackageSignature,
    signing_public_key_sha256: str,
    preflight: TargetPlatformPreflight,
    current_package_version: str | None,
    current_manifest_sha256: str | None = None,
    install_requires_sudo: bool,
) -> BootstrapPlan:
    signature.validate_manifest(manifest)
    noop = (
        current_package_version == manifest.package_version
        and current_manifest_sha256 == manifest.canonical_sha256()
    )
    if noop:
        steps = [
            BootstrapStep(
                step_id="verify-current",
                kind=BootstrapStepKind.VERIFY,
                risk="R1",
                requires_sudo=False,
                sanitized_summary="Verify the installed target runtime digest.",
            ),
            BootstrapStep(
                step_id="health-current",
                kind=BootstrapStepKind.HEALTH_CHECK,
                risk="R1",
                requires_sudo=False,
                sanitized_summary="Run the fixed target runtime health check.",
            ),
        ]
        approvals: list[Literal["INSTALL_TARGET_RUNTIME", "USE_SUDO"]] = []
    else:
        steps = [
            BootstrapStep(
                step_id="upload-package",
                kind=BootstrapStepKind.UPLOAD,
                risk="R1",
                requires_sudo=False,
                sanitized_summary="Upload the digest-bound target runtime package.",
            ),
            BootstrapStep(
                step_id="verify-package",
                kind=BootstrapStepKind.VERIFY,
                risk="R1",
                requires_sudo=False,
                sanitized_summary="Verify the package manifest, signature, and file digests.",
            ),
            BootstrapStep(
                step_id="install-package",
                kind=BootstrapStepKind.INSTALL,
                risk="R3" if install_requires_sudo else "R2",
                requires_sudo=install_requires_sudo,
                sanitized_summary=(
                    "Install the verified target runtime into an immutable version directory."
                ),
            ),
            BootstrapStep(
                step_id="activate-package",
                kind=BootstrapStepKind.ACTIVATE,
                risk="R3" if install_requires_sudo else "R2",
                requires_sudo=install_requires_sudo,
                sanitized_summary="Atomically activate the verified target runtime version.",
            ),
            BootstrapStep(
                step_id="health-package",
                kind=BootstrapStepKind.HEALTH_CHECK,
                risk="R1",
                requires_sudo=False,
                sanitized_summary=(
                    "Run the fixed target runtime health check without invoking robot operations."
                ),
            ),
            BootstrapStep(
                step_id="rollback-package",
                kind=BootstrapStepKind.ROLLBACK,
                risk="R2",
                requires_sudo=install_requires_sudo,
                sanitized_summary=(
                    "Restore the previous active version if health verification fails."
                ),
            ),
        ]
        approvals = ["INSTALL_TARGET_RUNTIME"]
        if install_requires_sudo:
            approvals.append("USE_SUDO")
        approvals.sort()
    return BootstrapPlan(
        target_id=target_id,
        package_id=manifest.package_id,
        package_version=manifest.package_version,
        manifest_sha256=manifest.canonical_sha256(),
        signature_key_id=signature.key_id,
        signing_public_key_sha256=signing_public_key_sha256,
        preflight=preflight,
        current_package_version=current_package_version,
        current_manifest_sha256=current_manifest_sha256,
        idempotent_noop=noop,
        steps=steps,
        approval_actions=approvals,
    )


class TargetInstalledRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    install_path: str = Field(min_length=1, max_length=4096)


class TargetInstallIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-install-index/v1"] = (
        "rolo-target-install-index/v1"
    )
    current: TargetInstalledRelease
    previous: TargetInstalledRelease | None = None
    activated_at: datetime


class BootstrapInstallStatus(str, Enum):
    ACTIVATED = "ACTIVATED"
    ALREADY_ACTIVE = "ALREADY_ACTIVE"
    HEALTH_CHECK_FAILED = "HEALTH_CHECK_FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class TargetBootstrapInstallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-install-result/v1"] = (
        "rolo-target-bootstrap-install-result/v1"
    )
    status: BootstrapInstallStatus
    installed: TargetInstalledRelease
    active: TargetInstalledRelease | None = None
    previous_preserved: bool
