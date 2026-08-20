from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rolo.core.hashing import sha256_bytes
from rolo.core.models import DiscoveryReport, RouteEvidence
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
    report: DiscoveryReport, artifact_root: Path | None
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


def target_fingerprint_payload(
    report: DiscoveryReport, artifact_root: Path | None = None
) -> dict[str, Any]:
    """Return stable target facts that can invalidate a generated adapter release."""
    candidates = []
    for candidate in sorted(report.operation_candidates, key=lambda item: item.operation):
        candidates.append(
            {
                "operation": candidate.operation,
                "semantic_bindings": sorted(candidate.semantic_bindings),
                "routes": sorted(
                    (_stable_route(route) for route in candidate.route_evidence),
                    key=lambda item: (item["kind"], item["resource_id"]),
                ),
            }
        )
    observed_routes = []
    for layer, probe in sorted(report.probes.items()):
        for route in observed_probe_routes(probe):
            observed_routes.append({"layer": layer, **_stable_route(route)})
    observed_routes.sort(key=lambda item: (item["layer"], item["kind"], item["resource_id"]))
    hardware = report.probes.get("hw")
    components = hardware.data.get("components", []) if hardware is not None else []
    stable_components = sorted(
        (
            {
                key: value
                for key, value in component.items()
                if key not in {"source", "observed_at"}
            }
            for component in components
            if isinstance(component, dict)
        ),
        key=lambda item: (str(item.get("kind", "")), str(item.get("name", ""))),
    )
    return {
        "schema_version": "robot-target-fingerprint/v1",
        "robot_id": report.robot_id,
        "platform": report.platform,
        "candidates": candidates,
        "observed_routes": observed_routes,
        "hardware_components": stable_components,
        "application_artifacts": _application_artifacts(report, artifact_root),
    }


def target_fingerprint_sha256(
    report: DiscoveryReport, artifact_root: Path | None = None
) -> str:
    payload = json.dumps(
        target_fingerprint_payload(report, artifact_root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)
