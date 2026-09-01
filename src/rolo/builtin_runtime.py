"""Dispatch for product-owned, bounded read-only operations.

Builtin operations are part of the Rolo product rather than generated adapter
code.  They still need an invocation path: leaving them as ``AVAILABLE`` made
the generated Tool Catalog unusable to downstream Tool Sessions even though
the implementation already existed in the canonical CLI.  This module keeps
the mapping explicit and argv-free so the invocation policy and output-schema
validation remain in the normal adapter runtime.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from rolo import __version__, host_introspection
from rolo.runtime import create_runtime
from rolo.stages.adapt.discovery import ApplicationProbe, HardwareProbe, RosProbe
from rolo.stages.adapt.models import StateGraphBaseline, ToolCatalog
from rolo.stages.adapt.workset import evidence_metadata

BuiltinHandler = Callable[[dict[str, Any], str, Path, Any, Any], dict[str, Any]]

_CONTROLLER_BUILTINS = {
    "tool.catalog",
    "tool.schema",
    "runtime.health",
    "runtime.version",
    "state.graph.snapshot",
    "state.graph.query",
    "evidence.resolve",
}

# These operations can be answered from the signed, bounded hw/linux/ros
# probes collected by the remote target-evidence transport.  Do not advertise
# controller-local host probes as target tools for a remote release.
_TARGET_EVIDENCE_BUILTINS = {
    "hw.inventory.scan",
    "linux.host.inventory",
    "linux.host.status",
    "linux.process.list",
    "middleware.inspect",
    "middleware.status",
    "middleware.graph.snapshot",
    "ros.graph.snapshot",
    "ros.node.status",
    "ros.node.list",
    "ros.topic.list",
    "ros.service.list",
    "ros.action.list",
    "ros.parameter.list",
}


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
    payload: dict[str, Any], _robot_id: str, _artifact_root: Path, _context: Any, _catalog: Any
) -> dict[str, Any]:
    roots = payload.get("source_roots") or [str(Path.cwd())]
    return ApplicationProbe().run([Path(str(root)) for root in roots]).model_dump(mode="json")


def _hardware(
    _payload: dict[str, Any], robot_id: str, artifact_root: Path, context: Any, _catalog: Any
) -> dict[str, Any]:
    target = _target_probe(context, artifact_root, robot_id, "hw")
    if target is not None:
        return _probe_output(target, layer="hw")
    return HardwareProbe().run(robot_id=robot_id).model_dump(mode="json")


def _ros_graph(
    _payload: dict[str, Any],
    _robot_id: str,
    _artifact_root: Path,
    context: Any,
    _catalog: Any,
) -> dict[str, Any]:
    target = _target_probe(context, _artifact_root, _robot_id, "ros")
    if target is not None:
        return _probe_output(target, layer="ros")
    return RosProbe().run().model_dump(mode="json")


def _release_from_context(context: Any) -> Any:
    if isinstance(context, tuple) and len(context) == 2:
        return context[1]
    return None


def _target_probe(
    context: Any, artifact_root: Path, robot_id: str, layer: str
) -> dict[str, Any] | None:
    """Load the signed discovery report bound to the active release.

    Remote Adapt deliberately does not execute controller-side probes against a
    target.  The collector's target-bound report is therefore the only valid
    source for a target-scoped builtin invocation.
    """

    release = _release_from_context(context)
    discovery_id = getattr(release, "discovery_id", None)
    if not isinstance(discovery_id, str) or not discovery_id:
        return None
    report_path = (
        artifact_root
        / "discovery"
        / robot_id
        / "runs"
        / discovery_id
        / "report.json"
    )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, Mapping):
        return None
    if report.get("robot_id") != robot_id or report.get("discovery_id") != discovery_id:
        return None
    probes = report.get("probes")
    probe = probes.get(layer) if isinstance(probes, Mapping) else None
    return dict(probe) if isinstance(probe, Mapping) else None


def _probe_output(probe: Mapping[str, Any], *, layer: str) -> dict[str, Any]:
    """Return a target probe using the canonical layer-probe contract shape."""

    return {
        "layer": layer,
        "status": str(probe.get("status") or "UNAVAILABLE"),
        "data": dict(probe.get("data") or {})
        if isinstance(probe.get("data"), Mapping)
        else {},
        "warnings": [str(item) for item in probe.get("warnings", []) or []],
        "errors": [str(item) for item in probe.get("errors", []) or []],
        "observed_at": str(probe.get("observed_at") or ""),
    }


def _target_introspection(
    operation: str,
    probe: Mapping[str, Any],
    data: dict[str, Any],
    *,
    warning: str | None = None,
) -> dict[str, Any]:
    warnings = [str(item) for item in probe.get("warnings", []) or []]
    if warning:
        warnings.append(warning)
    evidence = [{"source": "target_evidence", "observed_at": probe.get("observed_at")}]
    return {
        "schema_version": "robot-host-introspection/v1",
        "operation": operation,
        "status": str(probe.get("status") or "UNAVAILABLE"),
        "observed_at": str(probe.get("observed_at") or ""),
        "data": data,
        "evidence": evidence,
        "warnings": warnings,
    }


def _target_ros_version(data: Mapping[str, Any]) -> int | None:
    environment = data.get("runtime_environment")
    raw = environment.get("ROS_VERSION") if isinstance(environment, Mapping) else None
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return None
    return version if version in {1, 2} else None


def _target_ros_list(
    operation: str,
    key: str,
    _payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    _catalog: Any,
) -> dict[str, Any]:
    probe = _target_probe(context, artifact_root, robot_id, "ros")
    if probe is None:
        return getattr(host_introspection, operation.replace(".", "_"))()
    data = probe.get("data")
    values = data.get(key, []) if isinstance(data, Mapping) else []
    if not isinstance(values, list):
        values = []
    return _target_introspection(
        operation,
        probe,
        {
            "ros_version": _target_ros_version(data) if isinstance(data, Mapping) else None,
            key: values,
        },
    )


def _target_ros_node_status(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    _catalog: Any,
) -> dict[str, Any]:
    probe = _target_probe(context, artifact_root, robot_id, "ros")
    if probe is None:
        return host_introspection.ros_node_status(str(payload["name"]))
    data = probe.get("data")
    nodes = data.get("nodes", []) if isinstance(data, Mapping) else []
    names = (
        {str(item).split(" [", 1)[0].strip() for item in nodes}
        if isinstance(nodes, list)
        else set()
    )
    name = str(payload["name"])
    return _target_introspection(
        "ros.node.status",
        probe,
        {
            "name": name,
            "visible": name in names,
            "ros_version": _target_ros_version(data) if isinstance(data, Mapping) else None,
        },
    )


def _target_ros_parameter_list(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    return _target_ros_list(
        "ros.parameter.list",
        "parameters",
        payload,
        robot_id,
        artifact_root,
        context,
        catalog,
    )


def _target_host(
    operation: str,
    robot_id: str,
    artifact_root: Path,
    context: Any,
    *,
    status_only: bool = False,
) -> dict[str, Any] | None:
    probe = _target_probe(context, artifact_root, robot_id, "linux")
    if probe is None:
        return None
    data = probe.get("data")
    host = data.get("host", {}) if isinstance(data, Mapping) else {}
    environment = data.get("environment", {}) if isinstance(data, Mapping) else {}
    if not isinstance(host, Mapping):
        host = {}
    if not isinstance(environment, Mapping):
        environment = {}
    if status_only:
        output = {
            "system": host.get("system"),
            "release": host.get("release"),
            "architecture": host.get("architecture"),
            "hostname": host.get("hostname"),
            "uptime_s": None,
        }
    else:
        output = {
            "host": dict(host),
            "middleware_environment": {
                key: value
                for key, value in environment.items()
                if key in host_introspection.SAFE_ENV_KEYS
            },
            "target_evidence": {
                "processes": data.get("processes", []) if isinstance(data, Mapping) else []
            },
        }
    return _target_introspection(
        operation,
        probe,
        output,
        warning="uptime is not included in the bounded target evidence"
        if status_only
        else None,
    )


def _host_inventory_target(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    target = _target_host("linux.host.inventory", robot_id, artifact_root, context)
    if target is not None:
        return target
    return _host_handler("host_inventory")(payload, robot_id, artifact_root, context, catalog)


def _host_status_target(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    target = _target_host("linux.host.status", robot_id, artifact_root, context, status_only=True)
    if target is not None:
        return target
    return _host_handler("host_status")(payload, robot_id, artifact_root, context, catalog)


def _host_uptime_target(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    target = _target_host("linux.host.uptime", robot_id, artifact_root, context, status_only=True)
    if target is not None:
        target["status"] = "UNAVAILABLE"
        target["data"] = {"uptime_s": None}
        return target
    return _host_handler("host_uptime")(payload, robot_id, artifact_root, context, catalog)


def _target_process_list(
    _payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    _catalog: Any,
) -> dict[str, Any]:
    probe = _target_probe(context, artifact_root, robot_id, "linux")
    if probe is None:
        return host_introspection.process_list()
    raw = probe.get("data", {})
    records = raw.get("processes", []) if isinstance(raw, Mapping) else []
    processes: list[dict[str, Any]] = []
    for item in records if isinstance(records, list) else []:
        parts = str(item).strip().split(None, 6)
        if len(parts) < 4 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        try:
            process: dict[str, Any] = {
                "pid": int(parts[0]),
                "ppid": int(parts[1]),
                "state": parts[2],
                "command": parts[3],
                "argv": parts[4] if len(parts) >= 5 else parts[3],
            }
            processes.append(process)
        except (TypeError, ValueError):
            continue
    return _target_introspection("linux.process.list", probe, {"processes": processes})


def _target_middleware_inspect(
    _payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    _catalog: Any,
) -> dict[str, Any]:
    probe = _target_probe(context, artifact_root, robot_id, "linux")
    if probe is None:
        return host_introspection.middleware_inspect()
    raw = probe.get("data", {})
    environment = raw.get("environment", {}) if isinstance(raw, Mapping) else {}
    executables = raw.get("executables", {}) if isinstance(raw, Mapping) else {}
    installed = {
        name: details.get("path")
        for name, details in (executables.items() if isinstance(executables, Mapping) else [])
        if isinstance(details, Mapping) and details.get("available")
    }
    data = {
        "installed_interfaces": installed,
        "process_candidates": [],
        "listeners": [],
        "environment": dict(environment) if isinstance(environment, Mapping) else {},
    }
    return _target_introspection(
        "middleware.inspect",
        probe,
        data,
        warning="remote target evidence does not include a live middleware listener scan",
    )


def _target_middleware_status(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    inspected = _target_middleware_inspect(payload, robot_id, artifact_root, context, catalog)
    data = inspected.get("data", {})
    return {
        **inspected,
        "operation": "middleware.status",
        "data": {
            "installed_interfaces": data.get("installed_interfaces", {}),
            "process_candidate_count": len(data.get("process_candidates", [])),
            "listener_count": len(data.get("listeners", [])),
        },
    }


def _target_middleware_graph(
    payload: dict[str, Any],
    robot_id: str,
    artifact_root: Path,
    context: Any,
    catalog: Any,
) -> dict[str, Any]:
    inspected = _target_middleware_inspect(payload, robot_id, artifact_root, context, catalog)
    installed = inspected.get("data", {}).get("installed_interfaces", {})
    nodes = [
        {"id": f"interface:{name}", "kind": "interface", "name": name, "path": path}
        for name, path in sorted(installed.items())
    ]
    return {
        **inspected,
        "operation": "middleware.graph.snapshot",
        "data": {"nodes": nodes[:1000], "edges": []},
    }


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
    "linux.host.inventory": _host_inventory_target,
    "linux.host.status": _host_status_target,
    "linux.host.uptime": _host_uptime_target,
    "linux.service.list": _host_handler("service_list"),
    "linux.service.inspect": _host_handler("service_inspect", "name"),
    "linux.container.list": _container_list,
    "linux.container.inspect": _container_inspect,
    "linux.container.stats": _container_stats,
    "linux.schedule.list": _host_handler("schedule_list"),
    "linux.schedule.inspect": _host_handler("schedule_inspect", "name"),
    "linux.process.list": _target_process_list,
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
    "middleware.inspect": _target_middleware_inspect,
    "middleware.status": _target_middleware_status,
    "middleware.graph.snapshot": _target_middleware_graph,
    "ros.graph.snapshot": _ros_graph,
    "ros.node.status": _target_ros_node_status,
    "ros.node.list": lambda payload, robot_id, artifact_root, context, catalog: _target_ros_list(
        "ros.node.list", "nodes", payload, robot_id, artifact_root, context, catalog
    ),
    "ros.node.inspect": _host_handler("ros_node_inspect", "name"),
    "ros.node.lifecycle": _host_handler("ros_node_lifecycle", "name"),
    "ros.topic.list": lambda payload, robot_id, artifact_root, context, catalog: _target_ros_list(
        "ros.topic.list", "topics", payload, robot_id, artifact_root, context, catalog
    ),
    "ros.topic.describe": _host_handler("ros_topic_describe", "name"),
    "ros.service.list": lambda payload, robot_id, artifact_root, context, catalog: _target_ros_list(
        "ros.service.list", "services", payload, robot_id, artifact_root, context, catalog
    ),
    "ros.service.describe": _host_handler("ros_service_describe", "name"),
    "ros.action.list": lambda payload, robot_id, artifact_root, context, catalog: _target_ros_list(
        "ros.action.list", "actions", payload, robot_id, artifact_root, context, catalog
    ),
    "ros.action.describe": _host_handler("ros_action_describe", "name"),
    "ros.parameter.list": _target_ros_parameter_list,
    "ros.parameter.get": _ros_parameter_get,
    "ros.parameter.describe": _ros_parameter_describe,
    "ros.clock.status": _host_handler("ros_clock_status"),
    "ros.bag.inspect": _ros_bag_inspect,
    "app.robot.discover": _discover,
}


def supported_builtin_operations() -> set[str]:
    """Return builtins with a deterministic, schema-compatible dispatcher."""
    return set(_HANDLERS)


def target_verified_builtin_operations() -> set[str]:
    """Return builtins whose remote target evidence projection is implemented."""

    return _CONTROLLER_BUILTINS | _TARGET_EVIDENCE_BUILTINS


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
    return handler(payload, robot_id, artifact_root, context, catalog)
