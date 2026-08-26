from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_CREDENTIAL_REF_PATTERN = r"^[a-z][a-z0-9+.-]*://[^\s]{1,2048}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SSH_FINGERPRINT_PATTERN = r"^SHA256:[A-Za-z0-9+/]{43}$"
_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"
_PRINCIPAL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"


class OrchestratorPlacement(str, Enum):
    TARGET_LOCAL = "TARGET_LOCAL"
    CONTROLLER = "CONTROLLER"


class TargetTransport(str, Enum):
    LOCAL = "LOCAL"
    SSH = "SSH"


class InteractionSurface(str, Enum):
    CLI = "CLI"
    API = "API"
    TUI = "TUI"
    GUI = "GUI"
    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"


class TargetTrustLevel(str, Enum):
    STRICT = "STRICT"
    CONFIRMED = "CONFIRMED"
    TOFU_DEV = "TOFU_DEV"


def _validate_no_control_characters(value: str, *, field_name: str) -> str:
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError(f"{field_name} contains control characters")
    return value


def _validate_target_workspace(value: str) -> str:
    value = _validate_no_control_characters(value.strip(), field_name="workspace_root")
    workspace = PurePosixPath(value)
    if not workspace.is_absolute():
        raise ValueError("workspace_root must be an absolute target POSIX path")
    if ".." in workspace.parts:
        raise ValueError("workspace_root cannot traverse parent directories")
    return str(workspace)


def validate_credential_reference(value: str) -> str:
    """Validate an opaque provider reference without ever resolving credential material."""
    value = _validate_no_control_characters(value.strip(), field_name="credential_ref")
    parsed = urlsplit(value)
    if not parsed.scheme or not value.startswith(f"{parsed.scheme}://"):
        raise ValueError("credential_ref must use an explicit provider URI scheme")
    if parsed.scheme != parsed.scheme.lower():
        raise ValueError("credential_ref scheme must be lowercase")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential_ref cannot contain URI userinfo")
    if parsed.query or parsed.fragment:
        raise ValueError("credential_ref cannot contain query or fragment data")
    locator = f"{parsed.netloc}{parsed.path}"
    if not locator or any(part == ".." for part in parsed.path.split("/")):
        raise ValueError("credential_ref requires a bounded non-traversing locator")
    return value


def _validate_command_workspace(value: str) -> str:
    value = _validate_no_control_characters(value.strip(), field_name="workspace_root")
    if re.fullmatch(r"[A-Za-z]:[\\/].+", value):
        return value.replace("\\", "/")
    return _validate_target_workspace(value)


class TargetConnectionProfile(BaseModel):
    """Non-secret SSH metadata with an optional bootstrap-to-runtime identity split."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-connection-profile/v1"] = (
        "rolo-target-connection-profile/v1"
    )
    connection_profile_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    transport: Literal[TargetTransport.SSH] = TargetTransport.SSH
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65_535)
    user: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    credential_ref: str = Field(pattern=_CREDENTIAL_REF_PATTERN)
    provisioning_user: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    provisioning_credential_ref: str | None = Field(
        default=None,
        pattern=_CREDENTIAL_REF_PATTERN,
    )
    runtime_user: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    runtime_credential_ref: str | None = Field(
        default=None,
        pattern=_CREDENTIAL_REF_PATTERN,
    )
    known_hosts_path: str = Field(min_length=1, max_length=4096)
    trust_level: TargetTrustLevel = TargetTrustLevel.STRICT
    expected_host_key_sha256: str | None = Field(
        default=None,
        pattern=_SSH_FINGERPRINT_PATTERN,
    )
    ssh_ca_ref: str | None = Field(default=None, pattern=_CREDENTIAL_REF_PATTERN)
    proxy_jump_profile_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = _validate_no_control_characters(value.strip(), field_name="host")
        if not value or any(character.isspace() for character in value):
            raise ValueError("host cannot contain whitespace")
        return value

    @field_validator("known_hosts_path")
    @classmethod
    def validate_known_hosts_path(cls, value: str) -> str:
        value = _validate_no_control_characters(
            value.strip(),
            field_name="known_hosts_path",
        )
        if not Path(value).expanduser().is_absolute():
            raise ValueError("known_hosts_path must be an absolute controller path")
        return value

    _credential_reference = field_validator("credential_ref")(validate_credential_reference)

    @field_validator("runtime_credential_ref")
    @classmethod
    def validate_runtime_credential_reference(cls, value: str | None) -> str | None:
        return validate_credential_reference(value) if value is not None else None

    @field_validator("provisioning_credential_ref")
    @classmethod
    def validate_provisioning_credential_reference(
        cls,
        value: str | None,
    ) -> str | None:
        return validate_credential_reference(value) if value is not None else None

    @field_validator("ssh_ca_ref")
    @classmethod
    def validate_optional_ssh_ca_ref(cls, value: str | None) -> str | None:
        return validate_credential_reference(value) if value is not None else None

    @model_validator(mode="after")
    def require_pinned_strict_trust(self) -> TargetConnectionProfile:
        if (
            self.trust_level == TargetTrustLevel.STRICT
            and not self.expected_host_key_sha256
            and not self.ssh_ca_ref
        ):
            raise ValueError("STRICT SSH trust requires a host fingerprint or SSH CA reference")
        if self.proxy_jump_profile_id == self.connection_profile_id:
            raise ValueError("SSH connection profile cannot proxy through itself")
        runtime_fields = (self.runtime_user, self.runtime_credential_ref)
        if any(value is not None for value in runtime_fields) and not all(
            value is not None for value in runtime_fields
        ):
            raise ValueError(
                "runtime SSH user and credential reference must be configured together"
            )
        if (
            self.runtime_user == self.user
            and self.runtime_credential_ref == self.credential_ref
        ):
            raise ValueError(
                "explicit runtime SSH identity must differ by user or credential"
            )
        provisioning_fields = (
            self.provisioning_user,
            self.provisioning_credential_ref,
        )
        if any(value is not None for value in provisioning_fields) and not all(
            value is not None for value in provisioning_fields
        ):
            raise ValueError(
                "provisioning SSH user and credential reference must be configured together"
            )
        if (
            self.provisioning_user == self.user
            and self.provisioning_credential_ref == self.credential_ref
        ):
            raise ValueError(
                "explicit provisioning SSH identity must differ from bootstrap identity"
            )
        if (
            self.provisioning_user is not None
            and self.runtime_user is not None
            and self.provisioning_user == self.runtime_user
            and self.provisioning_credential_ref == self.runtime_credential_ref
        ):
            raise ValueError(
                "provisioning SSH identity must differ from runtime identity"
            )
        return self

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-profile/v1"] = "rolo-target-profile/v1"
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    orchestrator_placement: OrchestratorPlacement
    transport: TargetTransport
    connection_profile_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    workspace_root: str = Field(min_length=1, max_length=4096)
    desired_rolo_version: str = Field(pattern=_VERSION_PATTERN)
    trust_level: TargetTrustLevel = TargetTrustLevel.STRICT
    release_signing_key_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    release_signing_public_key_path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
    )
    release_signing_public_key_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )

    _workspace = field_validator("workspace_root")(_validate_command_workspace)

    @field_validator("release_signing_public_key_path")
    @classmethod
    def validate_release_signing_public_key_path(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        value = _validate_no_control_characters(
            value.strip(),
            field_name="release_signing_public_key_path",
        )
        if not Path(value).expanduser().is_absolute():
            raise ValueError("release signing public key path must be absolute")
        return value

    @model_validator(mode="after")
    def require_transport_profile(self) -> TargetProfile:
        if self.transport == TargetTransport.SSH and not self.connection_profile_id:
            raise ValueError("SSH target requires connection_profile_id")
        if self.transport == TargetTransport.SSH:
            workspace = PurePosixPath(self.workspace_root)
            if not workspace.is_absolute():
                raise ValueError("SSH target workspace_root must be an absolute POSIX path")
        if self.transport == TargetTransport.LOCAL and self.connection_profile_id:
            raise ValueError("LOCAL target cannot reference an SSH connection profile")
        release_pin = (
            self.release_signing_key_id,
            self.release_signing_public_key_path,
            self.release_signing_public_key_sha256,
        )
        if any(value is not None for value in release_pin) and not all(
            value is not None for value in release_pin
        ):
            raise ValueError("release signing key pin fields must be configured together")
        return self

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class DeploymentCommandKind(str, Enum):
    ASSESS_CONNECTION = "ASSESS_CONNECTION"
    PROVISION_HOST = "PROVISION_HOST"
    RECONCILE_HOST = "RECONCILE_HOST"
    ROLLBACK_HOST = "ROLLBACK_HOST"
    START_TARGET_SERVICE = "START_TARGET_SERVICE"
    RECONCILE_TARGET_SERVICE = "RECONCILE_TARGET_SERVICE"
    BOOTSTRAP = "BOOTSTRAP"
    ENROLL = "ENROLL"
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"
    ADAPT = "ADAPT"
    BOOTSTRAP_AND_ADAPT = "BOOTSTRAP_AND_ADAPT"
    UPGRADE = "UPGRADE"
    ROTATE_ENROLLMENT = "ROTATE_ENROLLMENT"
    ROLLBACK_TARGET_RUNTIME = "ROLLBACK_TARGET_RUNTIME"


_WORKSPACE_COMMANDS = {
    DeploymentCommandKind.BOOTSTRAP,
    DeploymentCommandKind.ADAPT,
    DeploymentCommandKind.BOOTSTRAP_AND_ADAPT,
}


class DeploymentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-command/v1"] = "rolo-deployment-command/v1"
    command: DeploymentCommandKind
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_root: str | None = Field(default=None, min_length=1, max_length=4096)
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly"
    run_adapter_agent: bool = True
    requested_by: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$",
    )
    interaction_surface: InteractionSurface
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$",
    )
    parameters_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @field_validator("workspace_root")
    @classmethod
    def validate_optional_workspace(cls, value: str | None) -> str | None:
        return _validate_command_workspace(value) if value is not None else None

    @model_validator(mode="after")
    def require_command_inputs(self) -> DeploymentCommand:
        if self.command in _WORKSPACE_COMMANDS and self.workspace_root is None:
            raise ValueError(f"{self.command.value} requires workspace_root")
        if self.command not in _WORKSPACE_COMMANDS and self.workspace_root is not None:
            raise ValueError(f"{self.command.value} does not accept workspace_root")
        if (
            self.command == DeploymentCommandKind.ASSESS_CONNECTION
            and self.parameters_sha256 is None
        ):
            raise ValueError("ASSESS_CONNECTION requires target registration digest")
        return self

    def canonical_sha256(self) -> str:
        # The interaction surface is provenance, not execution semantics. Keeping it out of
        # the digest lets CLI/TUI/GUI/NL reproduce one command while retaining its origin.
        payload = json.dumps(
            self.model_dump(mode="json", exclude={"interaction_surface"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class DeploymentJobState(str, Enum):
    CREATED = "CREATED"
    CONNECTING = "CONNECTING"
    HOST_KEY_APPROVAL_REQUIRED = "HOST_KEY_APPROVAL_REQUIRED"
    PREFLIGHT = "PREFLIGHT"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    ROLLING_BACK = "ROLLING_BACK"
    ENROLLING = "ENROLLING"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    DISCOVERING = "DISCOVERING"
    ADAPTING = "ADAPTING"
    GATING = "GATING"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DeploymentJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-job/v1"] = "rolo-deployment-job/v1"
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    command: DeploymentCommand
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    state: DeploymentJobState = DeploymentJobState.CREATED
    current_step: str | None = Field(default=None, min_length=1, max_length=128)
    blockers: list[str] = Field(default_factory=list, max_length=64)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def bind_command_and_time(self) -> DeploymentJob:
        if self.command_sha256 != self.command.canonical_sha256():
            raise ValueError("deployment job command digest mismatch")
        if self.updated_at < self.created_at:
            raise ValueError("deployment job updated_at cannot precede created_at")
        return self


class ApprovalAction(str, Enum):
    ACCEPT_HOST_KEY = "ACCEPT_HOST_KEY"
    INSTALL_TARGET_RUNTIME = "INSTALL_TARGET_RUNTIME"
    USE_SUDO = "USE_SUDO"
    REPLACE_ENROLLMENT = "REPLACE_ENROLLMENT"
    UPGRADE_TARGET_RUNTIME = "UPGRADE_TARGET_RUNTIME"
    ACTIVATE_RELEASE = "ACTIVATE_RELEASE"
    ROLLBACK_RELEASE = "ROLLBACK_RELEASE"
    ROLLBACK_TARGET_RUNTIME = "ROLLBACK_TARGET_RUNTIME"
    ROLLBACK_HOST_CONFIGURATION = "ROLLBACK_HOST_CONFIGURATION"
    START_TARGET_SERVICE = "START_TARGET_SERVICE"
    RECONCILE_TARGET_SERVICE = "RECONCILE_TARGET_SERVICE"
    STAGE_RELEASE = "STAGE_RELEASE"
    DESCRIBE_RELEASE = "DESCRIBE_RELEASE"
    READ_PROJECT_EVIDENCE = "READ_PROJECT_EVIDENCE"
    ANALYZE_PROJECT_SOURCE = "ANALYZE_PROJECT_SOURCE"
    COLLECT_RUNTIME_EVIDENCE = "COLLECT_RUNTIME_EVIDENCE"
    RAW_SSH_EXPERT_MODE = "RAW_SSH_EXPERT_MODE"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-approval-request/v1"] = "rolo-approval-request/v1"
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorization_scope_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    requester_principal: str = Field(pattern=_PRINCIPAL_PATTERN)
    approver_principal: str = Field(pattern=_PRINCIPAL_PATTERN)
    action: ApprovalAction
    risk: Literal["R1", "R2", "R3"]
    sanitized_summary: str = Field(min_length=1, max_length=1000)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def require_future_expiry(self) -> ApprovalRequest:
        if self.expires_at <= self.requested_at:
            raise ValueError("approval expiry must follow request time")
        if (self.expires_at - self.requested_at).total_seconds() > 24 * 60 * 60:
            raise ValueError("approval lifetime exceeds twenty-four hours")
        if self.requester_principal == self.approver_principal:
            raise ValueError("approval requester cannot approve its own request")
        if self.status != ApprovalStatus.PENDING:
            raise ValueError("approval request must remain pending; decisions are separate")
        return self

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class DeploymentEventType(str, Enum):
    STATE_CHANGED = "STATE_CHANGED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    ARTIFACT_WRITTEN = "ARTIFACT_WRITTEN"


class DeploymentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-event/v1"] = "rolo-deployment-event/v1"
    event_id: str = Field(pattern=r"^event-[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    step_id: str = Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    event_type: DeploymentEventType
    timestamp: datetime
    attempt: int = Field(default=1, ge=1, le=100)
    state: DeploymentJobState
    sanitized_summary: str = Field(min_length=1, max_length=1000)
    artifact_refs: list[str] = Field(default_factory=list, max_length=32)
    approval_ref: str | None = Field(default=None, pattern=r"^approval-[0-9a-f]{32}$")

    @field_validator("artifact_refs")
    @classmethod
    def require_artifact_refs(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("deployment event artifact refs must be unique")
        if any(re.fullmatch(r"artifact://[^\x00\r\n]{1,4096}", value) is None for value in values):
            raise ValueError("deployment event artifact ref is invalid")
        return values
