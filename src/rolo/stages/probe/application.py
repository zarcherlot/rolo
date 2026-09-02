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


class ApplicationOperationRule(BaseModel):
    """Provider-neutral discovery rule for one v1 application operation."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(pattern=r"^app\.[a-z][a-z0-9_.-]+$")
    signals: list[str] = Field(min_length=1, max_length=8)
    minimum_signals: int = Field(ge=1, le=8)
    risk: Literal["R0", "R1"]
    description: str = Field(min_length=1, max_length=256)


# This is deliberately a small first slice of the v1 vocabulary.  The complete
# inventory and migration order are documented in
# docs/probe/APPLICATION_OPERATION_V1_INVENTORY.md.
APPLICATION_OPERATION_RULES: dict[str, ApplicationOperationRule] = {
    operation_id: ApplicationOperationRule(
        operation_id=operation_id,
        signals=signals,
        minimum_signals=minimum,
        risk=risk,
        description=description,
    )
    for operation_id, signals, minimum, risk, description in (
        (
            "app.robot.discover",
            ["runtime_started"],
            1,
            "R0",
            "Discover a running application "
            "runtime",
        ),
        (
            "app.robot.status",
            ["runtime_started"],
            1,
            "R0",
            "Observe application lifecycle "
            "readiness",
        ),
        (
            "app.robot.health",
            ["runtime_started"],
            1,
            "R0",
            "Observe application runtime health "
            "routes",
        ),
        ("app.base.status", ["motion_command"], 1, "R0", "Observe mobile-base control routes"),
        ("app.localization.status", ["localization"], 1, "R0", "Observe localization routes"),
        ("app.localization.pose", ["localization"], 1, "R0", "Observe a localization pose route"),
        (
            "app.localization.quality",
            ["localization"],
            1,
            "R0",
            "Observe localization quality "
            "routes",
        ),
        ("app.odometry.status", ["localization"], 1, "R0", "Observe odometry status routes"),
        ("app.odometry.sample", ["localization"], 1, "R1", "Observe bounded odometry samples"),
        ("app.lidar.list", ["range"], 1, "R0", "Discover application-visible range routes"),
        ("app.lidar.status", ["range"], 1, "R0", "Observe range sensor status routes"),
        ("app.lidar.inspect", ["range"], 1, "R0", "Inspect range sensor routes"),
        ("app.lidar.snapshot", ["range"], 1, "R0", "Observe a bounded range snapshot route"),
        ("app.camera.snapshot", ["image"], 1, "R0", "Observe a bounded camera image route"),
        (
            "app.navigation.status",
            ["motion_command", "localization"],
            2,
            "R0",
            "Observe navigation readiness routes",
        ),
        (
            "app.navigation.plan",
            ["motion_command", "localization"],
            2,
            "R1",
            "Discover bounded navigation planning inputs",
        ),
        ("app.map.inspect", ["map_state"], 1, "R0", "Observe map metadata routes"),
        ("app.map.list", ["map_state"], 1, "R0", "Discover visible map routes"),
        ("app.map.export", ["map_state"], 1, "R1", "Discover bounded map export routes"),
        ("app.navigation.costmap.inspect", ["costmap"], 1, "R0", "Observe costmap metadata routes"),
        ("app.navigation.path.inspect", ["path"], 1, "R0", "Observe navigation path routes"),
        (
            "app.manipulation.status",
            ["arm_control", "joint_state"],
            1,
            "R0",
            "Observe manipulator control routes",
        ),
        (
            "app.manipulation.plan",
            ["arm_control", "joint_state"],
            1,
            "R1",
            "Discover bounded manipulation planning inputs",
        ),
        (
            "app.gripper.status",
            ["gripper_control", "joint_state"],
            1,
            "R0",
            "Observe gripper control routes",
        ),
        ("app.imu.list", ["imu"], 1, "R0", "Discover inertial sensor routes"),
        ("app.imu.status", ["imu"], 1, "R0", "Observe inertial sensor status routes"),
        ("app.imu.inspect", ["imu"], 1, "R0", "Inspect inertial sensor routes"),
        ("app.imu.sample", ["imu"], 1, "R1", "Observe bounded inertial samples"),
        ("app.gnss.list", ["gnss"], 1, "R0", "Discover GNSS routes"),
        ("app.gnss.status", ["gnss"], 1, "R0", "Observe GNSS status routes"),
        ("app.gnss.inspect", ["gnss"], 1, "R0", "Inspect GNSS routes"),
        ("app.gnss.sample", ["gnss"], 1, "R1", "Observe bounded GNSS samples"),
    )
}

_V1_WRITE_OPERATION_IDS = {
    "app.teleop.velocity", "app.safety.emergency_stop", "app.safety.protective_stop",
    "app.safety.stop.clear", "app.camera.stream.start", "app.camera.stream.stop",
    "app.localization.initialize", "app.localization.reset", "app.localization.relocalize",
    "app.map.create", "app.map.save", "app.map.load", "app.map.clear", "app.map.import",
    "app.parameter.set", "app.parameter.rollback", "app.odometry.reset",
    "app.tuning.baseline.create", "app.tuning.candidate.create", "app.tuning.commit",
    "app.tuning.rollback", "app.task.start", "app.task.cancel", "app.task.pause",
    "app.task.resume", "app.task.stop", "app.test.run", "app.test.cancel",
    "app.regression.run", "app.regression.cancel", "app.diagnosis.run", "app.diagnosis.cancel",
    "app.teleop.pose", "app.teleop.joint", "app.teleop.stop", "app.base.velocity",
    "app.base.move_distance", "app.base.rotate", "app.base.stop", "app.base.recover",
    "app.manipulation.execute", "app.manipulation.cancel", "app.manipulation.stop",
    "app.manipulation.home", "app.gripper.open", "app.gripper.close", "app.gripper.set",
    "app.gripper.stop", "app.navigation.start", "app.navigation.pause", "app.navigation.resume",
    "app.navigation.cancel", "app.navigation.stop", "app.navigation.recover",
    "app.robot.start", "app.robot.stop", "app.robot.restart",
    "app.calibration.run", "app.calibration.apply", "app.calibration.rollback",
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
                )
            )
        )
    if signal == "costmap":
        return route.kind in {"ros_topic", "ros_service", "ros_action"} and "costmap" in text
    if signal == "path":
        return route.kind in {"ros_topic", "ros_service", "ros_action"} and (
            "path" in text or "nav_msgs/msg/path" in text
        )
    if signal == "arm_control":
        return route.kind == "ros_action" and (
            "arm" in text or "follow_joint_trajectory" in text
        )
    if signal == "gripper_control":
        return route.kind == "ros_action" and "gripper" in text
    if signal == "joint_state":
        return route.kind == "ros_topic" and ("joint" in text or "servo" in text)
    if signal == "image":
        return route.kind == "ros_topic" and (
            "image" in text or "sensor_msgs/msg/image" in text
        )
    if signal == "imu":
        return route.kind == "ros_topic" and (
            "imu" in text or "inertial" in text or "sensor_msgs/msg/imu" in text
        )
    if signal == "gnss":
        return route.kind == "ros_topic" and any(
            token in text for token in ("gnss", "gps", "navsat", "nav_sat", "satfix")
        )
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


OperationCandidateStatus = Literal[
    "CANDIDATE", "PARTIAL", "NOT_FOUND", "UNMAPPED", "DEFERRED", "UNSUPPORTED"
]


class ApplicationOperationCandidate(BaseModel):
    """One v1 application operation evaluated against target runtime evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-operation-candidate/v1"] = (
        "rolo-application-operation-candidate/v1"
    )
    candidate_id: str = Field(pattern=r"^app-operation-candidate-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: str = Field(pattern=r"^app\.[a-z][a-z0-9_.-]+$")
    access: Literal["read", "write", "unknown"]
    risk: Literal["R0", "R1", "R2", "R3"] | None = None
    status: OperationCandidateStatus
    signals: list[str] = Field(min_length=1, max_length=8)
    matched_signals: list[str] = Field(default_factory=list, max_length=8)
    missing_signals: list[str] = Field(default_factory=list, max_length=8)
    matched_routes: list[RouteEvidence] = Field(default_factory=list, max_length=128)
    evidence_refs: list[str] = Field(default_factory=list, max_length=130)
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime
    limitations: list[str] = Field(default_factory=list, max_length=16)


class ApplicationOperationObservation(BaseModel):
    """A route-presence observation intent for one semantic operation."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(pattern=r"^app\.[a-z][a-z0-9_.-]+$")
    kind: Literal["route_presence"] = "route_presence"
    route_resource_ids: list[str] = Field(default_factory=list, max_length=128)
    tool_id: str = Field(pattern=r"^native\.(hardware|os|middleware)\.[a-z0-9_.-]+$")
    mode: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    arguments: dict[str, str] = Field(default_factory=dict, max_length=8)
    access: Literal["read"] = "read"


class ApplicationOperationAdapterBundle(BaseModel):
    """The operation-level equivalent of the four-family application bundle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-operation-adapter-bundle/v1"] = (
        "rolo-application-operation-adapter-bundle/v1"
    )
    bundle_id: str = Field(pattern=r"^app-operation-bundle-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: str = Field(pattern=r"^app\.[a-z][a-z0-9_.-]+$")
    candidate_id: str = Field(pattern=r"^app-operation-candidate-[0-9a-f]{24}$")
    candidate_status: OperationCandidateStatus
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access: Literal["READ_ONLY", "DEFERRED_WRITE", "UNSUPPORTED"]
    routes: list[RouteEvidence] = Field(default_factory=list, max_length=128)
    observations: list[ApplicationOperationObservation] = Field(
        default_factory=list, max_length=8
    )
    generated_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


class ApplicationOperationConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-operation-conformance/v1"] = (
        "rolo-application-operation-conformance/v1"
    )
    conformance_scope: Literal["ROUTE_BINDING"] = "ROUTE_BINDING"
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: str = Field(pattern=r"^app\.[a-z][a-z0-9_.-]+$")
    bundle_id: str = Field(pattern=r"^app-operation-bundle-[0-9a-f]{24}$")
    adapter_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASS", "FAIL"]
    checks: list[ApplicationConformanceCheck] = Field(min_length=1, max_length=32)
    checked_at: datetime = Field(default_factory=_utc_now)


def _operation_candidate_id(
    bundle: TargetEvidenceBundle,
    operation_id: str,
    status: OperationCandidateStatus,
    routes: list[RouteEvidence],
) -> str:
    return "app-operation-candidate-" + _digest(
        {
            "robot_id": bundle.robot_id,
            "operation_id": operation_id,
            "target_evidence_sha256": bundle.payload_sha256,
            "status": status,
            "route_ids": [route.resource_id for route in routes],
        }
    )[:24]


def application_operation_rule(operation_id: str) -> ApplicationOperationRule | None:
    return APPLICATION_OPERATION_RULES.get(operation_id)


def discover_application_operation(
    bundle: TargetEvidenceBundle,
    operation_id: str,
) -> ApplicationOperationCandidate:
    """Evaluate one v1 operation; writes are explicitly deferred, never invoked."""

    if not operation_id.startswith("app.") or len(operation_id) > 128:
        raise ValueError("application operation must use an app.* identifier")
    rule = application_operation_rule(operation_id)
    if rule is None:
        is_write = operation_id in _V1_WRITE_OPERATION_IDS
        status: OperationCandidateStatus = "DEFERRED" if is_write else "UNSUPPORTED"
        access: Literal["read", "write", "unknown"] = "write" if is_write else "unknown"
        signals = ["write_authorization"] if is_write else ["operation_rule"]
        limitations = [
            "v1 write operation is not exposed by the Probe Tool Surface"
            if is_write
            else "operation is not in the current verified v2 operation slice",
            "No service, action, executable, or actuator was invoked",
        ]
        candidate_id = _operation_candidate_id(bundle, operation_id, status, [])
        return ApplicationOperationCandidate(
            candidate_id=candidate_id,
            robot_id=bundle.robot_id,
            operation_id=operation_id,
            access=access,
            status=status,
            signals=signals,
            missing_signals=signals,
            evidence_refs=[f"target-evidence:{bundle.payload_sha256}"],
            confidence=0.0,
            observed_at=bundle.collected_at,
            limitations=limitations,
        )

    routes = _observed_routes(bundle)
    matched_signals = [
        signal for signal in rule.signals if any(_signal_matches(signal, route) for route in routes)
    ]
    missing_signals = [signal for signal in rule.signals if signal not in matched_signals]
    matched_routes = [
        route
        for route in routes
        if any(_signal_matches(signal, route) for signal in matched_signals)
    ]
    matched_routes = sorted(
        {route.resource_id: route for route in matched_routes}.values(),
        key=lambda item: item.resource_id,
    )
    if not matched_signals:
        status = "NOT_FOUND"
    elif len(matched_signals) < rule.minimum_signals:
        status = "PARTIAL"
    else:
        status = "CANDIDATE"
    candidate_id = _operation_candidate_id(bundle, operation_id, status, matched_routes)
    return ApplicationOperationCandidate(
        candidate_id=candidate_id,
        robot_id=bundle.robot_id,
        operation_id=operation_id,
        access="read",
        risk=rule.risk,
        status=status,
        signals=rule.signals,
        matched_signals=matched_signals,
        missing_signals=missing_signals,
        matched_routes=matched_routes,
        evidence_refs=[
            f"target-evidence:{bundle.payload_sha256}",
            *(f"route:{route.resource_id}" for route in matched_routes),
        ],
        confidence=round(len(matched_signals) / len(rule.signals), 3),
        observed_at=bundle.collected_at,
        limitations=[
            "Route presence is not proof that the application operation is behaviorally correct",
            "No service, action, executable, or actuator was invoked during discovery",
        ],
    )


def application_operation_candidate_sha256(
    candidate: ApplicationOperationCandidate,
) -> str:
    return _digest(candidate.model_dump(mode="json"))


def application_operation_bundle_sha256(
    bundle: ApplicationOperationAdapterBundle,
) -> str:
    return _digest(bundle.model_dump(mode="json"))


def _minimum_operation_routes(
    candidate: ApplicationOperationCandidate,
) -> list[RouteEvidence]:
    rule = application_operation_rule(candidate.operation_id)
    if rule is None:
        return []
    selected: list[RouteEvidence] = []
    for signal in candidate.matched_signals[: rule.minimum_signals]:
        route = next(
            (item for item in candidate.matched_routes if _signal_matches(signal, item)),
            None,
        )
        if route is not None and route.resource_id not in {item.resource_id for item in selected}:
            selected.append(route)
    return selected


def _operation_observation(
    operation_id: str,
    route: RouteEvidence,
) -> ApplicationOperationObservation:
    """Bind a route to an existing public native observation Tool shape."""

    sample_operations = {
        "app.camera.snapshot",
        "app.gnss.sample",
        "app.imu.sample",
        "app.lidar.snapshot",
        "app.odometry.sample",
    }
    if operation_id in sample_operations and route.kind == "ros_topic":
        return ApplicationOperationObservation(
            operation_id=operation_id,
            route_resource_ids=[route.resource_id],
            tool_id="native.middleware.observe",
            mode="sample",
            arguments={"topic": route.endpoint},
        )
    if route.kind == "ros_topic":
        return ApplicationOperationObservation(
            operation_id=operation_id,
            route_resource_ids=[route.resource_id],
            tool_id="native.middleware.graph.inspect",
            mode="topic_describe",
            arguments={"topic": route.endpoint},
        )
    if route.kind == "ros_service":
        return ApplicationOperationObservation(
            operation_id=operation_id,
            route_resource_ids=[route.resource_id],
            tool_id="native.middleware.graph.inspect",
            mode="service_describe",
            arguments={"name": route.endpoint},
        )
    if route.kind == "ros_action":
        return ApplicationOperationObservation(
            operation_id=operation_id,
            route_resource_ids=[route.resource_id],
            tool_id="native.middleware.graph.inspect",
            mode="action_describe",
            arguments={"name": route.endpoint},
        )
    raise ValueError(f"operation route cannot be bound to a native observation tool: {route.kind}")


def build_application_operation_adapter_bundle(
    candidate: ApplicationOperationCandidate,
    *,
    target_evidence_sha256: str,
) -> ApplicationOperationAdapterBundle:
    routes = _minimum_operation_routes(candidate)
    access: Literal["READ_ONLY", "DEFERRED_WRITE", "UNSUPPORTED"] = (
        "READ_ONLY"
        if candidate.access == "read"
        else "DEFERRED_WRITE"
        if candidate.access == "write"
        else "UNSUPPORTED"
    )
    observations = (
        [_operation_observation(candidate.operation_id, route) for route in routes]
        if routes and access == "READ_ONLY"
        else []
    )
    seed = {
        "robot_id": candidate.robot_id,
        "operation_id": candidate.operation_id,
        "candidate_id": candidate.candidate_id,
        "candidate_sha256": application_operation_candidate_sha256(candidate),
        "target_evidence_sha256": target_evidence_sha256,
        "route_ids": [route.resource_id for route in routes],
    }
    bundle_id = "app-operation-bundle-" + _digest(seed)[:24]
    return ApplicationOperationAdapterBundle(
        bundle_id=bundle_id,
        robot_id=candidate.robot_id,
        operation_id=candidate.operation_id,
        candidate_id=candidate.candidate_id,
        candidate_status=candidate.status,
        candidate_sha256=application_operation_candidate_sha256(candidate),
        target_evidence_sha256=target_evidence_sha256,
        access=access,
        routes=routes,
        observations=observations,
        limitations=candidate.limitations,
    )


def conform_application_operation_bundle(
    bundle: ApplicationOperationAdapterBundle,
    candidate: ApplicationOperationCandidate,
    evidence: TargetEvidenceBundle,
) -> ApplicationOperationConformanceReport:
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
        and bundle.candidate_sha256 == application_operation_candidate_sha256(candidate)
        and bundle.operation_id == candidate.operation_id
        and bundle.robot_id == candidate.robot_id,
        "bundle is bound to the exact operation candidate",
        "bundle operation candidate identity or digest does not match",
    )
    check(
        "target_evidence_binding",
        bundle.target_evidence_sha256 == evidence.payload_sha256
        and evidence.robot_id == bundle.robot_id,
        "bundle is bound to the target evidence payload",
        "bundle target evidence identity does not match",
    )
    observed = {route.resource_id: route for route in _observed_routes(evidence)}
    routes_ok = bool(bundle.routes) and all(
        route.evidence_origin == "OBSERVED_RUNTIME"
        and route.resource_id in observed
        and observed[route.resource_id].model_dump(mode="json") == route.model_dump(mode="json")
        for route in bundle.routes
    )
    check(
        "runtime_route_bindings",
        routes_ok,
        "every operation route is an exact runtime-observed route",
        "operation bundle contains no complete set of exact runtime-observed routes",
    )
    bundle_routes = {route.resource_id: route for route in bundle.routes}
    observation_route_ids = {
        route_id
        for observation in bundle.observations
        for route_id in observation.route_resource_ids
    }

    def valid_observation(observation: ApplicationOperationObservation) -> bool:
        if len(observation.route_resource_ids) != 1:
            return False
        route = bundle_routes.get(observation.route_resource_ids[0])
        if route is None:
            return False
        if observation.mode == "sample" or observation.mode == "topic_describe":
            return route.kind == "ros_topic" and observation.arguments == {
                "topic": route.endpoint
            }
        if observation.mode in {"service_describe", "action_describe"}:
            expected_kind = (
                "ros_service" if observation.mode == "service_describe" else "ros_action"
            )
            return route.kind == expected_kind and observation.arguments == {
                "name": route.endpoint
            }
        return False

    observation_ok = (
        bundle.access == "READ_ONLY"
        and bool(bundle.observations)
        and all(
            observation.operation_id == bundle.operation_id
            and observation.access == "read"
            and valid_observation(observation)
            and bool(observation.route_resource_ids)
            and (
                (
                    observation.tool_id == "native.middleware.observe"
                    and observation.mode == "sample"
                    and set(observation.arguments) == {"topic"}
                )
                or (
                    observation.tool_id == "native.middleware.graph.inspect"
                    and observation.mode
                    in {"topic_describe", "service_describe", "action_describe"}
                    and set(observation.arguments) in ({"topic"}, {"name"})
                )
            )
            for observation in bundle.observations
        )
        and observation_route_ids == {route.resource_id for route in bundle.routes}
    )
    check(
        "read_only_observation",
        observation_ok,
        "operation is represented only as a route-presence observation",
        "operation bundle is not a single read-only route observation",
    )
    check(
        "candidate_status",
        bundle.candidate_status == "CANDIDATE" and candidate.status == "CANDIDATE",
        "operation meets its minimum signal threshold",
        f"operation candidate status is {candidate.status}; it is not callable",
    )
    return ApplicationOperationConformanceReport(
        robot_id=bundle.robot_id,
        operation_id=bundle.operation_id,
        bundle_id=bundle.bundle_id,
        adapter_bundle_sha256=application_operation_bundle_sha256(bundle),
        status="PASS" if all(item.status == "PASS" for item in checks) else "FAIL",
        checks=checks,
    )


__all__ = [
    "APPLICATION_IDS",
    "ApplicationAdapterBundle",
    "ApplicationAdapterOperation",
    "ApplicationCandidate",
    "ApplicationOperationAdapterBundle",
    "ApplicationOperationCandidate",
    "ApplicationOperationConformanceReport",
    "ApplicationOperationObservation",
    "ApplicationOperationRule",
    "APPLICATION_OPERATION_RULES",
    "ApplicationConformanceCheck",
    "ApplicationConformanceReport",
    "adapter_bundle_sha256",
    "application_operation_bundle_sha256",
    "application_operation_candidate_sha256",
    "application_operation_rule",
    "build_application_operation_adapter_bundle",
    "build_application_adapter_bundle",
    "candidate_sha256",
    "conform_application_operation_bundle",
    "conform_application_bundle",
    "discover_application_operation",
    "discover_application_candidate",
    "discover_application_candidates",
]
