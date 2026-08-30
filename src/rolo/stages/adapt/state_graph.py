from __future__ import annotations

from rolo.core.hashing import sha256_bytes
from rolo.core.models import DiscoveryReport, RouteEvidence
from rolo.stages.adapt.models import AdapterBundleManifest, StateGraphBaseline

_NODE_KINDS = {"robot", "adapter", "operation", "route"}
_EDGE_RELATIONS = {"contains", "implements", "routes_to"}


def _route_node_id(resource_id: str) -> str:
    return f"route:{sha256_bytes(resource_id.encode('utf-8'))[:16]}"


def _route_rank(route: RouteEvidence) -> tuple[int, int]:
    """Match the deterministic preference used while building the graph."""
    return (
        int(route.observed),
        sum(
            getattr(route, field) is not None
            for field in (
                "interface_type",
                "interface_schema_sha256",
                "provider_id",
                "runtime_revision",
            )
        ),
    )


def build_state_graph_baseline(
    report: DiscoveryReport, bundle: AdapterBundleManifest
) -> StateGraphBaseline:
    """Build the Rolo-owned graph from gated identities and route evidence."""
    candidates = {item.operation: item for item in report.operation_candidates}
    robot_node = f"robot:{report.robot_id}"
    adapter_node = f"adapter:{bundle.bundle_id}"
    nodes: list[dict[str, object]] = [
        {
            "id": robot_node,
            "kind": "robot",
            "robot_id": report.robot_id,
            "evidence_refs": [f"discovery:{report.discovery_id}"],
        },
        {
            "id": adapter_node,
            "kind": "adapter",
            "bundle_id": bundle.bundle_id,
            "bundle_version": bundle.bundle_version,
            "evidence_refs": [f"bundle:{bundle.bundle_id}"],
        },
    ]
    edges: list[dict[str, object]] = [
        {
            "source": robot_node,
            "target": adapter_node,
            "relation": "contains",
            "evidence_refs": [f"discovery:{report.discovery_id}"],
        }
    ]
    route_node_indexes: dict[str, int] = {}
    seen_route_edges: set[tuple[str, str]] = set()
    route_ranks: dict[str, tuple[int, int]] = {}
    for entry in sorted(bundle.operations, key=lambda item: item.operation):
        candidate = candidates[entry.operation]
        semantic_bindings_by_endpoint: dict[str, list[str]] = {}
        for semantic_binding, endpoint in zip(
            candidate.semantic_bindings,
            candidate.evidence,
            strict=False,
        ):
            semantic_bindings_by_endpoint.setdefault(endpoint, []).append(semantic_binding)
        operation_node = f"operation:{entry.operation}"
        nodes.append(
            {
                "id": operation_node,
                "kind": "operation",
                "operation": entry.operation,
                "entrypoint": entry.entrypoint,
                "contract_version": entry.contract_version,
                "contract_sha256": entry.contract_sha256,
                "evidence_refs": list(
                    dict.fromkeys([f"bundle:{bundle.bundle_id}", *candidate.evidence])
                ),
            }
        )
        edges.append(
            {
                "source": adapter_node,
                "target": operation_node,
                "relation": "implements",
                "evidence_refs": [f"bundle:{bundle.bundle_id}"],
            }
        )
        for route in candidate.route_evidence:
            route_node = _route_node_id(route.resource_id)
            route_payload = {
                "id": route_node,
                "kind": "route",
                "resource_id": route.resource_id,
                "route_kind": route.kind,
                "endpoint": route.endpoint,
                "interface_type": route.interface_type,
                "interface_schema_sha256": route.interface_schema_sha256,
                "provider_id": route.provider_id,
                "runtime_revision": route.runtime_revision,
                "evidence_origin": route.evidence_origin,
                "semantic_bindings": semantic_bindings_by_endpoint.get(route.endpoint, []),
                "evidence_refs": [route.source],
            }
            rank = _route_rank(route)
            if route_node not in route_node_indexes:
                route_node_indexes[route_node] = len(nodes)
                route_ranks[route_node] = rank
                nodes.append(route_payload)
            else:
                node = nodes[route_node_indexes[route_node]]
                evidence_refs = list(dict.fromkeys([*node["evidence_refs"], route.source]))
                semantic_bindings = list(
                    dict.fromkeys(
                        [*node.get("semantic_bindings", []), *route_payload["semantic_bindings"]]
                    )
                )
                if rank > route_ranks[route_node]:
                    route_ranks[route_node] = rank
                    route_payload["evidence_refs"] = evidence_refs
                    route_payload["semantic_bindings"] = semantic_bindings
                    nodes[route_node_indexes[route_node]] = route_payload
                else:
                    node["evidence_refs"] = evidence_refs
                    node["semantic_bindings"] = semantic_bindings
            edge_identity = (operation_node, route_node)
            if edge_identity not in seen_route_edges:
                seen_route_edges.add(edge_identity)
                edges.append(
                    {
                        "source": operation_node,
                        "target": route_node,
                        "relation": "routes_to",
                        "evidence_refs": [route.source],
                    }
                )
    graph = StateGraphBaseline(
        schema_version="robot-state-graph/v2",
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        owner="ROLO_GATE",
        nodes=nodes,
        edges=edges,
    )
    validate_state_graph_baseline(graph, report, bundle)
    return graph


def validate_state_graph_baseline(
    graph: StateGraphBaseline,
    report: DiscoveryReport,
    bundle: AdapterBundleManifest,
) -> None:
    if graph.schema_version != "robot-state-graph/v2" or graph.owner != "ROLO_GATE":
        raise ValueError("published State Graph must be the Rolo-owned v2 baseline")
    if graph.robot_id != report.robot_id or graph.discovery_id != report.discovery_id:
        raise ValueError("State Graph identity does not match discovery")
    node_ids = [str(node.get("id", "")) for node in graph.nodes]
    if not node_ids or any(not value for value in node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError("State Graph node identities must be non-empty and unique")
    node_by_id = {str(node["id"]): node for node in graph.nodes}
    for node in graph.nodes:
        if node.get("kind") not in _NODE_KINDS:
            raise ValueError(f"State Graph has an unsupported node kind: {node.get('kind')}")
        if not isinstance(node.get("evidence_refs"), list) or not node["evidence_refs"]:
            raise ValueError(f"State Graph node lacks evidence refs: {node.get('id')}")
    for edge in graph.edges:
        if edge.get("relation") not in _EDGE_RELATIONS:
            raise ValueError(f"State Graph has an unsupported relation: {edge.get('relation')}")
        if edge.get("source") not in node_by_id or edge.get("target") not in node_by_id:
            raise ValueError("State Graph contains a dangling edge")
        if not isinstance(edge.get("evidence_refs"), list) or not edge["evidence_refs"]:
            raise ValueError("State Graph edge lacks evidence refs")

    candidates = {item.operation: item for item in report.operation_candidates}
    bundle_operations = {item.operation for item in bundle.operations}
    expected_routes: dict[str, list[RouteEvidence]] = {}
    for operation, candidate in candidates.items():
        if operation not in bundle_operations:
            continue
        for route in candidate.route_evidence:
            expected_routes.setdefault(route.resource_id, []).append(route)
    expected_best_routes = {
        resource_id: max(routes, key=_route_rank)
        for resource_id, routes in expected_routes.items()
    }
    expected_route_sources = {
        resource_id: {route.source for route in routes}
        for resource_id, routes in expected_routes.items()
    }
    expected_route_semantics: dict[str, set[str]] = {}
    for operation, candidate in candidates.items():
        if operation not in bundle_operations:
            continue
        for semantic_binding, endpoint in zip(
            candidate.semantic_bindings,
            candidate.evidence,
            strict=False,
        ):
            for route in candidate.route_evidence:
                if route.endpoint == endpoint:
                    expected_route_semantics.setdefault(route.resource_id, set()).add(
                        semantic_binding
                    )
    robot_id = f"robot:{report.robot_id}"
    adapter_id = f"adapter:{bundle.bundle_id}"
    if node_by_id.get(robot_id, {}).get("kind") != "robot":
        raise ValueError("State Graph lacks its robot root")
    if node_by_id.get(adapter_id, {}).get("kind") != "adapter":
        raise ValueError("State Graph lacks its adapter node")
    if not any(
        edge.get("source") == robot_id
        and edge.get("target") == adapter_id
        and edge.get("relation") == "contains"
        for edge in graph.edges
    ):
        raise ValueError("State Graph lacks the robot-to-adapter binding")
    for entry in bundle.operations:
        operation_id = f"operation:{entry.operation}"
        operation_node = node_by_id.get(operation_id)
        if (
            operation_node is None
            or operation_node.get("operation") != entry.operation
            or operation_node.get("entrypoint") != entry.entrypoint
            or operation_node.get("contract_version") != entry.contract_version
            or operation_node.get("contract_sha256") != entry.contract_sha256
        ):
            raise ValueError(f"State Graph operation binding mismatch: {entry.operation}")
        if not any(
            edge.get("relation") == "implements"
            and edge.get("source") == adapter_id
            and edge.get("target") == operation_id
            for edge in graph.edges
        ):
            raise ValueError(f"State Graph lacks adapter binding: {entry.operation}")
        expected_resources = {
            route.resource_id for route in candidates[entry.operation].route_evidence
        }
        routed_resources = {
            str(node_by_id[str(edge["target"])].get("resource_id"))
            for edge in graph.edges
            if edge.get("relation") == "routes_to" and edge.get("source") == operation_id
        }
        if not expected_resources or routed_resources != expected_resources:
            raise ValueError(f"State Graph route coverage mismatch: {entry.operation}")
        for resource_id in expected_resources:
            route_node_id = _route_node_id(resource_id)
            route_node = node_by_id.get(route_node_id)
            if route_node is None or route_node.get("kind") != "route":
                raise ValueError(
                    f"State Graph route node mismatch: {entry.operation}:{resource_id}"
                )
            expected = expected_best_routes[resource_id]
            for field in (
                "resource_id",
                "route_kind",
                "endpoint",
                "interface_type",
                "interface_schema_sha256",
                "provider_id",
                "runtime_revision",
                "evidence_origin",
            ):
                expected_value = (
                    expected.kind if field == "route_kind" else getattr(expected, field)
                )
                if route_node.get(field) != expected_value:
                    raise ValueError(
                        "State Graph route binding mismatch: "
                        f"{entry.operation}:{resource_id}:{field}"
                    )
            actual_sources = set(route_node.get("evidence_refs", []))
            if not expected_route_sources[resource_id] <= actual_sources:
                raise ValueError(
                    f"State Graph route evidence mismatch: {entry.operation}:{resource_id}"
                )
            actual_semantics = set(route_node.get("semantic_bindings", []))
            if not expected_route_semantics.get(resource_id, set()) <= actual_semantics:
                raise ValueError(
                    f"State Graph route semantic binding mismatch: {entry.operation}:{resource_id}"
                )
