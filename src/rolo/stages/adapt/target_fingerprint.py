from __future__ import annotations

import json
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


def runtime_environment_from_report(report: DiscoveryReport) -> dict[str, str]:
    """Return the canonical non-secret runtime context captured by discovery."""
    for layer, field in (("ros", "runtime_environment"), ("linux", "environment")):
        probe = report.probes.get(layer)
        raw = probe.data.get(field, {}) if probe is not None else {}
        if isinstance(raw, Mapping) and raw:
            return admitted_runtime_environment(
                {str(name): str(value) for name, value in raw.items()}
            )
    return {}


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
        "runtime_environment": runtime_environment_from_report(report),
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
