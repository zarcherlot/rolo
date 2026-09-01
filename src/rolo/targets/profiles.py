"""Persisted target profiles with explicit credential and host-key references."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.target_ref import SshTargetRef, TargetRef

_PROFILE_ID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_CREDENTIAL_REF = re.compile(r"^[a-z][a-z0-9_-]{0,31}:[A-Za-z0-9._/-]{1,127}$")
_SSH_FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]+={0,2}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CredentialReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["ssh-agent", "secret-store", "platform-keychain"]
    reference: str = Field(min_length=3, max_length=160)

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        if not _CREDENTIAL_REF.fullmatch(value):
            raise ValueError("credential reference must be a typed reference, not secret material")
        return value


class HostKeyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PENDING", "APPROVED", "REVOKED"] = "PENDING"
    host: str = Field(min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    fingerprint: str | None = None
    decided_at: datetime | None = None
    decided_by: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not _SSH_FINGERPRINT.fullmatch(value):
            raise ValueError("host-key fingerprint must use the SHA256:... format")
        return value

    @field_validator("decided_by")
    @classmethod
    def validate_decider(cls, value: str | None) -> str | None:
        if value is not None and any(character.isspace() for character in value):
            raise ValueError("host-key decision actor must not contain whitespace")
        return value


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-profile/v1"] = "rolo-target-profile/v1"
    profile_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    robot_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    target: TargetRef
    credential: CredentialReference
    # Controller-side pinned host-key file used by read-only Diagnose/Verify.
    # Keeping this in the profile makes the SSH transport reproducible while
    # the credential itself remains an opaque reference.
    known_hosts: Path | None = None
    known_hosts_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ssh_identity_file: Path | None = None
    ssh_identity_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    host_key: HostKeyDecision | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_transport_fields(self) -> TargetProfile:
        if not isinstance(self.target, SshTargetRef) and (
            self.known_hosts is not None
            or self.known_hosts_sha256 is not None
            or self.ssh_identity_file is not None
            or self.ssh_identity_sha256 is not None
        ):
            raise ValueError("known_hosts is only valid for SSH target profiles")
        return self

    @field_validator("profile_id", "robot_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not _PROFILE_ID.fullmatch(value):
            raise ValueError("profile and robot identifiers must match ^[a-z][a-z0-9_-]{2,63}$")
        return value


class TargetProfileStore:
    def __init__(self, config_root: Path) -> None:
        self.root = config_root.expanduser().resolve() / "target-profiles"

    def path_for(self, profile_id: str) -> Path:
        if not _PROFILE_ID.fullmatch(profile_id):
            raise ValueError("profile_id must match ^[a-z][a-z0-9_-]{2,63}$")
        return self.root / f"{profile_id}.json"

    def load(self, profile_id: str) -> TargetProfile:
        path = self.path_for(profile_id)
        if path.is_symlink():
            raise ValueError(f"target profile must not be a symlink: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"target profile is missing: {path}")
        try:
            profile = TargetProfile.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"invalid target profile {path}: {exc}") from exc
        if profile.profile_id != profile_id or profile.robot_id != profile_id:
            raise ValueError("target profile identity does not match its path")
        return profile

    def list_profiles(self) -> list[TargetProfile]:
        """Load every persisted profile in stable order.

        A malformed profile is an unavailable producer fact, so fail the complete
        read model instead of silently returning a partial fleet projection.
        """

        if not self.root.is_dir():
            return []
        profiles: list[TargetProfile] = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.name):
            if path.is_symlink():
                raise ValueError(f"target profile must not be a symlink: {path}")
            profile_id = path.stem
            profiles.append(self.load(profile_id))
        return profiles

    def save(self, profile: TargetProfile) -> Path:
        if profile.profile_id != profile.robot_id:
            raise ValueError("target profile_id and robot_id must match")
        if isinstance(profile.target, SshTargetRef) and profile.known_hosts is not None:
            known_hosts_sha256 = validate_known_hosts_file(
                profile.known_hosts, expected_sha256=profile.known_hosts_sha256
            )
            if profile.known_hosts_sha256 is None:
                profile = profile.model_copy(update={"known_hosts_sha256": known_hosts_sha256})
        if isinstance(profile.target, SshTargetRef) and profile.ssh_identity_file is not None:
            identity_sha256 = validate_identity_file(
                profile.ssh_identity_file, expected_sha256=profile.ssh_identity_sha256
            )
            if profile.ssh_identity_sha256 is None:
                profile = profile.model_copy(update={"ssh_identity_sha256": identity_sha256})
        path = self.path_for(profile.profile_id)
        with interprocess_lock(path):
            if path.is_symlink():
                raise ValueError(f"target profile must not be a symlink: {path}")
            if path.is_file():
                previous = self.load(profile.profile_id)
                if previous.target != profile.target:
                    raise ValueError("target profile target is immutable; create a new profile")
                profile = profile.model_copy(update={"created_at": previous.created_at})
            atomic_write_text(
                path,
                profile.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
        return path

    def create(
        self,
        *,
        robot_id: str,
        target: TargetRef,
        credential: CredentialReference,
        known_hosts: Path | None = None,
        ssh_identity_file: Path | None = None,
        now: datetime | None = None,
    ) -> TargetProfile:
        timestamp = now or _utc_now()
        host_key = None
        known_hosts_sha256 = None
        ssh_identity_sha256 = None
        if isinstance(target, SshTargetRef):
            host_key = HostKeyDecision(host=target.host, port=target.port)
            if known_hosts is not None:
                known_hosts_sha256 = validate_known_hosts_file(known_hosts)
            if ssh_identity_file is not None:
                ssh_identity_sha256 = validate_identity_file(ssh_identity_file)
        profile = TargetProfile(
            profile_id=robot_id,
            robot_id=robot_id,
            target=target,
            credential=credential,
            known_hosts=(known_hosts.expanduser().resolve() if known_hosts else None),
            known_hosts_sha256=known_hosts_sha256,
            ssh_identity_file=(
                ssh_identity_file.expanduser().resolve() if ssh_identity_file else None
            ),
            ssh_identity_sha256=ssh_identity_sha256,
            host_key=host_key,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.save(profile)
        return profile


def validate_known_hosts_file(
    path: Path, *, expected_sha256: str | None = None
) -> str:
    """Validate and hash a controller-side pinned known_hosts file."""

    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ValueError("pinned known_hosts must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError("pinned known_hosts must be an existing regular file")
    if resolved.stat().st_size == 0:
        raise ValueError("pinned known_hosts file must not be empty")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("pinned known_hosts content differs from the profile enrollment")
    return digest


def validate_identity_file(path: Path, *, expected_sha256: str | None = None) -> str:
    """Validate and hash an optional controller-side SSH private key reference."""

    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ValueError("SSH identity file must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError("SSH identity file must be an existing regular file")
    if os.name != "nt" and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise ValueError("SSH identity file permissions must not be group/world accessible")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("SSH identity file content differs from the profile enrollment")
    return digest


def known_hosts_fingerprints(path: Path, target: SshTargetRef) -> set[str]:
    """Return SHA256 host-key fingerprints for exact host entries only."""

    validate_known_hosts_file(path)
    resolved = path.expanduser().resolve()
    host_tokens = {target.host}
    if target.port is not None:
        host_tokens.add(f"[{target.host}]:{target.port}")
    else:
        host_tokens.add(f"[{target.host}]:22")
    fingerprints: set[str] = set()
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0].startswith("@"):
            fields = fields[1:]
        if len(fields) < 3:
            continue
        hosts, _key_type, key_blob = fields[:3]
        if not host_tokens.intersection(hosts.split(",")):
            continue
        try:
            padding = "=" * (-len(key_blob) % 4)
            decoded = base64.b64decode(key_blob + padding, validate=True)
        except ValueError:
            continue
        fingerprint = base64.b64encode(hashlib.sha256(decoded).digest()).decode("ascii").rstrip("=")
        fingerprints.add(f"SHA256:{fingerprint}")
    return fingerprints


def validate_host_key_pin(profile: TargetProfile) -> None:
    """Ensure the approved fingerprint matches the enrolled known_hosts entry."""

    if not isinstance(profile.target, SshTargetRef):
        return
    if profile.known_hosts is None or profile.known_hosts_sha256 is None:
        raise ValueError("SSH target profile requires an enrolled known_hosts digest")
    validate_known_hosts_file(profile.known_hosts, expected_sha256=profile.known_hosts_sha256)
    if profile.host_key is None or profile.host_key.status != "APPROVED":
        raise ValueError("SSH target profile host key is not approved")
    if profile.host_key.fingerprint is None:
        raise ValueError("SSH target profile approval is missing a host-key fingerprint")
    if profile.host_key.fingerprint not in known_hosts_fingerprints(
        profile.known_hosts, profile.target
    ):
        raise ValueError("approved host-key fingerprint does not match pinned known_hosts")


def validate_ssh_credential(profile: TargetProfile) -> Path | None:
    """Resolve the supported agent or explicitly pinned identity-file credential."""

    if not isinstance(profile.target, SshTargetRef):
        return None
    if (
        profile.credential.kind != "ssh-agent"
        or profile.credential.reference != "ssh-agent:default"
    ):
        raise ValueError(
            "SSH profile currently supports ssh-agent:default or a pinned identity file"
        )
    if profile.ssh_identity_file is None:
        return None
    if profile.ssh_identity_sha256 is None:
        raise ValueError("SSH identity file is missing its enrollment digest")
    validate_identity_file(profile.ssh_identity_file, expected_sha256=profile.ssh_identity_sha256)
    return profile.ssh_identity_file.expanduser().resolve()
