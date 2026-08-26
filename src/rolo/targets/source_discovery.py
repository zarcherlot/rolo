"""Proof-bound, bounded target-side source discovery contracts.

The target may parse source files after an explicit R2 approval, but it returns
only product-owned structured facts.  Source text, controller-native paths and
unbounded parser diagnostics never cross the executor protocol.
"""

from __future__ import annotations

import hashlib
import json
import stat
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.models import DiscoveryStatus, RouteEvidence
from rolo.stages.adapt.application_cli_mapping import ApplicationCliRouteProvider
from rolo.stages.adapt.discovery import ApplicationProbe
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
)
from rolo.targets.runtime_deployment import TargetWorkspaceRef

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_APPROVAL_PATTERN = r"^approval-[0-9a-f]{32}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SOURCE_REVISION_PATTERN = r"^[0-9a-fA-F]{40,64}$"
_MAX_PROJECTS = 16
_MAX_ITEMS = 1_000
_MAX_TEXT = 4_096
_ENTRYPOINT_SOURCES = {
    "cmake",
    "cmake_install_program",
    "pyproject",
    "setup.cfg",
    "setup.py",
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _structured_text(value: str) -> str:
    if not value or len(value) > _MAX_TEXT:
        raise ValueError("source discovery text is empty or too long")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("source discovery text contains control characters")
    return value


def _relative_path(value: str, *, allow_root: bool = False) -> str:
    if allow_root and value == ".":
        return value
    if not value or len(value) > _MAX_TEXT:
        raise ValueError("source discovery path is empty or too long")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or "." in path.parts or ".." in path.parts:
        raise ValueError("source discovery path must be normalized and relative")
    if any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
        raise ValueError("source discovery path contains forbidden characters")
    return str(path)


class TargetSourceDiscoveryLimits(BaseModel):
    """The exact v1 parser budget; literals prevent a request from overstating limits."""

    model_config = ConfigDict(extra="forbid")

    max_projects: Literal[16] = 16
    max_files_per_project: Literal[10_000] = 10_000
    max_file_read_bytes: Literal[2_000_000] = 2_000_000
    max_items_per_collection: Literal[1_000] = 1_000


class TargetSourceDiscoveryRequest(BaseModel):
    """One immutable authorization scope for recursive, read-only source analysis."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-request/v1"] = (
        "rolo-target-source-discovery-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace: TargetWorkspaceRef
    scan_roots: list[str] = Field(min_length=1, max_length=_MAX_PROJECTS)
    limits: TargetSourceDiscoveryLimits = Field(default_factory=TargetSourceDiscoveryLimits)
    approval_id: str = Field(pattern=_APPROVAL_PATTERN)
    authorization: DeploymentAuthorizationProof | None = None
    timeout_s: float = Field(default=120.0, ge=1.0, le=300.0)

    @field_validator("scan_roots")
    @classmethod
    def validate_scan_roots(cls, value: list[str]) -> list[str]:
        normalized = [_relative_path(item, allow_root=True) for item in value]
        if normalized != sorted(set(normalized)):
            raise ValueError("target source discovery roots must be unique and sorted")
        if "." in normalized and len(normalized) != 1:
            raise ValueError("workspace root cannot be combined with nested scan roots")
        return normalized

    @model_validator(mode="after")
    def bind_authorization(self) -> TargetSourceDiscoveryRequest:
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.workspace.target_id,
            expected_approval_id=self.approval_id,
        )
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json"))).hexdigest()


class TargetSourceDependencyDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=512)
    ecosystem: Literal["python", "ros"]
    scope: str = Field(min_length=1, max_length=128)
    required: bool
    specifier: str | None = Field(default=None, max_length=1_024)
    marker: str | None = Field(default=None, max_length=1_024)
    applicable: bool | None = None
    extras: list[str] = Field(default_factory=list, max_length=128)
    source: str = Field(min_length=1, max_length=_MAX_TEXT)

    @field_validator("name", "scope", "specifier", "marker")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return _structured_text(value) if value is not None else None

    @field_validator("extras")
    @classmethod
    def validate_extras(cls, value: list[str]) -> list[str]:
        values = [_structured_text(item) for item in value]
        if values != sorted(set(values)):
            raise ValueError("dependency extras must be unique and sorted")
        return values

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return _relative_path(value)


class TargetSourceEntrypoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=2_048)
    source: Literal[
        "cmake",
        "cmake_install_program",
        "pyproject",
        "setup.cfg",
        "setup.py",
    ]
    source_files: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("name", "target")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _structured_text(value)

    @field_validator("source_files")
    @classmethod
    def validate_source_files(cls, value: list[str]) -> list[str]:
        values = [_relative_path(item) for item in value]
        if values != sorted(set(values)):
            raise ValueError("entrypoint source files must be unique and sorted")
        return values


class TargetSourceRosInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["publisher", "subscriber", "service", "client"]
    name: str = Field(min_length=1, max_length=1_024)
    type: str = Field(min_length=1, max_length=1_024)
    source: str = Field(min_length=1, max_length=_MAX_TEXT)
    name_source: Literal["STRING_LITERAL"] = "STRING_LITERAL"

    @field_validator("name", "type")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _structured_text(value)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return _relative_path(value)


class TargetSourceSemanticCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal[
        "geometry.hard_max_angular_velocity_radps",
        "geometry.hard_max_linear_velocity_mps",
    ]
    value: float = Field(gt=0)
    unit: Literal["m/s", "rad/s"]
    source_kind: Literal["config", "launch"]
    source_path: str = Field(min_length=1, max_length=_MAX_TEXT)
    source_key: Literal[
        "max_angular_speed",
        "max_angular_velocity",
        "max_linear_speed",
        "max_linear_velocity",
        "max_vel_theta",
        "max_vel_x",
    ]
    status: Literal["DISCOVERED_UNVERIFIED"] = "DISCOVERED_UNVERIFIED"
    safety_authority: Literal["none"] = "none"

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _relative_path(value)


class TargetSourceRosNames(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    services: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    actions: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)

    @field_validator("topics", "services", "actions")
    @classmethod
    def validate_names(cls, value: list[str]) -> list[str]:
        values = [_structured_text(item) for item in value]
        if values != sorted(set(values)):
            raise ValueError("ROS names must be unique and sorted")
        return values


class TargetSourceProjectSummary(BaseModel):
    """Strict transport form of one ApplicationProbe project."""

    model_config = ConfigDict(extra="forbid")

    root: str = Field(min_length=1, max_length=_MAX_TEXT)
    file_count_scanned: int = Field(ge=0, le=10_000)
    scan_truncated: bool
    build_systems: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    packages: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    entrypoints: list[TargetSourceEntrypoint] = Field(
        default_factory=list, max_length=_MAX_ITEMS
    )
    launch_files: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    readmes: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    config_files: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    semantic_candidates: list[TargetSourceSemanticCandidate] = Field(
        default_factory=list, max_length=_MAX_ITEMS
    )
    ros_names: TargetSourceRosNames = Field(default_factory=TargetSourceRosNames)
    ros_interfaces: list[TargetSourceRosInterface] = Field(
        default_factory=list, max_length=_MAX_ITEMS
    )
    protocols: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    languages: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    build_targets: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    declared_dependencies: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    dependency_declarations: list[TargetSourceDependencyDeclaration] = Field(
        default_factory=list, max_length=_MAX_ITEMS
    )
    manifest_digests: dict[str, str] = Field(default_factory=dict)
    source_revision: str | None = Field(default=None, pattern=_SOURCE_REVISION_PATTERN)

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        return _relative_path(value, allow_root=True)

    @field_validator("launch_files", "readmes", "config_files")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        values = [_relative_path(item) for item in value]
        if values != sorted(set(values)):
            raise ValueError("source discovery paths must be unique and sorted")
        return values

    @field_validator(
        "build_systems",
        "packages",
        "protocols",
        "languages",
        "build_targets",
        "declared_dependencies",
    )
    @classmethod
    def validate_text_collection(cls, value: list[str]) -> list[str]:
        values = [_structured_text(item) for item in value]
        if values != sorted(set(values)):
            raise ValueError("source discovery collections must be unique and sorted")
        return values

    @field_validator("manifest_digests")
    @classmethod
    def validate_manifest_digests(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > _MAX_ITEMS:
            raise ValueError("source manifest digest collection exceeds its limit")
        normalized = {_relative_path(path): digest for path, digest in value.items()}
        if list(normalized) != sorted(normalized):
            raise ValueError("source manifest digests must be sorted")
        if any(
            len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)
            for digest in normalized.values()
        ):
            raise ValueError("source manifest digest is invalid")
        return normalized


class TargetSourceDiscoveryWarning(str, Enum):
    PARSER_WARNING_REDACTED = "PARSER_WARNING_REDACTED"
    RESULT_COLLECTION_TRUNCATED = "RESULT_COLLECTION_TRUNCATED"
    SOURCE_FILE_LIMIT_REACHED = "SOURCE_FILE_LIMIT_REACHED"


class TargetSourceDiscoverySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-snapshot/v1"] = (
        "rolo-target-source-discovery-snapshot/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_sha256: str = Field(pattern=_SHA256_PATTERN)
    status: DiscoveryStatus
    projects: list[TargetSourceProjectSummary] = Field(
        default_factory=list, max_length=_MAX_PROJECTS
    )
    route_evidence: list[RouteEvidence] = Field(default_factory=list, max_length=_MAX_ITEMS)
    warnings: list[TargetSourceDiscoveryWarning] = Field(default_factory=list)
    summary_sha256: str = Field(pattern=_SHA256_PATTERN)
    observed_at: datetime

    @model_validator(mode="after")
    def require_canonical_snapshot(self) -> TargetSourceDiscoverySnapshot:
        if self.observed_at.tzinfo is None:
            raise ValueError("target source discovery timestamp must be timezone-aware")
        roots = [project.root for project in self.projects]
        if roots != sorted(set(roots)):
            raise ValueError("target source discovery projects must be unique and sorted")
        route_ids = [route.resource_id for route in self.route_evidence]
        if route_ids != sorted(set(route_ids)):
            raise ValueError("target source discovery routes must be unique and sorted")
        if self.warnings != sorted(set(self.warnings), key=lambda item: item.value):
            raise ValueError("target source discovery warnings must be unique and sorted")
        if self.status == DiscoveryStatus.UNAVAILABLE and self.projects:
            raise ValueError("unavailable source discovery cannot contain projects")
        if self.status != DiscoveryStatus.UNAVAILABLE and not self.projects:
            raise ValueError("available source discovery requires projects")
        if self.summary_sha256 != self.compute_summary_sha256():
            raise ValueError("target source discovery summary digest mismatch")
        return self

    def summary_payload(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "request_sha256": self.request_sha256,
            "target_id": self.target_id,
            "robot_id": self.robot_id,
            "workspace_id": self.workspace_id,
            "workspace_sha256": self.workspace_sha256,
            "status": self.status.value,
            "projects": [project.model_dump(mode="json") for project in self.projects],
            "route_evidence": [route.model_dump(mode="json") for route in self.route_evidence],
            "warnings": [warning.value for warning in self.warnings],
        }

    def compute_summary_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.summary_payload())).hexdigest()

    def to_application_probe(self):  # type: ignore[no-untyped-def]
        """Build the existing internal ProbeResult without source text."""
        from rolo.core.models import ProbeResult

        return ProbeResult(
            layer="application",
            status=self.status,
            data={
                "projects": [project.model_dump(mode="json") for project in self.projects],
                "route_evidence": [route.model_dump(mode="json") for route in self.route_evidence],
                "target_source_discovery": {
                    "target_id": self.target_id,
                    "robot_id": self.robot_id,
                    "workspace_id": self.workspace_id,
                    "request_sha256": self.request_sha256,
                    "summary_sha256": self.summary_sha256,
                    "observed_at": self.observed_at.isoformat(),
                },
            },
            warnings=[warning.value for warning in self.warnings],
            observed_at=self.observed_at,
        )


class TargetSourceDiscoveryExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-source-discovery-execution-result/v1"] = (
        "rolo-target-source-discovery-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    workspace_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    snapshot: TargetSourceDiscoverySnapshot | None = None

    @model_validator(mode="after")
    def require_consistent_execution(self) -> TargetSourceDiscoveryExecutionResult:
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.snapshot is None:
                raise ValueError("successful target source discovery execution is incomplete")
        elif self.error_code is None or self.snapshot is not None:
            raise ValueError("failed target source discovery execution is inconsistent")
        if self.snapshot is not None and (
            self.snapshot.request_id != self.request_id
            or self.snapshot.request_sha256 != self.request_sha256
            or self.snapshot.target_id != self.target_id
            or self.snapshot.robot_id != self.robot_id
            or self.snapshot.workspace_id != self.workspace_id
        ):
            raise ValueError("target source discovery execution binding mismatch")
        return self


def _relative_to_workspace(value: str, workspace_root: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(
                "source discovery parser returned a path outside its workspace"
            ) from exc
        return relative.as_posix()
    return _relative_path(value)


def _bounded_texts(values: object) -> tuple[list[str], bool]:
    items = sorted({_structured_text(str(item)) for item in values if str(item)})  # type: ignore[union-attr]
    return items[:_MAX_ITEMS], len(items) > _MAX_ITEMS


def _sanitize_project(
    raw: dict[str, object],
    *,
    workspace_root: Path,
    requested_root: str,
) -> tuple[TargetSourceProjectSummary, bool]:
    truncated = False

    def paths(name: str) -> list[str]:
        nonlocal truncated
        values = sorted(
            {
                _relative_to_workspace(str(item), workspace_root)
                for item in raw.get(name, [])  # type: ignore[union-attr]
            }
        )
        truncated = truncated or len(values) > _MAX_ITEMS
        return values[:_MAX_ITEMS]

    text_fields: dict[str, list[str]] = {}
    for name in (
        "build_systems",
        "packages",
        "protocols",
        "languages",
        "build_targets",
        "declared_dependencies",
    ):
        text_fields[name], clipped = _bounded_texts(raw.get(name, []))
        truncated = truncated or clipped

    entries: list[TargetSourceEntrypoint] = []
    for item in raw.get("entrypoints", []):  # type: ignore[union-attr]
        if not isinstance(item, dict) or item.get("source") not in _ENTRYPOINT_SOURCES:
            continue
        entries.append(
            TargetSourceEntrypoint(
                name=str(item.get("name", "")),
                target=str(item.get("target", "")),
                source=str(item["source"]),  # type: ignore[arg-type]
                source_files=sorted(
                    {
                        _relative_to_workspace(str(path), workspace_root)
                        for path in item.get("source_files", [])
                    }
                )[:128],
            )
        )
    entries = sorted(entries, key=lambda item: (item.name, item.target, item.source))
    truncated = truncated or len(entries) > _MAX_ITEMS

    dependencies: list[TargetSourceDependencyDeclaration] = []
    for item in raw.get("dependency_declarations", []):  # type: ignore[union-attr]
        if not isinstance(item, dict):
            continue
        dependencies.append(
            TargetSourceDependencyDeclaration(
                name=str(item.get("name", "")),
                ecosystem=str(item.get("ecosystem", "")),  # type: ignore[arg-type]
                scope=str(item.get("scope", "")),
                required=bool(item.get("required", False)),
                specifier=(str(item["specifier"]) if item.get("specifier") is not None else None),
                marker=str(item["marker"]) if item.get("marker") is not None else None,
                applicable=(
                    bool(item["applicable"])
                    if item.get("applicable") is not None
                    else None
                ),
                extras=sorted({_structured_text(str(value)) for value in item.get("extras", [])}),
                source=_relative_to_workspace(str(item.get("source", "")), workspace_root),
            )
        )
    dependencies = sorted(
        dependencies,
        key=lambda item: (item.ecosystem, item.name.casefold(), item.scope, item.source),
    )
    truncated = truncated or len(dependencies) > _MAX_ITEMS

    interfaces: list[TargetSourceRosInterface] = []
    for item in raw.get("ros_interfaces", []):  # type: ignore[union-attr]
        if not isinstance(item, dict) or item.get("name_source") != "STRING_LITERAL":
            continue
        interfaces.append(
            TargetSourceRosInterface(
                role=str(item.get("role", "")),  # type: ignore[arg-type]
                name=str(item.get("name", "")),
                type=str(item.get("type", "")),
                source=_relative_to_workspace(str(item.get("source", "")), workspace_root),
            )
        )
    interfaces = sorted(
        interfaces,
        key=lambda item: (item.role, item.name, item.type, item.source),
    )
    truncated = truncated or len(interfaces) > _MAX_ITEMS

    candidates: list[TargetSourceSemanticCandidate] = []
    for item in raw.get("semantic_candidates", []):  # type: ignore[union-attr]
        if not isinstance(item, dict):
            continue
        candidates.append(
            TargetSourceSemanticCandidate(
                field=str(item.get("field", "")),  # type: ignore[arg-type]
                value=float(item.get("value", 0)),
                unit=str(item.get("unit", "")),  # type: ignore[arg-type]
                source_kind=str(item.get("source_kind", "")),  # type: ignore[arg-type]
                source_path=_relative_to_workspace(
                    str(item.get("source_path", "")), workspace_root
                ),
                source_key=str(item.get("source_key", "")),  # type: ignore[arg-type]
            )
        )
    candidates = sorted(
        candidates,
        key=lambda item: (item.field, item.value, item.source_path, item.source_key),
    )
    truncated = truncated or len(candidates) > _MAX_ITEMS

    raw_names = raw.get("ros_names", {})
    names = raw_names if isinstance(raw_names, dict) else {}
    manifest_digests = {
        _relative_to_workspace(str(path), workspace_root): str(digest)
        for path, digest in sorted(
            (raw.get("manifest_digests", {}) or {}).items()  # type: ignore[union-attr]
        )
    }
    truncated = truncated or len(manifest_digests) > _MAX_ITEMS
    summary = TargetSourceProjectSummary(
        root=requested_root,
        file_count_scanned=int(raw.get("file_count_scanned", 0)),
        scan_truncated=bool(raw.get("scan_truncated", False)),
        **text_fields,
        entrypoints=entries[:_MAX_ITEMS],
        launch_files=paths("launch_files"),
        readmes=paths("readmes"),
        config_files=paths("config_files"),
        semantic_candidates=candidates[:_MAX_ITEMS],
        ros_names=TargetSourceRosNames(
            topics=_bounded_texts(names.get("topics", []))[0],
            services=_bounded_texts(names.get("services", []))[0],
            actions=_bounded_texts(names.get("actions", []))[0],
        ),
        ros_interfaces=interfaces[:_MAX_ITEMS],
        dependency_declarations=dependencies[:_MAX_ITEMS],
        manifest_digests=dict(list(manifest_digests.items())[:_MAX_ITEMS]),
        source_revision=(
            str(raw["source_revision"]) if raw.get("source_revision") is not None else None
        ),
    )
    return summary, truncated


def _resolve_scan_root(workspace_root: Path, relative: str) -> Path:
    current = workspace_root
    parts = () if relative == "." else PurePosixPath(relative).parts
    for part in parts:
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("target source discovery root cannot traverse a symbolic link")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(workspace_root):
        raise ValueError("target source discovery root escaped its workspace")
    if not resolved.is_dir():
        raise ValueError("target source discovery root is not a directory")
    return resolved


def discover_target_source(
    request: TargetSourceDiscoveryRequest,
    *,
    observed_at: datetime | None = None,
) -> TargetSourceDiscoverySnapshot:
    """Run the existing inert parsers locally and emit a strict secret-closed summary."""

    workspace_root = Path(request.workspace.root)
    try:
        metadata = workspace_root.lstat()
    except OSError as exc:
        raise ValueError("target source discovery workspace is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("target source discovery workspace is not a real directory")
    workspace_root = workspace_root.resolve(strict=True)
    resolved_roots = [
        _resolve_scan_root(workspace_root, relative) for relative in request.scan_roots
    ]
    scan = ApplicationProbe().scan(resolved_roots)
    projects: list[TargetSourceProjectSummary] = []
    warnings: set[TargetSourceDiscoveryWarning] = set()
    if scan.probe.warnings:
        warnings.add(TargetSourceDiscoveryWarning.PARSER_WARNING_REDACTED)
    for relative, raw in zip(request.scan_roots, scan.probe.data.get("projects", []), strict=True):
        if not isinstance(raw, dict):
            raise ValueError("target source discovery parser returned an invalid project")
        project, truncated = _sanitize_project(
            raw,
            workspace_root=workspace_root,
            requested_root=relative,
        )
        projects.append(project)
        if project.scan_truncated:
            warnings.add(TargetSourceDiscoveryWarning.SOURCE_FILE_LIMIT_REACHED)
        if truncated:
            warnings.add(TargetSourceDiscoveryWarning.RESULT_COLLECTION_TRUNCATED)
    projects.sort(key=lambda item: item.root)
    routes = ApplicationCliRouteProvider().declared_routes(
        [project.model_dump(mode="json") for project in projects]
    )
    status = scan.probe.status
    if warnings and status == DiscoveryStatus.SUCCEEDED:
        status = DiscoveryStatus.PARTIAL
    values = {
        "request_id": request.request_id,
        "request_sha256": request.canonical_sha256(),
        "target_id": request.workspace.target_id,
        "robot_id": request.workspace.robot_id,
        "workspace_id": request.workspace.workspace_id,
        "workspace_sha256": request.workspace.canonical_sha256(),
        "status": status,
        "projects": projects,
        "route_evidence": routes,
        "warnings": sorted(warnings, key=lambda item: item.value),
        "summary_sha256": "0" * 64,
        "observed_at": observed_at or datetime.now(timezone.utc),
    }
    draft = TargetSourceDiscoverySnapshot.model_construct(**values)
    values["summary_sha256"] = draft.compute_summary_sha256()
    return TargetSourceDiscoverySnapshot.model_validate(values)
