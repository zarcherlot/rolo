"""Small, evidence-backed application capability bundles.

Application discovery is intentionally narrower than a product registry.  The
Agent may suggest a semantic gap, but this module only turns target-observed
Middleware routes into four bounded small-car application candidates.  It never
invokes a service, action, executable, or actuator.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import DiscoveryStatus, RouteEvidence
from rolo.stages.probe.routes import observed_probe_routes
from rolo.stages.probe.target_evidence import TargetEvidenceBundle

ApplicationId = Literal["startup", "navigation", "mapping", "manipulation"]
ApplicationStatus = Literal["CANDIDATE", "PARTIAL", "NOT_FOUND"]

APPLICATION_IDS: tuple[str, ...] = ("startup", "navigation", "mapping", "manipulation")

_SIGNALS: dict[str, tuple[str, ...]] = {
    "startup": ("runtime_started",),
    "navigation": ("motion_command", "localization", "range", "frames"),
    "mapping": ("map_state",),
    "manipulation": ("arm_control", "gripper_control", "joint_state"),
}
_MINIMUM_SIGNALS: dict[str, int] = {
    "startup": 1,
    # Two independent observations prevent a lone generic topic from being
    # mistaken for a navigation application.
    "navigation": 2,
    "mapping": 1,
    "manipulation": 1,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


class ApplicationCandidate(BaseModel):
    """An untrusted semantic candidate derived from observed runtime routes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-candidate/v1"] = (
        "rolo-application-candidate/v1"
    )
    candidate_id: str = Field(pattern=r"^app-candidate-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    application: ApplicationId
    status: ApplicationStatus
    signals: list[str] = Field(min_length=1, max_length=8)
    matched_signals: list[str] = Field(default_factory=list, max_length=8)
    missing_signals: list[str] = Field(default_factory=list, max_length=8)
    matched_routes: list[RouteEvidence] = Field(default_factory=list, max_length=128)
    evidence_refs: list[str] = Field(default_factory=list, max_length=130)
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime
    limitations: list[str] = Field(default_factory=list, max_length=16)


class ApplicationAdapterOperation(BaseModel):
    """A read-only observation intent bound to route identities."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(pattern=r"^application\.[a-z]+\.[a-z0-9_.-]+$")
    kind: Literal["route_presence"] = "route_presence"
    route_resource_ids: list[str] = Field(default_factory=list, max_length=128)
    access: Literal["read"] = "read"


class ApplicationAdapterBundle(BaseModel):
    """The smallest reusable application adapter: route bindings only."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-adapter-bundle/v1"] = (
        "rolo-application-adapter-bundle/v1"
    )
    bundle_id: str = Field(pattern=r"^app-bundle-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    application: ApplicationId
    candidate_id: str = Field(pattern=r"^app-candidate-[0-9a-f]{24}$")
    candidate_status: ApplicationStatus
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access: Literal["READ_ONLY"] = "READ_ONLY"
    routes: list[RouteEvidence] = Field(default_factory=list, max_length=128)
    operations: list[ApplicationAdapterOperation] = Field(default_factory=list, max_length=16)
    generated_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


class ApplicationConformanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=96)
    status: Literal["PASS", "FAIL"]
    detail: str = Field(min_length=1, max_length=512)


class ApplicationConformanceReport(BaseModel):
    """A non-Agent verdict over one application adapter bundle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-conformance/v1"] = (
        "rolo-application-conformance/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    application: ApplicationId
    bundle_id: str = Field(pattern=r"^app-bundle-[0-9a-f]{24}$")
    adapter_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASS", "FAIL"]
    checks: list[ApplicationConformanceCheck] = Field(min_length=1, max_length=32)
    checked_at: datetime = Field(default_factory=_utc_now)


def _route_text(route: RouteEvidence) -> str:
    return " ".join(
        item.lower()
        for item in (route.endpoint, route.interface_type or "", route.provider_id or "")
    )


def _signal_matches(signal: str, route: RouteEvidence) -> bool:
    """Map provider-observed route shapes to a small semantic signal vocabulary."""

    text = _route_text(route)
    if signal == "runtime_started":
        if route.kind == "ros_service":
            if any(
                token in text for token in ("init_finish", "startup", "ready", "lifecycle")
            ):
                return True
            return not any(
                token in route.endpoint.lower()
                for token in (
                    "/describe_parameters",
                    "/get_parameter_types",
                    "/get_parameters",
                    "/list_parameters",
                    "/set_parameters",
                    "/set_parameters_atomically",
                )
            )
        if route.kind == "ros_action":
            return True
        if route.kind == "ros_topic":
            return route.endpoint not in {"/parameter_events", "/tf", "/tf_static"}
        return False
    if signal == "motion_command":
        return route.kind == "ros_topic" and (
            "cmd_vel" in text or "twist" in text
        )
    if signal == "localization":
        return route.kind == "ros_topic" and ("odom" in text or "odometry" in text)
    if signal == "range":
        return route.kind == "ros_topic" and ("scan" in text or "laserscan" in text)
    if signal == "frames":
        return route.kind == "ros_topic" and ("/tf" in text or "tf_static" in text)
    if signal == "map_state":
        return (
            route.kind in {"ros_topic", "ros_service", "ros_action"}
            and any(
                token in text
                for token in (
                    "/map",
                    "occupancygrid",
                    "occupancy_grid",
                    "slam",
                    "costmap",
                )
            )
        )
    if signal == "arm_control":
        return route.kind == "ros_action" and (
            "arm" in text or "follow_joint_trajectory" in text
        )
    if signal == "gripper_control":
        return route.kind == "ros_action" and "gripper" in text
    if signal == "joint_state":
        return route.kind == "ros_topic" and ("joint" in text or "servo" in text)
    return False


def _observed_routes(bundle: TargetEvidenceBundle) -> list[RouteEvidence]:
    routes: dict[str, RouteEvidence] = {}
    for probe in bundle.probes.values():
        if probe.status not in {DiscoveryStatus.SUCCEEDED, DiscoveryStatus.PARTIAL}:
            continue
        for route in observed_probe_routes(probe):
            routes[route.resource_id] = route
    return [routes[key] for key in sorted(routes)]


def discover_application_candidate(
    bundle: TargetEvidenceBundle, application: ApplicationId
) -> ApplicationCandidate:
    """Discover one application candidate without claiming it is functioning."""

    if application not in APPLICATION_IDS:
        raise ValueError(f"unsupported application: {application}")
    routes = _observed_routes(bundle)
    signals = _SIGNALS[application]
    matched_signals = [
        signal for signal in signals if any(_signal_matches(signal, route) for route in routes)
    ]
    missing_signals = [signal for signal in signals if signal not in matched_signals]
    matched_routes = [
        route
        for route in routes
        if any(signal in matched_signals and _signal_matches(signal, route) for signal in signals)
    ]
    matched_routes = sorted(
        {route.resource_id: route for route in matched_routes}.values(),
        key=lambda item: item.resource_id,
    )
    minimum = _MINIMUM_SIGNALS[application]
    if not matched_signals:
        status: ApplicationStatus = "NOT_FOUND"
    elif len(matched_signals) < minimum:
        status = "PARTIAL"
    else:
        status = "CANDIDATE"
    candidate_seed = {
        "robot_id": bundle.robot_id,
        "application": application,
        "target_evidence_sha256": bundle.payload_sha256,
        "status": status,
        "matched_route_ids": [route.resource_id for route in matched_routes],
    }
    candidate_id = f"app-candidate-{_digest(candidate_seed)[:24]}"
    return ApplicationCandidate(
        candidate_id=candidate_id,
        robot_id=bundle.robot_id,
        application=application,
        status=status,
        signals=list(signals),
        matched_signals=matched_signals,
        missing_signals=missing_signals,
        matched_routes=matched_routes,
        evidence_refs=[
            f"target-evidence:{bundle.payload_sha256}",
            *(f"route:{route.resource_id}" for route in matched_routes),
        ],
        confidence=round(len(matched_signals) / len(signals), 3),
        observed_at=bundle.collected_at,
        limitations=[
            "Route presence is not proof that the application is healthy or behaviorally correct",
            "No service, action, executable, or actuator was invoked during discovery",
        ],
    )


def discover_application_candidates(bundle: TargetEvidenceBundle) -> list[ApplicationCandidate]:
    return [
        discover_application_candidate(bundle, application)  # type: ignore[arg-type]
        for application in APPLICATION_IDS
    ]


def candidate_sha256(candidate: ApplicationCandidate) -> str:
    return _digest(candidate.model_dump(mode="json"))


def adapter_bundle_sha256(bundle: ApplicationAdapterBundle) -> str:
    return _digest(bundle.model_dump(mode="json"))


def _minimum_route_bindings(candidate: ApplicationCandidate) -> list[RouteEvidence]:
    """Select one deterministic route per minimum signal for a small bundle."""

    selected: list[RouteEvidence] = []
    minimum = _MINIMUM_SIGNALS[candidate.application]
    for signal in candidate.matched_signals[:minimum]:
        route = next(
            (item for item in candidate.matched_routes if _signal_matches(signal, item)),
            None,
        )
        if route is not None and route.resource_id not in {item.resource_id for item in selected}:
            selected.append(route)
    return selected


def build_application_adapter_bundle(
    candidate: ApplicationCandidate,
    *,
    target_evidence_sha256: str,
) -> ApplicationAdapterBundle:
    """Build a route-only bundle, including a rejected candidate for auditability."""

    routes = _minimum_route_bindings(candidate)
    route_ids = [route.resource_id for route in routes]
    operations = []
    if route_ids:
        operations.append(
            ApplicationAdapterOperation(
                operation_id=f"application.{candidate.application}.route_presence",
                route_resource_ids=route_ids,
            )
        )
    seed = {
        "robot_id": candidate.robot_id,
        "application": candidate.application,
        "candidate_id": candidate.candidate_id,
        "candidate_sha256": candidate_sha256(candidate),
        "target_evidence_sha256": target_evidence_sha256,
        "route_ids": route_ids,
    }
    bundle_id = f"app-bundle-{_digest(seed)[:24]}"
    return ApplicationAdapterBundle(
        bundle_id=bundle_id,
        robot_id=candidate.robot_id,
        application=candidate.application,
        candidate_id=candidate.candidate_id,
        candidate_status=candidate.status,
        candidate_sha256=candidate_sha256(candidate),
        target_evidence_sha256=target_evidence_sha256,
        routes=routes,
        operations=operations,
        limitations=candidate.limitations,
    )


def conform_application_bundle(
    bundle: ApplicationAdapterBundle,
    candidate: ApplicationCandidate,
    evidence: TargetEvidenceBundle,
) -> ApplicationConformanceReport:
    """Independently verify candidate, target evidence, route identity and safety."""

    checks: list[ApplicationConformanceCheck] = []

    def check(name: str, ok: bool, passed: str, failed: str) -> None:
        checks.append(
            ApplicationConformanceCheck(
                name=name,
                status="PASS" if ok else "FAIL",
                detail=passed if ok else failed,
            )
        )

    check(
        "candidate_binding",
        bundle.candidate_id == candidate.candidate_id
        and bundle.candidate_sha256 == candidate_sha256(candidate)
        and bundle.application == candidate.application
        and bundle.robot_id == candidate.robot_id,
        "bundle is bound to the exact candidate",
        "bundle candidate identity or digest does not match",
    )
    check(
        "target_evidence_binding",
        bundle.target_evidence_sha256 == evidence.payload_sha256
        and evidence.robot_id == bundle.robot_id,
        "bundle is bound to the target evidence payload",
        "bundle target evidence identity does not match",
    )
    observed = {
        route.resource_id: route
        for route in _observed_routes(evidence)
    }
    routes_ok = bool(bundle.routes) and all(
        route.evidence_origin == "OBSERVED_RUNTIME"
        and route.resource_id in observed
        and observed[route.resource_id].model_dump(mode="json") == route.model_dump(mode="json")
        for route in bundle.routes
    )
    check(
        "runtime_route_bindings",
        routes_ok,
        "every adapter route is an exact runtime-observed route",
        "adapter contains no complete set of exact runtime-observed routes",
    )
    operation_refs_ok = all(
        operation.access == "read"
        and operation.kind == "route_presence"
        and set(operation.route_resource_ids).issubset(
            {route.resource_id for route in bundle.routes}
        )
        for operation in bundle.operations
    )
    check(
        "read_only_operations",
        bundle.access == "READ_ONLY" and operation_refs_ok,
        "bundle operations are route-presence observations only",
        "bundle declares a non-read-only or unbound operation",
    )
    check(
        "candidate_status",
        bundle.candidate_status == "CANDIDATE" and candidate.status == "CANDIDATE",
        "candidate meets the minimum signal threshold",
        f"candidate status is {candidate.status}; minimum signal threshold is not met",
    )
    return ApplicationConformanceReport(
        robot_id=bundle.robot_id,
        application=bundle.application,
        bundle_id=bundle.bundle_id,
        adapter_bundle_sha256=adapter_bundle_sha256(bundle),
        status="PASS" if all(item.status == "PASS" for item in checks) else "FAIL",
        checks=checks,
    )


__all__ = [
    "APPLICATION_IDS",
    "ApplicationAdapterBundle",
    "ApplicationAdapterOperation",
    "ApplicationCandidate",
    "ApplicationConformanceCheck",
    "ApplicationConformanceReport",
    "adapter_bundle_sha256",
    "build_application_adapter_bundle",
    "candidate_sha256",
    "conform_application_bundle",
    "discover_application_candidate",
    "discover_application_candidates",
]
