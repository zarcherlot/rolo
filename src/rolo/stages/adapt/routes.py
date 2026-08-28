from __future__ import annotations

from rolo.core.models import (
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
)

ROUTE_PROBE_LAYER = {
    "ros_topic": "ros",
    "ros_service": "ros",
    "ros_action": "ros",
    "device": "hw",
    "cli": "linux",
}


def _ros_endpoint_and_type(value: object) -> tuple[str, str | None]:
    parts = str(value).strip().split(maxsplit=1)
    if not parts:
        return "", None
    endpoint = f"/{parts[0].lstrip('/')}"
    interface_type = parts[1].strip() if len(parts) == 2 else None
    if interface_type and interface_type.startswith("[") and interface_type.endswith("]"):
        interface_type = interface_type[1:-1].strip()
    return endpoint, interface_type or None


def legacy_probe_routes(probe: ProbeResult) -> list[RouteEvidence]:
    """Normalize legacy probe payloads without inferring operation success."""
    routes: list[RouteEvidence] = []
    if probe.layer == "ros":
        for kind, field in {
            "ros_topic": "topics",
            "ros_service": "services",
            "ros_action": "actions",
        }.items():
            for value in probe.data.get(field, []):
                if not isinstance(value, str):
                    continue
                endpoint, interface_type = _ros_endpoint_and_type(value)
                if endpoint:
                    routes.append(
                        RouteEvidence(
                            resource_id=f"{kind}:{endpoint}",
                            kind=kind,
                            endpoint=endpoint,
                            interface_type=interface_type,
                            runtime_revision=":".join(
                                str(item)
                                for item in (
                                    probe.data.get("ros_distro"),
                                    probe.data.get("rmw"),
                                )
                                if item
                            )
                            or None,
                            observed_at=probe.observed_at,
                            evidence_origin="OBSERVED_RUNTIME",
                            source="runtime_probe:ros",
                            limitations=[
                                "ROS interface schema digest was not collected",
                                "ROS provider identity was not collected",
                            ],
                        )
                    )
    elif probe.layer == "hw":
        for value in probe.data.get("devices", []):
            if not isinstance(value, dict) or not value.get("path"):
                continue
            endpoint = str(value["path"])
            routes.append(
                RouteEvidence(
                    resource_id=f"device:{endpoint}",
                    kind="device",
                    endpoint=endpoint,
                    interface_type=value.get("category"),
                    provider_id=value.get("driver"),
                    runtime_revision=value.get("model"),
                    observed_at=probe.observed_at,
                    evidence_origin="OBSERVED_RUNTIME",
                    source="runtime_probe:hw",
                    limitations=["Device interface schema digest is not applicable or unavailable"],
                )
            )
    elif probe.layer == "linux":
        executables = probe.data.get("executables", {})
        if isinstance(executables, dict):
            for name, value in executables.items():
                if not isinstance(value, dict) or not value.get("available"):
                    continue
                revision = "\n".join(str(item) for item in value.get("version_output", [])) or None
                endpoints = {str(name)}
                if value.get("path"):
                    endpoints.add(str(value["path"]))
                for endpoint in endpoints:
                    routes.append(
                        RouteEvidence(
                            resource_id=f"cli:{endpoint}",
                            kind="cli",
                            endpoint=endpoint,
                            provider_id=str(value.get("path") or name),
                            runtime_revision=revision,
                            observed_at=probe.observed_at,
                            evidence_origin="OBSERVED_RUNTIME",
                            source="runtime_probe:linux",
                            limitations=["CLI interface schema digest is not applicable"],
                        )
                    )
    return routes


def probe_routes(probe: ProbeResult) -> list[RouteEvidence]:
    """Return every structured route, including static declarations.

    Legacy probe payloads only describe runtime observations, so their
    normalized routes remain observed.  Keeping this broader reader separate
    from :func:`observed_probe_routes` lets the mapping Agent reference static
    application entrypoints without allowing them to satisfy a runtime gate.
    """
    structured = probe.data.get("route_evidence", [])
    if structured:
        return [RouteEvidence.model_validate(item) for item in structured]
    return legacy_probe_routes(probe)


def observed_probe_routes(probe: ProbeResult) -> list[RouteEvidence]:
    return [route for route in probe_routes(probe) if route.observed]


def persist_route_evidence(probe: ProbeResult) -> ProbeResult:
    """Attach immutable v2 route records while retaining existing probe fields."""
    if "route_evidence" in probe.data:
        routes = [RouteEvidence.model_validate(item) for item in probe.data["route_evidence"]]
        enrichment = probe.data.get("route_enrichment")
        if probe.layer == "ros" and isinstance(enrichment, dict):
            providers = enrichment.get("provider_ids", {})
            schemas = enrichment.get("interface_schema_sha256", {})
            routes = [
                route.model_copy(
                    update={
                        "provider_id": route.provider_id or providers.get(route.endpoint),
                        "interface_schema_sha256": route.interface_schema_sha256
                        or schemas.get(route.interface_type),
                        "limitations": [
                            item
                            for item in route.limitations
                            if not (
                                item == "ROS interface schema digest was not collected"
                                and schemas.get(route.interface_type)
                            )
                            and not (
                                item == "ROS provider identity was not collected"
                                and providers.get(route.endpoint)
                            )
                        ],
                    }
                )
                for route in routes
            ]
            data = dict(probe.data)
            data["route_evidence"] = [route.model_dump(mode="json") for route in routes]
            return probe.model_copy(update={"data": data})
        observed_probe_routes(probe)
        return probe
    data = dict(probe.data)
    routes = legacy_probe_routes(probe)
    enrichment = probe.data.get("route_enrichment")
    if probe.layer == "ros" and isinstance(enrichment, dict):
        providers = enrichment.get("provider_ids", {})
        schemas = enrichment.get("interface_schema_sha256", {})
        routes = [
            route.model_copy(
                update={
                    "provider_id": providers.get(route.endpoint),
                    "interface_schema_sha256": schemas.get(route.interface_type),
                    "limitations": [
                        item
                        for item in route.limitations
                        if not (
                            item == "ROS interface schema digest was not collected"
                            and schemas.get(route.interface_type)
                        )
                        and not (
                            item == "ROS provider identity was not collected"
                            and providers.get(route.endpoint)
                        )
                    ],
                }
            )
            for route in routes
        ]
    data["route_evidence"] = [route.model_dump(mode="json") for route in routes]
    return probe.model_copy(update={"data": data})


def _route_matches(expected: RouteEvidence, observed: RouteEvidence) -> bool:
    if (
        expected.kind != observed.kind
        or expected.resource_id != observed.resource_id
        or expected.endpoint != observed.endpoint
    ):
        return False
    for field in (
        "interface_type",
        "interface_schema_sha256",
        "provider_id",
        "runtime_revision",
    ):
        expected_value = getattr(expected, field)
        if expected_value is not None and expected_value != getattr(observed, field):
            return False
    return True


def candidate_route_observed(candidate: OperationCandidate, probes: dict[str, ProbeResult]) -> bool:
    """Require one exact v2 route match against target-observed probe evidence."""
    for route in candidate.route_evidence:
        probe = probes.get(ROUTE_PROBE_LAYER[route.kind])
        if probe is None or probe.status not in {
            DiscoveryStatus.SUCCEEDED,
            DiscoveryStatus.PARTIAL,
        }:
            continue
        if any(_route_matches(route, observed) for observed in observed_probe_routes(probe)):
            return True
    return False


def candidate_routes_fully_observed(
    candidate: OperationCandidate, probes: dict[str, ProbeResult]
) -> bool:
    """Require every declared route to have an exact target observation.

    The previous helper intentionally answered the weaker question "did any route
    match?".  That is useful for applicability, but it is not sufficient to
    promote a multi-route adapter to a runtime-verified catalog entry.
    """
    if not candidate.route_evidence:
        return False
    for route in candidate.route_evidence:
        probe = probes.get(ROUTE_PROBE_LAYER[route.kind])
        if probe is None or probe.status not in {
            DiscoveryStatus.SUCCEEDED,
            DiscoveryStatus.PARTIAL,
        }:
            return False
        if not any(_route_matches(route, observed) for observed in observed_probe_routes(probe)):
            return False
    return True


def candidate_runtime_evidence_complete(
    candidate: OperationCandidate, probes: dict[str, ProbeResult]
) -> bool:
    """Check provider/schema/revision evidence for every observed route."""
    if not candidate_routes_fully_observed(candidate, probes):
        return False
    # Legacy v2 snapshots predate the enrichment collector.  Preserve their
    # historical route-only semantics for compatibility; production probes set
    # ``route_enrichment`` and therefore take the strict evidence path below.
    strict_ros_evidence = any(
        route.kind.startswith("ros_")
        and isinstance((probe := probes.get(ROUTE_PROBE_LAYER[route.kind])), ProbeResult)
        and "route_enrichment" in probe.data
        for route in candidate.route_evidence
    )
    if not strict_ros_evidence:
        return True
    for route in candidate.route_evidence:
        probe = probes.get(ROUTE_PROBE_LAYER[route.kind])
        assert probe is not None
        observed = next(
            item for item in observed_probe_routes(probe) if _route_matches(route, item)
        )
        if route.kind.startswith("ros_") and not (
            observed.provider_id and observed.interface_schema_sha256 and observed.runtime_revision
        ):
            return False
    return True
