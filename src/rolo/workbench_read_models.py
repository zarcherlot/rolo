from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.adapter_runtime import load_current_release
from rolo.core.models import RobotCapability, utc_now
from rolo.stages.contracts import PipelineAssessment

SafeAttribute = str | int | float | bool


class TopologyLayer(str, Enum):
    HARDWARE = "Hardware"
    LINUX = "Linux"
    MIDDLEWARE = "Middleware"
    APPLICATION = "Application"


class TopologyState(str, Enum):
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    GATED = "GATED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class EvidenceAuthority(str, Enum):
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    GATED = "GATED"


class TopologyNode(BaseModel):
    schema_version: Literal["rolo-topology-node/v1"] = "rolo-topology-node/v1"
    node_id: str
    kind: str
    label: str
    subtitle: str = ""
    layer: TopologyLayer
    state: TopologyState
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, SafeAttribute] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    schema_version: Literal["rolo-topology-edge/v1"] = "rolo-topology-edge/v1"
    edge_id: str
    source: str
    target: str
    relation: str
    state: TopologyState
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    evidence_ids: list[str] = Field(default_factory=list)


class RobotTopology(BaseModel):
    schema_version: Literal["rolo-robot-topology/v1"] = "rolo-robot-topology/v1"
    robot_id: str
    snapshot_id: str
    coverage: Literal["REGISTRY_ONLY", "GATED_RELEASE"]
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    observed_at: datetime
    freshness: Literal["fresh", "unknown"] = "fresh"
    source_kind: Literal["robot_registry", "gated_state_graph"]
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    limitations: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    schema_version: Literal["rolo-evidence-record/v1"] = "rolo-evidence-record/v1"
    evidence_id: str
    robot_id: str
    title: str
    summary: str
    authority: EvidenceAuthority
    source_kind: Literal["robot_manifest", "gated_artifact", "pipeline_artifact"]
    integrity_status: Literal["validated", "verified"]
    classification: Literal["INTERNAL"] = "INTERNAL"
    observed_at: datetime
    freshness: Literal["fresh", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    reference_hint: str
    reference_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    related_node_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EvidenceCollection(BaseModel):
    schema_version: Literal["rolo-evidence-collection/v1"] = (
        "rolo-evidence-collection/v1"
    )
    robot_id: str
    items: list[EvidenceRecord]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Literal["fresh", "unknown"] = "fresh"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{_digest(value)[:18]}"


def evidence_id_for_reference(robot_id: str, reference: str) -> str:
    return _stable_id("ev", f"{robot_id}\0{reference}")


def _reference_hint(reference: str) -> str:
    if reference.startswith("artifact://"):
        portable_path = reference.removeprefix("artifact://").replace("\\", "/")
        name = Path(portable_path).name or "artifact"
        return f"artifact://…/{name}"
    if reference.startswith(("bundle:", "discovery:", "robot-manifest:")):
        prefix, _, value = reference.partition(":")
        safe_value = "".join(
            character
            for character in value
            if character.isalnum() or character in ":._-"
        )
        return f"{prefix}:{safe_value[:64]}"
    return "redacted-reference"


def _registry_record(
    robot: RobotCapability,
    subject: str,
    node_id: str,
    observed_at: datetime,
) -> EvidenceRecord:
    reference = f"robot-manifest:{robot.robot_id}:{subject}"
    return EvidenceRecord(
        evidence_id=evidence_id_for_reference(robot.robot_id, reference),
        robot_id=robot.robot_id,
        title=f"Declared {subject.replace(':', ' ')}",
        summary="This component is declared by the validated robot capability manifest.",
        authority=EvidenceAuthority.DECLARED,
        source_kind="robot_manifest",
        integrity_status="validated",
        observed_at=observed_at,
        freshness="fresh",
        confidence=1.0,
        reference_hint=_reference_hint(reference),
        reference_digest=_digest(reference),
        related_node_ids=[node_id],
        limitations=["A registry declaration does not prove runtime presence."],
    )


def _graph_record(
    robot_id: str,
    reference: str,
    node_id: str,
    observed_at: datetime,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id_for_reference(robot_id, reference),
        robot_id=robot_id,
        title="Gated topology evidence",
        summary="This reference is bound to the hash-verified active adapter release.",
        authority=EvidenceAuthority.GATED,
        source_kind="gated_artifact",
        integrity_status="verified",
        observed_at=observed_at,
        freshness="unknown",
        confidence=1.0,
        reference_hint=_reference_hint(reference),
        reference_digest=_digest(reference),
        related_node_ids=[node_id],
        limitations=[
            "Source observation time is unavailable; observed_at is read-model resolution time."
        ],
    )


def _pipeline_record(
    robot_id: str,
    stage: str,
    artifact_name: str,
    reference: str,
    observed_at: datetime,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id_for_reference(robot_id, reference),
        robot_id=robot_id,
        title=f"{stage.title()} pipeline artifact: {artifact_name}",
        summary="The pipeline assessment references this bounded stage artifact.",
        authority=EvidenceAuthority.OBSERVED,
        source_kind="pipeline_artifact",
        integrity_status="validated",
        observed_at=observed_at,
        freshness="unknown",
        confidence=1.0,
        reference_hint=_reference_hint(reference),
        reference_digest=_digest(reference),
        limitations=[
            "The source path is withheld; validation does not imply a hash-verified release."
        ],
    )


def _add_evidence(
    records: dict[str, EvidenceRecord],
    record: EvidenceRecord,
) -> None:
    current = records.get(record.evidence_id)
    if current is None:
        records[record.evidence_id] = record
        return
    current.related_node_ids = sorted(
        set(current.related_node_ids) | set(record.related_node_ids)
    )


def _node_layer(kind: str, raw: dict[str, object]) -> TopologyLayer:
    if kind == "robot":
        return TopologyLayer.HARDWARE
    if kind in {"adapter", "operation"}:
        return TopologyLayer.APPLICATION
    route_kind = str(raw.get("route_kind", "")).lower()
    interface = str(raw.get("interface_type", "")).lower()
    if "ros" in route_kind or "ros" in interface:
        return TopologyLayer.MIDDLEWARE
    return TopologyLayer.LINUX


def _safe_graph_attributes(raw: dict[str, object]) -> dict[str, SafeAttribute]:
    allowed = {
        "operation",
        "contract_version",
        "route_kind",
        "interface_type",
        "evidence_origin",
    }
    return {
        key: value
        for key, value in raw.items()
        if key in allowed and isinstance(value, (str, int, float, bool))
    }


def _load_gated_graph(output_root: Path, robot_id: str) -> dict[str, object] | None:
    try:
        release_root, release, _, _ = load_current_release(output_root, robot_id)
    except FileNotFoundError:
        return None
    graph_path = (release_root / release.state_graph).resolve()
    try:
        graph_path.relative_to(release_root.resolve())
    except ValueError as exc:
        raise ValueError("active State Graph escapes the release root") from exc
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("active State Graph must be an object")
    if payload.get("robot_id") != robot_id:
        raise ValueError("active State Graph robot identity mismatch")
    if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
        raise ValueError("active State Graph nodes and edges must be arrays")
    return payload


def build_robot_topology(
    robot: RobotCapability,
    output_root: Path,
    *,
    observed_at: datetime | None = None,
) -> tuple[RobotTopology, dict[str, EvidenceRecord]]:
    observed_at = observed_at or utc_now()
    records: dict[str, EvidenceRecord] = {}
    nodes: dict[str, TopologyNode] = {}
    edges: dict[str, TopologyEdge] = {}

    def add_registry_node(
        *,
        subject: str,
        kind: str,
        label: str,
        subtitle: str,
        layer: TopologyLayer,
        attributes: dict[str, SafeAttribute] | None = None,
    ) -> str:
        node_id = _stable_id(kind, f"{robot.robot_id}\0{subject}")
        record = _registry_record(robot, subject, node_id, observed_at)
        _add_evidence(records, record)
        nodes[node_id] = TopologyNode(
            node_id=node_id,
            kind=kind,
            label=label,
            subtitle=subtitle,
            layer=layer,
            state=TopologyState.DECLARED,
            confidence=1.0,
            integrity_status="validated",
            evidence_ids=[record.evidence_id],
            attributes=attributes or {},
        )
        return node_id

    root_id = add_registry_node(
        subject="robot",
        kind="robot",
        label=robot.robot_id,
        subtitle=str(robot.platform.get("drive_model", "registered robot")),
        layer=TopologyLayer.HARDWARE,
    )
    platform_attributes = {
        key: value
        for key in ("architecture", "os", "ros_distro", "drive_model")
        if isinstance((value := robot.platform.get(key)), (str, int, float, bool))
    }
    platform_id = add_registry_node(
        subject="platform",
        kind="platform",
        label=str(robot.platform.get("os", "Platform")),
        subtitle=str(robot.platform.get("architecture", "")),
        layer=TopologyLayer.LINUX,
        attributes=platform_attributes,
    )
    adapter_id = add_registry_node(
        subject="adapter",
        kind="adapter",
        label="Adapter",
        subtitle=robot.adapter,
        layer=TopologyLayer.APPLICATION,
        attributes={"adapter": robot.adapter},
    )

    def add_edge(source: str, target: str, relation: str, evidence_ids: list[str]) -> None:
        edge_id = _stable_id("edge", f"{source}\0{target}\0{relation}")
        edges[edge_id] = TopologyEdge(
            edge_id=edge_id,
            source=source,
            target=target,
            relation=relation,
            state=TopologyState.DECLARED,
            confidence=1.0,
            integrity_status="validated",
            evidence_ids=evidence_ids,
        )

    add_edge(root_id, platform_id, "runs", nodes[platform_id].evidence_ids)
    add_edge(platform_id, adapter_id, "hosts", nodes[adapter_id].evidence_ids)

    for name, payload in sorted(robot.sensors.items()):
        sensor = payload if isinstance(payload, dict) else {}
        sensor_id = add_registry_node(
            subject=f"sensor:{name}",
            kind="sensor",
            label=name.replace("_", " ").title(),
            subtitle=str(sensor.get("modality", "sensor")),
            layer=TopologyLayer.HARDWARE,
            attributes={
                key: value
                for key in ("semantic_uri", "modality")
                if isinstance((value := sensor.get(key)), (str, int, float, bool))
            },
        )
        add_edge(sensor_id, platform_id, "connects_to", nodes[sensor_id].evidence_ids)

    for name, enabled in sorted(robot.features.items()):
        if not isinstance(enabled, bool) or not enabled:
            continue
        feature_id = add_registry_node(
            subject=f"feature:{name}",
            kind="feature",
            label=name.replace("_", " ").title(),
            subtitle="declared feature",
            layer=TopologyLayer.APPLICATION,
            attributes={"enabled": True},
        )
        add_edge(adapter_id, feature_id, "declares", nodes[feature_id].evidence_ids)

    coverage: Literal["REGISTRY_ONLY", "GATED_RELEASE"] = "REGISTRY_ONLY"
    source_kind: Literal["robot_registry", "gated_state_graph"] = "robot_registry"
    integrity_status: Literal["validated", "verified"] = "validated"
    freshness: Literal["fresh", "unknown"] = "fresh"
    limitations = [
        "Only registry declarations are available; runtime presence is not asserted."
    ]
    confidence = 0.7
    graph = _load_gated_graph(output_root, robot.robot_id)
    if graph is not None:
        raw_nodes = [item for item in graph["nodes"] if isinstance(item, dict)]
        raw_edges = [item for item in graph["edges"] if isinstance(item, dict)]
        raw_to_read: dict[str, str] = {}
        for raw in raw_nodes:
            raw_id = str(raw.get("id", ""))
            kind = str(raw.get("kind", "component"))
            if not raw_id:
                raise ValueError("active State Graph node identity is missing")
            if kind == "robot":
                node_id = root_id
            elif kind == "adapter":
                node_id = adapter_id
            else:
                node_id = _stable_id(kind, f"{robot.robot_id}\0{raw_id}")
            raw_to_read[raw_id] = node_id
            evidence_ids: list[str] = []
            refs = raw.get("evidence_refs", [])
            if not isinstance(refs, list) or not refs:
                raise ValueError("active State Graph node lacks evidence references")
            for reference in refs:
                if not isinstance(reference, str) or not reference:
                    raise ValueError("active State Graph evidence reference is invalid")
                record = _graph_record(robot.robot_id, reference, node_id, observed_at)
                _add_evidence(records, record)
                evidence_ids.append(record.evidence_id)
            label = str(raw.get("operation") or raw.get("endpoint") or raw.get("bundle_id") or kind)
            current = nodes.get(node_id)
            nodes[node_id] = TopologyNode(
                node_id=node_id,
                kind=kind,
                label=current.label if current else label,
                subtitle=current.subtitle if current else str(raw.get("interface_type", "")),
                layer=_node_layer(kind, raw),
                state=TopologyState.GATED,
                confidence=1.0,
                integrity_status="verified",
                evidence_ids=sorted(set((current.evidence_ids if current else []) + evidence_ids)),
                attributes={
                    **(current.attributes if current else {}),
                    **_safe_graph_attributes(raw),
                },
            )
        for raw in raw_edges:
            source = raw_to_read.get(str(raw.get("source", "")))
            target = raw_to_read.get(str(raw.get("target", "")))
            relation = str(raw.get("relation", "related_to"))
            if not source or not target:
                raise ValueError("active State Graph contains a dangling edge")
            evidence_ids = []
            refs = raw.get("evidence_refs", [])
            if not isinstance(refs, list) or not refs:
                raise ValueError("active State Graph edge lacks evidence references")
            for reference in refs:
                if not isinstance(reference, str) or not reference:
                    raise ValueError("active State Graph edge evidence reference is invalid")
                record = _graph_record(robot.robot_id, reference, source, observed_at)
                record.related_node_ids.append(target)
                _add_evidence(records, record)
                evidence_ids.append(record.evidence_id)
            edge_id = _stable_id("edge", f"{source}\0{target}\0{relation}")
            edges[edge_id] = TopologyEdge(
                edge_id=edge_id,
                source=source,
                target=target,
                relation=relation,
                state=TopologyState.GATED,
                confidence=1.0,
                integrity_status="verified",
                evidence_ids=sorted(set(evidence_ids)),
            )
        coverage = "GATED_RELEASE"
        source_kind = "gated_state_graph"
        integrity_status = "verified"
        freshness = "unknown"
        limitations = [
            "Gated evidence proves the published binding, not physical task outcome correctness."
        ]
        confidence = 1.0

    topology = RobotTopology(
        robot_id=robot.robot_id,
        snapshot_id=_stable_id(
            "topology",
            f"{robot.robot_id}\0{coverage}\0{'|'.join(sorted(nodes))}\0{'|'.join(sorted(edges))}",
        ),
        coverage=coverage,
        nodes=sorted(nodes.values(), key=lambda item: (item.layer.value, item.label, item.node_id)),
        edges=sorted(edges.values(), key=lambda item: item.edge_id),
        observed_at=observed_at,
        freshness=freshness,
        source_kind=source_kind,
        confidence=confidence,
        integrity_status=integrity_status,
        limitations=limitations,
    )
    return topology, records


def build_evidence_collection(
    robot: RobotCapability,
    output_root: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    authority: EvidenceAuthority | None = None,
    pipeline: PipelineAssessment | None = None,
    observed_at: datetime | None = None,
) -> EvidenceCollection:
    topology, records = build_robot_topology(
        robot,
        output_root,
        observed_at=observed_at,
    )
    if pipeline is not None:
        for stage in pipeline.stages:
            for artifact_name, reference in sorted(stage.artifacts.items()):
                _add_evidence(
                    records,
                    _pipeline_record(
                        robot.robot_id,
                        stage.stage.value,
                        artifact_name,
                        reference,
                        stage.observed_at,
                    ),
                )
    items = sorted(records.values(), key=lambda item: (item.title, item.evidence_id))
    if authority is not None:
        items = [item for item in items if item.authority is authority]
    next_offset = offset + limit if offset + limit < len(items) else None
    return EvidenceCollection(
        robot_id=robot.robot_id,
        items=items[offset : offset + limit],
        total=len(items),
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        observed_at=topology.observed_at,
        freshness=topology.freshness,
    )


def find_evidence(
    robots: list[RobotCapability],
    output_root: Path,
    evidence_id: str,
    pipelines: dict[str, PipelineAssessment] | None = None,
) -> EvidenceRecord | None:
    for robot in robots:
        _, records = build_robot_topology(robot, output_root)
        pipeline = (pipelines or {}).get(robot.robot_id)
        if pipeline is not None:
            for stage in pipeline.stages:
                for artifact_name, reference in stage.artifacts.items():
                    _add_evidence(
                        records,
                        _pipeline_record(
                            robot.robot_id,
                            stage.stage.value,
                            artifact_name,
                            reference,
                            stage.observed_at,
                        ),
                    )
        if record := records.get(evidence_id):
            return record
    return None
