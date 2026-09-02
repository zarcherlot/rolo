"""Deterministic, auditable ROS environment bootstrap for target evidence."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.runtime_context import AdapterRuntimeContext

MAX_ENVIRONMENT_BYTES = 1_000_000
SOURCE_TIMEOUT_S = 30
_ENV_MARKER = b"\x00ROLO_ENV_START\x00"
_EXTRA_ENVIRONMENT_KEYS = {"PATH"}


class RosSetupFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["BASE", "OVERLAY", "EXPLICIT"]


class RosEnvironmentResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-ros-environment/v1"] = "rolo-ros-environment/v1"
    mode: Literal["INHERITED", "AUTO", "EXPLICIT", "DISABLED"]
    setup_files: list[RosSetupFileRecord] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path, kind: Literal["BASE", "OVERLAY", "EXPLICIT"]) -> RosSetupFileRecord:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"ROS setup file is unavailable: {resolved}")
    return RosSetupFileRecord(path=str(resolved), sha256=_sha256(resolved), kind=kind)


def _overlay_setup(install_root: Path) -> Path | None:
    for name in ("local_setup.bash", "setup.bash"):
        candidate = install_root / name
        if candidate.is_file():
            return candidate
    return None


def select_ros_setup_files(
    *,
    auto_source: bool,
    configured: Sequence[Path],
    project_root: Path | None,
    install_roots: Sequence[Path] = (),
    environment: Mapping[str, str] | None = None,
    ros_root: Path = Path("/opt/ros"),
) -> tuple[Literal["INHERITED", "AUTO", "EXPLICIT", "DISABLED"], list[RosSetupFileRecord]]:
    source = dict(os.environ if environment is None else environment)
    if configured:
        return "EXPLICIT", [_record(path, "EXPLICIT") for path in configured]
    if not auto_source:
        return "DISABLED", []

    records: list[RosSetupFileRecord] = []
    base_candidates: list[Path] = []
    configured_distro = source.get("ROS_DISTRO")
    if configured_distro:
        candidate = ros_root / configured_distro / "setup.bash"
        if candidate.is_file():
            base_candidates = [candidate]
    if not base_candidates and ros_root.is_dir():
        base_candidates = sorted(
            candidate / "setup.bash"
            for candidate in ros_root.iterdir()
            if candidate.is_dir() and (candidate / "setup.bash").is_file()
        )
    if len(base_candidates) > 1:
        raise ValueError(
            "multiple ROS distributions are installed; configure ros.setup_files explicitly: "
            + ", ".join(str(path) for path in base_candidates)
        )
    if base_candidates:
        records.append(_record(base_candidates[0], "BASE"))

    overlay_candidates: list[Path] = []
    for root in dict.fromkeys(path.expanduser().resolve() for path in install_roots):
        if setup := _overlay_setup(root):
            overlay_candidates.append(setup)
    if project_root is not None:
        direct_install = project_root.expanduser().resolve() / "install"
        direct_setup = _overlay_setup(direct_install)
        if direct_setup is not None:
            overlay_candidates = [direct_setup]
    overlay_candidates = list(dict.fromkeys(path.resolve() for path in overlay_candidates))
    if len(overlay_candidates) > 1:
        raise ValueError(
            "multiple ROS workspace overlays were found; configure ros.setup_files explicitly: "
            + ", ".join(str(path) for path in overlay_candidates)
        )
    if overlay_candidates:
        records.append(_record(overlay_candidates[0], "OVERLAY"))

    return ("AUTO" if records else "INHERITED"), records


def verify_pinned_setup_files(records: Sequence[RosSetupFileRecord]) -> None:
    for record in records:
        path = Path(record.path)
        if not path.is_file():
            raise ValueError(f"pinned ROS setup file is unavailable: {path}")
        if _sha256(path) != record.sha256:
            raise ValueError(f"pinned ROS setup file digest changed: {path}")


def _source_setup_files(
    records: Sequence[RosSetupFileRecord],
    source: Mapping[str, str],
) -> dict[str, str]:
    if not records:
        return dict(source)
    bash = shutil.which("bash", path=source.get("PATH"))
    if bash is None:
        raise ValueError("bash is required to source ROS setup files")
    script = (
        'set -eo pipefail; for setup in "$@"; do source "$setup"; done; '
        "printf '\\0ROLO_ENV_START\\0'; env -0"
    )
    try:
        completed = subprocess.run(
            [bash, "--noprofile", "--norc", "-c", script, "rolo-ros-bootstrap", *(
                record.path for record in records
            )],
            capture_output=True,
            check=False,
            timeout=SOURCE_TIMEOUT_S,
            env=dict(source),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"ROS setup bootstrap failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[:4_000]
        raise ValueError(f"ROS setup bootstrap exited {completed.returncode}: {detail}")
    marker = completed.stdout.rfind(_ENV_MARKER)
    if marker < 0:
        raise ValueError("ROS setup bootstrap did not return a bounded environment")
    payload = completed.stdout[marker + len(_ENV_MARKER) :]
    if len(payload) > MAX_ENVIRONMENT_BYTES:
        raise ValueError("ROS setup bootstrap environment exceeded its size limit")
    result = dict(source)
    admitted = {
        field.alias for field in AdapterRuntimeContext.model_fields.values() if field.alias
    } | _EXTRA_ENVIRONMENT_KEYS
    for item in payload.split(b"\x00"):
        if not item or b"=" not in item:
            continue
        raw_name, raw_value = item.split(b"=", 1)
        name = raw_name.decode("utf-8", errors="strict")
        if name in admitted:
            result[name] = raw_value.decode("utf-8", errors="strict")
    path_value = result.get("PATH", "")
    if len(path_value) > 32_768:
        raise ValueError("ROS setup bootstrap PATH exceeded its size limit")
    path_entries = [entry for entry in path_value.split(os.pathsep) if entry]
    if len(path_entries) > 128 or any(not Path(entry).is_absolute() for entry in path_entries):
        raise ValueError("ROS setup bootstrap PATH must contain at most 128 absolute entries")
    return result


def resolve_ros_environment(
    *,
    auto_source: bool,
    configured: Sequence[Path],
    project_root: Path | None,
    install_roots: Sequence[Path] = (),
    environment: Mapping[str, str] | None = None,
    ros_root: Path = Path("/opt/ros"),
    domain_id: str | None = None,
    rmw_implementation: str | None = None,
) -> RosEnvironmentResolution:
    source = dict(os.environ if environment is None else environment)
    mode, records = select_ros_setup_files(
        auto_source=auto_source,
        configured=configured,
        project_root=project_root,
        install_roots=install_roots,
        environment=source,
        ros_root=ros_root,
    )
    verify_pinned_setup_files(records)
    resolved = _source_setup_files(records, source)
    if domain_id is not None:
        resolved["ROS_DOMAIN_ID"] = domain_id
    if rmw_implementation is not None:
        resolved["RMW_IMPLEMENTATION"] = rmw_implementation
    runtime = AdapterRuntimeContext.capture(resolved).as_environment()
    warnings: list[str] = []
    if shutil.which("ros2", path=resolved.get("PATH")) is None:
        warnings.append("ROS 2 CLI is unavailable after environment bootstrap")
    return RosEnvironmentResolution(
        mode=mode,
        setup_files=records,
        environment={**resolved, **runtime},
        warnings=warnings,
    )


def resolve_pinned_ros_environment(
    records: Sequence[RosSetupFileRecord],
    *,
    environment: Mapping[str, str] | None = None,
) -> RosEnvironmentResolution:
    source = dict(os.environ if environment is None else environment)
    verify_pinned_setup_files(records)
    resolved = _source_setup_files(records, source)
    return RosEnvironmentResolution(
        mode="EXPLICIT" if records else "INHERITED",
        setup_files=list(records),
        environment=resolved,
        warnings=(
            []
            if shutil.which("ros2", path=resolved.get("PATH")) is not None
            else ["ROS 2 CLI is unavailable after environment bootstrap"]
        ),
    )
