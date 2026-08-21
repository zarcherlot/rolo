from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.hashing import sha256_file
from rolo.core.models import RobotCapability, utc_now
from rolo.stages.adapt.conformance import validate_adapter_handoff
from rolo.stages.adapt.models import AdapterReleaseIndex, AdapterReleaseManifest
from rolo.workbench_read_models import (
    RobotTopology,
    TopologyEdge,
    TopologyNode,
    build_robot_topology,
)

_MAX_RELEASES = 100
_MAX_CHANGES = 500


class TopologyChangeKind(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CHANGED = "CHANGED"


class TopologySnapshotSummary(BaseModel):
    schema_version: Literal["rolo-topology-snapshot-summary/v1"] = (
        "rolo-topology-snapshot-summary/v1"
    )
    snapshot_id: str
    release_id: str
    published_at: datetime
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    coverage: Literal["GATED_RELEASE"] = "GATED_RELEASE"
    integrity_status: Literal["verified"] = "verified"
    is_current: bool = False


class TopologySnapshotCollection(BaseModel):
    schema_version: Literal["rolo-topology-snapshot-collection/v1"] = (
        "rolo-topology-snapshot-collection/v1"
    )
    robot_id: str
    items: list[TopologySnapshotSummary]
    total: int = Field(ge=0)
    observed_at: datetime
    freshness: Literal["unknown"] = "unknown"
    limitations: list[str] = Field(default_factory=list)


class TopologyNodeChange(BaseModel):
    schema_version: Literal["rolo-topology-node-change/v1"] = (
        "rolo-topology-node-change/v1"
    )
    node_id: str
    change: TopologyChangeKind
    changed_fields: list[str] = Field(default_factory=list)
    before: TopologyNode | None = None
    after: TopologyNode | None = None


class TopologyEdgeChange(BaseModel):
    schema_version: Literal["rolo-topology-edge-change/v1"] = (
        "rolo-topology-edge-change/v1"
    )
    edge_id: str
    change: TopologyChangeKind
    changed_fields: list[str] = Field(default_factory=list)
    before: TopologyEdge | None = None
    after: TopologyEdge | None = None


class TopologyDiff(BaseModel):
    schema_version: Literal["rolo-topology-diff/v1"] = "rolo-topology-diff/v1"
    robot_id: str
    from_snapshot: TopologySnapshotSummary
    to_snapshot: TopologySnapshotSummary
    added_nodes: int = Field(ge=0)
    removed_nodes: int = Field(ge=0)
    changed_nodes: int = Field(ge=0)
    added_edges: int = Field(ge=0)
    removed_edges: int = Field(ge=0)
    changed_edges: int = Field(ge=0)
    node_changes: list[TopologyNodeChange]
    edge_changes: list[TopologyEdgeChange]
    observed_at: datetime
    freshness: Literal["unknown"] = "unknown"
    integrity_status: Literal["verified"] = "verified"
    limitations: list[str] = Field(default_factory=list)


class _VerifiedSnapshot(BaseModel):
    summary: TopologySnapshotSummary
    topology: RobotTopology


def _safe_segment(value: str, label: str) -> str:
    if not value or any(
        character
        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in value
    ):
        raise ValueError(f"invalid {label}")
    return value


def _bounded_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("unsafe topology snapshot path")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("topology snapshot path escapes release root") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _snapshot_id(robot_id: str, release_id: str, manifest_digest: str) -> str:
    digest = sha256(f"{robot_id}\0{release_id}\0{manifest_digest}".encode()).hexdigest()
    return f"topology_snapshot_{digest[:18]}"


def _current_release_id(output_root: Path, robot_id: str) -> str | None:
    path = output_root / "robots" / _safe_segment(robot_id, "robot_id") / "current.json"
    try:
        index = AdapterReleaseIndex.model_validate_json(path.read_text(encoding="utf-8"))
        if index.robot_id != robot_id:
            return None
        release_root = path.parent / "releases" / _safe_segment(index.release_id, "release_id")
        manifest_path = _bounded_file(release_root, index.manifest)
        if sha256_file(manifest_path) != index.manifest_sha256:
            return None
    except (FileNotFoundError, ValueError):
        return None
    return index.release_id


def _load_verified_snapshot(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
    handoff_path: Path,
    *,
    current_release_id: str | None,
) -> _VerifiedSnapshot:
    handoff = validate_adapter_handoff(
        artifact_root,
        robot.robot_id,
        handoff_path=handoff_path,
        output_root=output_root,
    )
    prefix = "output://"
    relative = Path(handoff.release_ref.removeprefix(prefix))
    manifest_path = (output_root / relative).resolve()
    try:
        manifest_path.relative_to(output_root.resolve())
    except ValueError as exc:
        raise ValueError("release manifest escapes output root") from exc
    release = AdapterReleaseManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if release.robot_id != robot.robot_id or release.release_id != handoff.source_agent_run_id:
        raise ValueError("release identity does not match verified handoff")
    release_root = manifest_path.parent
    graph_path = _bounded_file(release_root, release.state_graph)
    if sha256_file(graph_path) != release.state_graph_sha256:
        raise ValueError("release State Graph hash mismatch")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or graph.get("robot_id") != robot.robot_id:
        raise ValueError("release State Graph identity mismatch")
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError("release State Graph shape is invalid")
    snapshot_id = _snapshot_id(
        robot.robot_id,
        release.release_id,
        handoff.release_manifest_sha256,
    )
    topology, _ = build_robot_topology(
        robot,
        output_root,
        observed_at=release.published_at,
        gated_graph=graph,
        load_active_graph=False,
        snapshot_id=snapshot_id,
    )
    return _VerifiedSnapshot(
        summary=TopologySnapshotSummary(
            snapshot_id=snapshot_id,
            release_id=release.release_id,
            published_at=release.published_at,
            node_count=len(topology.nodes),
            edge_count=len(topology.edges),
            is_current=release.release_id == current_release_id,
        ),
        topology=topology,
    )


def _discover_verified_snapshots(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
) -> tuple[list[_VerifiedSnapshot], int]:
    runs_root = (
        artifact_root
        / "adapt"
        / _safe_segment(robot.robot_id, "robot_id")
        / "runs"
    )
    if not runs_root.is_dir():
        return [], 0
    current_release_id = _current_release_id(output_root, robot.robot_id)
    snapshots: list[_VerifiedSnapshot] = []
    rejected = 0
    run_roots = sorted(
        (path for path in runs_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )[:_MAX_RELEASES]
    for run_root in run_roots:
        try:
            _safe_segment(run_root.name, "run_id")
            snapshots.append(
                _load_verified_snapshot(
                    robot,
                    artifact_root,
                    output_root,
                    run_root / "handoff.json",
                    current_release_id=current_release_id,
                )
            )
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            rejected += 1
    snapshots.sort(
        key=lambda item: (item.summary.published_at, item.summary.snapshot_id),
        reverse=True,
    )
    return snapshots, rejected


def build_topology_snapshot_collection(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
) -> TopologySnapshotCollection:
    snapshots, rejected = _discover_verified_snapshots(robot, artifact_root, output_root)
    limitations = [
        "Only releases backed by a passed independent gate and a complete "
        "hash-verified handoff are listed."
    ]
    if rejected:
        limitations.append(
            f"{rejected} unverified or unreadable release candidate(s) were omitted."
        )
    if not snapshots:
        limitations.append("No verified topology snapshot history is available for this robot.")
    return TopologySnapshotCollection(
        robot_id=robot.robot_id,
        items=[item.summary for item in snapshots],
        total=len(snapshots),
        observed_at=utc_now(),
        limitations=limitations,
    )


def _changed_fields(before: BaseModel, after: BaseModel, identity: str) -> list[str]:
    before_values = before.model_dump(mode="json")
    after_values = after.model_dump(mode="json")
    ignored = {"schema_version", identity}
    return sorted(
        key
        for key in set(before_values) | set(after_values)
        if key not in ignored and before_values.get(key) != after_values.get(key)
    )


def build_topology_diff(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
    from_snapshot_id: str,
    to_snapshot_id: str,
) -> TopologyDiff | None:
    snapshots, _ = _discover_verified_snapshots(robot, artifact_root, output_root)
    by_id = {item.summary.snapshot_id: item for item in snapshots}
    before = by_id.get(from_snapshot_id)
    after = by_id.get(to_snapshot_id)
    if before is None or after is None:
        return None

    before_nodes = {item.node_id: item for item in before.topology.nodes}
    after_nodes = {item.node_id: item for item in after.topology.nodes}
    node_changes: list[TopologyNodeChange] = []
    for node_id in sorted(set(before_nodes) | set(after_nodes)):
        old = before_nodes.get(node_id)
        new = after_nodes.get(node_id)
        if old is None:
            node_changes.append(
                TopologyNodeChange(node_id=node_id, change=TopologyChangeKind.ADDED, after=new)
            )
        elif new is None:
            node_changes.append(
                TopologyNodeChange(node_id=node_id, change=TopologyChangeKind.REMOVED, before=old)
            )
        elif fields := _changed_fields(old, new, "node_id"):
            node_changes.append(
                TopologyNodeChange(
                    node_id=node_id,
                    change=TopologyChangeKind.CHANGED,
                    changed_fields=fields,
                    before=old,
                    after=new,
                )
            )

    before_edges = {item.edge_id: item for item in before.topology.edges}
    after_edges = {item.edge_id: item for item in after.topology.edges}
    edge_changes: list[TopologyEdgeChange] = []
    for edge_id in sorted(set(before_edges) | set(after_edges)):
        old = before_edges.get(edge_id)
        new = after_edges.get(edge_id)
        if old is None:
            edge_changes.append(
                TopologyEdgeChange(edge_id=edge_id, change=TopologyChangeKind.ADDED, after=new)
            )
        elif new is None:
            edge_changes.append(
                TopologyEdgeChange(edge_id=edge_id, change=TopologyChangeKind.REMOVED, before=old)
            )
        elif fields := _changed_fields(old, new, "edge_id"):
            edge_changes.append(
                TopologyEdgeChange(
                    edge_id=edge_id,
                    change=TopologyChangeKind.CHANGED,
                    changed_fields=fields,
                    before=old,
                    after=new,
                )
            )

    limitations = [
        "The diff compares two hash-verified gated topology declarations; "
        "it does not prove a physical runtime change."
    ]
    if len(node_changes) > _MAX_CHANGES or len(edge_changes) > _MAX_CHANGES:
        limitations.append(f"Change details are limited to {_MAX_CHANGES} nodes and edges.")
    return TopologyDiff(
        robot_id=robot.robot_id,
        from_snapshot=before.summary,
        to_snapshot=after.summary,
        added_nodes=sum(item.change is TopologyChangeKind.ADDED for item in node_changes),
        removed_nodes=sum(item.change is TopologyChangeKind.REMOVED for item in node_changes),
        changed_nodes=sum(item.change is TopologyChangeKind.CHANGED for item in node_changes),
        added_edges=sum(item.change is TopologyChangeKind.ADDED for item in edge_changes),
        removed_edges=sum(item.change is TopologyChangeKind.REMOVED for item in edge_changes),
        changed_edges=sum(item.change is TopologyChangeKind.CHANGED for item in edge_changes),
        node_changes=node_changes[:_MAX_CHANGES],
        edge_changes=edge_changes[:_MAX_CHANGES],
        observed_at=max(before.summary.published_at, after.summary.published_at),
        limitations=limitations,
    )
