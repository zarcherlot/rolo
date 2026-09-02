from datetime import datetime, timezone

from rolo.core.models import DiscoveryStatus, ProbeResult, RouteEvidence
from rolo.stages.probe.application_safety import (
    conform_motion_safety_candidate,
    discover_motion_safety_candidate,
)
from rolo.stages.probe.target_evidence import TargetEvidenceBundle


def _bundle(*routes: RouteEvidence) -> TargetEvidenceBundle:
    probe = ProbeResult(
        layer="ros",
        status=DiscoveryStatus.SUCCEEDED,
        data={"route_evidence": [r.model_dump(mode="json") for r in routes]},
    )
    return TargetEvidenceBundle(
        robot_id="testbot",
        collector_id="collector-test",
        target_host_fingerprint="1" * 64,
        request_nonce="2" * 32,
        requested_layers=["ros"],
        collected_at=datetime.now(timezone.utc),
        probes={"ros": probe},
        payload_sha256="3" * 64,
        signature_hmac_sha256="4" * 64,
    )


def _route(resource_id: str, endpoint: str, kind: str, interface_type: str) -> RouteEvidence:
    return RouteEvidence(
        resource_id=resource_id,
        kind=kind,  # type: ignore[arg-type]
        endpoint=endpoint,
        interface_type=interface_type,
        evidence_origin="OBSERVED_RUNTIME",
        source="test:runtime",
        observed_at=datetime.now(timezone.utc),
    )


def test_safety_conformance_fails_closed_without_arbiter_watchdog_or_estop() -> None:
    candidate = discover_motion_safety_candidate(
        _bundle(
            _route("ros_topic:/scan", "/scan", "ros_topic", "sensor_msgs/msg/LaserScan"),
            _route("ros_topic:/cmd_vel", "/cmd_vel", "ros_topic", "geometry_msgs/msg/Twist"),
            _route("ros_service:/enable", "/enable", "ros_service", "std_srvs/srv/Empty"),
        )
    )
    report = conform_motion_safety_candidate(candidate)
    assert report.status == "FAIL"
    assert report.checks == {
        "typed_scan_input": "PASS",
        "typed_command_input": "PASS",
        "distinct_safe_output": "FAIL",
        "watchdog_zero_stop": "FAIL",
        "independent_emergency_stop": "FAIL",
    }


def test_safety_candidate_can_pass_route_discovery_but_behavior_gate_stays_closed() -> None:
    candidate = discover_motion_safety_candidate(
        _bundle(
            _route("ros_topic:/scan", "/scan", "ros_topic", "sensor_msgs/msg/LaserScan"),
            _route("ros_topic:/cmd_vel", "/cmd_vel", "ros_topic", "geometry_msgs/msg/Twist"),
            _route("ros_topic:/cmd_vel_safe", "/cmd_vel_safe", "ros_topic", "geometry_msgs/msg/Twist"),
            _route("ros_service:/emergency_stop", "/emergency_stop", "ros_service", "std_srvs/srv/SetBool"),
        )
    )
    report = conform_motion_safety_candidate(candidate)
    assert candidate.status == "CANDIDATE"
    assert report.status == "FAIL"
    assert report.checks["watchdog_zero_stop"] == "FAIL"
