"""Independent motion-safety readiness Conformance for application writes.

This module never sends velocity.  It proves (or rejects) the runtime wiring
needed before a mapping session may be coupled to exploration motion.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import RouteEvidence
from rolo.stages.probe.application import _observed_routes
from rolo.stages.probe.target_evidence import TargetEvidenceBundle

_TWIST = "geometry_msgs/msg/Twist"
_SCAN = "sensor_msgs/msg/LaserScan"
_ESTOP_NAME = re.compile(r"(?:emergency|e[_-]?stop|protective[_-]?stop)", re.I)
_SAFE_OUTPUT_NAME = re.compile(r"(?:cmd_vel_(?:safe|out|filtered)|safe_cmd_vel)", re.I)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class MotionSafetyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-motion-safety-candidate/v1"] = "rolo-motion-safety-candidate/v1"
    candidate_id: str = Field(pattern=r"^motion-safety-candidate-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    target_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scan_route: RouteEvidence | None = None
    command_route: RouteEvidence | None = None
    safe_output_route: RouteEvidence | None = None
    emergency_stop_route: RouteEvidence | None = None
    status: Literal["CANDIDATE", "NOT_FOUND"]
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    limitations: list[str] = Field(default_factory=list, max_length=16)


class MotionSafetyConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-motion-safety-conformance/v1"] = (
        "rolo-motion-safety-conformance/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    candidate_id: str = Field(pattern=r"^motion-safety-candidate-[0-9a-f]{24}$")
    status: Literal["PASS", "FAIL"]
    checks: dict[str, Literal["PASS", "FAIL"]] = Field(min_length=5, max_length=8)
    details: list[str] = Field(min_length=1, max_length=16)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def discover_motion_safety_candidate(
    evidence: TargetEvidenceBundle,
    *,
    runtime_topic_info: dict[str, str] | None = None,
    runtime_service_info: dict[str, str] | None = None,
) -> MotionSafetyCandidate:
    routes = _observed_routes(evidence)
    observed_at = datetime.now(timezone.utc)
    # The signed collector graph can race a driver restart.  A safety check may
    # add direct, bounded ``topic info`` observations, but keeps them visibly
    # separate from the signed TargetEvidence payload.
    for endpoint, output in (runtime_topic_info or {}).items():
        match = re.search(r"^Type:\s*(.+)$", output, re.MULTILINE)
        if not match:
            continue
        interface_type = match.group(1).strip()
        resource_id = f"ros_topic:{endpoint}"
        if not any(route.resource_id == resource_id for route in routes):
            routes.append(
                RouteEvidence(
                    resource_id=resource_id,
                    kind="ros_topic",
                    endpoint=endpoint,
                    interface_type=interface_type,
                    runtime_revision="direct-topic-info",
                    observed_at=observed_at,
                    evidence_origin="OBSERVED_RUNTIME",
                    source="safety-conformance:topic-info",
                    limitations=["direct bounded safety preflight; not part of signed collector payload"],
                )
            )
    for endpoint, output in (runtime_service_info or {}).items():
        match = re.search(r"^Type:\s*(.+)$", output, re.MULTILINE)
        if not match:
            continue
        resource_id = f"ros_service:{endpoint}"
        if not any(route.resource_id == resource_id for route in routes):
            routes.append(
                RouteEvidence(
                    resource_id=resource_id,
                    kind="ros_service",
                    endpoint=endpoint,
                    interface_type=match.group(1).strip(),
                    runtime_revision="direct-service-info",
                    observed_at=observed_at,
                    evidence_origin="OBSERVED_RUNTIME",
                    source="safety-conformance:service-info",
                    limitations=["direct bounded safety preflight; not part of signed collector payload"],
                )
            )
    scan = next(
        (r for r in routes if r.kind == "ros_topic" and r.endpoint == "/scan" and r.interface_type == _SCAN),
        None,
    )
    command = next(
        (r for r in routes if r.kind == "ros_topic" and r.endpoint == "/cmd_vel" and r.interface_type == _TWIST),
        None,
    )
    safe = next(
        (r for r in routes if r.kind == "ros_topic" and _SAFE_OUTPUT_NAME.search(r.endpoint) and r.interface_type == _TWIST),
        None,
    )
    estop = next(
        (
            r
            for r in routes
            if r.kind in {"ros_service", "ros_action"}
            and _ESTOP_NAME.search(r.endpoint)
            and r.interface_type not in {None, "std_srvs/srv/Empty"}
        ),
        None,
    )
    seed = {
        "robot_id": evidence.robot_id,
        "target_evidence_sha256": evidence.payload_sha256,
        "scan": scan.resource_id if scan else None,
        "command": command.resource_id if command else None,
        "safe": safe.resource_id if safe else None,
        "estop": estop.resource_id if estop else None,
    }
    status = "CANDIDATE" if scan is not None and command is not None else "NOT_FOUND"
    return MotionSafetyCandidate(
        candidate_id="motion-safety-candidate-" + _digest(seed)[:24],
        robot_id=evidence.robot_id,
        target_evidence_sha256=evidence.payload_sha256,
        scan_route=scan,
        command_route=command,
        safe_output_route=safe,
        emergency_stop_route=estop,
        status=status,
        limitations=[
            "Route presence cannot prove obstacle classification or physical stopping",
            "Watchdog/zero-stop requires an active behavior test, not graph inspection",
        ],
    )


def conform_motion_safety_candidate(
    candidate: MotionSafetyCandidate,
) -> MotionSafetyConformanceReport:
    checks = {
        "typed_scan_input": "PASS" if candidate.scan_route is not None else "FAIL",
        "typed_command_input": "PASS" if candidate.command_route is not None else "FAIL",
        "distinct_safe_output": "PASS" if candidate.safe_output_route is not None else "FAIL",
        "watchdog_zero_stop": "FAIL",
        "independent_emergency_stop": "PASS" if candidate.emergency_stop_route is not None else "FAIL",
    }
    details = [
        "scan and command routes are typed runtime observations"
        if checks["typed_scan_input"] == checks["typed_command_input"] == "PASS"
        else "missing typed scan or command route",
        "a distinct Twist safety output route is observed"
        if checks["distinct_safe_output"] == "PASS"
        else "no distinct safety output/arbiter route is observed",
        "watchdog timeout and zero-stop behavior require a bounded active test",
        "an independent emergency-stop route is observed"
        if checks["independent_emergency_stop"] == "PASS"
        else "no typed independent emergency-stop route is observed",
    ]
    return MotionSafetyConformanceReport(
        robot_id=candidate.robot_id,
        candidate_id=candidate.candidate_id,
        status="PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
        checks=checks,
        details=details,
    )


__all__ = [
    "MotionSafetyCandidate",
    "MotionSafetyConformanceReport",
    "conform_motion_safety_candidate",
    "discover_motion_safety_candidate",
]
