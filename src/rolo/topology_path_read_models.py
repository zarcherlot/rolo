from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from rolo.workbench_read_models import (
    RobotTopology,
    TopologyEdge,
    TopologyNode,
    TopologyState,
)


class TopologyPathStep(BaseModel):
    schema_version: Literal["rolo-topology-path-step/v1"] = (
        "rolo-topology-path-step/v1"
    )
    index: int = Field(ge=0)
    from_node_id: str
    to_node_id: str
    edge_id: str
    relation: str
    direction: Literal["FORWARD", "REVERSE"]
    state: TopologyState
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    evidence_ids: list[str] = Field(default_factory=list)


class TopologyPathExplanation(BaseModel):
    schema_version: Literal["rolo-topology-path-explanation/v1"] = (
        "rolo-topology-path-explanation/v1"
    )
    robot_id: str
    snapshot_id: str
    from_node_id: str
    to_node_id: str
    found: bool
    hop_count: int = Field(ge=0)
    nodes: list[TopologyNode] = Field(default_factory=list, max_length=13)
    steps: list[TopologyPathStep] = Field(default_factory=list, max_length=12)
    summary: str
    observed_at: datetime
    freshness: Literal["fresh", "unknown"]
    source_kind: Literal["topology_path_projection"] = "topology_path_projection"
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    limitations: list[str] = Field(default_factory=list)


def explain_topology_path(
    topology: RobotTopology,
    from_node_id: str,
    to_node_id: str,
    *,
    max_hops: int = 8,
) -> TopologyPathExplanation:
    nodes = {node.node_id: node for node in topology.nodes}
    if from_node_id not in nodes or to_node_id not in nodes:
        raise KeyError("Unknown topology node")
    if from_node_id == to_node_id:
        node = nodes[from_node_id]
        return TopologyPathExplanation(
            robot_id=topology.robot_id,
            snapshot_id=topology.snapshot_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            found=True,
            hop_count=0,
            nodes=[node],
            steps=[],
            summary=f"{node.label} is the selected component.",
            observed_at=topology.observed_at,
            freshness=topology.freshness,
            confidence=node.confidence,
            integrity_status=node.integrity_status,
            limitations=[
                "A zero-hop path identifies one component; it does not assert runtime behavior."
            ],
        )

    adjacency: dict[
        str,
        list[tuple[str, TopologyEdge, Literal["FORWARD", "REVERSE"]]],
    ] = {node_id: [] for node_id in nodes}
    for edge in topology.edges:
        adjacency[edge.source].append((edge.target, edge, "FORWARD"))
        adjacency[edge.target].append((edge.source, edge, "REVERSE"))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1].edge_id, item[2]))

    queue = deque([(from_node_id, 0)])
    previous: dict[
        str,
        tuple[str, TopologyEdge, Literal["FORWARD", "REVERSE"]],
    ] = {}
    visited = {from_node_id}
    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor, edge, direction in adjacency[current]:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            previous[neighbor] = (current, edge, direction)
            if neighbor == to_node_id:
                queue.clear()
                break
            queue.append((neighbor, depth + 1))

    if to_node_id not in previous:
        return TopologyPathExplanation(
            robot_id=topology.robot_id,
            snapshot_id=topology.snapshot_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            found=False,
            hop_count=0,
            nodes=[],
            steps=[],
            summary=f"No connection was found within {max_hops} hops.",
            observed_at=topology.observed_at,
            freshness=topology.freshness,
            confidence=topology.confidence,
            integrity_status=topology.integrity_status,
            limitations=[
                "No bounded path does not prove the components are physically disconnected."
            ],
        )

    reversed_steps: list[
        tuple[
            str,
            str,
            TopologyEdge,
            Literal["FORWARD", "REVERSE"],
        ]
    ] = []
    current = to_node_id
    while current != from_node_id:
        parent, edge, direction = previous[current]
        reversed_steps.append((parent, current, edge, direction))
        current = parent
    raw_steps = list(reversed(reversed_steps))
    steps = [
        TopologyPathStep(
            index=index,
            from_node_id=source,
            to_node_id=target,
            edge_id=edge.edge_id,
            relation=edge.relation,
            direction=direction,
            state=edge.state,
            confidence=edge.confidence,
            integrity_status=edge.integrity_status,
            evidence_ids=edge.evidence_ids,
        )
        for index, (source, target, edge, direction) in enumerate(raw_steps)
    ]
    path_node_ids = [from_node_id, *(step.to_node_id for step in steps)]
    path_nodes = [nodes[node_id] for node_id in path_node_ids]
    confidence = min(
        [node.confidence for node in path_nodes]
        + [step.confidence for step in steps]
    )
    integrity_status: Literal["validated", "verified"] = (
        "verified"
        if all(node.integrity_status == "verified" for node in path_nodes)
        and all(step.integrity_status == "verified" for step in steps)
        else "validated"
    )
    return TopologyPathExplanation(
        robot_id=topology.robot_id,
        snapshot_id=topology.snapshot_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        found=True,
        hop_count=len(steps),
        nodes=path_nodes,
        steps=steps,
        summary=f"A {len(steps)}-hop topology connection was found.",
        observed_at=topology.observed_at,
        freshness=topology.freshness,
        confidence=confidence,
        integrity_status=integrity_status,
        limitations=[
            "This path explains topology relationships; it does not prove physical "
            "reachability or task success."
        ],
    )
