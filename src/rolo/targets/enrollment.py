from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from base64 import b64decode, b64encode
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.hashing import sha256_file
from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.stages.adapt.ros_environment import (
    RosSetupFileRecord,
    verify_pinned_setup_files,
)
from rolo.stages.adapt.target_evidence import CollectorHelpExecutable
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)
from rolo.targets.package_signing import ed25519_public_key_sha256

MAX_ENROLLMENT_LIFETIME = timedelta(minutes=5)
MAX_ENROLLMENT_CLOCK_SKEW = timedelta(minutes=2)
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_NONCE_PATTERN = r"^[0-9a-f]{32}$"
_APPROVAL_PATTERN = r"^approval-[0-9a-f]{32}$"
_SIGNATURE_PATTERN = r"^[A-Za-z0-9+/]{86}==$"
_PUBLIC_KEY_PATTERN = r"^[A-Za-z0-9+/]{43}=$"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _decode_exact_base64(value: str, *, size: int, label: str) -> bytes:
    try:
        payload = b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError(f"{label} is invalid base64") from exc
    if len(payload) != size:
        raise ValueError(f"{label} must contain exactly {size} bytes")
    return payload


class TargetEnrollmentOperation(str, Enum):
    STATUS = "STATUS"
    ENROLL = "ENROLL"
    ROTATE = "ROTATE"


class TargetEnrollmentStatus(str, Enum):
    NOT_ENROLLED = "NOT_ENROLLED"
    ENROLLED = "ENROLLED"
    ALREADY_ENROLLED = "ALREADY_ENROLLED"
    ROTATED = "ROTATED"


class TargetEnrollmentErrorCode(str, Enum):
    INVALID_STATE = "INVALID_STATE"
    IO_ERROR = "IO_ERROR"
    STATE_CONFLICT = "STATE_CONFLICT"


class CollectorConfigurationV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-collector-configuration/v4"] = (
        "robot-target-collector-configuration/v4"
    )
    help_executables: list[CollectorHelpExecutable] = Field(
        default_factory=list,
        max_length=4,
    )
    ros_setup_files: list[RosSetupFileRecord] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def require_canonical_pins(self) -> CollectorConfigurationV4:
        help_ids = [item.executable_id for item in self.help_executables]
        help_paths = [item.path for item in self.help_executables]
        if help_ids != sorted(set(help_ids)) or len(help_paths) != len(set(help_paths)):
            raise ValueError("collector v4 help executable pins must be unique and sorted")
        setup_paths = [item.path for item in self.ros_setup_files]
        if len(set(setup_paths)) != len(setup_paths):
            raise ValueError("collector v4 ROS setup pins must be unique")
        if any(not Path(path).expanduser().is_absolute() for path in help_paths + setup_paths):
            raise ValueError("collector v4 pinned paths must be absolute")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class CollectorConfigurationDiscoveryV4(BaseModel):
    """Target-local, bounded inputs for deterministic collector configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-collector-configuration-discovery/v4"] = (
        "robot-target-collector-configuration-discovery/v4"
    )
    workspace_root: str = Field(min_length=1, max_length=4096)
    help_executable_relative_paths: list[str] = Field(
        default_factory=list,
        max_length=4,
    )
    ros_auto_source: bool = True

    @field_validator("help_executable_relative_paths")
    @classmethod
    def canonical_relative_paths(cls, values: list[str]) -> list[str]:
        canonical: list[str] = []
        for value in values:
            if not value or "\\" in value or ":" in value or value.startswith("/"):
                raise ValueError("collector discovery executable path must be relative")
            path = PurePosixPath(value)
            normalized = path.as_posix()
            if normalized != value or any(part in {"", ".", ".."} for part in path.parts):
                raise ValueError("collector discovery executable path must be normalized")
            canonical.append(normalized)
        if canonical != sorted(set(canonical)):
            raise ValueError("collector discovery executable paths must be unique and sorted")
        return canonical


def _resolve_workspace_file(workspace: Path, relative: str) -> Path:
    current = workspace
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("collector discovery path cannot contain a symbolic link")
    resolved = current.resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError("collector discovery path escaped the workspace")
    if not resolved.is_file():
        raise ValueError("collector discovery executable is unavailable")
    if resolved.stat().st_size > 250_000_000:
        raise ValueError("collector discovery executable exceeds size limit")
    return resolved


def discover_collector_configuration_v4(
    discovery: CollectorConfigurationDiscoveryV4,
    *,
    environment: dict[str, str] | None = None,
    ros_root: Path = Path("/opt/ros"),
) -> CollectorConfigurationV4:
    """Resolve only approved workspace-relative executables and fixed ROS roots."""

    unresolved = Path(discovery.workspace_root).expanduser()
    if not unresolved.is_absolute() or unresolved.is_symlink():
        raise ValueError("collector discovery workspace must be an absolute directory")
    workspace = unresolved.resolve()
    if not workspace.is_dir():
        raise ValueError("collector discovery workspace is unavailable")
    executables: list[CollectorHelpExecutable] = []
    for relative in discovery.help_executable_relative_paths:
        path = _resolve_workspace_file(workspace, relative)
        digest = sha256_file(path)
        executable_id = (
            "target-exe-" + hashlib.sha256(f"{relative}\0{digest}".encode()).hexdigest()[:24]
        )
        executables.append(
            CollectorHelpExecutable(
                executable_id=executable_id,
                path=str(path),
                sha256=digest,
            )
        )
    executables.sort(key=lambda item: item.executable_id)
    from rolo.stages.adapt.ros_environment import select_ros_setup_files

    _, ros_setup_files = select_ros_setup_files(
        auto_source=discovery.ros_auto_source,
        configured=(),
        project_root=workspace,
        install_roots=(workspace / "install",),
        environment=environment,
        ros_root=ros_root,
    )
    return CollectorConfigurationV4(
        help_executables=executables,
        ros_setup_files=ros_setup_files,
    )


class CollectorDescriptorV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-collector/v4"] = (
        "robot-target-evidence-collector/v4"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    signing_algorithm: Literal["Ed25519"] = "Ed25519"
    public_key_base64: str = Field(pattern=_PUBLIC_KEY_PATTERN)
    public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    configuration_sha256: str = Field(pattern=_SHA256_PATTERN)
    created_at: datetime

    @field_validator("public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        _decode_exact_base64(value, size=32, label="collector public key")
        return value

    @model_validator(mode="after")
    def bind_public_key(self) -> CollectorDescriptorV4:
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.public_key_sha256:
            raise ValueError("collector public key digest mismatch")
        return self

    def public_key_bytes(self) -> bytes:
        return _decode_exact_base64(
            self.public_key_base64,
            size=32,
            label="collector public key",
        )

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class CollectorEnrollmentAttestationV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-enrollment-attestation/v4"] = (
        "robot-target-enrollment-attestation/v4"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    challenge_nonce: str = Field(pattern=_NONCE_PATTERN)
    descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    issued_at: datetime
    expires_at: datetime
    signature_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        _decode_exact_base64(value, size=64, label="enrollment attestation signature")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> CollectorEnrollmentAttestationV4:
        if self.expires_at <= self.issued_at:
            raise ValueError("enrollment attestation expiry must follow issuance")
        if self.expires_at - self.issued_at > MAX_ENROLLMENT_LIFETIME:
            raise ValueError("enrollment attestation lifetime exceeds five minutes")
        return self

    def signed_payload(self) -> bytes:
        return _canonical_json(self.model_dump(mode="json", exclude={"signature_base64"}))


class CollectorRotationTransitionV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-transition/v4"] = (
        "robot-target-evidence-transition/v4"
    )
    transition_id: str = Field(pattern=r"^transition-[0-9a-f]{32}$")
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    previous_collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    previous_descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    previous_key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    new_collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    new_descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    new_key_id: str = Field(pattern=r"^collector-key-[0-9a-f]{32}$")
    authorized_at: datetime
    signature_by_previous_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_by_previous_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        _decode_exact_base64(value, size=64, label="collector rotation signature")
        return value

    @model_validator(mode="after")
    def require_identity_change(self) -> CollectorRotationTransitionV4:
        if self.previous_collector_id == self.new_collector_id:
            raise ValueError("collector rotation must change collector identity")
        if self.previous_key_id == self.new_key_id:
            raise ValueError("collector rotation must change signing key")
        return self

    def signed_payload(self) -> bytes:
        return _canonical_json(
            self.model_dump(mode="json", exclude={"signature_by_previous_base64"})
        )


class TargetEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-enrollment-request/v1",
        "rolo-target-enrollment-request/v2",
    ] = "rolo-target-enrollment-request/v2"
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    operation: TargetEnrollmentOperation
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    challenge_nonce: str = Field(pattern=_NONCE_PATTERN)
    issued_at: datetime
    expires_at: datetime
    configuration_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    configuration: CollectorConfigurationV4 | None = None
    configuration_discovery: CollectorConfigurationDiscoveryV4 | None = None
    expected_collector_id: str | None = Field(
        default=None,
        pattern=r"^collector-[0-9a-f]{32}$",
    )
    approval_id: str | None = Field(default=None, pattern=_APPROVAL_PATTERN)
    timeout_s: float = Field(default=30.0, ge=1.0, le=300.0)

    @model_validator(mode="after")
    def require_operation_inputs(self) -> TargetEnrollmentRequest:
        if self.expires_at <= self.issued_at:
            raise ValueError("target enrollment request expiry must follow issuance")
        if self.expires_at - self.issued_at > MAX_ENROLLMENT_LIFETIME:
            raise ValueError("target enrollment request lifetime exceeds five minutes")
        if self.operation == TargetEnrollmentOperation.STATUS:
            if any(
                value is not None
                for value in (
                    self.configuration_sha256,
                    self.configuration,
                    self.configuration_discovery,
                    self.expected_collector_id,
                    self.approval_id,
                )
            ):
                raise ValueError("target enrollment status rejects mutation inputs")
        elif self.operation == TargetEnrollmentOperation.ENROLL:
            explicit = self.configuration is not None
            discovered = self.configuration_discovery is not None
            if explicit == discovered or self.approval_id is None:
                raise ValueError("target enrollment requires one configuration source and approval")
            if explicit != (self.configuration_sha256 is not None):
                raise ValueError("explicit target enrollment configuration requires its digest")
            if self.expected_collector_id is not None:
                raise ValueError("initial target enrollment rejects an expected collector")
        else:
            explicit = self.configuration is not None
            discovered = self.configuration_discovery is not None
            if (
                explicit == discovered
                or self.expected_collector_id is None
                or self.approval_id is None
                or explicit != (self.configuration_sha256 is not None)
            ):
                raise ValueError(
                    "target enrollment rotation requires one configuration source, "
                    "old pin, and approval"
                )
        if self.configuration is not None and (
            self.configuration_sha256 != self.configuration.canonical_sha256()
        ):
            raise ValueError("target enrollment configuration digest mismatch")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetEnrollmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-enrollment-result/v1"] = "rolo-target-enrollment-result/v1"
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation: TargetEnrollmentOperation
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    transport_error_code: TargetExecutionErrorCode | None = None
    enrollment_error_code: TargetEnrollmentErrorCode | None = None
    enrollment_status: TargetEnrollmentStatus | None = None
    descriptor: CollectorDescriptorV4 | None = None
    configuration: CollectorConfigurationV4 | None = None
    attestation: CollectorEnrollmentAttestationV4 | None = None
    transition: CollectorRotationTransitionV4 | None = None

    @model_validator(mode="after")
    def require_consistent_result(self) -> TargetEnrollmentResult:
        succeeded = self.execution_status == TargetExecutionStatus.SUCCEEDED
        error_count = int(self.transport_error_code is not None) + int(
            self.enrollment_error_code is not None
        )
        if (succeeded and error_count != 0) or (not succeeded and error_count != 1):
            raise ValueError("target enrollment execution error fields are inconsistent")
        if succeeded != (self.enrollment_status is not None):
            raise ValueError("target enrollment status is inconsistent with execution")
        if not succeeded and any(
            value is not None
            for value in (
                self.descriptor,
                self.configuration,
                self.attestation,
                self.transition,
            )
        ):
            raise ValueError("failed target enrollment execution contains identity data")
        if not succeeded:
            return self
        absent = self.enrollment_status == TargetEnrollmentStatus.NOT_ENROLLED
        if absent != (
            self.descriptor is None or self.configuration is None or self.attestation is None
        ):
            raise ValueError("target enrollment result identity fields are inconsistent")
        if absent and any(
            value is not None for value in (self.descriptor, self.configuration, self.attestation)
        ):
            raise ValueError("not-enrolled result cannot contain an identity")
        if self.enrollment_status == TargetEnrollmentStatus.ROTATED:
            if self.operation != TargetEnrollmentOperation.ROTATE or self.transition is None:
                raise ValueError("rotated target enrollment result is incomplete")
        elif self.transition is not None:
            raise ValueError("non-rotation target enrollment result contains a transition")
        if self.descriptor is not None and (
            self.descriptor.target_id != self.target_id or self.descriptor.robot_id != self.robot_id
        ):
            raise ValueError("target enrollment descriptor identity mismatch")
        if (
            self.descriptor is not None
            and self.configuration is not None
            and (self.descriptor.configuration_sha256 != self.configuration.canonical_sha256())
        ):
            raise ValueError("target enrollment result configuration digest mismatch")
        return self


class CollectorIdentityRecordV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-collector-identity-record/v4"] = (
        "robot-target-collector-identity-record/v4"
    )
    descriptor: CollectorDescriptorV4
    configuration: CollectorConfigurationV4
    private_key_filename: Literal["private-key.pem"] = "private-key.pem"


class CollectorIdentityIndexV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-collector-identity-index/v4"] = (
        "robot-target-collector-identity-index/v4"
    )
    current_collector_id: str = Field(pattern=r"^collector-[0-9a-f]{32}$")
    previous_collector_id: str | None = Field(
        default=None,
        pattern=r"^collector-[0-9a-f]{32}$",
    )
    transition_id: str | None = Field(
        default=None,
        pattern=r"^transition-[0-9a-f]{32}$",
    )
    updated_at: datetime

    @model_validator(mode="after")
    def require_rotation_pair(self) -> CollectorIdentityIndexV4:
        if (self.previous_collector_id is None) != (self.transition_id is None):
            raise ValueError("collector identity index rotation fields are inconsistent")
        if self.previous_collector_id == self.current_collector_id:
            raise ValueError("collector identity index current and previous must differ")
        return self


class CollectorEnrollmentPinV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-controller-collector-enrollment-pin/v4"] = (
        "rolo-controller-collector-enrollment-pin/v4"
    )
    descriptor: CollectorDescriptorV4
    configuration: CollectorConfigurationV4
    descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    source_request_sha256: str = Field(pattern=_SHA256_PATTERN)
    approval_id: str = Field(pattern=_APPROVAL_PATTERN)
    transition_id: str | None = Field(
        default=None,
        pattern=r"^transition-[0-9a-f]{32}$",
    )
    pinned_at: datetime

    @model_validator(mode="after")
    def bind_descriptor(self) -> CollectorEnrollmentPinV4:
        if self.descriptor_sha256 != self.descriptor.canonical_sha256():
            raise ValueError("controller collector pin descriptor digest mismatch")
        if self.descriptor.configuration_sha256 != self.configuration.canonical_sha256():
            raise ValueError("controller collector pin configuration digest mismatch")
        return self


class TargetEnrollmentStateConflict(ValueError):
    """The active collector does not match the requested enrollment transition."""


class CollectorEnrollmentPinRegistry:
    """Controller-side public-key pin with explicit old-key-authorized rotation."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.pins = self.root / "pins"
        self.transitions = self.root / "transitions"

    def _pin_path(self, target_id: str) -> Path:
        if re.fullmatch(_IDENTIFIER_PATTERN, target_id) is None:
            raise ValueError("invalid enrollment pin target identity")
        path = (self.pins / f"{target_id}.json").resolve()
        if not path.is_relative_to(self.pins.resolve()):
            raise ValueError("enrollment pin path escaped its root")
        return path

    @staticmethod
    def _load(path: Path) -> CollectorEnrollmentPinV4:
        try:
            return CollectorEnrollmentPinV4.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("invalid controller collector enrollment pin") from exc

    def get(self, target_id: str) -> CollectorEnrollmentPinV4:
        pin = self._load(self._pin_path(target_id))
        if pin.descriptor.target_id != target_id:
            raise ValueError("controller collector pin filename identity mismatch")
        return pin

    def get_optional(self, target_id: str) -> CollectorEnrollmentPinV4 | None:
        path = self._pin_path(target_id)
        return self.get(target_id) if path.is_file() else None

    def apply(
        self,
        request: TargetEnrollmentRequest,
        result: TargetEnrollmentResult,
        *,
        now: datetime | None = None,
    ) -> CollectorEnrollmentPinV4:
        if request.operation not in {
            TargetEnrollmentOperation.ENROLL,
            TargetEnrollmentOperation.ROTATE,
        }:
            raise ValueError("controller collector pin requires an enrollment mutation")
        descriptor = verify_enrollment_attestation(request, result, now=now)
        configuration = result.configuration
        if descriptor is None or configuration is None or request.approval_id is None:
            raise ValueError("controller collector pin requires an approved identity")
        pin_path = self._pin_path(request.target_id)
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_lock(pin_path):
            existing = self._load(pin_path) if pin_path.is_file() else None
            if request.operation == TargetEnrollmentOperation.ENROLL:
                if existing is not None:
                    if existing.descriptor == descriptor:
                        return existing
                    raise TargetEnrollmentStateConflict(
                        "controller already pins a different collector identity"
                    )
                pin = CollectorEnrollmentPinV4(
                    descriptor=descriptor,
                    configuration=configuration,
                    descriptor_sha256=descriptor.canonical_sha256(),
                    source_request_id=request.request_id,
                    source_request_sha256=request.canonical_sha256(),
                    approval_id=request.approval_id,
                    pinned_at=now or _utc_now(),
                )
                atomic_write_text(
                    pin_path,
                    pin.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                    require_absent=True,
                )
                return pin
            transition = result.transition
            if transition is None:
                raise ValueError("controller collector rotation is missing its transition")
            if existing is not None and (
                existing.descriptor == descriptor
                and existing.transition_id == transition.transition_id
            ):
                return existing
            if existing is None:
                raise TargetEnrollmentStateConflict(
                    "controller collector rotation requires an existing pin"
                )
            if existing.descriptor.collector_id != request.expected_collector_id:
                raise TargetEnrollmentStateConflict(
                    "controller collector pin differs from expected rotation identity"
                )
            verify_collector_rotation_transition(
                transition,
                previous_descriptor=existing.descriptor,
                new_descriptor=descriptor,
            )
            pin = CollectorEnrollmentPinV4(
                descriptor=descriptor,
                configuration=configuration,
                descriptor_sha256=descriptor.canonical_sha256(),
                source_request_id=request.request_id,
                source_request_sha256=request.canonical_sha256(),
                approval_id=request.approval_id,
                transition_id=transition.transition_id,
                pinned_at=now or _utc_now(),
            )
            self.transitions.mkdir(parents=True, exist_ok=True)
            transition_path = self.transitions / f"{transition.transition_id}.json"
            if transition_path.exists():
                raise TargetEnrollmentStateConflict(
                    "controller collector transition record already exists"
                )
            atomic_write_text(
                transition_path,
                transition.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
                require_absent=True,
            )
            try:
                atomic_write_text(
                    pin_path,
                    pin.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                )
            except Exception:
                transition_path.unlink(missing_ok=True)
                raise
            return pin


def _public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _private_key_pem(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink() or not path.is_file():
        raise ValueError("collector private key is unavailable")
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("collector private key permissions are too broad")
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError("collector private key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("collector private key is not Ed25519")
    return key


def verify_enrollment_attestation(
    request: TargetEnrollmentRequest,
    result: TargetEnrollmentResult,
    *,
    now: datetime | None = None,
) -> CollectorDescriptorV4 | None:
    observed_at = now or _utc_now()
    if (
        result.request_id != request.request_id
        or result.request_sha256 != request.canonical_sha256()
        or result.operation != request.operation
        or result.target_id != request.target_id
        or result.robot_id != request.robot_id
    ):
        raise ValueError("target enrollment response request binding mismatch")
    if result.execution_status != TargetExecutionStatus.SUCCEEDED:
        raise ValueError("target enrollment response reports failed execution")
    if result.enrollment_status == TargetEnrollmentStatus.NOT_ENROLLED:
        return None
    descriptor = result.descriptor
    configuration = result.configuration
    attestation = result.attestation
    if descriptor is None or configuration is None or attestation is None:
        raise ValueError("target enrollment response is missing its identity attestation")
    if descriptor.configuration_sha256 != configuration.canonical_sha256():
        raise ValueError("target enrollment response configuration digest mismatch")
    if (
        attestation.request_id != request.request_id
        or attestation.request_sha256 != request.canonical_sha256()
        or attestation.challenge_nonce != request.challenge_nonce
        or attestation.descriptor_sha256 != descriptor.canonical_sha256()
        or attestation.key_id != descriptor.key_id
    ):
        raise ValueError("target enrollment attestation binding mismatch")
    if attestation.issued_at < request.issued_at - MAX_ENROLLMENT_CLOCK_SKEW:
        raise ValueError("target enrollment attestation predates its request")
    if attestation.expires_at > request.expires_at:
        raise ValueError("target enrollment attestation exceeds request expiry")
    if observed_at > attestation.expires_at + MAX_ENROLLMENT_CLOCK_SKEW:
        raise ValueError("target enrollment attestation expired")
    if attestation.issued_at > observed_at + MAX_ENROLLMENT_CLOCK_SKEW:
        raise ValueError("target enrollment attestation is from the future")
    try:
        Ed25519PublicKey.from_public_bytes(descriptor.public_key_bytes()).verify(
            _decode_exact_base64(
                attestation.signature_base64,
                size=64,
                label="enrollment attestation signature",
            ),
            attestation.signed_payload(),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("target enrollment attestation signature mismatch") from exc
    if result.transition is not None:
        transition = result.transition
        if (
            transition.target_id != descriptor.target_id
            or transition.robot_id != descriptor.robot_id
            or transition.target_host_fingerprint != descriptor.target_host_fingerprint
            or transition.new_collector_id != descriptor.collector_id
            or transition.new_descriptor_sha256 != descriptor.canonical_sha256()
            or transition.new_key_id != descriptor.key_id
        ):
            raise ValueError("collector rotation transition new identity mismatch")
    return descriptor


def verify_collector_rotation_transition(
    transition: CollectorRotationTransitionV4,
    *,
    previous_descriptor: CollectorDescriptorV4,
    new_descriptor: CollectorDescriptorV4,
) -> None:
    if (
        transition.previous_collector_id != previous_descriptor.collector_id
        or transition.previous_descriptor_sha256 != previous_descriptor.canonical_sha256()
        or transition.previous_key_id != previous_descriptor.key_id
        or transition.new_collector_id != new_descriptor.collector_id
        or transition.new_descriptor_sha256 != new_descriptor.canonical_sha256()
        or transition.new_key_id != new_descriptor.key_id
        or transition.target_id != previous_descriptor.target_id
        or transition.robot_id != previous_descriptor.robot_id
        or transition.target_host_fingerprint != previous_descriptor.target_host_fingerprint
        or new_descriptor.target_id != previous_descriptor.target_id
        or new_descriptor.robot_id != previous_descriptor.robot_id
        or new_descriptor.target_host_fingerprint != previous_descriptor.target_host_fingerprint
    ):
        raise ValueError("collector rotation transition identity binding mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(previous_descriptor.public_key_bytes()).verify(
            _decode_exact_base64(
                transition.signature_by_previous_base64,
                size=64,
                label="collector rotation signature",
            ),
            transition.signed_payload(),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("collector rotation transition signature mismatch") from exc


class TargetEnrollmentService:
    """Target-local, lock-serialized Ed25519 collector identity state machine."""

    def __init__(
        self,
        root: Path,
        *,
        host_fingerprint_provider: Callable[[], str] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.identities = self.root / "identities"
        self.transitions = self.root / "transitions"
        self.current_path = self.root / "current.json"
        self._host_fingerprint_provider = (
            host_fingerprint_provider or self._default_host_fingerprint
        )
        self._clock = clock

    @staticmethod
    def _default_host_fingerprint() -> str:
        from rolo.stages.adapt.target_evidence import target_host_fingerprint

        return target_host_fingerprint()

    def _validate_request_time(self, request: TargetEnrollmentRequest, now: datetime) -> None:
        if request.issued_at - MAX_ENROLLMENT_CLOCK_SKEW > now:
            raise ValueError("target enrollment request was issued in the future")
        if request.expires_at < now:
            raise ValueError("target enrollment request expired")

    def _identity_root(self, collector_id: str) -> Path:
        path = (self.identities / collector_id).resolve()
        if not path.is_relative_to(self.identities.resolve()):
            raise ValueError("collector identity path escaped its root")
        return path

    def _load_index(self) -> CollectorIdentityIndexV4 | None:
        if not self.current_path.is_file():
            return None
        try:
            return CollectorIdentityIndexV4.model_validate_json(
                self.current_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ValueError("invalid collector identity index") from exc

    def _load_record(
        self,
        collector_id: str,
    ) -> tuple[CollectorIdentityRecordV4, Ed25519PrivateKey]:
        identity_root = self._identity_root(collector_id)
        if identity_root.is_symlink() or not identity_root.is_dir():
            raise ValueError("collector identity directory is unavailable")
        record_path = identity_root / "identity.json"
        if record_path.is_symlink() or not record_path.is_file():
            raise ValueError("collector identity record is unavailable")
        try:
            record = CollectorIdentityRecordV4.model_validate_json(
                record_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ValueError("invalid collector identity record") from exc
        if record.descriptor.collector_id != collector_id:
            raise ValueError("collector identity directory binding mismatch")
        if record.descriptor.configuration_sha256 != record.configuration.canonical_sha256():
            raise ValueError("collector identity configuration digest mismatch")
        key = _load_private_key(identity_root / record.private_key_filename)
        if _public_key_bytes(key) != record.descriptor.public_key_bytes():
            raise ValueError("collector private key differs from descriptor public key")
        return record, key

    def _active(
        self,
    ) -> tuple[CollectorIdentityIndexV4, CollectorIdentityRecordV4, Ed25519PrivateKey] | None:
        index = self._load_index()
        if index is None:
            return None
        record, key = self._load_record(index.current_collector_id)
        fingerprint = self._host_fingerprint_provider()
        if record.descriptor.target_host_fingerprint != fingerprint:
            raise ValueError("collector identity belongs to a different target host")
        return index, record, key

    def _create_identity(
        self,
        request: TargetEnrollmentRequest,
        *,
        configuration: CollectorConfigurationV4,
        fingerprint: str,
        now: datetime,
    ) -> tuple[CollectorIdentityRecordV4, Ed25519PrivateKey, Path]:
        verify_pinned_setup_files(configuration.ros_setup_files)
        for executable in configuration.help_executables:
            path = Path(executable.path).expanduser()
            if path.is_symlink() or not path.is_file():
                raise ValueError("collector help executable pin is unavailable")
            if path.stat().st_size > 250_000_000:
                raise ValueError("collector help executable pin exceeds size limit")
            if sha256_file(path) != executable.sha256:
                raise ValueError("collector help executable pin digest mismatch")
        private_key = Ed25519PrivateKey.generate()
        public_key = _public_key_bytes(private_key)
        collector_id = f"collector-{uuid4().hex}"
        descriptor = CollectorDescriptorV4(
            target_id=request.target_id,
            robot_id=request.robot_id,
            collector_id=collector_id,
            target_host_fingerprint=fingerprint,
            key_id=f"collector-key-{uuid4().hex}",
            public_key_base64=b64encode(public_key).decode("ascii"),
            public_key_sha256=ed25519_public_key_sha256(public_key),
            configuration_sha256=configuration.canonical_sha256(),
            created_at=now,
        )
        record = CollectorIdentityRecordV4(
            descriptor=descriptor,
            configuration=configuration,
        )
        self.identities.mkdir(parents=True, exist_ok=True)
        staging = self.identities / f".staging-{uuid4().hex}"
        staging.mkdir(mode=0o700)
        try:
            private_path = staging / record.private_key_filename
            with private_path.open("xb") as stream:
                stream.write(_private_key_pem(private_key))
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != "nt":
                private_path.chmod(0o600)
            atomic_write_text(
                staging / "identity.json",
                record.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
                require_absent=True,
            )
            final = self._identity_root(collector_id)
            staging.replace(final)
        except Exception:
            if staging.is_dir() and staging.resolve().is_relative_to(self.identities.resolve()):
                shutil.rmtree(staging)
            raise
        return record, private_key, final

    def _write_index(self, index: CollectorIdentityIndexV4) -> None:
        atomic_write_text(
            self.current_path,
            index.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
        )

    def _attestation(
        self,
        request: TargetEnrollmentRequest,
        descriptor: CollectorDescriptorV4,
        private_key: Ed25519PrivateKey,
        *,
        now: datetime,
    ) -> CollectorEnrollmentAttestationV4:
        unsigned = CollectorEnrollmentAttestationV4(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            challenge_nonce=request.challenge_nonce,
            descriptor_sha256=descriptor.canonical_sha256(),
            key_id=descriptor.key_id,
            issued_at=now,
            expires_at=min(request.expires_at, now + MAX_ENROLLMENT_LIFETIME),
            signature_base64=b64encode(b"0" * 64).decode("ascii"),
        )
        signature = private_key.sign(unsigned.signed_payload())
        return unsigned.model_copy(
            update={"signature_base64": b64encode(signature).decode("ascii")}
        )

    def _result(
        self,
        request: TargetEnrollmentRequest,
        *,
        status: TargetEnrollmentStatus,
        record: CollectorIdentityRecordV4 | None = None,
        private_key: Ed25519PrivateKey | None = None,
        transition: CollectorRotationTransitionV4 | None = None,
        now: datetime,
    ) -> TargetEnrollmentResult:
        attestation = (
            self._attestation(request, record.descriptor, private_key, now=now)
            if record is not None and private_key is not None
            else None
        )
        return TargetEnrollmentResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            operation=request.operation,
            target_id=request.target_id,
            robot_id=request.robot_id,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            enrollment_status=status,
            descriptor=record.descriptor if record is not None else None,
            configuration=record.configuration if record is not None else None,
            attestation=attestation,
            transition=transition,
        )

    def current_record(self) -> CollectorIdentityRecordV4:
        """Return the validated public active record without exposing private key material."""

        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_lock(self.current_path):
            active = self._active()
            if active is None:
                raise TargetEnrollmentStateConflict("target has no active collector identity")
            return active[1]

    def sign_current(self, collector_id: str, payload: bytes) -> bytes:
        """Sign with the current key only when the caller's collector CAS pin still matches."""

        if not payload:
            raise ValueError("collector signing payload cannot be empty")
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_lock(self.current_path):
            active = self._active()
            if active is None or active[1].descriptor.collector_id != collector_id:
                raise TargetEnrollmentStateConflict(
                    "active collector changed before evidence signing"
                )
            return active[2].sign(payload)

    def execute(self, request: TargetEnrollmentRequest) -> TargetEnrollmentResult:
        now = self._clock()
        self._validate_request_time(request, now)
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_lock(self.current_path):
            active = self._active()
            if request.operation == TargetEnrollmentOperation.STATUS:
                if active is None:
                    return self._result(
                        request,
                        status=TargetEnrollmentStatus.NOT_ENROLLED,
                        now=now,
                    )
                _, record, key = active
                if (
                    record.descriptor.target_id != request.target_id
                    or record.descriptor.robot_id != request.robot_id
                ):
                    raise TargetEnrollmentStateConflict(
                        "active collector identity differs from requested target"
                    )
                return self._result(
                    request,
                    status=TargetEnrollmentStatus.ENROLLED,
                    record=record,
                    private_key=key,
                    now=now,
                )
            fingerprint = self._host_fingerprint_provider()
            configuration = request.configuration
            if configuration is None:
                discovery = request.configuration_discovery
                if discovery is None:
                    raise ValueError("target enrollment configuration source is missing")
                configuration = discover_collector_configuration_v4(discovery)
            if active is None:
                if request.operation == TargetEnrollmentOperation.ROTATE:
                    raise TargetEnrollmentStateConflict(
                        "collector rotation requires an active identity"
                    )
                record, key, identity_root = self._create_identity(
                    request,
                    configuration=configuration,
                    fingerprint=fingerprint,
                    now=now,
                )
                try:
                    self._write_index(
                        CollectorIdentityIndexV4(
                            current_collector_id=record.descriptor.collector_id,
                            updated_at=now,
                        )
                    )
                except Exception:
                    if identity_root.is_dir() and identity_root.is_relative_to(
                        self.identities.resolve()
                    ):
                        shutil.rmtree(identity_root)
                    raise
                return self._result(
                    request,
                    status=TargetEnrollmentStatus.ENROLLED,
                    record=record,
                    private_key=key,
                    now=now,
                )
            index, previous_record, previous_key = active
            previous = previous_record.descriptor
            if previous.target_id != request.target_id or previous.robot_id != request.robot_id:
                raise TargetEnrollmentStateConflict(
                    "active collector identity differs from requested target"
                )
            if request.operation == TargetEnrollmentOperation.ENROLL:
                if previous.configuration_sha256 != configuration.canonical_sha256():
                    raise TargetEnrollmentStateConflict(
                        "collector configuration changed; explicit rotation is required"
                    )
                return self._result(
                    request,
                    status=TargetEnrollmentStatus.ALREADY_ENROLLED,
                    record=previous_record,
                    private_key=previous_key,
                    now=now,
                )
            if previous.collector_id != request.expected_collector_id:
                raise TargetEnrollmentStateConflict(
                    "active collector differs from expected rotation pin"
                )
            new_record, new_key, new_root = self._create_identity(
                request,
                configuration=configuration,
                fingerprint=fingerprint,
                now=now,
            )
            transition_id = f"transition-{uuid4().hex}"
            unsigned = CollectorRotationTransitionV4(
                transition_id=transition_id,
                target_id=request.target_id,
                robot_id=request.robot_id,
                target_host_fingerprint=fingerprint,
                previous_collector_id=previous.collector_id,
                previous_descriptor_sha256=previous.canonical_sha256(),
                previous_key_id=previous.key_id,
                new_collector_id=new_record.descriptor.collector_id,
                new_descriptor_sha256=new_record.descriptor.canonical_sha256(),
                new_key_id=new_record.descriptor.key_id,
                authorized_at=now,
                signature_by_previous_base64=b64encode(b"0" * 64).decode("ascii"),
            )
            transition = unsigned.model_copy(
                update={
                    "signature_by_previous_base64": b64encode(
                        previous_key.sign(unsigned.signed_payload())
                    ).decode("ascii")
                }
            )
            verify_collector_rotation_transition(
                transition,
                previous_descriptor=previous,
                new_descriptor=new_record.descriptor,
            )
            self.transitions.mkdir(parents=True, exist_ok=True)
            transition_path = self.transitions / f"{transition.transition_id}.json"
            try:
                atomic_write_text(
                    transition_path,
                    transition.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                    require_absent=True,
                )
                self._write_index(
                    CollectorIdentityIndexV4(
                        current_collector_id=new_record.descriptor.collector_id,
                        previous_collector_id=index.current_collector_id,
                        transition_id=transition.transition_id,
                        updated_at=now,
                    )
                )
            except Exception:
                transition_path.unlink(missing_ok=True)
                if new_root.is_dir() and new_root.is_relative_to(self.identities.resolve()):
                    shutil.rmtree(new_root)
                raise
            return self._result(
                request,
                status=TargetEnrollmentStatus.ROTATED,
                record=new_record,
                private_key=new_key,
                transition=transition,
                now=now,
            )
