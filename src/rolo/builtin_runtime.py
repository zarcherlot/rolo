"""Dispatch for product-owned, bounded read-only operations.

Builtin operations are part of the Rolo product rather than generated adapter
code.  They still need an invocation path: leaving them as ``AVAILABLE`` made
the generated Tool Catalog unusable to downstream Tool Sessions even though
the implementation already existed in the canonical CLI.  This module keeps
the mapping explicit and argv-free so the invocation policy and output-schema
validation remain in the normal adapter runtime.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rolo import __version__, host_introspection
from rolo.runtime import create_runtime
from rolo.stages.adapt.discovery import ApplicationProbe, HardwareProbe, RosProbe
from rolo.stages.adapt.models import StateGraphBaseline, ToolCatalog
from rolo.stages.adapt.workset import evidence_metadata

BuiltinHandler = Callable[[dict[str, Any], str, Path, Any, Any], dict[str, Any]]


def _runtime_health(
    _payload: dict[str, Any],
    _robot_id: str,
    _artifact_root: Path,
    _release_root: Any,
    _catalog: Any,
) -> dict[str, Any]:
    try:
        runtime = create_runtime()
        return {
            "status": "HEALTHY",
            "version": __version__,
            "registered_robots": len(runtime.registry),
            "artifact_root": str(runtime.artifacts.root),
        }
    except (OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "version": __version__, "error": str(exc)}


def _runtime_version(
    _payload: dict[str, Any],
    _robot_id: str,
    _artifact_root: Path,
    _release_root: Any,
    _catalog: Any,
) -> dict[str, Any]:
    return {
        "status": "SUCCEEDED",
        "version": __version__,
        "operation_contract_schema": "robot-operation-contract/v1",
        "adapter_protocol": "robot-adapter-rpc/v1",
        "tool_catalog_schema": "robot-tool-catalog/v1",
    }


def _tool_catalog(
    _payload: dict[str, Any], robot_id: str, _artifact_root: Path, _release_root: Any, catalog: Any
) -> dict[str, Any]:
    if not isinstance(catalog, ToolCatalog):
        raise ValueError("active Tool Catalog is unavailable")
    return catalog.model_copy(update={"robot_id": robot_id}).model_dump(mode="json")


def _tool_schema(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, catalog: Any
) -> dict[str, Any]:
    operation = str(payload.get("operation", "")).strip()
    if not isinstance(catalog, ToolCatalog):
        raise ValueError("active Tool Catalog is unavailable")
    descriptor = next((item for item in catalog.tools if item.operation == operation), None)
    if descriptor is None:
        raise ValueError(f"unknown operation: {operation}")
    return {
        "operation": descriptor.operation,
        "input_schema": descriptor.input_schema,
        "output_schema": descriptor.output_schema,
        "availability": descriptor.availability,
    }


def _state_graph_snapshot(
    payload: dict[str, Any], robot_id: str, artifact_root: Path, context: Any, catalog: Any
) -> dict[str, Any]:
    graph = _state_graph_from_context(robot_id, context)
    return graph.model_dump(mode="json")


def _state_graph_query(
    payload: dict[str, Any], robot_id: str, _artifact_root: Path, context: Any, _catalog: Any
) -> dict[str, Any]:
    query = str(payload.get("query", ""))
    graph = _state_graph_from_context(robot_id, context)
    needle = query.casefold()
    nodes = [
        item
        for item in graph.nodes
        if needle in __import__("json").dumps(item, ensure_ascii=False, sort_keys=True).casefold()
    ]
    edges = [
        item
        for item in graph.edges
        if needle in __import__("json").dumps(item, ensure_ascii=False, sort_keys=True).casefold()
    ]
    return {
        "schema_version": "robot-state-graph-query/v1",
        "robot_id": graph.robot_id,
        "discovery_id": graph.discovery_id,
        "query": query,
        "nodes": nodes[:100],
        "edges": edges[:100],
        "truncated": len(nodes) > 100 or len(edges) > 100,
    }


def _state_graph_from_context(robot_id: str, context: Any) -> StateGraphBaseline:
    release_root, release = context
    relative = getattr(release, "state_graph", None)
    if not relative:
        raise ValueError("active release state graph is unavailable")
    path = Path(release_root) / str(relative)
    graph = StateGraphBaseline.model_validate_json(path.read_text(encoding="utf-8"))
    if graph.robot_id != robot_id:
        raise ValueError("state graph robot identity mismatch")
    return graph


def _discover(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    roots = payload.get("source_roots") or [str(Path.cwd())]
    return ApplicationProbe().run([Path(str(root)) for root in roots]).model_dump(mode="json")


def _hardware(
    _payload: dict[str, Any], robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return HardwareProbe().run(robot_id=robot_id).model_dump(mode="json")


def _ros_graph(
    _payload: dict[str, Any],
    _robot_id: str,
    _artifact_root: Path,
    _release_root: Any,
    _catalog: Any,
) -> dict[str, Any]:
    return RosProbe().run().model_dump(mode="json")


def _evidence(
    payload: dict[str, Any], robot_id: str, artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return evidence_metadata(artifact_root, robot_id, str(payload["reference"]))


def _host_call(name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    function = getattr(host_introspection, name)
    return function(*args, **kwargs)


def _host_handler(name: str, *arg_names: str, **fixed: Any) -> BuiltinHandler:
    operation_name = name

    def handler(
        payload: dict[str, Any],
        _robot_id: str,
        _artifact_root: Path,
        _release_root: Any,
        _catalog: Any,
    ) -> dict[str, Any]:
        args = []
        for argument_name in arg_names:
            value = payload[argument_name]
            if argument_name in {"path", "binary"}:
                value = Path(str(value))
            elif argument_name == "pid":
                value = int(value)
            args.append(value)
        return _host_call(operation_name, *args, **fixed)

    return handler


def _container_list(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.container_list(payload.get("runtime"))


def _container_inspect(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.container_inspect(str(payload["name"]), payload.get("runtime"))


def _container_stats(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.container_stats(payload.get("name"), payload.get("runtime"))


def _resource_disk(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.resource_disk(Path(payload["path"]) if payload.get("path") else None)


def _resource_snapshot(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.resource_snapshot(
        Path(payload["path"]) if payload.get("path") else None
    )


def _config_locate(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.config_locate(
        pid=payload.get("process"),
        binary=Path(payload["binary"]) if payload.get("binary") else None,
    )


def _file_list(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.file_list(Path(payload["path"]), int(payload.get("limit", 100)))


def _cli_probe(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.cli_probe(Path(payload["path"]), payload.get("args") or ["--help"])


def _binary_verify(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.binary_verify(Path(payload["path"]), str(payload["expected_sha256"]))


def _ros_parameter_get(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.ros_parameter_get(str(payload["node"]), str(payload["name"]))


def _ros_parameter_describe(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.ros_parameter_describe(str(payload["node"]), str(payload["name"]))


def _ros_bag_inspect(
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _release_root: Any, _catalog: Any
) -> dict[str, Any]:
    return host_introspection.ros_bag_inspect(Path(payload["path"]))


_HANDLERS: dict[str, BuiltinHandler] = {
    "tool.catalog": _tool_catalog,
    "tool.schema": _tool_schema,
    "runtime.health": _runtime_health,
    "runtime.version": _runtime_version,
    "state.graph.snapshot": _state_graph_snapshot,
    "state.graph.query": _state_graph_query,
    "evidence.resolve": _evidence,
    "hw.inventory.scan": _hardware,
    "linux.host.inventory": _host_handler("host_inventory"),
    "linux.host.status": _host_handler("host_status"),
    "linux.host.uptime": _host_handler("host_uptime"),
    "linux.service.list": _host_handler("service_list"),
    "linux.service.inspect": _host_handler("service_inspect", "name"),
    "linux.container.list": _container_list,
    "linux.container.inspect": _container_inspect,
    "linux.container.stats": _container_stats,
    "linux.schedule.list": _host_handler("schedule_list"),
    "linux.schedule.inspect": _host_handler("schedule_inspect", "name"),
    "linux.process.list": _host_handler("process_list"),
    "linux.process.inspect": _host_handler("process_inspect", "pid"),
    "linux.process.resources": _host_handler("process_resources", "pid"),
    "linux.binary.describe": _host_handler("binary_describe", "path"),
    "linux.binary.verify": _binary_verify,
    "linux.package.inspect": _host_handler("package_inspect", "name"),
    "linux.package.verify": _host_handler("package_verify", "name"),
    "linux.cli.probe": _cli_probe,
    "linux.config.locate": _config_locate,
    "linux.file.inspect": _host_handler("file_inspect", "path"),
    "linux.file.hash": _host_handler("file_hash", "path"),
    "linux.file.list": _file_list,
    "linux.network.interfaces": _host_handler("network_interfaces"),
    "linux.network.listeners": _host_handler("network_listeners"),
    "linux.network.routes": _host_handler("network_routes"),
    "linux.network.connections": _host_handler("network_connections"),
    "linux.network.statistics": _host_handler("network_statistics"),
    "linux.network.dns": _host_handler("network_dns"),
    "linux.resource.cpu": _host_handler("resource_cpu"),
    "linux.resource.memory": _host_handler("resource_memory"),
    "linux.resource.disk": _resource_disk,
    "linux.resource.snapshot": _resource_snapshot,
    "linux.resource.gpu": _host_handler("resource_gpu"),
    "linux.time.status": _host_handler("time_status"),
    "middleware.inspect": _host_handler("middleware_inspect"),
    "middleware.status": _host_handler("middleware_status"),
    "middleware.graph.snapshot": _host_handler("middleware_graph_snapshot"),
    "ros.graph.snapshot": _ros_graph,
    "ros.node.status": _host_handler("ros_node_status", "name"),
    "ros.node.list": _host_handler("ros_node_list"),
    "ros.node.inspect": _host_handler("ros_node_inspect", "name"),
    "ros.node.lifecycle": _host_handler("ros_node_lifecycle", "name"),
    "ros.topic.list": _host_handler("ros_topic_list"),
    "ros.topic.describe": _host_handler("ros_topic_describe", "name"),
    "ros.service.list": _host_handler("ros_service_list"),
    "ros.service.describe": _host_handler("ros_service_describe", "name"),
    "ros.action.list": _host_handler("ros_action_list"),
    "ros.action.describe": _host_handler("ros_action_describe", "name"),
    "ros.parameter.list": _host_handler("ros_parameter_list"),
    "ros.parameter.get": _ros_parameter_get,
    "ros.parameter.describe": _ros_parameter_describe,
    "ros.clock.status": _host_handler("ros_clock_status"),
    "ros.bag.inspect": _ros_bag_inspect,
    "app.robot.discover": _discover,
}


def supported_builtin_operations() -> set[str]:
    """Return builtins with a deterministic, schema-compatible dispatcher."""
    return set(_HANDLERS)


def invoke_builtin(
    operation: str,
    payload: dict[str, Any],
    *,
    robot_id: str,
    artifact_root: Path,
    release_root: Path,
    release: Any,
    catalog: Any,
) -> dict[str, Any]:
    try:
        handler = _HANDLERS[operation]
    except KeyError as exc:
        raise ValueError(f"builtin operation has no dispatcher: {operation}") from exc
    context = (release_root, release)
    if operation in {"state.graph.snapshot", "state.graph.query"}:
        return handler(payload, robot_id, artifact_root, context, catalog)
    return handler(payload, robot_id, artifact_root, release_root, catalog)
