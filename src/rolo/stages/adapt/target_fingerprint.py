from __future__ import annotations

import json
import os
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from rolo.core.hashing import sha256_bytes
from rolo.core.models import DiscoveryReport, RouteEvidence
from rolo.runtime_context import admitted_runtime_environment
from rolo.stages.adapt.routes import observed_probe_routes
from rolo.stages.artifact_paths import resolve_artifact_ref


def _stable_route(route: RouteEvidence) -> dict[str, Any]:
    return {
        "resource_id": route.resource_id,
        "kind": route.kind,
        "endpoint": route.endpoint,
        "interface_type": route.interface_type,
        "interface_schema_sha256": route.interface_schema_sha256,
        "provider_id": route.provider_id,
        "runtime_revision": route.runtime_revision,
        "evidence_origin": route.evidence_origin,
    }


def _application_artifacts(
    report: DiscoveryReport,
    artifact_root: Path | None,
    executable_ids: set[str] | None,
) -> list[dict[str, Any]]:
    if artifact_root is None or not report.active_discovery_report_ref:
        return []
    from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport

    path = resolve_artifact_ref(artifact_root, report.active_discovery_report_ref)
    active = ActiveDiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))
    if active.robot_id != report.robot_id or active.discovery_id != report.discovery_id:
        raise ValueError("active discovery identity differs from target fingerprint input")
    artifacts = []
    for executable in sorted(active.executables, key=lambda item: item.executable_id):
        if executable_ids is not None and executable.executable_id not in executable_ids:
            continue
        artifacts.append(
            {
                "executable_id": executable.executable_id,
                "name": executable.name,
                "origin": executable.origin,
                "sha256": executable.sha256,
                "file_format": executable.file_format,
                "architecture": executable.architecture,
                "entrypoint": executable.invocation.entrypoint,
                "binary_dependencies": executable.binary_dependencies,
                "documentation_sha256": executable.documentation_analysis.reference_sha256,
                "launch_sha256": executable.launch_analysis.reference_sha256,
                "dependency_status": executable.dependencies,
            }
        )
    return artifacts


def _hardware_components(
    report: DiscoveryReport,
    hardware_resource_ids: set[str] | None,
) -> list[dict[str, Any]]:
    probe = report.probes.get("hw")
    raw_components = probe.data.get("components", []) if probe is not None else []
    components: list[dict[str, Any]] = []
    for raw in raw_components:
        if not isinstance(raw, dict):
            continue
        stable = {
            key: value
            for key, value in raw.items()
            if key not in {"source", "observed_at"}
        }
        if hardware_resource_ids is not None and str(
            stable.get("resource_id", "")
        ) not in hardware_resource_ids:
            continue
        components.append(stable)
    return sorted(
        components,
        key=lambda item: (
            str(item.get("kind", "")),
            str(item.get("name", "")),
            json.dumps(item, ensure_ascii=False, sort_keys=True),
        ),
    )


def _selected_cli_directories(
    report: DiscoveryReport,
    operations: Collection[str] | None,
) -> list[Path]:
    requested = (
        set(operations)
        if operations is not None
        else {candidate.operation for candidate in report.operation_candidates}
    )
    directories: list[Path] = []
    for candidate in report.operation_candidates:
        if candidate.operation not in requested:
            continue
        for route in candidate.route_evidence:
            if route.kind != "cli":
                continue
            endpoints = [Path(route.endpoint).expanduser()]
            linux_probe = report.probes.get("linux")
            target_evidence = (
                linux_probe.data.get("target_evidence", {})
                if linux_probe is not None
                else {}
            )
            help_records = (
                target_evidence.get("executable_help", [])
                if isinstance(target_evidence, Mapping)
                else []
            )
            for record in help_records if isinstance(help_records, list) else []:
                if not isinstance(record, Mapping):
                    continue
                raw_path = record.get("path")
                executable_id = record.get("executable_id")
                if not isinstance(raw_path, str):
                    continue
                target_path = Path(raw_path).expanduser()
                if (
                    route.provider_id == executable_id
                    or target_path.name == Path(route.endpoint).name
                ):
                    endpoints.append(target_path)
            endpoint = next(
                (
                    candidate_path
                    for candidate_path in endpoints
                    if candidate_path.is_absolute() and candidate_path.is_file()
                ),
                None,
            )
            if endpoint is None:
                continue
            try:
                available = endpoint.is_absolute() and endpoint.is_file()
            except OSError:
                available = False
            if not available:
                continue
            try:
                parent = endpoint.resolve().parent
            except OSError:
                continue
            if parent not in directories:
                directories.append(parent)
    return sorted(directories, key=str)


def _editable_python_roots(executable_directories: Collection[Path]) -> list[Path]:
    """Return bounded project roots explicitly referenced by selected virtualenvs."""
    roots: list[Path] = []
    for executable_directory in executable_directories:
        virtualenv: Path | None = None
        for parent in (executable_directory, *executable_directory.parents):
            if (parent / "pyvenv.cfg").is_file():
                virtualenv = parent
                break
        if virtualenv is None:
            continue
        for site_packages in virtualenv.glob("lib/python*/site-packages"):
            if not site_packages.is_dir():
                continue
            for pth in sorted(site_packages.glob("*.pth")):
                try:
                    lines = pth.read_text(encoding="utf-8").splitlines()
                except OSError:
                    continue
                for line in lines:
                    value = line.strip()
                    if not value or value.startswith("#") or value.startswith("import "):
                        continue
                    referenced = Path(value).expanduser()
                    if not referenced.is_absolute():
                        referenced = site_packages / referenced
                    try:
                        root = referenced.resolve(strict=True)
                    except OSError:
                        continue
                    if not root.is_dir():
                        continue
                    try:
                        home = Path.home().resolve()
                    except OSError:
                        home = Path.home()
                    if root == home or root in home.parents:
                        continue
                    project_markers = ("pyproject.toml", "setup.py", "setup.cfg")
                    marker_found = False
                    for candidate in (root, *list(root.parents)[:3]):
                        if candidate == virtualenv or virtualenv in candidate.parents:
                            break
                        if any((candidate / marker).is_file() for marker in project_markers):
                            marker_found = True
                            break
                    if marker_found and root not in roots:
                        roots.append(root)
    return sorted(roots, key=str)


def runtime_environment_from_report(
    report: DiscoveryReport,
    *,
    operations: Collection[str] | None = None,
) -> dict[str, str]:
    """Return the canonical non-secret runtime context captured by discovery."""
    source: dict[str, str] = {}
    for layer, field in (("ros", "runtime_environment"), ("linux", "environment")):
        probe = report.probes.get(layer)
        raw = probe.data.get(field, {}) if probe is not None else {}
        if isinstance(raw, Mapping) and raw:
            source = {str(name): str(value) for name, value in raw.items()}
            break
    # Never reuse PATH captured by an older report or a generic controller probe.
    # The executable path below is rebuilt only from the selected CLI bindings.
    source.pop("PATH", None)

    # Application CLI adapters execute the exact target-observed entrypoints.
    # Preserve only existing absolute parent directories, then let the runtime
    # context validator canonicalize and bound the final PATH.  This keeps an
    # isolated virtualenv available without inheriting an arbitrary controller
    # service PATH into the release.
    executable_directories = _selected_cli_directories(report, operations)
    if executable_directories:
        source["PATH"] = os.pathsep.join(str(path) for path in executable_directories)
        editable_roots = _editable_python_roots(executable_directories)
        if editable_roots:
            existing = source.get("PYTHONPATH", "")
            source["PYTHONPATH"] = os.pathsep.join(
                [*(str(path) for path in editable_roots), existing]
            ).strip(os.pathsep)
    return admitted_runtime_environment(source, include_executable_path=True)


def target_fingerprint_payload(
    report: DiscoveryReport,
    artifact_root: Path | None = None,
    *,
    operations: Collection[str] | None = None,
) -> dict[str, Any]:
    """Return stable target facts relevant to one generated adapter release."""
    scoped = operations is not None
    requested = set(operations) if scoped else {
        candidate.operation for candidate in report.operation_candidates
    }
    available = {candidate.operation for candidate in report.operation_candidates}
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"target fingerprint operations lack discovery candidates: {missing}")
    candidates = []
    selected_candidates = sorted(
        (
            candidate
            for candidate in report.operation_candidates
            if candidate.operation in requested
        ),
        key=lambda item: item.operation,
    )
    relevant_routes: set[tuple[str, str, str]] = set()
    executable_ids: set[str] = set()
    hardware_resource_ids: set[str] = set()
    for candidate in selected_candidates:
        executable_ids.update(candidate.executable_ids)
        hardware_resource_ids.update(candidate.hardware_resource_ids)
        for route in candidate.route_evidence:
            relevant_routes.add((route.kind, route.resource_id, route.endpoint))
        candidates.append(
            {
                "operation": candidate.operation,
                "semantic_bindings": sorted(candidate.semantic_bindings),
                "executable_ids": sorted(candidate.executable_ids),
                "hardware_resource_ids": sorted(candidate.hardware_resource_ids),
                "routes": sorted(
                    (_stable_route(route) for route in candidate.route_evidence),
                    key=lambda item: (item["kind"], item["resource_id"]),
                ),
            }
        )
    observed_routes = []
    for layer, probe in sorted(report.probes.items()):
        for route in observed_probe_routes(probe):
            if (route.kind, route.resource_id, route.endpoint) not in relevant_routes:
                continue
            observed_routes.append({"layer": layer, **_stable_route(route)})
    observed_routes.sort(key=lambda item: (item["layer"], item["kind"], item["resource_id"]))
    return {
        "schema_version": "robot-target-fingerprint/v2",
        "robot_id": report.robot_id,
        "operation_scope": sorted(requested),
        "platform": report.platform,
        "runtime_environment": runtime_environment_from_report(
            report,
            operations=requested,
        ),
        "candidates": candidates,
        "observed_routes": observed_routes,
        "hardware_components": _hardware_components(
            report, hardware_resource_ids if scoped else None
        ),
        "application_artifacts": _application_artifacts(
            report, artifact_root, executable_ids if scoped else None
        ),
    }


def target_fingerprint_sha256(
    report: DiscoveryReport,
    artifact_root: Path | None = None,
    *,
    operations: Collection[str] | None = None,
) -> str:
    payload = json.dumps(
        target_fingerprint_payload(report, artifact_root, operations=operations),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)
