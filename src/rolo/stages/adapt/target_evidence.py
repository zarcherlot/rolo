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
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.models import ProbeResult
from rolo.stages.adapt.discovery import HardwareProbe, LinuxProbe, RosProbe
from rolo.stages.adapt.routes import persist_route_evidence

MAX_BUNDLE_BYTES = 8_000_000
MAX_CLOCK_SKEW = timedelta(minutes=2)
MAX_REQUEST_LIFETIME = timedelta(minutes=5)
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


class CollectorDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-collector/v1"] = (
        "robot-target-evidence-collector/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    collector_id: str = Field(min_length=1, max_length=128)
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    created_at: datetime = Field(default_factory=_utc_now)


class CollectorState(CollectorDescriptor):
    secret_path: str = Field(min_length=1, max_length=4096)


class EvidenceDeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-deployment/v1"] = (
        "robot-target-evidence-deployment/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    mode: EvidenceDeploymentMode
    collector: CollectorDescriptor
    verification_secret_path: str = Field(min_length=1, max_length=4096)
    verification_secret_sha256: str = Field(pattern=_SHA256_PATTERN)
    local_collector_state_path: str | None = None
    collector_config: str = ".rolo/config/target-evidence-collector.json"
    ssh_target: str | None = None
    known_hosts_path: str | None = None
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


class TargetEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-request/v1"] = (
        "robot-target-evidence-request/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    mode: Literal["READ_ONLY"] = "READ_ONLY"
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(
        default_factory=lambda: ["hw", "linux", "ros"], min_length=1, max_length=3
    )
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_window_and_layers(self) -> TargetEvidenceRequest:
        if len(set(self.requested_layers)) != len(self.requested_layers):
            raise ValueError("requested_layers must be unique")
        if self.expires_at <= self.issued_at:
            raise ValueError("request expiry must follow issuance")
        if self.expires_at - self.issued_at > MAX_REQUEST_LIFETIME:
            raise ValueError("request lifetime exceeds five minutes")
        return self


class TargetEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-evidence-bundle/v1"] = (
        "robot-target-evidence-bundle/v1"
    )
    robot_id: str
    collector_id: str
    target_host_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    request_nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    requested_layers: list[Literal["hw", "linux", "ros"]] = Field(min_length=1, max_length=3)
    access: Literal["READ_ONLY"] = "READ_ONLY"
    collected_at: datetime
    probes: dict[str, ProbeResult]
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_hmac_sha256: str = Field(pattern=_SHA256_PATTERN)


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
    *, robot_id: str, state_path: Path, secret_path: Path
) -> CollectorDescriptor:
    fingerprint = target_host_fingerprint()
    state_path = state_path.expanduser().resolve()
    if state_path.exists():
        raise ValueError(f"collector state already exists: {state_path}")
    _write_private_secret(secret_path, secrets.token_bytes(32))
    descriptor = CollectorDescriptor(
        robot_id=robot_id,
        collector_id=f"collector-{uuid4().hex}",
        target_host_fingerprint=fingerprint,
    )
    state = CollectorState(
        **descriptor.model_dump(),
        secret_path=str(secret_path.expanduser().resolve()),
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return descriptor


def load_collector_state(path: Path) -> CollectorState:
    try:
        state = CollectorState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid collector state: {exc}") from exc
    if target_host_fingerprint() != state.target_host_fingerprint:
        raise ValueError("collector state belongs to a different target host")
    _load_secret(Path(state.secret_path))
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
    verification_secret_path = verification_secret_path.expanduser().resolve()
    verification_secret_sha256 = hashlib.sha256(
        _load_secret(verification_secret_path)
    ).hexdigest()
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
            str(local_collector_state_path.expanduser().resolve())
            if local_collector_state_path is not None
            else None
        ),
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return config


def load_deployment(path: Path) -> EvidenceDeploymentConfig:
    try:
        return EvidenceDeploymentConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid target evidence deployment: {exc}") from exc


def new_request(robot_id: str, *, now: datetime | None = None) -> TargetEvidenceRequest:
    issued_at = now or _utc_now()
    return TargetEvidenceRequest(
        robot_id=robot_id,
        nonce=secrets.token_hex(16),
        issued_at=issued_at,
        expires_at=issued_at + MAX_REQUEST_LIFETIME,
    )


def _validate_request(
    request: TargetEvidenceRequest, state: CollectorState, *, now: datetime
) -> None:
    if request.robot_id != state.robot_id:
        raise ValueError("evidence request robot identity mismatch")
    if request.issued_at - MAX_CLOCK_SKEW > now:
        raise ValueError("evidence request was issued in the future")
    if request.expires_at < now:
        raise ValueError("evidence request expired")


def collect_target_evidence(
    request: TargetEvidenceRequest,
    state: CollectorState,
    *,
    now: datetime | None = None,
) -> TargetEvidenceBundle:
    collected_at = now or _utc_now()
    _validate_request(request, state, now=collected_at)
    collectors = {
        "hw": lambda: HardwareProbe().run(robot_id=state.robot_id),
        "linux": lambda: LinuxProbe().run(),
        "ros": lambda: RosProbe().run(),
    }
    probes = {
        layer: persist_route_evidence(collectors[layer]())
        for layer in request.requested_layers
    }
    base = {
        "schema_version": "robot-target-evidence-bundle/v1",
        "robot_id": state.robot_id,
        "collector_id": state.collector_id,
        "target_host_fingerprint": state.target_host_fingerprint,
        "request_nonce": request.nonce,
        "requested_layers": request.requested_layers,
        "access": "READ_ONLY",
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "probes": {key: value.model_dump(mode="json") for key, value in probes.items()},
    }
    payload_sha256 = hashlib.sha256(_canonical_json(base)).hexdigest()
    signature = hmac.new(
        _load_secret(Path(state.secret_path)), payload_sha256.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return TargetEvidenceBundle(
        **base,
        payload_sha256=payload_sha256,
        signature_hmac_sha256=signature,
    )


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
    base = bundle.model_dump(mode="json", exclude={"payload_sha256", "signature_hmac_sha256"})
    actual_payload_sha256 = hashlib.sha256(_canonical_json(base)).hexdigest()
    if not hmac.compare_digest(actual_payload_sha256, bundle.payload_sha256):
        raise ValueError("evidence bundle payload hash mismatch")
    verification_secret = _load_secret(
        secret_path or Path(deployment.verification_secret_path)
    )
    if hashlib.sha256(verification_secret).hexdigest() != (
        deployment.verification_secret_sha256
    ):
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
        data["target_evidence"] = {
            "schema_version": "robot-target-evidence-binding/v1",
            "robot_id": bundle.robot_id,
            "collector_id": bundle.collector_id,
            "target_host_fingerprint": bundle.target_host_fingerprint,
            "bundle_payload_sha256": bundle.payload_sha256,
            "access": bundle.access,
            "deployment_mode": deployment.mode.value,
            "collected_at": bundle.collected_at.isoformat(),
        }
        bound[layer] = probe.model_copy(update={"data": data})
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
