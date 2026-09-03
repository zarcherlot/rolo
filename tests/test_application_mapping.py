from datetime import datetime, timezone

from rolo.core.models import DiscoveryStatus, ProbeResult, RouteEvidence
from rolo.stages.probe.application_mapping import (
    conform_map_create_dispatch,
    discover_map_create_candidate,
    parse_mapping_session_pid,
)
from rolo.stages.probe.target_evidence import TargetEvidenceBundle


def _bundle() -> TargetEvidenceBundle:
    route = RouteEvidence(
        resource_id="ros_topic:/scan",
        kind="ros_topic",
        endpoint="/scan",
        interface_type="sensor_msgs/msg/LaserScan",
        evidence_origin="OBSERVED_RUNTIME",
        source="test:runtime",
        observed_at=datetime.now(timezone.utc),
    )
    probe = ProbeResult(
        layer="ros",
        status=DiscoveryStatus.SUCCEEDED,
        data={"route_evidence": [route.model_dump(mode="json")]},
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


def test_map_create_requires_scan_and_exact_static_entrypoint() -> None:
    evidence = _bundle()
    candidate = discover_map_create_candidate(
        evidence,
        static_entrypoints=["/home/ubuntu/ros2_ws/src/slam/launch/include/slam_base.launch.py"],
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.no_motion_contract is True

    rejected = discover_map_create_candidate(evidence, static_entrypoints=[])
    assert rejected.status == "NOT_FOUND"


def test_map_create_dispatch_parses_bounded_pid_and_does_not_require_motion() -> None:
    assert parse_mapping_session_pid("rolo_mapping_pid=1234\n") == 1234
    assert parse_mapping_session_pid("pid=1234\n") is None
    candidate = discover_map_create_candidate(
        _bundle(),
        static_entrypoints=["/home/ubuntu/ros2_ws/src/slam/launch/include/slam_base.launch.py"],
    )
    report = conform_map_create_dispatch(
        candidate,
        returncode=0,
        stdout="rolo_mapping_pid=1234\n",
        map_route_observed=False,
    )
    assert report.status == "PASS"
    assert report.session_started is True
    assert report.session_pid == 1234


def test_map_create_can_bind_a_verified_raw_scan_route() -> None:
    evidence = _bundle().model_copy(update={
        "probes": {
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "route_evidence": [
                        RouteEvidence(
                            resource_id="ros_topic:/scan_raw",
                            kind="ros_topic",
                            endpoint="/scan_raw",
                            interface_type="sensor_msgs/msg/LaserScan",
                            evidence_origin="OBSERVED_RUNTIME",
                            source="test:runtime",
                            observed_at=datetime.now(timezone.utc),
                        ).model_dump(mode="json")
                    ]
                },
            )
        }
    })
    candidate = discover_map_create_candidate(
        evidence,
        static_entrypoints=["/home/ubuntu/ros2_ws/src/slam/launch/include/slam_base.launch.py"],
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.scan_route is not None
    assert candidate.scan_route.endpoint == "/scan_raw"
