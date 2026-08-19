from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.adapter_runtime import load_current_release
from rolo.core.hashing import sha256_file
from rolo.core.models import DiscoveryReport, OperationCandidate
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport, ExecutableDiscovery
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationDefinition,
    builtin_operations,
    canonical_operation_registry,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref


class OperationApplicability(str, Enum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"


class OperationImplementation(str, Enum):
    BUILTIN = "BUILTIN"
    BUNDLE = "BUNDLE"
    UNBOUND = "UNBOUND"


class OperationRegistration(str, Enum):
    REGISTERED = "REGISTERED"
    NOT_REGISTERED = "NOT_REGISTERED"
    STALE = "STALE"


class OperationWorkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    layer: str
    applicability: OperationApplicability
    implementation: OperationImplementation
    registration: OperationRegistration
    candidate_status: str | None = None
    active_availability: str | None = None


class AdaptOperationWorkset(BaseModel):
    """Compact join of product definitions, current evidence and the gated release."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-operation-workset/v1"] = "robot-adapt-operation-workset/v1"
    robot_id: str
    discovery_id: str
    registry_operation_count: int
    candidate_operation_count: int
    registered_operation_count: int
    release_id: str | None = None
    release_discovery_id: str | None = None
    release_matches_discovery: bool = False
    operations: list[OperationWorkItem] = Field(default_factory=list)


def load_active_discovery(artifact_root: Path, report: DiscoveryReport) -> ActiveDiscoveryReport:
    path = resolve_artifact_ref(artifact_root, report.active_discovery_report_ref)
    return ActiveDiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))


def _load_selected_report(
    artifact_root: Path, robot_id: str, discovery_id: str | None
) -> DiscoveryReport:
    return (
        load_report(artifact_root, robot_id, discovery_id)
        if discovery_id
        else load_latest_report(artifact_root, robot_id)
    )


def build_operation_workset(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    discovery_id: str | None = None,
) -> AdaptOperationWorkset:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    candidates = {candidate.operation: candidate for candidate in report.operation_candidates}
    builtins = builtin_operations()
    release_id: str | None = None
    release_discovery_id: str | None = None
    active_by_operation: dict[str, Any] = {}
    try:
        _, release, bundle, catalog = load_current_release(output_root, robot_id)
    except FileNotFoundError:
        bundle = None
    else:
        release_id = release.release_id
        release_discovery_id = release.discovery_id
        active_by_operation = {tool.operation: tool for tool in catalog.tools}
    release_matches = release_discovery_id == report.discovery_id
    bundle_operations = {item.operation for item in bundle.operations} if bundle else set()

    items: list[OperationWorkItem] = []
    for definition in canonical_operation_registry().operations:
        candidate = candidates.get(definition.operation)
        active = active_by_operation.get(definition.operation)
        if definition.operation in builtins:
            implementation = OperationImplementation.BUILTIN
        elif release_matches and definition.operation in bundle_operations:
            implementation = OperationImplementation.BUNDLE
        else:
            implementation = OperationImplementation.UNBOUND

        if release_id is None:
            registration = OperationRegistration.NOT_REGISTERED
        elif not release_matches:
            registration = OperationRegistration.STALE
        elif active is not None and active.availability in {"AVAILABLE", "VERIFIED"}:
            registration = OperationRegistration.REGISTERED
        else:
            registration = OperationRegistration.NOT_REGISTERED
        items.append(
            OperationWorkItem(
                operation=definition.operation,
                layer=definition.layer,
                applicability=(
                    OperationApplicability.OBSERVED
                    if candidate is not None
                    else OperationApplicability.NOT_OBSERVED
                ),
                implementation=implementation,
                registration=registration,
                candidate_status=candidate.status if candidate else None,
                active_availability=active.availability if active else None,
            )
        )
    return AdaptOperationWorkset(
        robot_id=robot_id,
        discovery_id=report.discovery_id,
        registry_operation_count=len(items),
        candidate_operation_count=len(candidates),
        registered_operation_count=sum(
            item.registration == OperationRegistration.REGISTERED for item in items
        ),
        release_id=release_id,
        release_discovery_id=release_discovery_id,
        release_matches_discovery=release_matches,
        operations=items,
    )


def operation_detail(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    operation: str,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    workset = build_operation_workset(artifact_root, output_root, robot_id, discovery_id)
    definition = _definition(operation)
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    candidate = next(
        (item for item in report.operation_candidates if item.operation == operation), None
    )
    item = next(item for item in workset.operations if item.operation == operation)
    active = load_active_discovery(artifact_root, report)
    related = related_executables(active, candidate) if candidate else []
    return {
        "work_item": item.model_dump(mode="json"),
        "contract": definition.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json") if candidate else None,
        "related_executable_ids": [executable.executable_id for executable in related],
        "next_queries": [
            f"adapt candidates inspect --robot {robot_id} {operation}",
            *[
                f"adapt executable inspect --robot {robot_id} {executable.executable_id}"
                for executable in related[:10]
            ],
        ],
    }


def candidate_detail(
    artifact_root: Path,
    robot_id: str,
    operation: str,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    candidate = next(
        (item for item in report.operation_candidates if item.operation == operation), None
    )
    if candidate is None:
        raise ValueError(f"no discovery candidate for operation: {operation}")
    definition = _definition(operation)
    active = load_active_discovery(artifact_root, report)
    related = related_executables(active, candidate)
    return {
        "operation": operation,
        "contract": definition.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
        "related_executables": [
            {
                "executable_id": executable.executable_id,
                "name": executable.name,
                "origin": executable.origin,
                "entrypoint": executable.invocation.entrypoint,
                "launch_references": executable.launch_analysis.references,
            }
            for executable in related
        ],
    }


def _definition(operation: str) -> CanonicalOperationDefinition:
    for definition in canonical_operation_registry().operations:
        if definition.operation == operation:
            return definition
    raise ValueError(f"operation is not defined by the product registry: {operation}")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for child in value.values() for text in _strings(child)]
    if isinstance(value, list):
        return [text for child in value for text in _strings(child)]
    return []


def related_executables(
    report: ActiveDiscoveryReport, candidate: OperationCandidate
) -> list[ExecutableDiscovery]:
    needles = {
        value.casefold()
        for value in [*candidate.evidence, *candidate.semantic_bindings]
        if len(value.strip()) >= 2
    }
    if not needles:
        return []
    ranked: list[tuple[int, ExecutableDiscovery]] = []
    for executable in report.executables:
        identity = "\n".join(
            _strings(
                {
                    "name": executable.name,
                    "path": executable.path,
                    "entrypoint": executable.invocation.entrypoint,
                    "arguments": executable.invocation.arguments,
                    "subcommands": executable.invocation.subcommands,
                    "declared_executable": executable.launch_analysis.declared_executable,
                }
            )
        ).casefold()
        launch = "\n".join(
            _strings(
                {
                    "nodes": executable.launch_analysis.nodes,
                    "arguments": executable.launch_analysis.arguments,
                    "remappings": executable.launch_analysis.remappings,
                }
            )
        ).casefold()
        score = 0
        if any(needle in identity for needle in needles):
            score += 100
        if any(needle in launch for needle in needles):
            score += 60
        if score:
            ranked.append((score, executable))
    if not ranked and len(report.executables) == 1:
        only = report.executables[0]
        communication = "\n".join(_strings(only.communication.model_dump(mode="json"))).casefold()
        if any(needle in communication for needle in needles):
            ranked.append((10, only))
    ordered = sorted(ranked, key=lambda value: (-value[0], value[1].executable_id))
    return [item for _, item in ordered]


def executable_detail(
    artifact_root: Path,
    robot_id: str,
    executable_id: str,
    discovery_id: str | None = None,
) -> ExecutableDiscovery:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    active = load_active_discovery(artifact_root, report)
    for executable in active.executables:
        if executable.executable_id == executable_id:
            return executable
    raise ValueError(f"unknown executable_id: {executable_id}")


def _declared_roots(active: ActiveDiscoveryReport) -> list[tuple[Path, bool]]:
    roots: list[tuple[Path, bool]] = []
    for key, value in active.inputs.items():
        values = value if isinstance(value, list) else []
        for item in values:
            if isinstance(item, str):
                roots.append((Path(item).expanduser().resolve(), key == "executables"))
    return roots


def resolve_evidence_path(
    artifact_root: Path,
    robot_id: str,
    reference: str,
    discovery_id: str | None = None,
) -> tuple[Path, str]:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    if reference.startswith("artifact://"):
        path = resolve_artifact_ref(artifact_root, reference)
        discovery_root = (
            ArtifactLayout(artifact_root).discovery_run(robot_id, report.discovery_id).resolve()
        )
        try:
            path.relative_to(discovery_root)
        except ValueError as exc:
            raise ValueError("artifact evidence is outside the selected discovery run") from exc
        return path, "artifact"
    active = load_active_discovery(artifact_root, report)
    path = Path(reference).expanduser().resolve()
    allowed = False
    for root, exact_file in _declared_roots(active):
        if exact_file:
            if path == root:
                allowed = True
                break
            continue
        try:
            path.relative_to(root)
        except ValueError:
            continue
        allowed = True
        break
    if not allowed:
        raise ValueError("evidence path is outside the discovery input roots")
    return path, "discovery_input"


def evidence_metadata(
    artifact_root: Path,
    robot_id: str,
    reference: str,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    path, authority = resolve_evidence_path(artifact_root, robot_id, reference, discovery_id)
    if not path.exists():
        raise FileNotFoundError(path)
    result: dict[str, Any] = {
        "reference": reference,
        "resolved_path": str(path),
        "authority": authority,
        "kind": "directory" if path.is_dir() else "file",
    }
    if path.is_file():
        result.update(size_bytes=path.stat().st_size, sha256=sha256_file(path))
    return result


def evidence_snippet(
    artifact_root: Path,
    robot_id: str,
    reference: str,
    *,
    start_line: int = 1,
    line_count: int = 80,
    max_bytes: int = 32_000,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    path, authority = resolve_evidence_path(artifact_root, robot_id, reference, discovery_id)
    if not path.is_file():
        raise ValueError("evidence snippet requires a file")
    if path.stat().st_size > 2_000_000:
        raise ValueError("evidence file exceeds the bounded text limit")
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = max(start_line, 1) - 1
    selected = "\n".join(lines[start : start + max(1, min(line_count, 200))])
    encoded = selected.encode("utf-8")[:max_bytes]
    return {
        "reference": reference,
        "authority": authority,
        "start_line": start + 1,
        "line_count": len(encoded.decode("utf-8", errors="ignore").splitlines()),
        "truncated": len(selected.encode("utf-8")) > len(encoded),
        "content": encoded.decode("utf-8", errors="ignore"),
    }


def wiki_section(
    artifact_root: Path,
    robot_id: str,
    heading: str,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    path = resolve_artifact_ref(artifact_root, report.review_ref)
    lines = path.read_text(encoding="utf-8").splitlines()
    wanted = heading.strip().lstrip("#").strip().casefold()
    start: int | None = None
    level = 0
    end = len(lines)
    for index, line in enumerate(lines):
        if line.startswith("#"):
            title = line.lstrip("#").strip().casefold()
            if start is None and wanted in title:
                start = index
                level = len(line) - len(line.lstrip("#"))
                continue
            if start is not None and len(line) - len(line.lstrip("#")) <= level:
                end = index
                break
    if start is None:
        raise ValueError(f"Wiki section not found: {heading}")
    return {
        "wiki_ref": report.review_ref,
        "heading": lines[start],
        "content": "\n".join(lines[start:end]),
    }


def wiki_search(
    artifact_root: Path,
    robot_id: str,
    query: str,
    discovery_id: str | None = None,
) -> dict[str, Any]:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    path = resolve_artifact_ref(artifact_root, report.review_ref)
    matches = [
        {"line": index, "text": line}
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if query.casefold() in line.casefold()
    ][:100]
    return {"wiki_ref": report.review_ref, "query": query, "matches": matches}


def compact_agent_boot_context(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    discovery_id: str,
) -> dict[str, Any]:
    report = _load_selected_report(artifact_root, robot_id, discovery_id)
    active = load_active_discovery(artifact_root, report)
    workset = build_operation_workset(artifact_root, output_root, robot_id, discovery_id)
    candidates = [candidate.operation for candidate in report.operation_candidates]
    return {
        "robot_id": robot_id,
        "discovery_id": report.discovery_id,
        "platform": report.platform,
        "capabilities": sorted(
            report.capability_manifest.get("expected_profile", {}).get("features", {})
        ),
        "workset": {
            "registry_operations": workset.registry_operation_count,
            "candidate_operations": workset.candidate_operation_count,
            "registered_operations": workset.registered_operation_count,
            "release_matches_discovery": workset.release_matches_discovery,
        },
        "candidate_operations": candidates,
        "discovery": {
            "technical_status": active.technical_status,
            "executable_count": len(active.executables),
            "coverage": {
                key: value.model_dump(mode="json") for key, value in active.coverage.items()
            },
            "unknown_count": len(active.unknowns),
            "warning_count": len(active.warnings),
        },
        "wiki": {"ref": report.review_ref, "injected": False},
    }
