"""Narrow, human-confirmed application write canary support.

The first write slice is deliberately limited to ``app.base.stop``.  Discovery
uses the existing read-only Middleware graph Tool; dispatch is a fixed zero
Twist publication through the enrolled SSH connector.
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

_ZERO_TWIST = (
    "{linear: {x: 0.0, y: 0.0, z: 0.0}, "
    "angular: {x: 0.0, y: 0.0, z: 0.0}}"
)
_GRAPH_TYPE = "geometry_msgs/msg/Twist"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ApplicationWriteCanaryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-write-canary-candidate/v1"] = (
        "rolo-application-write-canary-candidate/v1"
    )
    candidate_id: str = Field(pattern=r"^app-write-candidate-[0-9a-f]{24}$")
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: Literal["app.base.stop"] = "app.base.stop"
    target_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    route: RouteEvidence | None = None
    endpoint: Literal["/cmd_vel"] = "/cmd_vel"
    interface_type: Literal["geometry_msgs/msg/Twist"] = _GRAPH_TYPE
    subscription_count: int = Field(ge=0, le=1024)
    status: Literal["CANDIDATE", "NOT_FOUND", "REJECTED"]
    observed_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


class ApplicationWriteCanaryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-application-write-canary-report/v1"] = (
        "rolo-application-write-canary-report/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    operation_id: Literal["app.base.stop"] = "app.base.stop"
    candidate_id: str = Field(pattern=r"^app-write-candidate-[0-9a-f]{24}$")
    status: Literal["PASS", "FAIL"]
    dispatch_returncode: int | None = None
    dispatch_stdout: str = ""
    dispatch_stderr: str = ""
    route_rechecked: bool = False
    checked_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list, max_length=16)


def fixed_zero_twist_payload() -> str:
    """Return the only payload accepted by the base-stop canary."""
    return _ZERO_TWIST


def discover_base_stop_write_candidate(
    evidence: TargetEvidenceBundle,
    *,
    graph_stdout: str,
) -> ApplicationWriteCanaryCandidate:
    """Bind ``app.base.stop`` to a subscribed, typed ``/cmd_vel`` route."""
    route = next(
        (
            item
            for item in _observed_routes(evidence)
            if item.kind == "ros_topic"
            and item.endpoint == "/cmd_vel"
            and item.interface_type == _GRAPH_TYPE
            and item.evidence_origin == "OBSERVED_RUNTIME"
        ),
        None,
    )
    type_match = re.search(r"^Type:\s*(.+)$", graph_stdout, re.MULTILINE)
    subscription_match = re.search(r"^Subscription count:\s*(\d+)\s*$", graph_stdout, re.MULTILINE)
    graph_type = type_match.group(1).strip() if type_match else ""
    subscriptions = int(subscription_match.group(1)) if subscription_match else 0
    candidate_status: Literal["CANDIDATE", "NOT_FOUND", "REJECTED"] = (
        "CANDIDATE"
        if route is not None and graph_type == _GRAPH_TYPE and subscriptions >= 1
        else "NOT_FOUND"
        if route is None
        else "REJECTED"
    )
    seed = {
        "robot_id": evidence.robot_id,
        "operation_id": "app.base.stop",
        "target_evidence_sha256": evidence.payload_sha256,
        "route_resource_id": route.resource_id if route else None,
        "graph_type": graph_type,
        "subscriptions": subscriptions,
        "status": candidate_status,
    }
    return ApplicationWriteCanaryCandidate(
        candidate_id="app-write-candidate-" + _digest(seed)[:24],
        robot_id=evidence.robot_id,
        target_evidence_sha256=evidence.payload_sha256,
        route=route,
        subscription_count=subscriptions,
        status=candidate_status,
        limitations=[
            "Graph capability proves only a possible stop route, not physical stopping",
            "Dispatch is fixed to one zero-Twist message and requires human confirmation",
        ],
    )


__all__ = [
    "ApplicationWriteCanaryCandidate",
    "ApplicationWriteCanaryReport",
    "discover_base_stop_write_candidate",
    "fixed_zero_twist_payload",
]
