"""Evidence-degrading application discovery and user-confirmation artifacts."""

from __future__ import annotations

import hashlib
import os
import platform
import queue
import re
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.models import ProbeResult, ToolDescriptor, utc_now

MAX_ACTIVE_FILES = 10_000
MAX_REPORT_EXECUTABLES = 200
MAX_EVIDENCE_REFS = 100
MAX_TEXT_EVIDENCE_FILES = 500
MAX_TEXT_BYTES = 2_000_000
MAX_HELP_BYTES = 200_000
MAX_HELP_PROBES = 20
HELP_TIMEOUT_S = 5.0
MAX_EXECUTABLE_HASH_BYTES = 256 * 1024 * 1024
MAX_EXECUTABLE_HASH_AGGREGATE_BYTES = 2 * 1024 * 1024 * 1024
TEXT_SUFFIXES = {".md", ".rst", ".txt", ".adoc", ".html", ".htm"}
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
SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
}


class DiscoveryModeLevel(str, Enum):
    SOURCE_FIRST = "SOURCE_FIRST"
    ARTIFACT_DOC = "ARTIFACT_DOC"
    BINARY_ONLY = "BINARY_ONLY"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActiveProbeMode(str, Enum):
    NONE = "none"
    HELP = "help"
    RUNTIME_READONLY = "runtime-readonly"


class SoftwareInventoryMode(str, Enum):
    OFF = "off"
    RELEVANT = "relevant"
    FULL = "full"


class ConfirmationStatus(str, Enum):
    AWAITING_USER_CONFIRMATION = "AWAITING_USER_CONFIRMATION"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"


class ConfirmationDecision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECT = "correct"


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
    software_inventory: SoftwareInventoryMode = SoftwareInventoryMode.RELEVANT

    @model_validator(mode="after")
    def require_primary_evidence(self) -> ActiveDiscoveryInputs:
        if not (self.source_roots or self.install_roots or self.executables):
            raise ValueError(
                "at least one --source-root, --install-root, or --executable is required"
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
    remappings: list[dict[str, str]] = Field(default_factory=list)


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
        "DISCOVERED_ARTIFACT",
        "SOURCE_DECLARED",
        "LAUNCH_DECLARED",
    ]
    sha256: str | None = None
    file_format: str | None = None
    architecture: str | None = None
    version: dict[str, Any] = Field(default_factory=dict)
    package_ownership: dict[str, Any] = Field(default_factory=dict)
    source_analysis: SourceAnalysis = Field(default_factory=SourceAnalysis)
    artifact_analysis: ArtifactAnalysis = Field(default_factory=ArtifactAnalysis)
    documentation_analysis: DocumentationAnalysis = Field(
        default_factory=DocumentationAnalysis
    )
    launch_analysis: LaunchAnalysis = Field(default_factory=LaunchAnalysis)
    invocation: InvocationAnalysis = Field(default_factory=InvocationAnalysis)
    communication: CommunicationAnalysis = Field(default_factory=CommunicationAnalysis)
    capability_candidates: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: dict[str, list[Any]] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, list[Any]] = Field(default_factory=dict)


class DiscoveryMode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: DiscoveryModeLevel
    confidence: Confidence
    reason: str


class ConfirmationPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = True
    prompt: str
    confirm_command: str
    correction_command: str


class ActiveDiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-active-discovery-report/v1"] = (
        "robot-active-discovery-report/v1"
    )
    discovery_id: str
    robot_id: str
    technical_status: str
    confirmation_status: ConfirmationStatus = ConfirmationStatus.AWAITING_USER_CONFIRMATION
    discovery_mode: DiscoveryMode
    inputs: dict[str, Any]
    coverage: dict[str, CoverageRecord]
    executables: list[ExecutableDiscovery] = Field(default_factory=list)
    canonical_operation_summary: list[dict[str, Any]] = Field(default_factory=list)
    dependency_summary: dict[str, Any] = Field(default_factory=dict)
    global_conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confirmation: ConfirmationPrompt
    created_at: datetime


class DiscoveryConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-discovery-confirmation/v1"] = (
        "robot-discovery-confirmation/v1"
    )
    discovery_id: str
    robot_id: str
    report_ref: str
    report_sha256: str
    decision: ConfirmationDecision
    confirmation_status: ConfirmationStatus
    corrections_ref: str | None = None
    corrections_sha256: str | None = None
    confirmed_at: datetime = Field(default_factory=utc_now)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_files(paths: Iterable[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        try:
            if path.is_file() and path.stat().st_size <= MAX_TEXT_BYTES:
                hashes[str(path)] = sha256_file(path)
        except OSError:
            continue
    return hashes


def _walk_files(roots: Sequence[Path]) -> tuple[list[Path], bool, list[str]]:
    files: list[Path] = []
    warnings: list[str] = []
    for root in roots:
        if root.is_file():
            if not root.is_symlink():
                files.append(root)
                if len(files) >= MAX_ACTIVE_FILES:
                    return files, True, warnings
            continue
        if not root.is_dir():
            warnings.append(f"root is not a file or directory: {root}")
            continue
        for directory, names, filenames in os.walk(root, followlinks=False):
            names[:] = sorted(name for name in names if name not in SKIP_DIRECTORIES)
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.is_symlink():
                    continue
                files.append(path)
                if len(files) >= MAX_ACTIVE_FILES:
                    return files, True, warnings
    return files, False, warnings


def _read_bounded_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


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
    lower_parts = {part.lower() for part in path.parts}
    if path.suffix.lower() in {".exe", ".bat", ".cmd", ".com", ".ps1"}:
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
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()


def run_bounded_help(path: Path, output_path: Path) -> HelpProbeResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(
            [str(path), "--help"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=path.parent,
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


def _extract_document_evidence(paths: Iterable[Path]) -> tuple[list[str], list[str], set[str]]:
    commands: set[str] = set()
    parameters: set[str] = set()
    protocols: set[str] = set()
    protocol_pattern = re.compile(
        r"(?i)\b(tcp|udp|http|https|grpc|websocket|mqtt|serial|can|dbus|shared[ _-]?memory)\b"
    )
    for path in paths:
        text = _read_bounded_text(path)
        if not text:
            continue
        parameters.update(re.findall(r"(?<!\w)--[a-zA-Z0-9][a-zA-Z0-9_-]*", text))
        protocols.update(
            match.lower().replace(" ", "_") for match in protocol_pattern.findall(text)
        )
        for line in text.splitlines():
            stripped = line.strip().lstrip("$>").strip()
            if len(stripped) <= 300 and re.search(r"\b(robotctl|ros2|launch|--help)\b", stripped):
                commands.add(stripped)
            if len(commands) >= 100:
                break
    return sorted(commands)[:100], sorted(parameters)[:500], protocols


def _extract_help_summary(text: str) -> tuple[list[str], list[str], list[str]]:
    usage: list[str] = []
    parameters = sorted(
        set(re.findall(r"(?<!\w)--[a-zA-Z0-9][a-zA-Z0-9_-]*", text))
    )
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


def _extract_launch_evidence(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    """Statically extract launch declarations without importing or executing launch files."""
    evidence: dict[str, dict[str, Any]] = {}
    for path in paths:
        text = _read_bounded_text(path)
        if not text:
            continue
        launch_arguments = set(
            re.findall(
                r"DeclareLaunchArgument\s*\(\s*['\"]([^'\"]+)['\"]",
                text,
            )
        )
        remappings = {
            (source, target)
            for source, target in re.findall(
                r"['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                text,
            )
            if source.startswith("/") or target.startswith("/")
        }
        declarations: list[tuple[str, str | None, str | None]] = []
        for block in re.findall(r"(?s)(?:Node|ComposableNode)\s*\((.*?)\)", text):
            executable_match = re.search(
                r"\bexecutable\s*=\s*['\"]([^'\"]+)['\"]", block
            )
            if not executable_match:
                continue
            package_match = re.search(r"\bpackage\s*=\s*['\"]([^'\"]+)['\"]", block)
            name_match = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", block)
            declarations.append(
                (
                    executable_match.group(1),
                    package_match.group(1) if package_match else None,
                    name_match.group(1) if name_match else None,
                )
            )
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            root = None
        if root is not None:
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "node":
                    continue
                executable = node.attrib.get("exec") or node.attrib.get("executable")
                if executable:
                    declarations.append(
                        (
                            executable,
                            node.attrib.get("pkg") or node.attrib.get("package"),
                            node.attrib.get("name"),
                        )
                    )
        for executable, package, node_name in declarations:
            record = evidence.setdefault(
                executable,
                {
                    "references": set(),
                    "packages": set(),
                    "nodes": set(),
                    "arguments": set(),
                    "remappings": set(),
                },
            )
            record["references"].add(str(path))
            if package:
                record["packages"].add(package)
            if node_name:
                record["nodes"].add(node_name)
            record["arguments"].update(launch_arguments)
            record["remappings"].update(remappings)
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


def _mode(projects: list[dict[str, Any]], docs: list[Path]) -> DiscoveryMode:
    if projects:
        return DiscoveryMode(
            level=DiscoveryModeLevel.SOURCE_FIRST,
            confidence=Confidence.HIGH,
            reason="usable source evidence was collected",
        )
    if docs:
        return DiscoveryMode(
            level=DiscoveryModeLevel.ARTIFACT_DOC,
            confidence=Confidence.MEDIUM,
            reason="artifact and documentation evidence were collected without source",
        )
    return DiscoveryMode(
        level=DiscoveryModeLevel.BINARY_ONLY,
        confidence=Confidence.LOW,
        reason="only executable or installed-artifact evidence was collected",
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
        parameters=[
            parameter
            for project in projects
            for parameter in project.get("semantic_candidates", [])
        ],
        source_revisions=sorted(
            {
                revision
                for project in projects
                if (revision := project.get("source_revision"))
            }
        ),
        manifest_sha256={
            str(Path(project["root"]) / relative): digest
            for project in projects
            for relative, digest in project.get("manifest_digests", {}).items()
        },
        evidence_refs=sorted({project["root"] for project in projects}),
    )


def _ros_communication(
    projects: list[dict[str, Any]],
    ros_probe: ProbeResult,
    *,
    include_runtime: bool,
) -> dict[str, Any]:
    source_interfaces = [
        interface
        for project in projects
        for interface in project.get("ros_interfaces", [])
    ]
    runtime = ros_probe.data if include_runtime else {}
    return {
        "nodes": runtime.get("nodes", []),
        "publishers": [item for item in source_interfaces if item.get("role") == "publisher"],
        "subscribers": [item for item in source_interfaces if item.get("role") == "subscriber"],
        "services": [
            *[item for item in source_interfaces if item.get("role") == "service"],
            *runtime.get("services", []),
        ],
        "clients": [item for item in source_interfaces if item.get("role") == "client"],
        "actions": runtime.get("actions", []),
        "runtime_topics": runtime.get("topics", []),
        "parameters": [],
        "tf_frames": [],
        "remappings": [],
    }


class ActiveDiscoveryAnalyzer:
    def __init__(
        self,
        *,
        inputs: ActiveDiscoveryInputs,
        projects: list[dict[str, Any]],
        ros_probe: ProbeResult,
        tools: Sequence[ToolDescriptor],
        run_root: Path,
        artifact_prefix: str,
    ) -> None:
        self.inputs = inputs.resolved()
        self.projects = projects
        self.ros_probe = ros_probe
        self.tools = tools
        self.run_root = run_root
        self.artifact_prefix = artifact_prefix.rstrip("/")

    def build(
        self,
        *,
        discovery_id: str,
        robot_id: str,
        technical_status: str,
        created_at: datetime,
    ) -> ActiveDiscoveryReport:
        usable_projects = _usable_projects(self.projects)
        build_files, build_truncated, build_warnings = _walk_files(self.inputs.build_roots)
        install_files, install_truncated, install_warnings = _walk_files(
            self.inputs.install_roots
        )
        doc_files, doc_truncated, doc_warnings = _walk_files(self.inputs.document_roots)
        launch_files, launch_truncated, launch_warnings = _walk_files(self.inputs.launch_roots)
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
        doc_files = list(dict.fromkeys([*doc_files, *source_doc_files]))
        launch_files = list(dict.fromkeys([*launch_files, *source_launch_files]))
        doc_files = [path for path in doc_files if path.suffix.lower() in TEXT_SUFFIXES]
        launch_files = [
            path
            for path in launch_files
            if "launch" in path.name.lower()
            or path.suffix.lower() in {".yaml", ".yml", ".xml", ".py"}
        ]
        if len(doc_files) > MAX_TEXT_EVIDENCE_FILES:
            doc_truncated = True
            doc_files = doc_files[:MAX_TEXT_EVIDENCE_FILES]
        if len(launch_files) > MAX_TEXT_EVIDENCE_FILES:
            launch_truncated = True
            launch_files = launch_files[:MAX_TEXT_EVIDENCE_FILES]
        documented_commands, documented_parameters, doc_protocols = _extract_document_evidence(
            doc_files
        )
        launch_commands, launch_parameters, launch_protocols = _extract_document_evidence(
            launch_files
        )
        documented_commands = sorted(set(documented_commands) | set(launch_commands))
        documented_parameters = sorted(set(documented_parameters) | set(launch_parameters))
        launch_evidence = _extract_launch_evidence(launch_files)

        explicit_paths = [path for path in self.inputs.executables if path.is_file()]
        invalid_explicit_paths = [
            path for path in self.inputs.executables if not path.is_file()
        ]
        discovered_paths = [path for path in install_files if _looks_executable(path)]
        all_discovered_paths = list(dict.fromkeys([*explicit_paths, *discovered_paths]))
        executable_truncated = len(all_discovered_paths) > MAX_REPORT_EXECUTABLES
        all_paths = all_discovered_paths[:MAX_REPORT_EXECUTABLES]
        source_names = {
            entry["name"]
            for project in usable_projects
            for entry in project.get("entrypoints", [])
            if entry.get("name")
        }
        if not all_paths and not source_names:
            source_names = {
                package
                for project in usable_projects
                for package in project.get("packages", [])
            }

        source_analysis = _source_analysis(usable_projects)
        intermediates = [
            str(path)
            for path in build_files
            if path.suffix.lower() in INTERMEDIATE_SUFFIXES
        ][:MAX_EVIDENCE_REFS]
        configs = [
            str(path)
            for path in [*build_files, *install_files, *launch_files]
            if path.suffix.lower() in CONFIG_SUFFIXES
        ][:MAX_EVIDENCE_REFS]
        plugins = [
            str(path)
            for path in install_files
            if path.suffix.lower() in {".so", ".dll", ".dylib"}
        ][:MAX_EVIDENCE_REFS]
        runtime_observed = (
            self.inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY
            and self.ros_probe.status.value in {"SUCCEEDED", "PARTIAL"}
        )
        ros_communication = _ros_communication(
            usable_projects,
            self.ros_probe,
            include_runtime=runtime_observed,
        )
        source_protocols = {
            protocol
            for project in usable_projects
            for protocol in project.get("protocols", [])
        }
        protocols = sorted(doc_protocols | launch_protocols | source_protocols)
        candidate_operations = [
            {
                "operation": tool.operation,
                "state": tool.availability,
                "confidence": (
                    Confidence.LOW.value
                    if tool.availability == "DISCOVERED_UNVERIFIED"
                    else Confidence.MEDIUM.value
                ),
                "evidence": tool.evidence,
                "required_adapter": tool.availability == "DISCOVERED_UNVERIFIED",
            }
            for tool in self.tools
        ]
        dependencies = source_analysis.declared_dependencies
        document_sha256 = _hash_files(doc_files[:MAX_EVIDENCE_REFS])
        launch_sha256 = _hash_files(launch_files[:MAX_EVIDENCE_REFS])

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
                remappings=[
                    {"from": source, "to": target}
                    for source, target in sorted(record["remappings"])
                ],
            )

        executables: list[ExecutableDiscovery] = []
        help_probe_count = 0
        executable_hash_bytes = 0
        hash_warnings: list[str] = []
        for index, path in enumerate(all_paths, start=1):
            explicit = path in explicit_paths
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
                    output_path = self.run_root / "active_probes" / f"help-{index:04d}.txt"
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
                hash_unresolved.append(
                    "executable exceeds the per-file SHA-256 size limit"
                )
            elif (
                executable_hash_bytes + executable_size
                > MAX_EXECUTABLE_HASH_AGGREGATE_BYTES
            ):
                sha256 = None
                hash_unresolved.append(
                    "per-run executable SHA-256 byte limit was reached"
                )
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
            launch_analysis = launch_analysis_for(path.name)
            executable_ros = dict(ros_communication)
            executable_ros["nodes"] = sorted(
                set(executable_ros.get("nodes", [])) | set(launch_analysis.nodes)
            )
            executable_ros["remappings"] = launch_analysis.remappings
            executables.append(
                ExecutableDiscovery(
                    executable_id=f"exe-{index:04d}",
                    name=path.name,
                    path=str(path),
                    origin="EXPLICIT" if explicit else "DISCOVERED_ARTIFACT",
                    sha256=sha256,
                    file_format=file_format,
                    architecture=architecture,
                    version={"value": None, "source": None, "confidence": "LOW"},
                    package_ownership={"manager": None, "package": None, "version": None},
                    source_analysis=source_analysis,
                    artifact_analysis=ArtifactAnalysis(
                        install_root=install_root,
                        build_roots=[str(root) for root in self.inputs.build_roots],
                        intermediate_outputs=intermediates,
                        plugins=plugins,
                        configuration_files=configs,
                    ),
                    documentation_analysis=DocumentationAnalysis(
                        available=bool(doc_files),
                        references=[str(path) for path in doc_files[:MAX_EVIDENCE_REFS]],
                        reference_sha256=document_sha256,
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
                            f"declared by {reference}"
                            for reference in launch_analysis.references
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
                            if usable_projects or doc_files or launch_analysis.available
                            else Confidence.LOW
                        ),
                        evidence_refs=[
                            str(item) for item in [*doc_files, *launch_files][:100]
                        ],
                    ),
                    capability_candidates=candidate_operations,
                    dependencies={
                        "declared": dependencies,
                        "binary_linked": [],
                        "runtime_observed": [],
                        "missing": [],
                        "version_conflicts": [],
                        "install_candidates": [],
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
                        "source": source_analysis.evidence_refs,
                        "artifacts": [str(path)],
                        "documentation": [str(item) for item in doc_files[:100]],
                        "help": [help_result.output_ref] if help_result.output_ref else [],
                        "ros_runtime": (
                            ["live_ros_graph"]
                            if runtime_observed
                            else []
                        ),
                        "conflicts": [],
                        "unresolved": hash_unresolved,
                    },
                )
            )
        declared_names = source_names | set(launch_evidence)
        for name in sorted(declared_names):
            if len(executables) >= MAX_REPORT_EXECUTABLES:
                executable_truncated = True
                break
            if any(
                executable.name == name
                or Path(executable.name).stem == Path(name).stem
                for executable in executables
            ):
                continue
            index = len(executables) + 1
            launch_analysis = launch_analysis_for(name)
            origin = "SOURCE_DECLARED" if name in source_names else "LAUNCH_DECLARED"
            executable_ros = dict(ros_communication)
            executable_ros["nodes"] = sorted(
                set(executable_ros.get("nodes", [])) | set(launch_analysis.nodes)
            )
            executable_ros["remappings"] = launch_analysis.remappings
            executables.append(
                ExecutableDiscovery(
                    executable_id=f"exe-{index:04d}",
                    name=name,
                    origin=origin,
                    source_analysis=source_analysis,
                    documentation_analysis=DocumentationAnalysis(
                        available=bool(doc_files),
                        references=[str(path) for path in doc_files[:MAX_EVIDENCE_REFS]],
                        reference_sha256=document_sha256,
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
                            f"declared by {reference}"
                            for reference in launch_analysis.references
                        ],
                    ),
                    communication=CommunicationAnalysis(
                        ros=executable_ros,
                        network={"protocols": protocols},
                        confidence=(
                            Confidence.HIGH
                            if name in source_names
                            else Confidence.MEDIUM
                            if doc_files or launch_analysis.available
                            else Confidence.LOW
                        ),
                    ),
                    capability_candidates=candidate_operations,
                    dependencies={
                        "declared": dependencies,
                        "binary_linked": [],
                        "runtime_observed": [],
                        "missing": [],
                        "version_conflicts": [],
                        "install_candidates": [],
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
                        "source": source_analysis.evidence_refs,
                        "artifacts": [],
                        "documentation": [str(item) for item in doc_files[:100]],
                        "help": [],
                        "ros_runtime": [],
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
        help_incomplete = any(
            result.status != HelpProbeStatus.SUCCEEDED for result in help_results
        )
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
                    if doc_files
                    else CoverageStatus.NOT_PROVIDED
                ),
                records=len(doc_files),
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
                    result.status != HelpProbeStatus.BLOCKED_BY_POLICY
                    for result in help_results
                ),
                truncated=any(
                    result.status == HelpProbeStatus.BLOCKED_BY_POLICY
                    for result in help_results
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
        mode = _mode(usable_projects, doc_files)
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
        if executable_truncated:
            warnings.append(
                f"executable report limit reached: {MAX_REPORT_EXECUTABLES}; "
                "artifact coverage is partial"
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
                "binary-only discovery is heuristic; all capability candidates require confirmation"
            )
        if self.inputs.active_probe in {ActiveProbeMode.HELP, ActiveProbeMode.RUNTIME_READONLY}:
            warnings.append(
                "--help was allowed only for explicitly supplied executables; "
                "launch files were not run"
            )
        confirm_command = (
            f"robotctl build discover confirm --robot {robot_id} "
            f"--discovery-id {discovery_id}"
        )
        effective_technical_status = technical_status
        if technical_status == "SUCCEEDED" and any(
            record.status == CoverageStatus.PARTIAL for record in coverage.values()
        ):
            effective_technical_status = "PARTIAL"
        return ActiveDiscoveryReport(
            discovery_id=discovery_id,
            robot_id=robot_id,
            technical_status=effective_technical_status,
            discovery_mode=mode,
            inputs=self.inputs.model_dump(mode="json"),
            coverage=coverage,
            executables=executables,
            canonical_operation_summary=candidate_operations,
            dependency_summary={
                "required": dependencies,
                "missing": [],
                "conflicting": [],
                "installation_plan_ref": None,
            },
            unknowns=(
                ["no executable entrypoint could be identified"] if not executables else []
            ),
            warnings=sorted(set(warnings)),
            confirmation=ConfirmationPrompt(
                prompt=(
                    "Confirm executable identity, invocation, communication, capability, "
                    "dependency, and safety findings."
                ),
                confirm_command=confirm_command,
                correction_command=f"{confirm_command} --decision correct --corrections <path>",
            ),
            created_at=created_at,
        )


def render_active_discovery_markdown(report: ActiveDiscoveryReport) -> str:
    def summarize(values: Iterable[Any], *, limit: int = 20) -> str:
        rendered: list[str] = []
        for value in list(values)[:limit]:
            if isinstance(value, dict):
                rendered.append(
                    str(
                        value.get("name")
                        or value.get("operation")
                        or value.get("path")
                        or value
                    )
                )
            else:
                rendered.append(str(value))
        return ", ".join(rendered) or "none"

    lines = [
        f"# Active discovery report: {report.robot_id}",
        "",
        f"- Discovery ID: `{report.discovery_id}`",
        f"- Technical status: `{report.technical_status}`",
        f"- Confirmation: `{report.confirmation_status.value}`",
        f"- Mode: `{report.discovery_mode.level.value}`",
        f"- Confidence: `{report.discovery_mode.confidence.value}`",
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
                f"- Documentation references: "
                f"{len(executable.documentation_analysis.references)}",
                f"- Launch packages / nodes: "
                f"{summarize(executable.launch_analysis.packages)} / "
                f"{summarize(executable.launch_analysis.nodes)}",
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
                f"- Capability candidates: {summarize(executable.capability_candidates)}",
                f"- Safety risk / motion possible: "
                f"`{executable.safety.get('risk', 'unknown')}` / "
                f"`{executable.safety.get('motion_possible', 'unknown')}`",
                f"- Unresolved evidence: "
                f"{summarize(executable.evidence.get('unresolved', []))}",
                "",
            ]
        )
    lines.extend(
        [
            "## Dependency summary",
            "",
            f"- Required: {summarize(report.dependency_summary.get('required', []), limit=100)}",
            f"- Missing: {summarize(report.dependency_summary.get('missing', []), limit=100)}",
            f"- Conflicting: "
            f"{summarize(report.dependency_summary.get('conflicting', []), limit=100)}",
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
    lines.extend(
        [
            "## Confirmation required",
            "",
            report.confirmation.prompt,
            "",
            "```bash",
            report.confirmation.confirm_command,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def confirmation_status_for_decision(decision: ConfirmationDecision) -> ConfirmationStatus:
    return {
        ConfirmationDecision.ACCEPT: ConfirmationStatus.ACCEPTED,
        ConfirmationDecision.REJECT: ConfirmationStatus.REJECTED,
        ConfirmationDecision.CORRECT: ConfirmationStatus.CORRECTION_REQUIRED,
    }[decision]


def load_active_report(path: Path) -> ActiveDiscoveryReport:
    return ActiveDiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))


def write_confirmation(
    *,
    report_path: Path,
    robot_id: str,
    discovery_id: str,
    decision: ConfirmationDecision,
    corrections: Path | None,
) -> DiscoveryConfirmation:
    report_payload = report_path.read_bytes()
    report = ActiveDiscoveryReport.model_validate_json(report_payload)
    if report.robot_id != robot_id or report.discovery_id != discovery_id:
        raise ValueError("active discovery report identity does not match confirmation request")
    if decision == ConfirmationDecision.CORRECT and corrections is None:
        raise ValueError("--corrections is required when --decision correct")
    if decision != ConfirmationDecision.CORRECT and corrections is not None:
        raise ValueError("--corrections is only valid when --decision correct")
    if corrections is not None and not corrections.is_file():
        raise ValueError(f"corrections file does not exist: {corrections}")
    corrections_path = corrections.expanduser().resolve() if corrections else None
    return DiscoveryConfirmation(
        discovery_id=discovery_id,
        robot_id=robot_id,
        report_ref=(
            f"artifact://discovery/{robot_id}/runs/{discovery_id}/"
            "active_discovery_report.json"
        ),
        report_sha256=hashlib.sha256(report_payload).hexdigest(),
        decision=decision,
        confirmation_status=confirmation_status_for_decision(decision),
        corrections_ref=str(corrections_path) if corrections_path else None,
        corrections_sha256=sha256_file(corrections_path) if corrections_path else None,
    )


def confirmation_matches_report(confirmation: DiscoveryConfirmation, report_path: Path) -> bool:
    try:
        payload = report_path.read_bytes()
        report = ActiveDiscoveryReport.model_validate_json(payload)
        report_sha256 = hashlib.sha256(payload).hexdigest()
    except (OSError, ValueError):
        return False
    return (
        confirmation.decision == ConfirmationDecision.ACCEPT
        and confirmation.confirmation_status == ConfirmationStatus.ACCEPTED
        and confirmation.robot_id == report.robot_id
        and confirmation.discovery_id == report.discovery_id
        and confirmation.report_sha256 == report_sha256
    )
