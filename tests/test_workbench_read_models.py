import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from rolo.core.models import RobotCapability
from rolo.stages.contracts import (
    AgentRequirement,
    PipelineAssessment,
    StageAssessment,
    StageName,
    StageStatus,
)
from rolo.workbench_read_models import (
    EvidenceAuthority,
    TopologyState,
    build_evidence_collection,
    build_robot_topology,
    evidence_id_for_reference,
    find_evidence,
)

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
ROBOT = RobotCapability(
    schema_version="robot-capability/v1",
    robot_id="test_robot",
    adapter="test-adapter",
    platform={
        "architecture": "arm64",
        "os": "ubuntu",
        "ros_distro": "humble",
        "drive_model": "differential",
    },
    geometry={},
    sensors={
        "front_lidar": {
            "semantic_uri": "semantic://sensor/front_lidar/scan",
            "modality": "lidar_2d",
            "binding": "secret-binding-that-must-not-leak",
        }
    },
    features={"navigation_2d": True, "private_config": {"token": "secret"}},
)


def test_registry_topology_is_declared_and_evidence_bound(tmp_path) -> None:
    topology, records = build_robot_topology(
        ROBOT,
        tmp_path,
        artifact_root=tmp_path,
        observed_at=NOW,
    )

    assert topology.schema_version == "rolo-robot-topology/v1"
    assert topology.coverage == "REGISTRY_ONLY"
    assert topology.source_kind == "robot_registry"
    assert topology.freshness == "fresh"
    assert all(node.state is TopologyState.DECLARED for node in topology.nodes)
    node_ids = {node.node_id for node in topology.nodes}
    assert len(node_ids) == len(topology.nodes)
    assert all(edge.source in node_ids and edge.target in node_ids for edge in topology.edges)
    assert all(
        evidence_id in records
        for node in topology.nodes
        for evidence_id in node.evidence_ids
    )
    serialized = topology.model_dump_json()
    assert "secret-binding-that-must-not-leak" not in serialized
    assert "private_config" not in serialized


def test_evidence_collection_is_bounded_and_opaque(tmp_path) -> None:
    collection = build_evidence_collection(
        ROBOT,
        tmp_path,
        artifact_root=tmp_path,
        limit=2,
        offset=1,
        observed_at=NOW,
    )

    assert collection.total > 2
    assert len(collection.items) == 2
    assert collection.offset == 1
    assert collection.next_offset == 3
    assert all(item.evidence_id.startswith("ev_") for item in collection.items)
    assert all(item.reference_digest != item.evidence_id for item in collection.items)
    found = find_evidence(
        [ROBOT],
        tmp_path,
        collection.items[0].evidence_id,
        artifact_root=tmp_path,
    )
    assert found is not None
    assert found.evidence_id == collection.items[0].evidence_id


def test_gated_topology_overlays_hash_verified_state_graph(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    graph = {
        "schema_version": "robot-state-graph/v2",
        "robot_id": ROBOT.robot_id,
        "discovery_id": "discovery-1",
        "nodes": [
            {
                "id": f"robot:{ROBOT.robot_id}",
                "kind": "robot",
                "evidence_refs": ["discovery:discovery-1"],
            },
            {
                "id": "adapter:bundle-1",
                "kind": "adapter",
                "bundle_id": "bundle-1",
                "evidence_refs": ["bundle:bundle-1"],
            },
            {
                "id": "operation:ros.topic.list",
                "kind": "operation",
                "operation": "ros.topic.list",
                "contract_version": "1.0.0",
                "evidence_refs": [r"artifact://C:\private\gate.json"],
            },
            {
                "id": "route:scan",
                "kind": "route",
                "route_kind": "ros2_topic",
                "interface_type": "sensor_msgs/msg/LaserScan",
                "endpoint": "/scan",
                "evidence_refs": [r"C:\private\probe-output.json"],
            },
        ],
        "edges": [
            {
                "source": f"robot:{ROBOT.robot_id}",
                "target": "adapter:bundle-1",
                "relation": "contains",
                "evidence_refs": ["discovery:discovery-1"],
            },
            {
                "source": "adapter:bundle-1",
                "target": "operation:ros.topic.list",
                "relation": "implements",
                "evidence_refs": ["bundle:bundle-1"],
            },
            {
                "source": "operation:ros.topic.list",
                "target": "route:scan",
                "relation": "routes_to",
                "evidence_refs": ["artifact://adapt/test_robot/gate.json"],
            },
        ],
    }
    (release_root / "state-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    monkeypatch.setattr(
        "rolo.workbench_read_models.load_current_release",
        lambda output_root, robot_id, *, artifact_root: (
            release_root,
            SimpleNamespace(state_graph="state-graph.json"),
            None,
            None,
        ),
    )

    topology, records = build_robot_topology(
        ROBOT,
        tmp_path,
        artifact_root=tmp_path,
        observed_at=NOW,
    )

    assert topology.coverage == "GATED_RELEASE"
    assert topology.source_kind == "gated_state_graph"
    assert topology.integrity_status == "verified"
    assert topology.freshness == "unknown"
    assert any(node.state is TopologyState.GATED for node in topology.nodes)
    assert any(node.layer.value == "Middleware" for node in topology.nodes)
    assert any(item.reference_hint == "redacted-reference" for item in records.values())
    assert any(
        item.reference_hint == "artifact://…/gate.json" for item in records.values()
    )
    assert any(item.freshness == "unknown" for item in records.values())
    assert r"C:\private" not in topology.model_dump_json()
    assert r"C:\private" not in "".join(item.model_dump_json() for item in records.values())


def test_pipeline_artifact_resolves_by_opaque_id_without_leaking_path(tmp_path) -> None:
    reference = r"C:\private\artifacts\adapt-inputs.json"
    pipeline = PipelineAssessment(
        robot_id=ROBOT.robot_id,
        stages=[
            StageAssessment(
                stage=StageName.ADAPT,
                robot_id=ROBOT.robot_id,
                status=StageStatus.BLOCKED,
                summary="Blocked",
                artifacts={"inputs": reference},
                blockers=["Fix inputs"],
                agent_requirement=AgentRequirement.ADAPTER_AGENT,
                observed_at=NOW,
            )
        ],
        observed_at=NOW,
    )

    collection = build_evidence_collection(
        ROBOT,
        tmp_path,
        artifact_root=tmp_path,
        pipeline=pipeline,
        observed_at=NOW,
    )
    evidence_id = evidence_id_for_reference(ROBOT.robot_id, reference)
    record = next(item for item in collection.items if item.evidence_id == evidence_id)
    resolved = find_evidence(
        [ROBOT],
        tmp_path,
        evidence_id,
        artifact_root=tmp_path,
        pipelines={ROBOT.robot_id: pipeline},
    )

    assert record.authority is EvidenceAuthority.OBSERVED
    assert record.reference_hint == "redacted-reference"
    assert reference not in record.model_dump_json()
    assert resolved is not None
    assert resolved.evidence_id == evidence_id
