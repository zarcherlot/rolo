"""Target-bound evidence collection for local and remote deployments.

The remote collector is deliberately a narrow stdin/stdout protocol.  SSH owns
transport authentication and host-key pinning; the bundle adds target identity,
freshness and an integrity signature that remains verifiable after transport.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.hashing import sha256_file
from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.stages.adapt.active_discovery import (
    HelpProbeResult,
    HelpProbeStatus,
    _extract_help_summary,
    run_bounded_help,
)
from rolo.stages.adapt.application_cli_mapping import ApplicationCliRouteProvider
from rolo.stages.adapt.discovery import HardwareProbe, LinuxProbe, RosProbe
from rolo.stages.adapt.ros_environment import (
    RosSetupFileRecord,
    resolve_pinned_ros_environment,
    verify_pinned_setup_files,
)
from rolo.stages.adapt.routes import persist_route_evidence, probe_routes

MAX_BUNDLE_BYTES = 8_000_000
MAX_CLOCK_SKEW = timedelta(minutes=2)
MAX_REQUEST_LIFETIME = timedelta(minutes=5)
MAX_HELP_EXECUTABLES = 4
MAX_HELP_EXECUTABLE_BYTES = 250_000_000
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SSH_TARGET_PATTERN = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9_.-]+$")
_REMOTE_CONFIG_PATTERN = re.compile(r"^[/A-Za-z0-9_.-]+$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


class EvidenceDeploymentMode(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class CollectorHelpExecutable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable_id: str = Field(pattern=r"^target-exe-[0-9a-f]{24}$")
    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class CollectorDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-target-evidence-collector/v1",
        "robot-target-evidence-collector/v2",
        "robot-target-evidence-collector/v3",
    ] = "robot-target-evidence-collector/v3"
    robot_id: str = Field(min_length=1, max_length=128)
    collector_id: str = Field(min_length=1, max_length=128)
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    help_executables: list[CollectorHelpExecutable] = Field(
        default_factory=list,
        max_length=MAX_HELP_EXECUTABLES,
    )
    ros_setup_files: list[RosSetupFileRecord] = Field(default_factory=list, max_length=8)
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def require_canonical_help_allowlist(self) -> CollectorDescriptor:
        identities = [item.executable_id for item in self.help_executables]
        paths = [item.path for item in self.help_executables]
        if identities != sorted(set(identities)) or len(paths) != len(set(paths)):
            raise ValueError("collector help executable allowlist must be unique and sorted")
        setup_paths = [item.path for item in self.ros_setup_files]
        if len(setup_paths) != len(setup_paths):
            raise ValueError("collector ROS setup file pins must be unique")
        return self


class CollectorState(CollectorDescriptor):
    secret_path: str = Field(min_length=1, max_length=4096)


class EvidenceDeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-target-evidence-deployment/v1", "robot-target-evidence-deployment/v2"
    ] = "robot-target-evidence-deployment/v2"
    robot_id: str = Field(min_length=1, max_length=128)
    mode: EvidenceDeploymentMode
    collector: CollectorDescriptor
    verification_secret_path: str = Field(min_length=1, max_length=4096)
    verification_secret_sha256: str = Field(pattern=_SHA256_PATTERN)
    local_collector_state_path: str | None = None
    collector_config: str = ".rolo/config/target-evidence-collector.json"
    ssh_target: str | None = None
    known_hosts_path: str | None = None
    transition_id: str | None = Field(default=None, pattern=r"^transition-[0-9a-f]{32}$")
    configured_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def require_mode_specific_transport(self) -> EvidenceDeploymentConfig:
        if self.collector.robot_id != self.robot_id:
            raise ValueError("collector descriptor robot identity mismatch")
        if self.mode == EvidenceDeploymentMode.REMOTE:
            if not self.ssh_target or not self.known_hosts_path:
                raise ValueError("remote mode requires ssh_target and known_hosts_path")
            if not _SSH_TARGET_PATTERN.fullmatch(self.ssh_target):
                raise ValueError("ssh_target contains unsupported characters")
            if not _REMOTE_CONFIG_PATTERN.fullmatch(self.collector_config):
                raise ValueError("collector_config contains unsupported characters")
        elif self.ssh_target or self.known_hosts_path:
            raise ValueError("local mode cannot configure a remote transport")
        if self.mode == EvidenceDeploymentMode.LOCAL and not self.local_collector_state_path:
            raise ValueError("local mode requires local_collector_state_path")
        if self.mode == EvidenceDeploymentMode.REMOTE and self.local_collector_state_path:
            raise ValueError("remote mode cannot configure local collector state")
        return self


class EvidenceDeploymentTransition(BaseModel):
    """Auditable authorization for one explicit collector re-enrollment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-transition/v1"] = (
        "robot-target-evidence-transition/v1"
    )
    transition_id: str = Field(pattern=r"^transition-[0-9a-f]{32}$")
    robot_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=8, max_length=500)
    previous_collector_id: str
    new_collector_id: str
    previous_target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    new_target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    previous_verification_secret_sha256: str = Field(pattern=_SHA256_PATTERN)
    new_verification_secret_sha256: str = Field(pattern=_SHA256_PATTERN)
    previous_mode: EvidenceDeploymentMode
    new_mode: EvidenceDeploymentMode
    authorized_at: datetime = Field(default_factory=_utc_now)


class TargetEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-target-evidence-request/v1", "robot-target-evidence-request/v2"
    ] = "robot-target-evidence-request/v2"
    robot_id: str = Field(min_length=1, max_length=128)
    mode: Literal["READ_ONLY"] = "READ_ONLY"
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(
        default_factory=lambda: ["hw", "linux", "ros"], min_length=1, max_length=3
    )
    requested_executable_help_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_HELP_EXECUTABLES,
    )
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_window_and_layers(self) -> TargetEvidenceRequest:
        if len(set(self.requested_layers)) != len(self.requested_layers):
            raise ValueError("requested_layers must be unique")
        if self.requested_executable_help_ids != sorted(set(self.requested_executable_help_ids)):
            raise ValueError("requested executable help IDs must be unique and sorted")
        if any(
            re.fullmatch(r"target-exe-[0-9a-f]{24}", executable_id) is None
            for executable_id in self.requested_executable_help_ids
        ):
            raise ValueError("requested executable help ID is invalid")
        if self.expires_at <= self.issued_at:
            raise ValueError("request expiry must follow issuance")
        if self.expires_at - self.issued_at > MAX_REQUEST_LIFETIME:
            raise ValueError("request lifetime exceeds five minutes")
        return self


class TargetExecutableHelpEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable_id: str = Field(pattern=r"^target-exe-[0-9a-f]{24}$")
    path: str = Field(min_length=1, max_length=4096)
    executable_sha256: str = Field(pattern=_SHA256_PATTERN)
    help_probe: HelpProbeResult
    output_text: str = Field(max_length=250_000)
    output_sha256: str = Field(pattern=_SHA256_PATTERN)
    usage: list[str] = Field(default_factory=list, max_length=20)
    parameters: list[str] = Field(default_factory=list, max_length=500)
    subcommands: list[str] = Field(default_factory=list, max_length=200)


class TargetEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-target-evidence-bundle/v1", "robot-target-evidence-bundle/v2"
    ] = "robot-target-evidence-bundle/v2"
    robot_id: str
    collector_id: str
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    request_nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(min_length=1, max_length=3)
    access: Literal["READ_ONLY"] = "READ_ONLY"
    collected_at: datetime
    probes: dict[str, ProbeResult]
    executable_help: list[TargetExecutableHelpEvidence] = Field(
        default_factory=list,
        max_length=MAX_HELP_EXECUTABLES,
    )
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_hmac_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def require_canonical_executable_help(self) -> TargetEvidenceBundle:
        identities = [item.executable_id for item in self.executable_help]
        if identities != sorted(set(identities)):
            raise ValueError("bundle executable help IDs must be unique and sorted")
        return self


def target_host_fingerprint() -> str:
    """Return a non-reversible stable identity for the host running the collector."""
    stable_id = ""
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            stable_id = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if stable_id:
            break
    if not stable_id and os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                stable_id = str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip()
        except OSError:
            stable_id = ""
    if not stable_id:
        raise ValueError("stable target machine identity is unavailable")
    payload = {
        "machine_id": stable_id,
        "node": platform.node(),
        "machine": platform.machine(),
        "system": platform.system(),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _write_private_secret(path: Path, secret: bytes) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"collector secret already exists: {path}")
    path.write_bytes(secret)
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise ValueError(f"cannot restrict collector secret permissions: {exc}") from exc


def _load_secret(path: Path) -> bytes:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"collector secret is unavailable: {path}")
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("collector secret permissions must not allow group or other access")
    secret = path.read_bytes()
    if len(secret) != 32:
        raise ValueError("collector secret must contain exactly 32 bytes")
    return secret


def initialize_collector(
    *,
    robot_id: str,
    state_path: Path,
    secret_path: Path,
    help_executables: Sequence[Path] = (),
    ros_setup_files: Sequence[RosSetupFileRecord] = (),
) -> CollectorDescriptor:
    fingerprint = target_host_fingerprint()
    state_path = state_path.expanduser().resolve()
    if state_path.exists():
        raise ValueError(f"collector state already exists: {state_path}")
    allowlist = _build_help_allowlist(help_executables)
    verify_pinned_setup_files(ros_setup_files)
    _write_private_secret(secret_path, secrets.token_bytes(32))
    descriptor = CollectorDescriptor(
        robot_id=robot_id,
        collector_id=f"collector-{uuid4().hex}",
        target_host_fingerprint=fingerprint,
        help_executables=allowlist,
        ros_setup_files=list(ros_setup_files),
    )
    state = CollectorState(
        **descriptor.model_dump(),
        secret_path=str(secret_path.expanduser().resolve()),
    )
    try:
        _atomic_write_text(state_path, state.model_dump_json(indent=2) + "\n")
    except OSError:
        secret_path.expanduser().resolve().unlink(missing_ok=True)
        raise
    return descriptor


def _build_help_allowlist(paths: Sequence[Path]) -> list[CollectorHelpExecutable]:
    if len(paths) > MAX_HELP_EXECUTABLES:
        raise ValueError(f"collector allows at most {MAX_HELP_EXECUTABLES} help executables")
    allowed: list[CollectorHelpExecutable] = []
    seen: set[Path] = set()
    for requested in paths:
        path = requested.expanduser().resolve()
        if path in seen:
            raise ValueError("collector help executable paths must be unique")
        seen.add(path)
        if not path.is_file():
            raise ValueError(f"collector help executable is not a regular file: {path}")
        if path.stat().st_size > MAX_HELP_EXECUTABLE_BYTES:
            raise ValueError(f"collector help executable exceeds size limit: {path}")
        digest = sha256_file(path)
        identity_digest = hashlib.sha256(
            _canonical_json({"path": str(path), "sha256": digest})
        ).hexdigest()
        allowed.append(
            CollectorHelpExecutable(
                executable_id=f"target-exe-{identity_digest[:24]}",
                path=str(path),
                sha256=digest,
            )
        )
    return sorted(allowed, key=lambda item: item.executable_id)


def stage_collector_rotation(
    *,
    previous_state_path: Path,
    expected_collector_id: str,
    new_state_path: Path,
    new_secret_path: Path,
    help_executables: Sequence[Path] = (),
    ros_setup_files: Sequence[RosSetupFileRecord] = (),
) -> CollectorDescriptor:
    """Stage parallel collector credentials while preserving the active collector."""
    previous = load_collector_state(previous_state_path)
    if previous.collector_id != expected_collector_id:
        raise ValueError("active collector identity differs from the expected rotation pin")
    descriptor = initialize_collector(
        robot_id=previous.robot_id,
        state_path=new_state_path,
        secret_path=new_secret_path,
        help_executables=help_executables,
        ros_setup_files=ros_setup_files,
    )
    if descriptor.target_host_fingerprint != previous.target_host_fingerprint:
        raise ValueError("staged collector rotation changed target host identity")
    return descriptor


def load_collector_state(path: Path) -> CollectorState:
    try:
        state = CollectorState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid collector state: {exc}") from exc
    if target_host_fingerprint() != state.target_host_fingerprint:
        raise ValueError("collector state belongs to a different target host")
    _load_secret(Path(state.secret_path))
    verify_pinned_setup_files(state.ros_setup_files)
    return state


def configure_deployment(
    *,
    robot_id: str,
    mode: EvidenceDeploymentMode,
    descriptor: CollectorDescriptor,
    verification_secret_path: Path,
    output_path: Path,
    ssh_target: str | None = None,
    known_hosts_path: Path | None = None,
    collector_config: str = ".rolo/config/target-evidence-collector.json",
    local_collector_state_path: Path | None = None,
) -> EvidenceDeploymentConfig:
    config = _build_deployment_config(
        robot_id=robot_id,
        mode=mode,
        descriptor=descriptor,
        verification_secret_path=verification_secret_path,
        ssh_target=ssh_target,
        known_hosts_path=known_hosts_path,
        collector_config=collector_config,
        local_collector_state_path=local_collector_state_path,
    )
    if output_path.exists():
        existing = load_deployment(output_path)
        stable_fields = {
            "robot_id",
            "mode",
            "collector",
            "verification_secret_path",
            "verification_secret_sha256",
            "local_collector_state_path",
            "collector_config",
            "ssh_target",
            "known_hosts_path",
        }
        existing_stable = existing.model_dump(mode="json", include=stable_fields)
        proposed_stable = config.model_dump(mode="json", include=stable_fields)
        if existing_stable != proposed_stable:
            raise ValueError(
                "target evidence deployment is already pinned; collector identity or transport "
                "changes require an explicit re-enroll/rotate workflow"
            )
        return existing
    _atomic_write_text(output_path, config.model_dump_json(indent=2) + "\n")
    return config


def ensure_local_deployment(
    *,
    robot_id: str,
    config_root: Path,
    help_executables: Sequence[Path] = (),
    ros_setup_files: Sequence[RosSetupFileRecord] = (),
) -> tuple[EvidenceDeploymentConfig, Path]:
    """Idempotently establish the target-local collector used by product journeys."""
    deployment_root = config_root.expanduser().resolve() / "target-evidence"
    deployment_path = deployment_root / f"{robot_id}.json"
    default_state_path = deployment_root / f"{robot_id}-collector.json"
    default_secret_path = deployment_root / f"{robot_id}-collector.key"
    if deployment_path.exists():
        deployment = load_deployment(deployment_path)
        if deployment.mode != EvidenceDeploymentMode.LOCAL:
            raise ValueError("existing target evidence deployment is not local")
        state_path = Path(deployment.local_collector_state_path or "")
        state = load_collector_state(state_path)
        descriptor = CollectorDescriptor.model_validate(state.model_dump(exclude={"secret_path"}))
        if help_executables:
            requested_allowlist = _build_help_allowlist(help_executables)
            if requested_allowlist != descriptor.help_executables:
                raise ValueError(
                    "local executable help allowlist changed; use collector rotation and "
                    "explicit re-enrollment"
                )
        if list(ros_setup_files) != descriptor.ros_setup_files:
            raise ValueError(
                "local ROS setup file pins changed; use collector rotation and explicit "
                "re-enrollment"
            )
        configured = configure_deployment(
            robot_id=robot_id,
            mode=EvidenceDeploymentMode.LOCAL,
            descriptor=descriptor,
            verification_secret_path=Path(deployment.verification_secret_path),
            output_path=deployment_path,
            local_collector_state_path=state_path,
        )
        return configured, state_path
    if default_state_path.exists() or default_secret_path.exists():
        raise ValueError(
            "local target evidence enrollment is incomplete; explicit recovery is required"
        )
    descriptor = initialize_collector(
        robot_id=robot_id,
        state_path=default_state_path,
        secret_path=default_secret_path,
        help_executables=help_executables,
        ros_setup_files=ros_setup_files,
    )
    deployment = configure_deployment(
        robot_id=robot_id,
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=default_secret_path,
        output_path=deployment_path,
        local_collector_state_path=default_state_path,
    )
    return deployment, default_state_path


def _build_deployment_config(
    *,
    robot_id: str,
    mode: EvidenceDeploymentMode,
    descriptor: CollectorDescriptor,
    verification_secret_path: Path,
    ssh_target: str | None,
    known_hosts_path: Path | None,
    collector_config: str,
    local_collector_state_path: Path | None,
    transition_id: str | None = None,
) -> EvidenceDeploymentConfig:
    verification_secret_path = verification_secret_path.expanduser().resolve()
    verification_secret_sha256 = hashlib.sha256(_load_secret(verification_secret_path)).hexdigest()
    resolved_local_state = (
        local_collector_state_path.expanduser().resolve()
        if local_collector_state_path is not None
        else None
    )
    if mode == EvidenceDeploymentMode.LOCAL and resolved_local_state is not None:
        local_state = load_collector_state(resolved_local_state)
        if (
            local_state.robot_id != descriptor.robot_id
            or local_state.collector_id != descriptor.collector_id
            or local_state.target_host_fingerprint != descriptor.target_host_fingerprint
        ):
            raise ValueError("local collector state differs from its descriptor")
        if hashlib.sha256(_load_secret(Path(local_state.secret_path))).hexdigest() != (
            verification_secret_sha256
        ):
            raise ValueError("local collector signing and verification secrets differ")
    known_hosts = None
    if known_hosts_path is not None:
        known_hosts_path = known_hosts_path.expanduser().resolve()
        if not known_hosts_path.is_file():
            raise ValueError("known_hosts_path must be an existing regular file")
        known_hosts = str(known_hosts_path)
    config = EvidenceDeploymentConfig(
        robot_id=robot_id,
        mode=mode,
        collector=descriptor,
        verification_secret_path=str(verification_secret_path),
        verification_secret_sha256=verification_secret_sha256,
        ssh_target=ssh_target,
        known_hosts_path=known_hosts,
        collector_config=collector_config,
        local_collector_state_path=(
            str(resolved_local_state) if resolved_local_state is not None else None
        ),
        transition_id=transition_id,
    )
    return config


def _atomic_write_text(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def reenroll_deployment(
    *,
    output_path: Path,
    expected_collector_id: str,
    reason: str,
    descriptor: CollectorDescriptor,
    verification_secret_path: Path,
    mode: EvidenceDeploymentMode | None = None,
    ssh_target: str | None = None,
    known_hosts_path: Path | None = None,
    collector_config: str | None = None,
    local_collector_state_path: Path | None = None,
    transition_dir: Path | None = None,
) -> tuple[EvidenceDeploymentConfig, EvidenceDeploymentTransition, Path]:
    """Explicitly replace a pinned deployment and preserve an immutable transition record."""
    if not output_path.is_file():
        raise ValueError("target evidence deployment must exist before re-enrollment")
    previous = load_deployment(output_path)
    if previous.collector.collector_id != expected_collector_id:
        raise ValueError("pinned collector identity differs from the expected re-enrollment pin")
    transition_id = f"transition-{uuid4().hex}"
    selected_mode = mode or previous.mode
    selected_collector_config = collector_config or previous.collector_config
    selected_ssh_target = ssh_target if selected_mode == EvidenceDeploymentMode.REMOTE else None
    selected_known_hosts = (
        known_hosts_path if selected_mode == EvidenceDeploymentMode.REMOTE else None
    )
    if selected_mode == EvidenceDeploymentMode.REMOTE:
        selected_ssh_target = selected_ssh_target or previous.ssh_target
        selected_known_hosts = selected_known_hosts or (
            Path(previous.known_hosts_path) if previous.known_hosts_path else None
        )
    elif local_collector_state_path is None and previous.local_collector_state_path:
        local_collector_state_path = Path(previous.local_collector_state_path)
    proposed = _build_deployment_config(
        robot_id=previous.robot_id,
        mode=selected_mode,
        descriptor=descriptor,
        verification_secret_path=verification_secret_path,
        ssh_target=selected_ssh_target,
        known_hosts_path=selected_known_hosts,
        collector_config=selected_collector_config,
        local_collector_state_path=local_collector_state_path,
        transition_id=transition_id,
    )
    if (
        proposed.collector == previous.collector
        and proposed.verification_secret_sha256 == previous.verification_secret_sha256
        and proposed.mode == previous.mode
        and proposed.collector_config == previous.collector_config
    ):
        raise ValueError("re-enrollment must change collector identity, credentials, or mode")
    transition = EvidenceDeploymentTransition(
        transition_id=transition_id,
        robot_id=previous.robot_id,
        reason=reason.strip(),
        previous_collector_id=previous.collector.collector_id,
        new_collector_id=proposed.collector.collector_id,
        previous_target_host_fingerprint=(previous.collector.target_host_fingerprint),
        new_target_host_fingerprint=proposed.collector.target_host_fingerprint,
        previous_verification_secret_sha256=(previous.verification_secret_sha256),
        new_verification_secret_sha256=proposed.verification_secret_sha256,
        previous_mode=previous.mode,
        new_mode=proposed.mode,
    )
    transitions = (
        transition_dir.expanduser().resolve()
        if transition_dir is not None
        else output_path.expanduser().resolve().parent / "transitions"
    )
    transition_path = transitions / f"{transition.transition_id}.json"
    if transition_path.exists():
        raise ValueError("target evidence transition record already exists")
    _atomic_write_text(
        transition_path,
        transition.model_dump_json(indent=2) + "\n",
    )
    _atomic_write_text(output_path, proposed.model_dump_json(indent=2) + "\n")
    return proposed, transition, transition_path


def load_deployment(path: Path) -> EvidenceDeploymentConfig:
    try:
        return EvidenceDeploymentConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid target evidence deployment: {exc}") from exc


def new_request(
    robot_id: str,
    *,
    now: datetime | None = None,
    executable_help_ids: Sequence[str] = (),
) -> TargetEvidenceRequest:
    issued_at = now or _utc_now()
    return TargetEvidenceRequest(
        robot_id=robot_id,
        nonce=secrets.token_hex(16),
        requested_executable_help_ids=sorted(set(executable_help_ids)),
        issued_at=issued_at,
        expires_at=issued_at + MAX_REQUEST_LIFETIME,
    )


def validate_target_evidence_request(
    request: TargetEvidenceRequest,
    *,
    robot_id: str,
    now: datetime,
) -> None:
    if request.robot_id != robot_id:
        raise ValueError("evidence request robot identity mismatch")
    if request.issued_at - MAX_CLOCK_SKEW > now:
        raise ValueError("evidence request was issued in the future")
    if request.expires_at < now:
        raise ValueError("evidence request expired")


def collect_target_evidence_payload(
    request: TargetEvidenceRequest,
    *,
    schema_version: str,
    robot_id: str,
    collector_id: str,
    target_host_fingerprint: str,
    help_executables: Sequence[CollectorHelpExecutable],
    ros_setup_files: Sequence[RosSetupFileRecord],
    identity_fields: Mapping[str, object] | None = None,
    now: datetime | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Collect one canonical unsigned payload shared by HMAC v2 and Ed25519 v4."""

    collected_at = now or _utc_now()
    validate_target_evidence_request(request, robot_id=robot_id, now=collected_at)
    ros_environment = resolve_pinned_ros_environment(
        ros_setup_files,
        environment=environment,
    )
    collectors = {
        "hw": lambda: HardwareProbe().run(robot_id=robot_id),
        "linux": lambda: LinuxProbe().run(),
        "ros": lambda: RosProbe().run(),
    }
    with _temporary_environment(ros_environment.environment):
        probes = {
            layer: persist_route_evidence(collectors[layer]())
            for layer in request.requested_layers
        }
        help_evidence = _collect_executable_help(request, help_executables)
    if ros_probe := probes.get("ros"):
        ros_probe.data["environment_bootstrap"] = ros_environment.model_dump(
            mode="json",
            exclude={"environment"},
        )
        ros_probe.warnings.extend(ros_environment.warnings)
    return {
        "schema_version": schema_version,
        "robot_id": robot_id,
        "collector_id": collector_id,
        "target_host_fingerprint": target_host_fingerprint,
        **dict(identity_fields or {}),
        "request_nonce": request.nonce,
        "requested_layers": request.requested_layers,
        "access": "READ_ONLY",
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "probes": {key: value.model_dump(mode="json") for key, value in probes.items()},
        "executable_help": [item.model_dump(mode="json") for item in help_evidence],
    }


def collect_target_evidence(
    request: TargetEvidenceRequest,
    state: CollectorState,
    *,
    now: datetime | None = None,
    environment: Mapping[str, str] | None = None,
) -> TargetEvidenceBundle:
    base = collect_target_evidence_payload(
        request,
        schema_version="robot-target-evidence-bundle/v2",
        robot_id=state.robot_id,
        collector_id=state.collector_id,
        target_host_fingerprint=state.target_host_fingerprint,
        help_executables=state.help_executables,
        ros_setup_files=state.ros_setup_files,
        now=now,
        environment=environment,
    )
    payload_sha256 = hashlib.sha256(_canonical_json(base)).hexdigest()
    signature = hmac.new(
        _load_secret(Path(state.secret_path)), payload_sha256.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return TargetEvidenceBundle(
        **base,
        payload_sha256=payload_sha256,
        signature_hmac_sha256=signature,
    )


@contextmanager
def _temporary_environment(environment: Mapping[str, str]):
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environment)
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _collect_executable_help(
    request: TargetEvidenceRequest,
    help_executables: Sequence[CollectorHelpExecutable],
) -> list[TargetExecutableHelpEvidence]:
    allowed = {item.executable_id: item for item in help_executables}
    unknown = sorted(set(request.requested_executable_help_ids) - set(allowed))
    if unknown:
        raise ValueError(f"requested executable help IDs are not allowlisted: {unknown}")
    evidence: list[TargetExecutableHelpEvidence] = []
    for executable_id in request.requested_executable_help_ids:
        descriptor = allowed[executable_id]
        path = Path(descriptor.path)
        if not path.is_file() or path.stat().st_size > MAX_HELP_EXECUTABLE_BYTES:
            raise ValueError(f"allowlisted executable is unavailable or oversized: {path}")
        if sha256_file(path) != descriptor.sha256:
            raise ValueError(f"allowlisted executable digest changed: {executable_id}")
        with tempfile.TemporaryDirectory(prefix="rolo-target-help-") as temporary:
            output_path = Path(temporary) / "help.txt"
            result = run_bounded_help(path, output_path)
            output = output_path.read_bytes() if output_path.is_file() else b""
        output_text = output.decode("utf-8", errors="replace")
        canonical_output = output_text.encode("utf-8")
        usage, parameters, subcommands = _extract_help_summary(output_text)
        evidence.append(
            TargetExecutableHelpEvidence(
                executable_id=executable_id,
                path=str(path),
                executable_sha256=descriptor.sha256,
                help_probe=result,
                output_text=output_text,
                output_sha256=hashlib.sha256(canonical_output).hexdigest(),
                usage=usage,
                parameters=parameters,
                subcommands=subcommands,
            )
        )
    return evidence


def bind_target_executable_routes(
    probe: ProbeResult,
    records: Sequence[TargetExecutableHelpEvidence],
    *,
    bundle_payload_sha256: str,
    observed_at: datetime,
) -> ProbeResult:
    """Derive application CLI routes from already verified target help evidence.

    The derivation happens on the controller after bundle signature validation.
    It therefore does not trust a collector-supplied route assertion and remains
    compatible with older v2 bundles that contain help evidence but no CLI route.
    """
    existing = {route.resource_id: route for route in probe_routes(probe)}
    for route in ApplicationCliRouteProvider().observed_routes(
        records,
        bundle_payload_sha256=bundle_payload_sha256,
        observed_at=observed_at,
    ):
        existing[route.resource_id] = route
    data = dict(probe.data)
    data["route_evidence"] = [
        route.model_dump(mode="json")
        for route in sorted(existing.values(), key=lambda item: item.resource_id)
    ]
    status = probe.status
    if (
        records
        and any(item.help_probe.status == HelpProbeStatus.SUCCEEDED for item in records)
        and status not in {DiscoveryStatus.SUCCEEDED, DiscoveryStatus.PARTIAL}
    ):
        status = DiscoveryStatus.PARTIAL
    return probe.model_copy(update={"status": status, "data": data})


def verify_evidence_bundle(
    bundle: TargetEvidenceBundle,
    *,
    deployment: EvidenceDeploymentConfig,
    request: TargetEvidenceRequest | None = None,
    secret_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, ProbeResult]:
    observed_at = now or _utc_now()
    descriptor = deployment.collector
    if bundle.robot_id != deployment.robot_id:
        raise ValueError("evidence bundle robot identity mismatch")
    if bundle.collector_id != descriptor.collector_id:
        raise ValueError("evidence bundle collector identity mismatch")
    if bundle.target_host_fingerprint != descriptor.target_host_fingerprint:
        raise ValueError("evidence bundle target host fingerprint mismatch")
    if request is not None:
        if request.robot_id != bundle.robot_id or request.nonce != bundle.request_nonce:
            raise ValueError("evidence bundle does not answer the issued request")
        if bundle.requested_layers != request.requested_layers:
            raise ValueError("evidence bundle layer set differs from the issued request")
        if [item.executable_id for item in bundle.executable_help] != (
            request.requested_executable_help_ids
        ):
            raise ValueError("evidence bundle executable help differs from the issued request")
        if bundle.collected_at < request.issued_at - MAX_CLOCK_SKEW:
            raise ValueError("evidence bundle predates the issued request")
        if bundle.collected_at > request.expires_at + MAX_CLOCK_SKEW:
            raise ValueError("evidence bundle was collected after request expiry")
    if bundle.collected_at > observed_at + MAX_CLOCK_SKEW:
        raise ValueError("evidence bundle timestamp is in the future")
    if observed_at - bundle.collected_at > MAX_REQUEST_LIFETIME + MAX_CLOCK_SKEW:
        raise ValueError("evidence bundle is stale")
    if set(bundle.probes) != set(bundle.requested_layers):
        raise ValueError("evidence bundle probe keys do not match its declared layers")
    allowed_help = {item.executable_id: item for item in descriptor.help_executables}
    for item in bundle.executable_help:
        allowed = allowed_help.get(item.executable_id)
        if allowed is None or item.path != allowed.path or item.executable_sha256 != allowed.sha256:
            raise ValueError("evidence bundle executable help is outside the pinned allowlist")
        if hashlib.sha256(item.output_text.encode("utf-8")).hexdigest() != (item.output_sha256):
            raise ValueError("evidence bundle executable help output hash mismatch")
    base = bundle.model_dump(mode="json", exclude={"payload_sha256", "signature_hmac_sha256"})
    actual_payload_sha256 = hashlib.sha256(_canonical_json(base)).hexdigest()
    if not hmac.compare_digest(actual_payload_sha256, bundle.payload_sha256):
        raise ValueError("evidence bundle payload hash mismatch")
    verification_secret = _load_secret(secret_path or Path(deployment.verification_secret_path))
    if hashlib.sha256(verification_secret).hexdigest() != (deployment.verification_secret_sha256):
        raise ValueError("collector verification secret differs from its pinned digest")
    expected_signature = hmac.new(
        verification_secret,
        bundle.payload_sha256.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, bundle.signature_hmac_sha256):
        raise ValueError("evidence bundle signature mismatch")
    bound: dict[str, ProbeResult] = {}
    for layer, probe in bundle.probes.items():
        data = dict(probe.data)
        target_binding = {
            "schema_version": "robot-target-evidence-binding/v2",
            "robot_id": bundle.robot_id,
            "collector_id": bundle.collector_id,
            "target_host_fingerprint": bundle.target_host_fingerprint,
            "bundle_payload_sha256": bundle.payload_sha256,
            "access": bundle.access,
            "deployment_mode": deployment.mode.value,
            "collected_at": bundle.collected_at.isoformat(),
        }
        if layer == "linux":
            target_binding["executable_help"] = [
                item.model_dump(mode="json") for item in bundle.executable_help
            ]
        data["target_evidence"] = target_binding
        verified_probe = probe.model_copy(update={"data": data})
        if layer == "linux":
            verified_probe = bind_target_executable_routes(
                verified_probe,
                bundle.executable_help,
                bundle_payload_sha256=bundle.payload_sha256,
                observed_at=bundle.collected_at,
            )
        bound[layer] = verified_probe
    return bound


def collect_over_ssh(
    deployment: EvidenceDeploymentConfig,
    request: TargetEvidenceRequest,
    *,
    timeout_s: float = 45.0,
) -> TargetEvidenceBundle:
    if deployment.mode != EvidenceDeploymentMode.REMOTE:
        raise ValueError("SSH collection requires remote deployment mode")
    known_hosts = Path(deployment.known_hosts_path or "").expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError("pinned SSH known_hosts file is unavailable")
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        deployment.ssh_target or "",
        "robotctl",
        "target-evidence",
        "collector-run",
        "--config",
        deployment.collector_config,
    ]
    try:
        completed = subprocess.run(
            command,
            input=request.model_dump_json(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"remote target evidence transport failed: {exc}") from exc
    if completed.returncode != 0:
        raise ValueError(
            "remote target evidence collector failed: " + completed.stderr.strip()[:1000]
        )
    if len(completed.stdout.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise ValueError("remote target evidence bundle exceeded its size limit")
    try:
        return TargetEvidenceBundle.model_validate_json(completed.stdout)
    except ValueError as exc:
        raise ValueError(f"remote target evidence collector returned invalid JSON: {exc}") from exc
