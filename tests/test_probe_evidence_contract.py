from datetime import datetime, timezone

import pytest

from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.stages.adapt.target_evidence import CollectorDescriptor, TargetEvidenceBundle


def test_collector_descriptor_pins_target_workspace_context() -> None:
    descriptor = CollectorDescriptor(
        robot_id="mentorpi",
        collector_id="collector-1234567890abcdef1234567890abcdef",
        target_host_fingerprint="a" * 64,
        source_root="/home/ubuntu/ros2_ws",
    )

    assert descriptor.source_root == "/home/ubuntu/ros2_ws"


def test_collector_descriptor_rejects_shell_in_workspace_context() -> None:
    with pytest.raises(ValueError, match="source_root"):
        CollectorDescriptor(
            robot_id="mentorpi",
            collector_id="collector-1234567890abcdef1234567890abcdef",
            target_host_fingerprint="a" * 64,
            source_root="/home/ubuntu/ros2_ws;id",
        )


def test_v3_target_bundle_accepts_signed_source_snapshot() -> None:
    bundle = TargetEvidenceBundle(
        schema_version="robot-target-evidence-bundle/v3",
        robot_id="mentorpi",
        collector_id="collector-1234567890abcdef1234567890abcdef",
        target_host_fingerprint="a" * 64,
        request_nonce="b" * 32,
        requested_layers=["linux"],
        collected_at=datetime.now(timezone.utc),
        probes={
            "linux": ProbeResult(layer="linux", status=DiscoveryStatus.SUCCEEDED),
        },
        source_snapshot={
            "schema_version": "robot-source-evidence/v1",
            "source_root": "/home/ubuntu/ros2_ws",
            "status": "PARTIAL",
        },
        payload_sha256="c" * 64,
        signature_hmac_sha256="d" * 64,
    )

    assert bundle.source_snapshot["source_root"] == "/home/ubuntu/ros2_ws"
