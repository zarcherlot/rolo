import pytest

from rolo.core.models import DiscoveryReport, DiscoveryStatus, OperationCandidate, RouteEvidence
from rolo.stages.adapt.models import AdapterBundleManifest
from rolo.stages.adapt.operation_registry import canonical_operation_registry
from rolo.stages.adapt.state_graph import (
    build_state_graph_baseline,
    validate_state_graph_baseline,
)


def _inputs() -> tuple[DiscoveryReport, AdapterBundleManifest]:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.snapshot"
    )
    report = DiscoveryReport(
        discovery_id="disc-graph",
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation=definition.operation,
                route_evidence=[
                    RouteEvidence(
                        resource_id="ros_topic:/camera/image_raw",
                        kind="ros_topic",
                        endpoint="/camera/image_raw",
                        evidence_origin="DECLARED_STATIC",
                        source="launch:camera.launch.py",
                    )
                ],
            )
        ],
    )
    bundle = AdapterBundleManifest(
        schema_version="robot-adapter-bundle/v1",
        bundle_id="camera",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-graph",
        package_file="adapter.py",
        package_sha256="a" * 64,
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_snapshot",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    return report, bundle


def test_state_graph_v2_binds_robot_adapter_contract_and_route() -> None:
    report, bundle = _inputs()

    graph = build_state_graph_baseline(report, bundle)

    assert graph.owner == "ROLO_GATE"
    assert all(node["evidence_refs"] for node in graph.nodes)
    validate_state_graph_baseline(graph, report, bundle)


def test_state_graph_rejects_contract_binding_mutation() -> None:
    report, bundle = _inputs()
    graph = build_state_graph_baseline(report, bundle)
    operation = next(node for node in graph.nodes if node["kind"] == "operation")
    operation["contract_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="operation binding mismatch"):
        validate_state_graph_baseline(graph, report, bundle)
