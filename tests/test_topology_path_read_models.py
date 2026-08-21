from datetime import datetime, timezone

import pytest

from rolo.core.models import RobotCapability
from rolo.topology_path_read_models import explain_topology_path
from rolo.workbench_read_models import build_robot_topology

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
ROBOT = RobotCapability(
    schema_version="robot-capability/v1",
    robot_id="path_robot",
    adapter="path-adapter",
    platform={"architecture": "arm64", "ros_distro": "humble"},
    geometry={},
    sensors={"front_lidar": {"modality": "lidar_2d"}},
    features={"navigation_2d": True},
)


def test_topology_path_explains_bounded_relationships_with_evidence(tmp_path) -> None:
    topology, _ = build_robot_topology(ROBOT, tmp_path, observed_at=NOW)
    sensor = next(node for node in topology.nodes if node.kind == "sensor")
    feature = next(node for node in topology.nodes if node.kind == "feature")

    path = explain_topology_path(topology, sensor.node_id, feature.node_id)
    reverse = explain_topology_path(topology, feature.node_id, sensor.node_id)

    assert path.schema_version == "rolo-topology-path-explanation/v1"
    assert path.found is True
    assert path.hop_count == 3
    assert [step.relation for step in path.steps] == [
        "connects_to",
        "hosts",
        "declares",
    ]
    assert all(step.evidence_ids for step in path.steps)
    assert all(step.direction == "FORWARD" for step in path.steps)
    assert all(step.direction == "REVERSE" for step in reverse.steps)
    assert path.integrity_status == "validated"
    assert "physical reachability" in path.limitations[0]


def test_topology_path_rejects_unknown_nodes(tmp_path) -> None:
    topology, _ = build_robot_topology(ROBOT, tmp_path, observed_at=NOW)

    with pytest.raises(KeyError, match="Unknown topology node"):
        explain_topology_path(topology, topology.nodes[0].node_id, "missing")
