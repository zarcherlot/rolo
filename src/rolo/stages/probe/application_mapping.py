"""Target-bound, no-motion implementation of ``app.map.create``.

The first mapping write is deliberately a session start, not exploration.  It
starts only the target's already-present SLAM launch entrypoint and returns a
bounded process handle.  Motion, obstacle avoidance and emergency-stop
Conformance remain separate gates.
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

_SCAN_TYPE = "sensor_msgs/msg/LaserScan"
_LAUNCH_SUFFIX = "/src/slam/launch/include/slam_base.launch.py"
_PID = re.compile(r"(?:^|\s)rolo_mapping_pid=(\d+)(?:\s|$)")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MapCreateCandidate(BaseModel):
    """Evidence-bound proposal for starting a no-motion mapping session."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-map-create-candidate/v1"] = "rolo-map-create-candidate/v1"
    candidate_id: str = Field(pattern=r"^app-map-create-candidate-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: Literal["app.map.create"] = "app.map.create"
    target_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    launch_file: str | None = None
    scan_route: RouteEvidence | None = None
    status: Literal["CANDIDATE", "NOT_FOUND", "REJECTED"]
    no_motion_contract: bool = False
    observed_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


class MapCreateReport(BaseModel):
    """Conformance and dispatch result for one mapping session start."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-map-create-report/v1"] = "rolo-map-create-report/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: Literal["app.map.create"] = "app.map.create"
    candidate_id: str = Field(pattern=r"^app-map-create-candidate-[0-9a-f]{24}$")
    status: Literal["PASS", "FAIL"]
    dispatch_returncode: int | None = None
    session_pid: int | None = Field(default=None, ge=1, le=999_999_999)
    session_started: bool = False
    map_route_observed: bool = False
    checks: list[str] = Field(min_length=1, max_length=16)
    checked_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


def discover_map_create_candidate(
    evidence: TargetEvidenceBundle,
    *,
    static_entrypoints: list[str],
) -> MapCreateCandidate:
    """Require a real scan route and the exact target workspace SLAM entrypoint."""
    observed = _observed_routes(evidence)
    scan_route = next(
        (
            route
            # Prefer the raw stream when both are advertised: a filtered topic
            # may exist in the graph while producing no samples.
            for endpoint in ("/scan_raw", "/scan")
            for route in observed
            if route.kind == "ros_topic"
            and route.endpoint == endpoint
            and route.interface_type == _SCAN_TYPE
            and route.evidence_origin == "OBSERVED_RUNTIME"
        ),
        None,
    )
    launch_file = next(
        (item.strip() for item in static_entrypoints if item.strip().endswith(_LAUNCH_SUFFIX)),
        None,
    )
    candidate_status: Literal["CANDIDATE", "NOT_FOUND", "REJECTED"] = (
        "CANDIDATE"
        if scan_route is not None and launch_file is not None
        else "NOT_FOUND"
    )
    seed = {
        "robot_id": evidence.robot_id,
        "operation_id": "app.map.create",
        "target_evidence_sha256": evidence.payload_sha256,
        "scan_route": scan_route.resource_id if scan_route else None,
        "launch_file": launch_file,
        "status": candidate_status,
    }
    return MapCreateCandidate(
        candidate_id="app-map-create-candidate-" + _digest(seed)[:24],
        robot_id=evidence.robot_id,
        target_evidence_sha256=evidence.payload_sha256,
        launch_file=launch_file,
        scan_route=scan_route,
        status=candidate_status,
        no_motion_contract=True,
        limitations=[
            "This operation starts SLAM only; it never publishes velocity or starts exploration",
            "A started SLAM session is not proof of map quality or physical safety",
            "The scan input is selected from observed /scan or /scan_raw routes",
        ],
    )


def parse_mapping_session_pid(stdout: str) -> int | None:
    """Parse only the fixed PID marker emitted by the mapping adapter."""
    match = _PID.search(stdout)
    if match is None:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 999_999_999 else None


def conform_map_create_dispatch(
    candidate: MapCreateCandidate,
    *,
    returncode: int,
    stdout: str,
    map_route_observed: bool,
) -> MapCreateReport:
    pid = parse_mapping_session_pid(stdout)
    checks = [
        "candidate is bound to a typed /scan runtime route"
        if candidate.status == "CANDIDATE" and candidate.scan_route is not None
        else "candidate lacks the required typed /scan runtime route",
        "launch entrypoint is the exact target workspace SLAM adapter"
        if candidate.status == "CANDIDATE" and candidate.launch_file is not None
        else "launch entrypoint was not found in target evidence",
        "dispatch returned success and a bounded session PID"
        if returncode == 0 and pid is not None
        else "dispatch did not return a bounded mapping session PID",
        "map route is observable after session start"
        if map_route_observed
        else "map route was not observable immediately after session start",
    ]
    passed = (
        candidate.status == "CANDIDATE"
        and candidate.no_motion_contract
        and candidate.scan_route is not None
        and candidate.launch_file is not None
        and returncode == 0
        and pid is not None
    )
    return MapCreateReport(
        robot_id=candidate.robot_id,
        candidate_id=candidate.candidate_id,
        status="PASS" if passed else "FAIL",
        dispatch_returncode=returncode,
        session_pid=pid,
        session_started=passed,
        map_route_observed=map_route_observed,
        checks=checks,
        limitations=[
            "PASS means only that the no-motion SLAM session was accepted and identified",
            "Exploration motion requires a separate validated obstacle/e-stop safety adapter",
        ],
    )


__all__ = [
    "MapCreateCandidate",
    "MapCreateReport",
    "conform_map_create_dispatch",
    "discover_map_create_candidate",
    "parse_mapping_session_pid",
]
