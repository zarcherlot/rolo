"""Evidence-degrading application discovery for the editable robot Wiki."""

from __future__ import annotations

import ast
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.stages.adapt.binary_dependencies import inspect_binary_dependencies
from rolo.stages.adapt.discovery_status import derive_discovery_status
from rolo.stages.adapt.evidence import (
    BASE_SKIP_DIRECTORIES,
    extract_protocols,
    read_text,
    walk_files,
)

MAX_ACTIVE_FILES = 10_000
MAX_REPORT_EXECUTABLES = 200
MAX_UNATTRIBUTED_INTERFACES = 100
MAX_EVIDENCE_REFS = 100
MAX_TEXT_EVIDENCE_FILES = 500
MAX_TEXT_BYTES = 2_000_000
MAX_HELP_BYTES = 200_000
MAX_HELP_PROBES = 20
HELP_TIMEOUT_S = 5.0
MAX_EXECUTABLE_HASH_BYTES = 256 * 1024 * 1024
MAX_EXECUTABLE_HASH_AGGREGATE_BYTES = 2 * 1024 * 1024 * 1024
TEXT_SUFFIXES = {".md", ".rst", ".txt", ".adoc", ".html", ".htm"}
STRUCTURED_DOCUMENT_NAMES = {"pyproject.toml", "package.xml", "Cargo.toml"}
CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}
INTERMEDIATE_SUFFIXES = {
    ".a",
    ".dll",
    ".dylib",
    ".exe",
    ".lib",
    ".o",
    ".obj",
    ".pdb",
    ".so",
}
SKIP_DIRECTORIES = BASE_SKIP_DIRECTORIES
SUPPLEMENTAL_SKIP_DIRECTORIES = BASE_SKIP_DIRECTORIES | {
    "third-party",
    "third_party",
    "vendor",
    "vendors",
}


def _stable_executable_id(name: str, path: Path | None = None) -> str:
    identity = f"path:{path.resolve()}" if path is not None else f"declared:{name}"
    return f"exe-{sha256_bytes(identity.encode('utf-8'))[:16]}"


class DiscoveryModeLevel(str, Enum):
    # Retained so historical immutable reports remain readable. New reports never emit it.
    SOURCE_FIRST = "SOURCE_FIRST"
    ARTIFACT_DOC = "ARTIFACT_DOC"
    DOC_PROBE = "DOC_PROBE"
    BINARY_ONLY = "BINARY_ONLY"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActiveProbeMode(str, Enum):
    NONE = "none"
    HELP = "help"
    RUNTIME_READONLY = "runtime-readonly"


class CoverageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NOT_PROVIDED = "NOT_PROVIDED"
    NOT_PROBED = "NOT_PROBED"
    OBSERVED = "OBSERVED"
    UNAVAILABLE = "UNAVAILABLE"


class HelpProbeStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    NOT_PROBED = "NOT_PROBED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"


class ActiveDiscoveryInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_roots: list[Path] = Field(default_factory=list)
    build_roots: list[Path] = Field(default_factory=list)
    install_roots: list[Path] = Field(default_factory=list)
    executables: list[Path] = Field(default_factory=list)
    document_roots: list[Path] = Field(default_factory=list)
    launch_roots: list[Path] = Field(default_factory=list)
    active_probe: ActiveProbeMode = ActiveProbeMode.NONE

    @model_validator(mode="after")
    def require_primary_evidence(self) -> ActiveDiscoveryInputs:
        if not (
            self.source_roots
            or self.build_roots
            or self.install_roots
            or self.executables
            or self.document_roots
            or self.launch_roots
            or self.active_probe == ActiveProbeMode.RUNTIME_READONLY
        ):
            raise ValueError(
                "at least one --build-root, --install-root, --executable, --doc-root, "
                "--launch-root, --source-root, or --active-probe runtime-readonly is required"
            )
        return self

    def resolved(self) -> ActiveDiscoveryInputs:
        def unique(paths: Sequence[Path]) -> list[Path]:
            return list(dict.fromkeys(path.expanduser().resolve() for path in paths))

        return self.model_copy(
            update={
                "source_roots": unique(self.source_roots),
                "build_roots": unique(self.build_roots),
                "install_roots": unique(self.install_roots),
                "executables": unique(self.executables),
                "document_roots": unique(self.document_roots),
                "launch_roots": unique(self.launch_roots),
            }
        )


class CoverageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CoverageStatus
    records: int = Field(default=0, ge=0)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class HelpProbeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HelpProbeStatus = HelpProbeStatus.NOT_PROBED
    output_ref: str | None = None
    timeout_s: float = HELP_TIMEOUT_S
    exit_code: int | None = None
    output_bytes: int = Field(default=0, ge=0)
    truncated: bool = False
    error: str | None = None
    usage: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    subcommands: list[str] = Field(default_factory=list)


class SourceAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool = False
    projects: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)
    build_targets: list[str] = Field(default_factory=list)
    entrypoint_symbols: list[str] = Field(default_factory=list)
    declared_dependencies: list[str] = Field(default_factory=list)
    dependency_declarations: list[dict[str, Any]] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    source_revisions: list[str] = Field(default_factory=list)
    manifest_sha256: dict[str, str] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class ArtifactAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_root: str | None = None
    build_roots: list[str] = Field(default_factory=list)
    intermediate_outputs: list[str] = Field(default_factory=list)
    linked_libraries: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    configuration_files: list[str] = Field(default_factory=list)


class DocumentationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool = False
    references: list[str] = Field(default_factory=list)
    reference_sha256: dict[str, str] = Field(default_factory=dict)
    documented_commands: list[str] = Field(default_factory=list)
    documented_parameters: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    stale_warnings: list[str] = Field(default_factory=list)


class LaunchAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool = False
    references: list[str] = Field(default_factory=list)
    reference_sha256: dict[str, str] = Field(default_factory=dict)
    packages: list[str] = Field(default_factory=list)
    declared_executable: str | None = None
    nodes: list[str] = Field(default_factory=list)
    arguments: list[str] = Field(default_factory=list)
    argument_defaults: dict[str, str | None] = Field(default_factory=dict)
    included_launch_files: list[str] = Field(default_factory=list)
    remappings: list[dict[str, str]] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    urdf_references: list[str] = Field(default_factory=list)
    verification: Literal["STATIC_UNVERIFIED"] = "STATIC_UNVERIFIED"


class InvocationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrypoint: str | None = None
    arguments: list[str] = Field(default_factory=list)
    subcommands: list[str] = Field(default_factory=list)
    required_environment: dict[str, str] = Field(default_factory=dict)
    startup_sequence: list[str] = Field(default_factory=list)
    shutdown_method: str | None = None
    exit_codes: list[int] = Field(default_factory=list)
    health_check: str | None = None
    help_probe: HelpProbeResult = Field(default_factory=HelpProbeResult)


class CommunicationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ros: dict[str, Any] = Field(default_factory=dict)
    network: dict[str, Any] = Field(default_factory=dict)
    ipc: dict[str, Any] = Field(default_factory=dict)
    hardware_bus: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence = Confidence.LOW
    evidence_refs: list[str] = Field(default_factory=list)


class ExecutableDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable_id: str
    name: str
    path: str | None = None
    origin: Literal[
        "EXPLICIT",
        "DISCOVERED_BUILD_ARTIFACT",
        "DISCOVERED_ARTIFACT",
        "SOURCE_DECLARED",
        "LAUNCH_DECLARED",
    ]
    sha256: str | None = None
    file_format: str | None = None
    architecture: str | None = None
    binary_dependencies: dict[str, Any] = Field(default_factory=dict)
    version: dict[str, Any] = Field(default_factory=dict)
    source_analysis: SourceAnalysis = Field(default_factory=SourceAnalysis)
    artifact_analysis: ArtifactAnalysis = Field(default_factory=ArtifactAnalysis)
    documentation_analysis: DocumentationAnalysis = Field(default_factory=DocumentationAnalysis)
    launch_analysis: LaunchAnalysis = Field(default_factory=LaunchAnalysis)
    invocation: InvocationAnalysis = Field(default_factory=InvocationAnalysis)
    communication: CommunicationAnalysis = Field(default_factory=CommunicationAnalysis)
    dependencies: dict[str, list[Any]] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, list[Any]] = Field(default_factory=dict)


class DiscoveryMode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: DiscoveryModeLevel
    confidence: Confidence
    reason: str


class EvidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_order: list[Literal["BUILD_ARTIFACT", "DOCUMENTATION", "PROBE"]] = Field(
        default_factory=lambda: ["BUILD_ARTIFACT", "DOCUMENTATION", "PROBE"]
    )
    supporting: list[Literal["SOURCE"]] = Field(default_factory=lambda: ["SOURCE"])
    conflict_rule: Literal["HIGHER_PRIORITY_WINS"] = "HIGHER_PRIORITY_WINS"
    source_role: Literal["SUPPORTING_ONLY"] = "SUPPORTING_ONLY"


class ActiveDiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-active-discovery-report/v1", "robot-active-discovery-report/v2"
    ] = "robot-active-discovery-report/v2"
    discovery_id: str
    robot_id: str
    technical_status: str
    discovery_mode: DiscoveryMode
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    inputs: dict[str, Any]
    coverage: dict[str, CoverageRecord]
    executables: list[ExecutableDiscovery] = Field(default_factory=list)
    unattributed_source_interfaces: list[dict[str, Any]] = Field(default_factory=list)
    dependency_summary: dict[str, Any] = Field(default_factory=dict)
    global_conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def discard_v1_duplicate_views(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        migrated.pop("canonical_operation_summary", None)
        executables = []
        for executable in migrated.get("executables", []):
            if isinstance(executable, dict):
                executable = dict(executable)
                executable.pop("capability_candidates", None)
            executables.append(executable)
        migrated["executables"] = executables
        return migrated


def _hash_files(paths: Iterable[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        try:
            if path.is_file() and path.stat().st_size <= MAX_TEXT_BYTES:
                hashes[str(path)] = sha256_file(path)
        except OSError:
            continue
    return hashes


def _read_bounded_text(path: Path) -> str | None:
    return read_text(path, MAX_TEXT_BYTES, oversized="reject")


def _binary_identity(path: Path) -> tuple[str | None, str | None]:
    try:
        with path.open("rb") as stream:
            header = stream.read(64)
    except OSError:
        return None, None
    if header.startswith(b"\x7fELF"):
        endian = "little" if len(header) > 5 and header[5] == 1 else "big"
        machine = int.from_bytes(header[18:20], endian) if len(header) >= 20 else 0
        architecture = {40: "arm", 62: "x86_64", 183: "arm64"}.get(machine, "unknown")
        return "ELF", architecture
    if header.startswith(b"MZ"):
        return "PE", None
    if header.startswith(b"#!"):
        return "SCRIPT", platform.machine().lower() or None
    return path.suffix.lstrip(".").upper() or "UNKNOWN", None


def _looks_executable(path: Path) -> bool:
    lower_parts = {part.casefold() for part in path.parts}
    lower_name = path.name.casefold()
    if (
        "cmakefiles" in lower_parts
        or "hook" in lower_parts
        or path.suffix.casefold() in (INTERMEDIATE_SUFFIXES - {".exe"})
        or lower_name in {"a.out", "setup.sh", "local_setup.sh", "setup.bash", "local_setup.bash"}
        or lower_name.startswith(("cmakeccompilerid", "cmakecxxcompilerid", "cmtc_"))
    ):
        return False
    if path.suffix.casefold() == ".ps1":
        return os.name == "nt" and path.is_file()
    if path.suffix.casefold() in {".exe", ".bat", ".cmd", ".com"}:
        return True
    if {"bin", "sbin", "libexec", "scripts"} & lower_parts:
        return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))
    return path.is_file() and os.name != "nt" and os.access(path, os.X_OK)


def _safe_environment() -> dict[str, str]:
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TMP", "TEMP")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        # Test doubles and alternative process implementations may not expose
        # a PID; retain the portable terminate path for those callers.
        process_pid = getattr(process, "pid", None)
        if os.name == "posix" and process_pid is not None:
            os.killpg(process_pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()


def run_bounded_help(
    path: Path,
    output_path: Path,
    *,
    require_isolation: bool = False,
) -> HelpProbeResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [str(path), "--help"]
    working_directory = path.parent
    if require_isolation:
        bubblewrap = shutil.which("bwrap") if platform.system() == "Linux" else None
        if bubblewrap is None:
            return HelpProbeResult(
                status=HelpProbeStatus.FAILED,
                error="help probe isolation is unavailable",
            )
        command = [
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-net",
            "--ro-bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            "/tmp",
            "--chdir",
            str(path.parent),
            str(path),
            "--help",
        ]
        working_directory = Path("/")
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=working_directory,
            env=_safe_environment(),
            start_new_session=os.name == "posix",
            shell=False,
        )
    except OSError as exc:
        return HelpProbeResult(status=HelpProbeStatus.FAILED, error=str(exc))
    assert process.stdout is not None
    output_queue: queue.Queue[bytes | OSError | None] = queue.Queue(maxsize=4)

    def read_output() -> None:
        try:
            for block in iter(lambda: process.stdout.read(8192), b""):
                output_queue.put(block)
        except OSError as exc:
            output_queue.put(exc)
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    retained = bytearray()
    total = 0
    output_limited = False
    timed_out = False
    read_error: str | None = None
    deadline = time.monotonic() + HELP_TIMEOUT_S
    while True:
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            timed_out = True
            _terminate_process(process)
            break
        try:
            item = output_queue.get(timeout=min(remaining_s, 0.1))
        except queue.Empty:
            continue
        if item is None:
            break
        if isinstance(item, OSError):
            read_error = str(item)
            _terminate_process(process)
            break
        total += len(item)
        remaining_bytes = max(0, MAX_HELP_BYTES - len(retained))
        retained.extend(item[:remaining_bytes])
        if total > MAX_HELP_BYTES:
            output_limited = True
            _terminate_process(process)
            break
    try:
        returncode = process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _terminate_process(process)
        returncode = process.returncode
        read_error = read_error or str(exc)
    output_path.write_bytes(bytes(retained))
    if timed_out:
        status = HelpProbeStatus.TIMED_OUT
    elif output_limited:
        status = HelpProbeStatus.OUTPUT_LIMIT
    elif read_error is not None:
        status = HelpProbeStatus.FAILED
    elif returncode == 0:
        status = HelpProbeStatus.SUCCEEDED
    else:
        status = HelpProbeStatus.FAILED
    return HelpProbeResult(
        status=status,
        output_ref=None,
        exit_code=returncode,
        output_bytes=total,
        truncated=output_limited,
        error=(
            read_error
            if read_error is not None
            else f"help exited with {returncode}"
            if status == HelpProbeStatus.FAILED
            else None
        ),
    )


def _evidence_text(path: Path, text_cache: Mapping[Path, str]) -> str | None:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved in text_cache:
        return text_cache[resolved]
    return _read_bounded_text(path)


def _extract_document_evidence(
    paths: Iterable[Path], text_cache: Mapping[Path, str]
) -> tuple[list[str], list[str], set[str]]:
    commands: set[str] = set()
    parameters: set[str] = set()
    protocols: set[str] = set()
    for path in paths:
        text = _evidence_text(path, text_cache)
        if not text:
            continue
        parameters.update(re.findall(r"(?<!\w)--[a-zA-Z0-9][a-zA-Z0-9_-]*", text))
        protocols.update(extract_protocols(text))
        for line in text.splitlines():
            stripped = line.strip().lstrip("$>").strip()
            if len(stripped) <= 300 and re.search(r"\b(robotctl|ros2|launch|--help)\b", stripped):
                commands.add(stripped)
            if len(commands) >= 100:
                break
    return sorted(commands)[:100], sorted(parameters)[:500], protocols


def _extract_help_summary(text: str) -> tuple[list[str], list[str], list[str]]:
    usage: list[str] = []
    parameters = sorted(set(re.findall(r"(?<!\w)--[a-zA-Z0-9][a-zA-Z0-9_-]*", text)))
    subcommands: set[str] = set()
    in_commands = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(?i)^usage\s*:", stripped) and len(stripped) <= 500:
            usage.append(stripped)
        if re.match(r"(?i)^(commands?|subcommands?|positional arguments?)\s*:$", stripped):
            in_commands = True
            continue
        if in_commands:
            if not stripped:
                continue
            if line[:1] not in {" ", "\t"}:
                in_commands = False
                continue
            token = stripped.split(maxsplit=1)[0].strip("{},")
            if token.startswith("{") and token.endswith("}"):
                subcommands.update(part for part in token[1:-1].split(",") if part)
            elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", token):
                subcommands.add(token)
    return usage[:20], parameters[:500], sorted(subcommands)[:200]


def _ast_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _ast_keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _ast_string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _launch_configurations(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    return {
        value
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and _ast_call_name(child.func) == "LaunchConfiguration"
        and child.args
        and (value := _ast_string(child.args[0]))
    }


def _literal_cli_arguments(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value.startswith("--")
    }


def _python_remappings(node: ast.AST | None) -> set[tuple[str, str]]:
    if node is None:
        return set()
    remappings: set[tuple[str, str]] = set()
    for child in ast.walk(node):
        if not isinstance(child, (ast.List, ast.Tuple)) or len(child.elts) != 2:
            continue
        source, target = (_ast_string(item) for item in child.elts)
        if source and target:
            remappings.add((source, target))
    return remappings


def _python_conditions(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    kind = _ast_call_name(node.func) if isinstance(node, ast.Call) else None
    prefix = "unless" if kind == "UnlessCondition" else "if"
    return {f"{prefix}:{name}" for name in _launch_configurations(node)}


def _python_urdf_references(node: ast.AST | None) -> set[str]:
    """Extract literal/package URDF references without evaluating Python expressions."""
    if node is None:
        return set()
    references: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value.lower().endswith((".urdf", ".xacro")):
                references.add(child.value)
        if not isinstance(child, ast.Call) or _ast_call_name(child.func) != "join":
            continue
        package: str | None = None
        parts: list[str] = []
        for argument in child.args:
            if (
                isinstance(argument, ast.Call)
                and _ast_call_name(argument.func) == "get_package_share_directory"
                and argument.args
            ):
                package = _ast_string(argument.args[0])
                continue
            if value := _ast_string(argument):
                parts.append(value)
        if package and parts and parts[-1].lower().endswith((".urdf", ".xacro")):
            references.add(f"package://{package}/{'/'.join(parts)}")
    package_references = {
        Path(reference).name for reference in references if reference.startswith("package://")
    }
    return {
        reference
        for reference in references
        if reference.startswith("package://") or Path(reference).name not in package_references
    }


def _python_launch_file_references(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    references: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value.lower().endswith((".launch.py", ".launch.xml")):
                references.add(child.value)
        if not isinstance(child, ast.Call) or _ast_call_name(child.func) != "join":
            continue
        package: str | None = None
        parts: list[str] = []
        for argument in child.args:
            if (
                isinstance(argument, ast.Call)
                and _ast_call_name(argument.func) == "get_package_share_directory"
                and argument.args
            ):
                package = _ast_string(argument.args[0])
                continue
            if value := _ast_string(argument):
                parts.append(value)
        if package and parts and parts[-1].lower().endswith((".launch.py", ".launch.xml")):
            references.add(f"package://{package}/{'/'.join(parts)}")
    package_names = {
        Path(reference).name for reference in references if reference.startswith("package://")
    }
    return {
        reference
        for reference in references
        if reference.startswith("package://") or Path(reference).name not in package_names
    }


def _python_launch_metadata(tree: ast.AST) -> tuple[dict[str, str | None], set[str]]:
    defaults: dict[str, str | None] = {}
    includes: set[str] = set()
    for child in ast.walk(tree):
        if not isinstance(child, ast.Call):
            continue
        kind = _ast_call_name(child.func)
        if kind == "DeclareLaunchArgument" and child.args:
            name = _ast_string(child.args[0])
            if name:
                defaults[name] = _ast_string(_ast_keyword(child, "default_value"))
        elif kind == "IncludeLaunchDescription":
            includes.update(_python_launch_file_references(child))
    return defaults, includes


def _record_launch_declaration(
    evidence: dict[str, dict[str, Any]],
    *,
    path: Path,
    executable: str,
    package: str | None,
    node_name: str | None,
    arguments: set[str],
    remappings: set[tuple[str, str]],
    conditions: set[str],
    urdf_references: set[str],
    argument_defaults: dict[str, str | None] | None = None,
    included_launch_files: set[str] | None = None,
) -> None:
    record = evidence.setdefault(
        executable,
        {
            "references": set(),
            "packages": set(),
            "nodes": set(),
            "arguments": set(),
            "remappings": set(),
            "conditions": set(),
            "urdf_references": set(),
            "argument_defaults": {},
            "included_launch_files": set(),
        },
    )
    record["references"].add(str(path))
    if package:
        record["packages"].add(package)
    if node_name:
        record["nodes"].add(node_name)
    record["arguments"].update(arguments)
    record["remappings"].update(remappings)
    record["conditions"].update(conditions)
    record["urdf_references"].update(urdf_references)
    record["argument_defaults"].update(argument_defaults or {})
    record["included_launch_files"].update(included_launch_files or set())


def _extract_python_launch_evidence(
    path: Path,
    text: str,
    evidence: dict[str, dict[str, Any]],
) -> None:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return
    argument_defaults, included_launch_files = _python_launch_metadata(tree)
    for child in ast.walk(tree):
        if not isinstance(child, ast.Call) or _ast_call_name(child.func) not in {
            "Node",
            "ComposableNode",
        }:
            continue
        executable = _ast_string(_ast_keyword(child, "executable"))
        if not executable:
            continue
        arguments_node = _ast_keyword(child, "arguments")
        condition_node = _ast_keyword(child, "condition")
        condition_configurations = _launch_configurations(condition_node)
        _record_launch_declaration(
            evidence,
            path=path,
            executable=executable,
            package=_ast_string(_ast_keyword(child, "package")),
            node_name=_ast_string(_ast_keyword(child, "name")),
            arguments=(
                _literal_cli_arguments(arguments_node)
                | (_launch_configurations(child) - condition_configurations)
            ),
            remappings=_python_remappings(_ast_keyword(child, "remappings")),
            conditions=_python_conditions(condition_node),
            urdf_references=_python_urdf_references(arguments_node),
            argument_defaults=argument_defaults,
            included_launch_files=included_launch_files,
        )


def _extract_xml_launch_evidence(
    path: Path,
    text: str,
    evidence: dict[str, dict[str, Any]],
) -> None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    if root.tag.rsplit("}", 1)[-1] != "launch":
        return
    argument_defaults = {
        node.attrib["name"]: node.attrib.get("default")
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "arg" and node.attrib.get("name")
    }
    included_launch_files = {
        node.attrib["file"]
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "include" and node.attrib.get("file")
    }
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "node":
            continue
        executable = node.attrib.get("exec") or node.attrib.get("executable")
        if not executable:
            continue
        remappings = {
            (source, target)
            for child in node
            if child.tag.rsplit("}", 1)[-1] == "remap"
            and (source := child.attrib.get("from"))
            and (target := child.attrib.get("to"))
        }
        _record_launch_declaration(
            evidence,
            path=path,
            executable=executable,
            package=node.attrib.get("pkg") or node.attrib.get("package"),
            node_name=node.attrib.get("name"),
            arguments=set(),
            remappings=remappings,
            conditions={f"if:{node.attrib['if']}" for _ in [0] if node.attrib.get("if")}
            | {f"unless:{node.attrib['unless']}" for _ in [0] if node.attrib.get("unless")},
            urdf_references=set(),
            argument_defaults=argument_defaults,
            included_launch_files=included_launch_files,
        )


def _extract_launch_evidence(
    paths: Iterable[Path], text_cache: Mapping[Path, str]
) -> dict[str, dict[str, Any]]:
    """Statically parse launch declarations without importing or executing launch files."""
    evidence: dict[str, dict[str, Any]] = {}
    for path in paths:
        text = _evidence_text(path, text_cache)
        if not text:
            continue
        if path.name.endswith(".launch.py"):
            _extract_python_launch_evidence(path, text, evidence)
        elif path.name.endswith(".launch.xml"):
            _extract_xml_launch_evidence(path, text, evidence)
    return evidence


def _usable_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_keys = (
        "build_systems",
        "packages",
        "entrypoints",
        "languages",
        "build_targets",
        "manifest_digests",
    )
    return [
        project
        for project in projects
        if project.get("file_count_scanned", 0) > 0
        and any(project.get(key) for key in evidence_keys)
    ]


def _mode(
    projects: list[dict[str, Any]],
    docs: list[Path],
    executable_artifacts: list[Path],
    *,
    probe_observed: bool,
) -> DiscoveryMode:
    if executable_artifacts and docs:
        return DiscoveryMode(
            level=DiscoveryModeLevel.ARTIFACT_DOC,
            confidence=Confidence.MEDIUM,
            reason=(
                "build/deployed artifacts and documentation are primary; probe evidence is "
                "correlated and source is supporting only"
                if probe_observed
                else "build/deployed artifacts and documentation are primary; probe evidence "
                "was not observed and source is supporting only"
            ),
        )
    if executable_artifacts:
        return DiscoveryMode(
            level=DiscoveryModeLevel.BINARY_ONLY,
            confidence=Confidence.MEDIUM if probe_observed else Confidence.LOW,
            reason=(
                "build/deployed artifact and probe evidence are primary; documentation is "
                "missing and source is supporting only"
                if probe_observed
                else "only build/deployed artifact evidence was collected; documentation and "
                "probe evidence are missing and source is supporting only"
            ),
        )
    if docs or probe_observed:
        return DiscoveryMode(
            level=DiscoveryModeLevel.DOC_PROBE,
            confidence=Confidence.MEDIUM if docs and probe_observed else Confidence.LOW,
            reason=(
                "documentation and probe evidence are primary; no executable build/deployed "
                "artifact was found and source is supporting only"
                if docs and probe_observed
                else "documentation is primary; no executable build/deployed artifact or "
                "active probe evidence was found and source is supporting only"
                if docs
                else "probe evidence is primary; no executable build/deployed artifact or "
                "documentation was found and source is supporting only"
            ),
        )
    source_note = (
        " Source evidence was collected but is supporting-only and cannot establish a mode."
        if projects
        else ""
    )
    raise ValueError(
        "no usable primary evidence was collected; provide a build/install artifact, readable "
        "documentation/launch evidence, or an observed read-only probe." + source_note
    )


def _source_analysis(projects: list[dict[str, Any]]) -> SourceAnalysis:
    return SourceAnalysis(
        available=bool(projects),
        projects=sorted({project["root"] for project in projects}),
        languages=sorted(
            {language for project in projects for language in project.get("languages", [])}
        ),
        build_systems=sorted(
            {system for project in projects for system in project.get("build_systems", [])}
        ),
        build_targets=sorted(
            {target for project in projects for target in project.get("build_targets", [])}
        ),
        entrypoint_symbols=sorted(
            {
                entry["target"]
                for project in projects
                for entry in project.get("entrypoints", [])
                if entry.get("target")
            }
        ),
        declared_dependencies=sorted(
            {
                dependency
                for project in projects
                for dependency in project.get("declared_dependencies", [])
            }
        ),
        dependency_declarations=[
            declaration
            for project in projects
            for declaration in project.get("dependency_declarations", [])
        ],
        parameters=[
            parameter
            for project in projects
            for parameter in project.get("semantic_candidates", [])
        ],
        source_revisions=sorted(
            {revision for project in projects if (revision := project.get("source_revision"))}
        ),
        manifest_sha256={
            str(Path(project["root"]) / relative): digest
            for project in projects
            for relative, digest in project.get("manifest_digests", {}).items()
        },
        evidence_refs=sorted({project["root"] for project in projects}),
    )


def _name_keys(value: str) -> set[str]:
    name = Path(value).name.casefold()
    return {name, Path(name).stem}


def _evidence_files_for_executable(
    name: str,
    paths: Sequence[Path],
    *,
    text_cache: Mapping[Path, str],
    allow_single_executable_fallback: bool,
    inspect_text: bool,
) -> list[Path]:
    """Associate supplemental evidence without copying it to every executable."""
    keys = {key.casefold() for key in _name_keys(name) if len(key) >= 3}
    matches: list[Path] = []
    for path in paths:
        path_keys = _name_keys(path.name)
        if keys & path_keys:
            matches.append(path)
            continue
        if inspect_text:
            text = _evidence_text(path, text_cache)
            if text and any(key in text.casefold() for key in keys):
                matches.append(path)
    if matches:
        return list(dict.fromkeys(matches))
    return list(paths) if allow_single_executable_fallback else []


def _project_executable_names(project: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for entrypoint in project.get("entrypoints", []):
        if entrypoint.get("name"):
            names.add(str(entrypoint["name"]))
        target = str(entrypoint.get("target", "")).split(":", 1)[0]
        if target:
            names.add(target.rsplit(".", 1)[-1])
    names.update(str(target) for target in project.get("build_targets", []))
    names.update(str(package) for package in project.get("packages", []))
    return names


def _projects_for_executable(
    name: str,
    projects: list[dict[str, Any]],
    *,
    allow_single_project_fallback: bool,
) -> list[dict[str, Any]]:
    requested_keys = _name_keys(name)
    matched = [
        project
        for project in projects
        if any(
            requested_keys & _name_keys(candidate)
            for candidate in _project_executable_names(project)
        )
    ]
    if matched:
        return matched
    if allow_single_project_fallback and len(projects) == 1:
        return projects
    return []


def _interface_source_matches(source: str, candidates: set[str]) -> bool:
    normalized = source.replace("\\", "/").casefold()
    source_path = Path(normalized)
    source_keys = _name_keys(source_path.name) | _name_keys(source_path.stem)
    normalized_candidates = {
        candidate.replace("\\", "/").casefold().lstrip("./")
        for candidate in candidates
        if candidate
    }
    if any(
        "/" in candidate and normalized.endswith(candidate) for candidate in normalized_candidates
    ):
        return True
    simple_candidates = {candidate for candidate in normalized_candidates if "/" not in candidate}
    return bool(
        source_keys & {key for candidate in simple_candidates for key in _name_keys(candidate)}
    )


def _project_interfaces_for_executable(
    name: str,
    project: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    interfaces = list(project.get("ros_interfaces", []))
    if not interfaces:
        return [], 0
    requested_keys = _name_keys(name)
    matching_entrypoints = [
        entrypoint
        for entrypoint in project.get("entrypoints", [])
        if requested_keys & _name_keys(str(entrypoint.get("name", "")))
        or requested_keys & _name_keys(str(entrypoint.get("target", "")))
    ]
    source_candidates: set[str] = set()
    for entrypoint in matching_entrypoints:
        source_candidates.update(str(item) for item in entrypoint.get("source_files", []))
        target = str(entrypoint.get("target", "")).split(":", 1)[0].strip()
        if target and entrypoint.get("source") != "cmake":
            module_path = target.replace(".", "/")
            source_candidates.update({f"{module_path}.py", f"{module_path}/__init__.py"})
            if len(project.get("entrypoints", [])) == 1:
                source_candidates.add(f"{module_path.rsplit('/', 1)[-1]}.py")
    source_candidates.add(name)
    matched = [
        {**interface, "attribution": "SOURCE_FILE_MATCH"}
        for interface in interfaces
        if _interface_source_matches(str(interface.get("source", "")), source_candidates)
    ]
    if matched:
        return matched, len(interfaces) - len(matched)
    executable_names = _project_executable_names(project)
    if len(executable_names) == 1:
        return [
            {**interface, "attribution": "SINGLE_ENTRYPOINT_FALLBACK"} for interface in interfaces
        ], 0
    return [], len(interfaces)


def _source_interface_key(interface: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(interface.get("role", "")),
        str(interface.get("name", "")),
        str(interface.get("type", "")),
        str(interface.get("source", "")),
    )


def _ros_communication(
    executable_name: str,
    projects: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [
        _project_interfaces_for_executable(executable_name, project) for project in projects
    ]
    source_interfaces = [interface for interfaces, _ in selected for interface in interfaces]
    unattributed_count = sum(count for _, count in selected)
    return {
        # The live ROS graph is robot-global evidence. It must not be copied onto
        # every executable without process/node ownership evidence.
        "nodes": [],
        "publishers": [item for item in source_interfaces if item.get("role") == "publisher"],
        "subscribers": [item for item in source_interfaces if item.get("role") == "subscriber"],
        "services": [item for item in source_interfaces if item.get("role") == "service"],
        "clients": [item for item in source_interfaces if item.get("role") == "client"],
        "actions": [],
        "parameters": [],
        "tf_frames": [],
        "remappings": [],
        "unattributed_source_interfaces": unattributed_count,
    }


class ActiveDiscoveryAnalyzer:
    def __init__(
        self,
        *,
        inputs: ActiveDiscoveryInputs,
        projects: list[dict[str, Any]],
        ros_probe: ProbeResult,
        run_root: Path,
        artifact_prefix: str,
        evidence_text: Mapping[Path, str] | None = None,
    ) -> None:
        self.inputs = inputs.resolved()
        self.projects = projects
        self.ros_probe = ros_probe
        self.run_root = run_root
        self.artifact_prefix = artifact_prefix.rstrip("/")
        self.evidence_text = {path.resolve(): text for path, text in (evidence_text or {}).items()}

    def build(
        self,
        *,
        discovery_id: str,
        robot_id: str,
        technical_status: str,
        created_at: datetime,
    ) -> ActiveDiscoveryReport:
        usable_projects = _usable_projects(self.projects)
        build_files, build_truncated, build_warnings = walk_files(
            self.inputs.build_roots,
            limit=MAX_ACTIVE_FILES,
            skip_directories=SKIP_DIRECTORIES,
        )
        install_files, install_truncated, install_warnings = walk_files(
            self.inputs.install_roots,
            limit=MAX_ACTIVE_FILES,
            skip_directories=SKIP_DIRECTORIES,
        )
        doc_files, doc_truncated, doc_warnings = walk_files(
            self.inputs.document_roots,
            limit=MAX_ACTIVE_FILES,
            skip_directories=SUPPLEMENTAL_SKIP_DIRECTORIES,
        )
        launch_files, launch_truncated, launch_warnings = walk_files(
            self.inputs.launch_roots,
            limit=MAX_ACTIVE_FILES,
            skip_directories=SUPPLEMENTAL_SKIP_DIRECTORIES,
        )
        source_doc_files = [
            Path(project["root"]) / relative
            for project in usable_projects
            for relative in project.get("readmes", [])
        ]
        source_launch_files = [
            Path(project["root"]) / relative
            for project in usable_projects
            for relative in project.get("launch_files", [])
        ]
        structured_document_files = list(
            dict.fromkeys(
                Path(project["root"]) / relative
                for project in usable_projects
                for relative in project.get("manifest_digests", {})
                if Path(relative).name in STRUCTURED_DOCUMENT_NAMES
            )
        )
        doc_files = list(dict.fromkeys([*doc_files, *source_doc_files]))
        launch_files = list(dict.fromkeys([*launch_files, *source_launch_files]))
        doc_files = [path for path in doc_files if path.suffix.lower() in TEXT_SUFFIXES]
        launch_files = [
            path for path in launch_files if path.name.endswith((".launch.py", ".launch.xml"))
        ]
        if len(doc_files) > MAX_TEXT_EVIDENCE_FILES:
            doc_truncated = True
            doc_files = doc_files[:MAX_TEXT_EVIDENCE_FILES]
        if len(launch_files) > MAX_TEXT_EVIDENCE_FILES:
            launch_truncated = True
            launch_files = launch_files[:MAX_TEXT_EVIDENCE_FILES]
        launch_evidence = _extract_launch_evidence(launch_files, self.evidence_text)

        source_projects_by_name: dict[str, list[dict[str, Any]]] = {}
        for project in usable_projects:
            for entry in project.get("entrypoints", []):
                if name := entry.get("name"):
                    source_projects_by_name.setdefault(str(name), []).append(project)
        source_names = set(source_projects_by_name)
        declared_names = source_names | set(launch_evidence)

        explicit_paths = [path for path in self.inputs.executables if path.is_file()]
        invalid_explicit_paths = [path for path in self.inputs.executables if not path.is_file()]
        discovered_build_paths = [path for path in build_files if _looks_executable(path)]
        discovered_install_paths = [path for path in install_files if _looks_executable(path)]
        explicit_path_set = set(explicit_paths)
        build_path_set = set(discovered_build_paths)
        install_path_set = set(discovered_install_paths)
        discovered_candidates = list(
            dict.fromkeys([*explicit_paths, *discovered_install_paths, *discovered_build_paths])
        )

        def artifact_priority(path: Path) -> tuple[int, str]:
            names = {path.name, path.stem}
            if path in explicit_path_set:
                rank = 0
            elif names & declared_names:
                rank = 1
            elif path in install_path_set:
                rank = 2
            else:
                rank = 3
            return rank, str(path).casefold()

        all_discovered_paths = sorted(discovered_candidates, key=artifact_priority)
        discovered_names = {
            name for path in all_discovered_paths for name in (path.name, path.stem)
        }
        represented_declarations = declared_names & discovered_names
        declaration_reserve = min(
            MAX_REPORT_EXECUTABLES,
            len(declared_names - represented_declarations),
        )
        artifact_limit = MAX_REPORT_EXECUTABLES - declaration_reserve
        executable_truncated = len(all_discovered_paths) > artifact_limit
        all_paths = all_discovered_paths[:artifact_limit]
        if not all_paths and not source_projects_by_name:
            for project in usable_projects:
                for package in project.get("packages", []):
                    source_projects_by_name.setdefault(str(package), []).append(project)
        source_names = set(source_projects_by_name)

        global_source_analysis = _source_analysis(usable_projects)
        intermediates = [
            str(path) for path in build_files if path.suffix.lower() in INTERMEDIATE_SUFFIXES
        ][:MAX_EVIDENCE_REFS]
        configs = [
            str(path)
            for path in [*build_files, *install_files, *launch_files]
            if path.suffix.lower() in CONFIG_SUFFIXES
        ][:MAX_EVIDENCE_REFS]
        plugins = [
            str(path) for path in install_files if path.suffix.lower() in {".so", ".dll", ".dylib"}
        ][:MAX_EVIDENCE_REFS]
        runtime_observed = (
            self.inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY
            and self.ros_probe.status.value in {"SUCCEEDED", "PARTIAL"}
        )
        document_sha256 = _hash_files(doc_files[:MAX_EVIDENCE_REFS])
        launch_sha256 = _hash_files(launch_files[:MAX_EVIDENCE_REFS])
        declared_names = set(source_names) | set(launch_evidence)
        executable_name_count = len(
            {
                *[path.name for path in all_paths],
                *declared_names,
            }
        )
        allow_supplemental_fallback = executable_name_count == 1

        def launch_analysis_for(name: str) -> LaunchAnalysis:
            declared_name = name if name in launch_evidence else Path(name).stem
            record = launch_evidence.get(declared_name)
            if not record:
                return LaunchAnalysis()
            return LaunchAnalysis(
                available=True,
                references=sorted(record["references"]),
                reference_sha256={
                    reference: launch_sha256[reference]
                    for reference in sorted(record["references"])
                    if reference in launch_sha256
                },
                packages=sorted(record["packages"]),
                declared_executable=declared_name,
                nodes=sorted(record["nodes"]),
                arguments=sorted(record["arguments"]),
                argument_defaults=dict(sorted(record["argument_defaults"].items())),
                included_launch_files=sorted(record["included_launch_files"]),
                remappings=[
                    {"from": source, "to": target}
                    for source, target in sorted(record["remappings"])
                ],
                conditions=sorted(record["conditions"]),
                urdf_references=sorted(record["urdf_references"]),
            )

        executables: list[ExecutableDiscovery] = []
        help_probe_count = 0
        executable_hash_bytes = 0
        hash_warnings: list[str] = []
        for path in all_paths:
            executable_id = _stable_executable_id(path.name, path)
            explicit = path in explicit_path_set
            from_build_root = path in build_path_set
            executable_projects = _projects_for_executable(
                path.name,
                usable_projects,
                allow_single_project_fallback=False,
            )
            source_analysis = _source_analysis(executable_projects)
            ros_communication = _ros_communication(
                path.name,
                executable_projects,
            )
            source_protocols = {
                protocol
                for project in executable_projects
                for protocol in project.get("protocols", [])
            }
            executable_docs = _evidence_files_for_executable(
                path.name,
                doc_files,
                text_cache=self.evidence_text,
                allow_single_executable_fallback=allow_supplemental_fallback,
                inspect_text=True,
            )
            executable_launch_files = [
                Path(item) for item in launch_analysis_for(path.name).references
            ]
            documented_commands, documented_parameters, doc_protocols = _extract_document_evidence(
                executable_docs, self.evidence_text
            )
            launch_commands, launch_parameters, launch_protocols = _extract_document_evidence(
                executable_launch_files, self.evidence_text
            )
            documented_commands = sorted(set(documented_commands) | set(launch_commands))
            documented_parameters = sorted(set(documented_parameters) | set(launch_parameters))
            primary_protocols = doc_protocols | launch_protocols
            protocols = sorted(primary_protocols or source_protocols)
            file_format, architecture = _binary_identity(path)
            help_result = HelpProbeResult()
            executable_parameters = list(documented_parameters)
            if explicit and self.inputs.active_probe in {
                ActiveProbeMode.HELP,
                ActiveProbeMode.RUNTIME_READONLY,
            }:
                if help_probe_count >= MAX_HELP_PROBES:
                    help_result = HelpProbeResult(
                        status=HelpProbeStatus.BLOCKED_BY_POLICY,
                        error=f"per-run help probe limit is {MAX_HELP_PROBES}",
                    )
                else:
                    help_probe_count += 1
                    output_path = self.run_root / "active_probes" / f"help-{executable_id}.txt"
                    help_result = run_bounded_help(path, output_path)
                    if output_path.is_file():
                        help_result.output_ref = (
                            f"{self.artifact_prefix}/active_probes/{output_path.name}"
                        )
                        help_text = _read_bounded_text(output_path) or ""
                        usage, help_parameters, subcommands = _extract_help_summary(help_text)
                        help_result.usage = usage
                        help_result.parameters = help_parameters
                        help_result.subcommands = subcommands
                        executable_parameters = sorted(
                            set(executable_parameters) | set(help_parameters)
                        )
            hash_unresolved: list[str] = []
            try:
                executable_size = path.stat().st_size
            except OSError:
                executable_size = None
            if executable_size is None:
                sha256 = None
                hash_unresolved.append("executable size could not be read; SHA-256 omitted")
            elif executable_size > MAX_EXECUTABLE_HASH_BYTES:
                sha256 = None
                hash_unresolved.append("executable exceeds the per-file SHA-256 size limit")
            elif executable_hash_bytes + executable_size > MAX_EXECUTABLE_HASH_AGGREGATE_BYTES:
                sha256 = None
                hash_unresolved.append("per-run executable SHA-256 byte limit was reached")
            else:
                try:
                    sha256 = sha256_file(path)
                    executable_hash_bytes += executable_size
                except OSError:
                    sha256 = None
                    hash_unresolved.append("executable SHA-256 read failed")
            hash_warnings.extend(f"{path}: {warning}" for warning in hash_unresolved)
            install_root = next(
                (str(root) for root in self.inputs.install_roots if path.is_relative_to(root)),
                None,
            )
            executable_build_roots = [
                str(root) for root in self.inputs.build_roots if path.is_relative_to(root)
            ]
            executable_intermediates = _evidence_files_for_executable(
                path.name,
                [Path(item) for item in intermediates],
                text_cache=self.evidence_text,
                allow_single_executable_fallback=allow_supplemental_fallback,
                inspect_text=False,
            )
            executable_configs = _evidence_files_for_executable(
                path.name,
                [Path(item) for item in configs],
                text_cache=self.evidence_text,
                allow_single_executable_fallback=allow_supplemental_fallback,
                inspect_text=True,
            )
            executable_plugins = _evidence_files_for_executable(
                path.name,
                [Path(item) for item in plugins],
                text_cache=self.evidence_text,
                allow_single_executable_fallback=allow_supplemental_fallback,
                inspect_text=False,
            )
            launch_analysis = launch_analysis_for(path.name)
            executable_ros = dict(ros_communication)
            executable_ros["nodes"] = sorted(
                set(executable_ros.get("nodes", [])) | set(launch_analysis.nodes)
            )
            executable_ros["remappings"] = launch_analysis.remappings
            executables.append(
                ExecutableDiscovery(
                    executable_id=executable_id,
                    name=path.name,
                    path=str(path),
                    origin=(
                        "EXPLICIT"
                        if explicit
                        else "DISCOVERED_BUILD_ARTIFACT"
                        if from_build_root
                        else "DISCOVERED_ARTIFACT"
                    ),
                    sha256=sha256,
                    file_format=file_format,
                    architecture=architecture,
                    binary_dependencies=inspect_binary_dependencies(path),
                    version={"value": None, "source": None, "confidence": "LOW"},
                    source_analysis=source_analysis,
                    artifact_analysis=ArtifactAnalysis(
                        install_root=install_root,
                        build_roots=executable_build_roots,
                        intermediate_outputs=[str(item) for item in executable_intermediates],
                        plugins=[str(item) for item in executable_plugins],
                        configuration_files=[str(item) for item in executable_configs],
                    ),
                    documentation_analysis=DocumentationAnalysis(
                        available=bool(executable_docs),
                        references=[str(item) for item in executable_docs[:MAX_EVIDENCE_REFS]],
                        reference_sha256={
                            str(item): document_sha256[str(item)]
                            for item in executable_docs[:MAX_EVIDENCE_REFS]
                            if str(item) in document_sha256
                        },
                        documented_commands=documented_commands,
                        documented_parameters=documented_parameters,
                    ),
                    launch_analysis=launch_analysis,
                    invocation=InvocationAnalysis(
                        entrypoint=str(path),
                        arguments=sorted(
                            set(executable_parameters) | set(launch_analysis.arguments)
                        ),
                        subcommands=help_result.subcommands,
                        startup_sequence=[
                            f"declared by {reference}" for reference in launch_analysis.references
                        ],
                        help_probe=help_result,
                    ),
                    communication=CommunicationAnalysis(
                        ros=executable_ros,
                        network={
                            "protocols": protocols,
                            "listen_endpoints": [],
                            "remote_endpoints": [],
                            "authentication": None,
                            "schemas": [],
                        },
                        ipc={"unix_sockets": [], "shared_memory": [], "dbus": []},
                        hardware_bus={"serial": [], "can": [], "i2c": [], "spi": []},
                        confidence=(
                            Confidence.MEDIUM
                            if executable_docs
                            or launch_analysis.available
                            or help_result.status == HelpProbeStatus.SUCCEEDED
                            else Confidence.LOW
                        ),
                        evidence_refs=[
                            str(item) for item in [*executable_docs, *executable_launch_files][:100]
                        ],
                    ),
                    dependencies={
                        "declared": source_analysis.declared_dependencies,
                        "installed": [],
                        "missing": [],
                        "unknown": [],
                        "version_conflicts": [],
                    },
                    safety={
                        "access": "read",
                        "risk": "R0",
                        "possible_side_effects": (
                            ["explicit executable was invoked with --help"]
                            if help_result.status
                            not in {
                                HelpProbeStatus.NOT_PROBED,
                                HelpProbeStatus.BLOCKED_BY_POLICY,
                            }
                            else []
                        ),
                        "device_access": [],
                        "network_access": [],
                        "privilege_required": False,
                        "motion_possible": False,
                    },
                    evidence={
                        "artifacts": [str(path)],
                        "documentation": [str(item) for item in executable_docs[:100]],
                        "help": [help_result.output_ref] if help_result.output_ref else [],
                        "source_support": source_analysis.evidence_refs,
                        "conflicts": [],
                        "unresolved": hash_unresolved,
                    },
                )
            )
        for name in sorted(declared_names):
            if len(executables) >= MAX_REPORT_EXECUTABLES:
                executable_truncated = True
                break
            if any(
                executable.name == name or Path(executable.name).stem == Path(name).stem
                for executable in executables
            ):
                continue
            launch_analysis = launch_analysis_for(name)
            origin = "SOURCE_DECLARED" if name in source_names else "LAUNCH_DECLARED"
            executable_projects = source_projects_by_name.get(name) or _projects_for_executable(
                name,
                usable_projects,
                allow_single_project_fallback=False,
            )
            source_analysis = _source_analysis(executable_projects)
            ros_communication = _ros_communication(
                name,
                executable_projects,
            )
            source_protocols = {
                protocol
                for project in executable_projects
                for protocol in project.get("protocols", [])
            }
            executable_docs = _evidence_files_for_executable(
                name,
                doc_files,
                text_cache=self.evidence_text,
                allow_single_executable_fallback=allow_supplemental_fallback,
                inspect_text=True,
            )
            executable_launch_files = [Path(item) for item in launch_analysis.references]
            documented_commands, documented_parameters, doc_protocols = _extract_document_evidence(
                executable_docs, self.evidence_text
            )
            launch_commands, launch_parameters, launch_protocols = _extract_document_evidence(
                executable_launch_files, self.evidence_text
            )
            documented_commands = sorted(set(documented_commands) | set(launch_commands))
            documented_parameters = sorted(set(documented_parameters) | set(launch_parameters))
            primary_protocols = doc_protocols | launch_protocols
            protocols = sorted(primary_protocols or source_protocols)
            executable_ros = dict(ros_communication)
            executable_ros["nodes"] = sorted(
                set(executable_ros.get("nodes", [])) | set(launch_analysis.nodes)
            )
            executable_ros["remappings"] = launch_analysis.remappings
            executables.append(
                ExecutableDiscovery(
                    executable_id=_stable_executable_id(name),
                    name=name,
                    origin=origin,
                    source_analysis=source_analysis,
                    documentation_analysis=DocumentationAnalysis(
                        available=bool(executable_docs),
                        references=[str(path) for path in executable_docs[:MAX_EVIDENCE_REFS]],
                        reference_sha256={
                            str(path): document_sha256[str(path)]
                            for path in executable_docs[:MAX_EVIDENCE_REFS]
                            if str(path) in document_sha256
                        },
                        documented_commands=documented_commands,
                        documented_parameters=documented_parameters,
                    ),
                    launch_analysis=launch_analysis,
                    invocation=InvocationAnalysis(
                        entrypoint=name,
                        arguments=sorted(
                            set(documented_parameters) | set(launch_analysis.arguments)
                        ),
                        startup_sequence=[
                            f"declared by {reference}" for reference in launch_analysis.references
                        ],
                    ),
                    communication=CommunicationAnalysis(
                        ros=executable_ros,
                        network={"protocols": protocols},
                        confidence=(
                            Confidence.MEDIUM
                            if executable_docs or launch_analysis.available
                            else Confidence.LOW
                        ),
                    ),
                    dependencies={
                        "declared": source_analysis.declared_dependencies,
                        "installed": [],
                        "missing": [],
                        "unknown": [],
                        "version_conflicts": [],
                    },
                    safety={
                        "access": "unknown",
                        "risk": "R0",
                        "possible_side_effects": [],
                        "device_access": [],
                        "network_access": [],
                        "privilege_required": False,
                        "motion_possible": False,
                    },
                    evidence={
                        "artifacts": [],
                        "documentation": [str(item) for item in executable_docs[:100]],
                        "help": [],
                        "source_support": source_analysis.evidence_refs,
                        "conflicts": [],
                        "unresolved": ["compiled executable path was not supplied or found"],
                    },
                )
            )

        source_truncated = any(project.get("scan_truncated", False) for project in self.projects)
        source_unusable = bool(self.projects) and not usable_projects
        help_requested = self.inputs.active_probe in {
            ActiveProbeMode.HELP,
            ActiveProbeMode.RUNTIME_READONLY,
        }
        help_results = [
            executable.invocation.help_probe
            for executable in executables
            if executable.origin == "EXPLICIT"
        ]
        help_incomplete = any(result.status != HelpProbeStatus.SUCCEEDED for result in help_results)
        coverage = {
            "source": CoverageRecord(
                status=(
                    CoverageStatus.PARTIAL
                    if source_truncated or source_unusable
                    else CoverageStatus.COMPLETE
                    if usable_projects
                    else CoverageStatus.NOT_PROVIDED
                ),
                records=len(usable_projects),
                truncated=source_truncated,
                warnings=(
                    ["source roots contained no usable source or manifest evidence"]
                    if source_unusable
                    else []
                ),
            ),
            "artifacts": CoverageRecord(
                status=(
                    CoverageStatus.PARTIAL
                    if build_truncated
                    or install_truncated
                    or executable_truncated
                    or build_warnings
                    or install_warnings
                    or invalid_explicit_paths
                    else CoverageStatus.COMPLETE
                    if self.inputs.build_roots or self.inputs.install_roots or explicit_paths
                    else CoverageStatus.NOT_PROVIDED
                ),
                records=len(build_files) + len(install_files) + len(explicit_paths),
                truncated=build_truncated or install_truncated or executable_truncated,
                warnings=[
                    *build_warnings,
                    *install_warnings,
                    *[
                        f"explicit executable does not exist or is not a file: {path}"
                        for path in invalid_explicit_paths
                    ],
                ],
            ),
            "documentation": CoverageRecord(
                status=(
                    CoverageStatus.PARTIAL
                    if doc_truncated or doc_warnings
                    else CoverageStatus.COMPLETE
                    if doc_files or structured_document_files
                    else CoverageStatus.NOT_PROVIDED
                ),
                records=len(doc_files) + len(structured_document_files),
                truncated=doc_truncated,
                warnings=doc_warnings,
            ),
            "launch": CoverageRecord(
                status=(
                    CoverageStatus.PARTIAL
                    if launch_truncated or launch_warnings
                    else CoverageStatus.COMPLETE
                    if launch_files
                    else CoverageStatus.NOT_PROVIDED
                ),
                records=len(launch_files),
                truncated=launch_truncated,
                warnings=launch_warnings,
            ),
            "help_probes": CoverageRecord(
                status=(
                    CoverageStatus.NOT_PROBED
                    if not help_requested
                    else CoverageStatus.NOT_PROVIDED
                    if not explicit_paths
                    else CoverageStatus.PARTIAL
                    if help_incomplete
                    else CoverageStatus.COMPLETE
                ),
                records=sum(
                    result.status != HelpProbeStatus.BLOCKED_BY_POLICY for result in help_results
                ),
                truncated=any(
                    result.status == HelpProbeStatus.BLOCKED_BY_POLICY for result in help_results
                ),
                warnings=[
                    f"{result.status.value}: {result.error}"
                    for result in help_results
                    if result.status != HelpProbeStatus.SUCCEEDED
                ],
            ),
            "ros_runtime": CoverageRecord(
                status=(
                    CoverageStatus.OBSERVED
                    if runtime_observed
                    else CoverageStatus.UNAVAILABLE
                    if self.inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY
                    else CoverageStatus.NOT_PROBED
                ),
                records=sum(
                    len(self.ros_probe.data.get(key, []))
                    for key in ("nodes", "topics", "services", "actions")
                )
                if runtime_observed
                else 0,
            ),
        }
        probe_observed = runtime_observed or any(
            result.status == HelpProbeStatus.SUCCEEDED for result in help_results
        )
        mode = _mode(
            usable_projects,
            list(dict.fromkeys([*doc_files, *structured_document_files, *launch_files])),
            all_discovered_paths,
            probe_observed=probe_observed,
        )
        all_source_interfaces = {
            _source_interface_key(interface): interface
            for project in usable_projects
            for interface in project.get("ros_interfaces", [])
            if isinstance(interface, dict)
        }
        attributed_interface_keys = {
            _source_interface_key(interface)
            for executable in executables
            for role in ("publishers", "subscribers", "services", "clients")
            for interface in executable.communication.ros.get(role, [])
            if isinstance(interface, dict) and interface.get("source")
        }
        unattributed_source_interfaces = [
            all_source_interfaces[key]
            for key in sorted(all_source_interfaces.keys() - attributed_interface_keys)
        ]
        warnings = [
            *build_warnings,
            *install_warnings,
            *doc_warnings,
            *launch_warnings,
            *hash_warnings,
        ]
        warnings.extend(
            f"explicit executable does not exist or is not a file: {path}"
            for path in invalid_explicit_paths
        )
        if source_unusable:
            warnings.append("source roots contained no usable source or manifest evidence")
        if usable_projects:
            warnings.append(
                "source findings are supporting-only; build/deployed artifacts, documentation, "
                "and probe evidence take precedence"
            )
        if executable_truncated:
            warnings.append(
                f"executable report limit reached: {MAX_REPORT_EXECUTABLES}; "
                "artifact coverage is partial"
            )
        if len(unattributed_source_interfaces) > MAX_UNATTRIBUTED_INTERFACES:
            warnings.append(
                f"unattributed source interface limit reached: "
                f"{MAX_UNATTRIBUTED_INTERFACES} of {len(unattributed_source_interfaces)} retained"
            )
        if len(explicit_paths) > MAX_HELP_PROBES and self.inputs.active_probe in {
            ActiveProbeMode.HELP,
            ActiveProbeMode.RUNTIME_READONLY,
        }:
            warnings.append(
                f"help probe limit reached: {MAX_HELP_PROBES}; remaining explicit "
                "executables were not run"
            )
        if mode.level == DiscoveryModeLevel.BINARY_ONLY:
            warnings.append(
                "binary-only discovery is heuristic; all capability candidates require "
                "independent validation"
            )
        if self.inputs.active_probe in {ActiveProbeMode.HELP, ActiveProbeMode.RUNTIME_READONLY}:
            warnings.append(
                "--help was allowed only for explicitly supplied executables; "
                "launch files were not run"
            )
        effective_technical_status = derive_discovery_status(
            DiscoveryStatus(technical_status),
            partial_coverage=any(
                record.status == CoverageStatus.PARTIAL for record in coverage.values()
            ),
        )
        return ActiveDiscoveryReport(
            discovery_id=discovery_id,
            robot_id=robot_id,
            technical_status=effective_technical_status.value,
            discovery_mode=mode,
            evidence_policy=EvidencePolicy(),
            inputs=self.inputs.model_dump(mode="json"),
            coverage=coverage,
            executables=executables,
            unattributed_source_interfaces=unattributed_source_interfaces[
                :MAX_UNATTRIBUTED_INTERFACES
            ],
            dependency_summary={
                "report_ref": None,
                "candidates": [],
                "declared": global_source_analysis.declared_dependencies,
                "required": [],
                "installed": [],
                "missing": [],
                "unknown": [],
                "conflicting": [],
                "unresolved_executables": [],
            },
            unknowns=(["no executable entrypoint could be identified"] if not executables else []),
            warnings=sorted(set(warnings)),
            created_at=created_at,
        )


def render_active_discovery_markdown(report: ActiveDiscoveryReport) -> str:
    def summarize(values: Iterable[Any], *, limit: int = 20) -> str:
        rendered: list[str] = []
        for value in list(values)[:limit]:
            if isinstance(value, dict):
                rendered.append(
                    str(value.get("name") or value.get("operation") or value.get("path") or value)
                )
            else:
                rendered.append(str(value))
        return ", ".join(rendered) or "none"

    lines = [
        f"# Active discovery report: {report.robot_id}",
        "",
        f"- Discovery ID: `{report.discovery_id}`",
        f"- Technical status: `{report.technical_status}`",
        f"- Mode: `{report.discovery_mode.level.value}`",
        f"- Confidence: `{report.discovery_mode.confidence.value}`",
        f"- Primary evidence order: `{' > '.join(report.evidence_policy.primary_order)}`",
        f"- Source role: `{report.evidence_policy.source_role}`",
        "",
        "## Coverage",
        "",
        "| Area | Status | Records | Truncated |",
        "|---|---:|---:|---:|",
    ]
    for name, coverage in report.coverage.items():
        lines.append(
            f"| {name} | {coverage.status.value} | {coverage.records} | "
            f"{'yes' if coverage.truncated else 'no'} |"
        )
    lines.extend(["", "## Executables", ""])
    if not report.executables:
        lines.append("No executable entrypoint was identified.")
    for executable in report.executables:
        lines.extend(
            [
                f"### {executable.name}",
                "",
                f"- Path: `{executable.path or 'not resolved'}`",
                f"- Origin: `{executable.origin}`",
                f"- Format / architecture: `{executable.file_format or 'unknown'}` / "
                f"`{executable.architecture or 'unknown'}`",
                f"- SHA-256: `{executable.sha256 or 'not collected'}`",
                f"- Help probe: `{executable.invocation.help_probe.status.value}`",
                f"- Invocation: `{executable.invocation.entrypoint or 'unknown'}`",
                f"- Arguments: {summarize(executable.invocation.arguments)}",
                f"- Subcommands: {summarize(executable.invocation.subcommands)}",
                f"- Source projects: {', '.join(executable.source_analysis.projects) or 'none'}",
                f"- Source languages: {summarize(executable.source_analysis.languages)}",
                f"- Build systems / targets: "
                f"{summarize(executable.source_analysis.build_systems)} / "
                f"{summarize(executable.source_analysis.build_targets)}",
                f"- Declared dependencies: "
                f"{', '.join(executable.source_analysis.declared_dependencies) or 'none'}",
                f"- Documentation references: {len(executable.documentation_analysis.references)}",
                f"- Launch packages / nodes: "
                f"{summarize(executable.launch_analysis.packages)} / "
                f"{summarize(executable.launch_analysis.nodes)}",
                f"- Launch conditions / arguments: "
                f"{summarize(executable.launch_analysis.conditions)} / "
                f"{summarize(executable.launch_analysis.arguments)}",
                f"- Launch URDF references: "
                f"{summarize(executable.launch_analysis.urdf_references)}",
                f"- ROS nodes: {summarize(executable.communication.ros.get('nodes', []))}",
                f"- ROS publishers: "
                f"{summarize(executable.communication.ros.get('publishers', []))}",
                f"- ROS subscribers: "
                f"{summarize(executable.communication.ros.get('subscribers', []))}",
                f"- ROS services / actions: "
                f"{summarize(executable.communication.ros.get('services', []))} / "
                f"{summarize(executable.communication.ros.get('actions', []))}",
                f"- Network protocols: "
                f"{', '.join(executable.communication.network.get('protocols', [])) or 'none'}",
                f"- Network listen / remote endpoints: "
                f"{summarize(executable.communication.network.get('listen_endpoints', []))} / "
                f"{summarize(executable.communication.network.get('remote_endpoints', []))}",
                f"- Safety risk / motion possible: "
                f"`{executable.safety.get('risk', 'unknown')}` / "
                f"`{executable.safety.get('motion_possible', 'unknown')}`",
                f"- Unresolved evidence: {summarize(executable.evidence.get('unresolved', []))}",
                "",
            ]
        )
    dependency_candidates = {
        candidate.get("candidate_id"): candidate
        for candidate in report.dependency_summary.get("candidates", [])
    }

    def dependency_names(key: str) -> list[str]:
        return [
            str(dependency_candidates.get(candidate_id, {}).get("name", candidate_id))
            for candidate_id in report.dependency_summary.get(key, [])
        ]

    lines.extend(
        [
            "## Unattributed source interfaces",
            "",
            f"- Count: {len(report.unattributed_source_interfaces)}",
            f"- Candidates: {summarize(report.unattributed_source_interfaces, limit=100)}",
            "",
            "## Dependency summary",
            "",
            f"- Required: {summarize(dependency_names('required'), limit=100)}",
            f"- Missing: {summarize(dependency_names('missing'), limit=100)}",
            f"- Conflicting: {summarize(dependency_names('conflicting'), limit=100)}",
            "",
            "## Unknowns and conflicts",
            "",
            f"- Unknowns: {summarize(report.unknowns, limit=100)}",
            f"- Conflicts: {summarize(report.global_conflicts, limit=100)}",
            "",
        ]
    )
    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")
    return "\n".join(lines)
