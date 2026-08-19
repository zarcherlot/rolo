from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from rolo import host_introspection
from rolo.adapter_runtime import invoke_adapter, load_current_release
from rolo.commands.common import emit
from rolo.contract_catalog import load_operation_contracts, render_contract_catalog
from rolo.core.config import get_settings
from rolo.invocation_policy import authorize_data_access
from rolo.stages.adapt.discovery import (
    ApplicationProbe,
    HardwareProbe,
    RosProbe,
)
from rolo.stages.adapt.models import StateGraphBaseline, ToolCatalog
from rolo.stages.adapt.operation_registry import canonical_operation_registry

tool_app = typer.Typer(help="Inspect the generated canonical tool catalog.")
contract_app = typer.Typer(help="Validate and inspect product-owned operation contracts.")
hw_app = typer.Typer(help="Canonical hardware-layer tools.")
hw_inventory_app = typer.Typer(help="Hardware inventory operations.")
linux_app = typer.Typer(help="Canonical Linux-layer tools.")
linux_host_app = typer.Typer(help="Linux host operations.")
linux_service_app = typer.Typer(help="Read-only service discovery operations.")
linux_container_app = typer.Typer(help="Read-only local container discovery operations.")
linux_schedule_app = typer.Typer(help="Read-only scheduled-task discovery operations.")
linux_process_app = typer.Typer(help="Read-only process discovery operations.")
linux_binary_app = typer.Typer(help="Static binary inspection operations.")
linux_package_app = typer.Typer(help="Read-only installed-package metadata operations.")
linux_cli_app = typer.Typer(help="Bounded CLI self-description probes.")
linux_config_app = typer.Typer(help="Configuration-location operations.")
linux_file_app = typer.Typer(help="Bounded read-only file operations.")
linux_network_app = typer.Typer(help="Read-only network discovery operations.")
linux_resource_app = typer.Typer(help="Read-only host resource operations.")
linux_time_app = typer.Typer(help="Read-only host clock operations.")
middleware_app = typer.Typer(help="Canonical middleware discovery tools.")
middleware_graph_app = typer.Typer(help="Middleware topology snapshot operations.")
ros_app = typer.Typer(help="Canonical ROS-layer tools.")
ros_graph_app = typer.Typer(help="ROS graph operations.")
ros_node_app = typer.Typer(help="ROS node inspection operations.")
ros_topic_app = typer.Typer(help="ROS topic discovery operations.")
ros_service_app = typer.Typer(help="ROS service discovery operations.")
ros_action_app = typer.Typer(help="ROS action discovery operations.")
ros_parameter_app = typer.Typer(help="ROS parameter read operations.")
ros_clock_app = typer.Typer(help="ROS clock inspection operations.")
ros_bag_app = typer.Typer(help="ROS bag inspection operations.")
application_app = typer.Typer(help="Canonical application-layer tools.")
app_robot_cli = typer.Typer(help="Application robot discovery operations.")
state_app = typer.Typer(help="Inspect the active gated robot state model.")
state_graph_app = typer.Typer(help="State Graph snapshot and query operations.")

hw_app.add_typer(hw_inventory_app, name="inventory")
linux_app.add_typer(linux_host_app, name="host")
linux_app.add_typer(linux_service_app, name="service")
linux_app.add_typer(linux_container_app, name="container")
linux_app.add_typer(linux_schedule_app, name="schedule")
linux_app.add_typer(linux_process_app, name="process")
linux_app.add_typer(linux_binary_app, name="binary")
linux_app.add_typer(linux_package_app, name="package")
linux_app.add_typer(linux_cli_app, name="cli")
linux_app.add_typer(linux_config_app, name="config")
linux_app.add_typer(linux_file_app, name="file")
linux_app.add_typer(linux_network_app, name="network")
linux_app.add_typer(linux_resource_app, name="resource")
linux_app.add_typer(linux_time_app, name="time")
middleware_app.add_typer(middleware_graph_app, name="graph")
ros_app.add_typer(ros_graph_app, name="graph")
ros_app.add_typer(ros_node_app, name="node")
ros_app.add_typer(ros_topic_app, name="topic")
ros_app.add_typer(ros_service_app, name="service")
ros_app.add_typer(ros_action_app, name="action")
ros_app.add_typer(ros_parameter_app, name="parameter")
ros_app.add_typer(ros_clock_app, name="clock")
ros_app.add_typer(ros_bag_app, name="bag")
application_app.add_typer(app_robot_cli, name="robot")
state_app.add_typer(state_graph_app, name="graph")
tool_app.add_typer(contract_app, name="contract")


@contract_app.command("validate")
def contract_validate() -> None:
    """Compile all contract files and validate them against the product vocabulary."""
    catalog = load_operation_contracts()
    registry = canonical_operation_registry()
    counts: dict[str, int] = {}
    for operation in registry.operations:
        counts[operation.contract_lifecycle.value] = (
            counts.get(operation.contract_lifecycle.value, 0) + 1
        )
    emit(
        {
            "status": "SUCCEEDED",
            "registry_operations": len(registry.operations),
            "authored_contracts": len(catalog.contracts),
            "contract_lifecycle_counts": counts,
            "contract_catalog_sha256": catalog.sha256,
        }
    )


@contract_app.command("show")
def contract_show(operation: Annotated[str, typer.Argument()]) -> None:
    """Show the compiled product contract or DRAFT vocabulary entry."""
    definition = next(
        (
            item
            for item in canonical_operation_registry().operations
            if item.operation == operation
        ),
        None,
    )
    if definition is None:
        raise typer.BadParameter(f"unknown canonical operation: {operation}")
    emit(definition)


@contract_app.command("export")
def contract_export(
    output: Annotated[
        Path, typer.Option(help="Generated Markdown contract catalog path")
    ] = Path("docs/OPERATION_CONTRACTS.md"),
) -> None:
    """Generate the reviewable contract lifecycle and digest catalog."""
    catalog = load_operation_contracts()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_contract_catalog(catalog), encoding="utf-8")
    emit({"status": "SUCCEEDED", "output": str(output), "sha256": catalog.sha256})


@tool_app.command("registry")
def tool_registry(
    layer: Annotated[str | None, typer.Option("--layer")] = None,
) -> None:
    """Inspect product-defined operations without probing a robot host."""
    registry = canonical_operation_registry()
    operations = registry.operations
    if layer:
        operations = [operation for operation in operations if operation.layer == layer]
    emit(
        {
            "schema_version": registry.schema_version,
            "operations": [operation.model_dump(mode="json") for operation in operations],
        }
    )


@hw_inventory_app.command("scan")
def hw_inventory_scan() -> None:
    """Implement canonical `hw inventory scan` with read-only host probes."""
    emit(HardwareProbe().run())


@linux_host_app.command("inspect")
def linux_host_inspect() -> None:
    """Backward-compatible alias for `linux host inventory`."""
    emit(host_introspection.host_inventory())


@linux_host_app.command("inventory")
def linux_host_inventory() -> None:
    """Inventory host identity and available control planes without changing them."""
    emit(host_introspection.host_inventory())


@linux_host_app.command("status")
def linux_host_status() -> None:
    """Read compact host identity and uptime status."""
    emit(host_introspection.host_status())


@linux_host_app.command("uptime")
def linux_host_uptime() -> None:
    """Read elapsed time since the host booted when supported."""
    emit(host_introspection.host_uptime())


@linux_service_app.command("list")
def linux_service_list() -> None:
    """List services through the native service manager."""
    emit(host_introspection.service_list())


@linux_service_app.command("inspect")
def linux_service_inspect(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect one service definition, state, dependencies, and launch context."""
    try:
        emit(host_introspection.service_inspect(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_container_app.command("list")
def linux_container_list(
    runtime: Annotated[str | None, typer.Option("--runtime")] = None,
) -> None:
    """List local Docker or Podman containers without changing them."""
    try:
        emit(host_introspection.container_list(runtime))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_container_app.command("inspect")
def linux_container_inspect(
    name: Annotated[str, typer.Argument()],
    runtime: Annotated[str | None, typer.Option("--runtime")] = None,
) -> None:
    """Inspect one local Docker or Podman container."""
    try:
        emit(host_introspection.container_inspect(name, runtime))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_container_app.command("stats")
def linux_container_stats(
    name: Annotated[str | None, typer.Argument()] = None,
    runtime: Annotated[str | None, typer.Option("--runtime")] = None,
) -> None:
    """Read one bounded Docker or Podman resource snapshot."""
    try:
        emit(host_introspection.container_stats(name, runtime))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_schedule_app.command("list")
def linux_schedule_list() -> None:
    """List system timers, the current user crontab, or Windows scheduled tasks."""
    emit(host_introspection.schedule_list())


@linux_schedule_app.command("inspect")
def linux_schedule_inspect(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect one system timer or Windows scheduled task."""
    try:
        emit(host_introspection.schedule_inspect(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_process_app.command("list")
def linux_process_list() -> None:
    """List bounded, redacted process metadata."""
    emit(host_introspection.process_list())


@linux_process_app.command("inspect")
def linux_process_inspect(pid: Annotated[int, typer.Argument(min=1)]) -> None:
    """Inspect one process tree anchor, executable, environment keys, and loaded files."""
    try:
        emit(host_introspection.process_inspect(pid))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_process_app.command("resources")
def linux_process_resources(pid: Annotated[int, typer.Argument(min=1)]) -> None:
    """Read CPU, memory, I/O, thread, and handle metadata for one process."""
    try:
        emit(host_introspection.process_resources(pid))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_binary_app.command("describe")
def linux_binary_describe(path: Annotated[Path, typer.Argument()]) -> None:
    """Describe a binary statically without invoking its operational interface."""
    emit(host_introspection.binary_describe(path))


@linux_binary_app.command("verify")
def linux_binary_verify(
    path: Annotated[Path, typer.Argument()],
    expected_sha256: Annotated[str, typer.Option("--expected-sha256")],
) -> None:
    """Compare one explicit binary against an expected SHA-256 digest."""
    try:
        emit(host_introspection.binary_verify(path, expected_sha256))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_package_app.command("inspect")
def linux_package_inspect(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect one installed package without changing package-manager state."""
    try:
        emit(host_introspection.package_inspect(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_package_app.command("verify")
def linux_package_verify(name: Annotated[str, typer.Argument()]) -> None:
    """Run the native read-only integrity check for one installed package."""
    try:
        emit(host_introspection.package_verify(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_cli_app.command("probe")
def linux_cli_probe(
    path: Annotated[Path, typer.Argument()],
    args: Annotated[
        list[str] | None,
        typer.Option("--arg", help="Safe self-description argument; repeat as needed"),
    ] = None,
) -> None:
    """Run an explicit executable with bounded self-description arguments only."""
    try:
        emit(host_introspection.cli_probe(path, args or ["--help"]))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_config_app.command("locate")
def linux_config_locate(
    process: Annotated[int | None, typer.Option("--process", min=1)] = None,
    binary: Annotated[Path | None, typer.Option("--binary")] = None,
) -> None:
    """Locate configuration candidates associated with a process or binary."""
    try:
        emit(host_introspection.config_locate(pid=process, binary=binary))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_file_app.command("hash")
def linux_file_hash(path: Annotated[Path, typer.Argument()]) -> None:
    """Calculate a bounded SHA-256 digest for one explicit regular file."""
    emit(host_introspection.file_hash(path))


@linux_file_app.command("inspect")
def linux_file_inspect(path: Annotated[Path, typer.Argument()]) -> None:
    """Read metadata for one explicit filesystem entry without reading its content."""
    emit(host_introspection.file_inspect(path))


@linux_file_app.command("list")
def linux_file_list(
    path: Annotated[Path, typer.Argument()],
    limit: Annotated[int, typer.Option(min=1, max=1_000)] = 100,
) -> None:
    """List one directory level with a strict result bound."""
    try:
        emit(host_introspection.file_list(path, limit))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@linux_network_app.command("listeners")
def linux_network_listeners() -> None:
    """List bounded local listening sockets and owning processes when available."""
    emit(host_introspection.network_listeners())


@linux_network_app.command("routes")
def linux_network_routes() -> None:
    """List bounded local routing-table entries without changing them."""
    emit(host_introspection.network_routes())


@linux_network_app.command("interfaces")
def linux_network_interfaces() -> None:
    """List bounded network-interface and assigned-address metadata."""
    emit(host_introspection.network_interfaces())


@linux_network_app.command("statistics")
def linux_network_statistics() -> None:
    """Read bounded per-interface packet and byte counters."""
    emit(host_introspection.network_statistics())


@linux_network_app.command("connections")
def linux_network_connections() -> None:
    """List bounded local connection metadata and owning processes when available."""
    emit(host_introspection.network_connections())


@linux_network_app.command("dns")
def linux_network_dns() -> None:
    """Read bounded local DNS resolver configuration metadata."""
    emit(host_introspection.network_dns())


@linux_resource_app.command("cpu")
def linux_resource_cpu() -> None:
    """Read bounded CPU topology and load metadata."""
    emit(host_introspection.resource_cpu())


@linux_resource_app.command("memory")
def linux_resource_memory() -> None:
    """Read physical memory totals and availability."""
    emit(host_introspection.resource_memory())


@linux_resource_app.command("disk")
def linux_resource_disk(
    path: Annotated[
        Path | None, typer.Option(help="Existing path on the target filesystem")
    ] = None,
) -> None:
    """Read filesystem capacity for one explicit path."""
    emit(host_introspection.resource_disk(path))


@linux_resource_app.command("snapshot")
def linux_resource_snapshot(
    path: Annotated[
        Path | None, typer.Option(help="Existing path on the target filesystem")
    ] = None,
) -> None:
    """Read one bounded CPU, memory, and disk resource snapshot."""
    emit(host_introspection.resource_snapshot(path))


@linux_resource_app.command("gpu")
def linux_resource_gpu() -> None:
    """Read available GPU identity and utilization metadata."""
    emit(host_introspection.resource_gpu())


@linux_time_app.command("status")
def linux_time_status() -> None:
    """Read wall-clock and monotonic-clock metadata without synchronizing time."""
    emit(host_introspection.time_status())


@middleware_app.command("inspect")
def middleware_inspect() -> None:
    """Identify ROS and non-ROS middleware candidates from host evidence."""
    emit(host_introspection.middleware_inspect())


@middleware_app.command("status")
def middleware_status() -> None:
    """Read a compact status summary of discovered middleware interfaces."""
    emit(host_introspection.middleware_status())


@middleware_graph_app.command("snapshot")
def middleware_graph_snapshot() -> None:
    """Read a bounded middleware process and interface relationship snapshot."""
    emit(host_introspection.middleware_graph_snapshot())


@ros_graph_app.command("snapshot")
def ros_graph_snapshot() -> None:
    """Implement canonical `ros graph snapshot` using bounded ROS 2 introspection."""
    emit(RosProbe().run())


@ros_node_app.command("status")
def ros_node_status(name: Annotated[str, typer.Argument()]) -> None:
    """Read compact visibility status for one ROS 1 or ROS 2 node."""
    try:
        emit(host_introspection.ros_node_status(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app_robot_cli.command("discover")
def application_robot_discover(
    source_root: Annotated[
        list[Path] | None,
        typer.Option("--source-root", help="Application source root; repeat for overlays"),
    ] = None,
) -> None:
    """Implement canonical `app robot discover` for local source workspaces."""
    emit(ApplicationProbe().run(source_root or [Path.cwd()]))


@tool_app.command("catalog")
def tool_catalog(
    robot: Annotated[str, typer.Option("--robot")],
    layer: Annotated[str | None, typer.Option("--layer")] = None,
) -> None:
    """List the Active Tool Catalog from the latest gated adapter release."""
    settings = get_settings()
    try:
        _, _, _, catalog = load_current_release(settings.rolo_output_dir, robot)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    tools = catalog.tools
    if layer:
        tools = [tool for tool in tools if tool.layer == layer]
    emit(
        ToolCatalog(
            robot_id=robot,
            discovery_id=catalog.discovery_id,
            contract_catalog_sha256=catalog.contract_catalog_sha256,
            tools=tools,
        )
    )


@tool_app.command("schema")
def tool_schema(
    operation: Annotated[str, typer.Argument(help="Canonical operation, e.g. hw.inventory.scan")],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show a schema from the latest gated Active Tool Catalog."""
    settings = get_settings()
    try:
        _, _, _, catalog = load_current_release(settings.rolo_output_dir, robot)
        descriptor = next(tool for tool in catalog.tools if tool.operation == operation)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except StopIteration as exc:
        raise typer.BadParameter(f"Unknown discovered operation: {operation}") from exc
    emit(
        {
            "operation": descriptor.operation,
            "input_schema": descriptor.input_schema,
            "output_schema": descriptor.output_schema,
            "availability": descriptor.availability,
        }
    )


@tool_app.command("invoke")
def tool_invoke(
    operation: Annotated[str, typer.Argument(help="Canonical operation identifier")],
    robot: Annotated[str, typer.Option("--robot")],
    input_json: Annotated[
        str, typer.Option("--input", help="Operation input as one JSON object")
    ] = "{}",
) -> None:
    """Invoke an operation through the active, independently gated adapter release."""
    try:
        payload = json.loads(input_json)
        if not isinstance(payload, dict):
            raise ValueError("operation input must be a JSON object")
        settings = get_settings()
        emit(
            invoke_adapter(
                settings.rolo_output_dir,
                robot,
                operation,
                payload,
                policy_path=settings.rolo_invocation_policy,
                audit_path=settings.rolo_invocation_audit_log,
                r3_authorizer_path=settings.rolo_r3_authorizer,
                artifact_root=settings.rolo_artifact_dir,
            )
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_node_app.command("list")
def ros_node_list() -> None:
    """List bounded node names from an available ROS 2 or ROS 1 graph."""
    emit(host_introspection.ros_node_list())


@ros_node_app.command("inspect")
def ros_node_inspect(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect one observed ROS node and its interfaces."""
    try:
        emit(host_introspection.ros_node_inspect(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_node_app.command("lifecycle")
def ros_node_lifecycle(name: Annotated[str, typer.Argument()]) -> None:
    """Read one ROS 2 managed node lifecycle state when available."""
    try:
        emit(host_introspection.ros_node_lifecycle(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_topic_app.command("list")
def ros_topic_list() -> None:
    """List bounded topic names and declared types."""
    emit(host_introspection.ros_topic_list())


@ros_topic_app.command("describe")
def ros_topic_describe(name: Annotated[str, typer.Argument()]) -> None:
    """Read publisher, subscriber, and type metadata for one topic."""
    try:
        emit(host_introspection.ros_topic_describe(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_service_app.command("list")
def ros_service_list() -> None:
    """List bounded ROS service names and declared types."""
    emit(host_introspection.ros_service_list())


@ros_service_app.command("describe")
def ros_service_describe(name: Annotated[str, typer.Argument()]) -> None:
    """Read declared type metadata for one ROS service."""
    try:
        emit(host_introspection.ros_service_describe(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_action_app.command("list")
def ros_action_list() -> None:
    """List bounded ROS 2 action names and declared types."""
    emit(host_introspection.ros_action_list())


@ros_action_app.command("describe")
def ros_action_describe(name: Annotated[str, typer.Argument()]) -> None:
    """Read client, server, and type metadata for one ROS 2 action."""
    try:
        emit(host_introspection.ros_action_describe(name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_parameter_app.command("list")
def ros_parameter_list() -> None:
    """List bounded parameter names visible through the active ROS graph."""
    emit(host_introspection.ros_parameter_list())


@ros_parameter_app.command("get")
def ros_parameter_get(
    name: Annotated[str, typer.Argument()],
    node: Annotated[str, typer.Option("--node")],
) -> None:
    """Read one parameter value from an explicit node namespace."""
    try:
        settings = get_settings()
        authorize_data_access(
            "SENSITIVE",
            robot_id="local-host",
            operation="ros.parameter.get",
            policy_path=settings.rolo_invocation_policy,
            audit_path=settings.rolo_invocation_audit_log,
        )
        emit(host_introspection.ros_parameter_get(node, name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_parameter_app.command("describe")
def ros_parameter_describe(
    name: Annotated[str, typer.Argument()],
    node: Annotated[str, typer.Option("--node")],
) -> None:
    """Read one ROS 2 parameter descriptor without changing its value."""
    try:
        emit(host_introspection.ros_parameter_describe(node, name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ros_clock_app.command("status")
def ros_clock_status() -> None:
    """Inspect ROS clock-topic availability without sampling or changing time."""
    emit(host_introspection.ros_clock_status())


@ros_bag_app.command("inspect")
def ros_bag_inspect(path: Annotated[Path, typer.Argument()]) -> None:
    """Read metadata for one explicit ROS 2 or ROS 1 bag path."""
    emit(host_introspection.ros_bag_inspect(path))


def _active_state_graph(robot: str) -> StateGraphBaseline:
    settings = get_settings()
    release_root, release, _, _ = load_current_release(settings.rolo_output_dir, robot)
    return StateGraphBaseline.model_validate_json(
        (release_root / release.state_graph).read_text(encoding="utf-8")
    )


@state_graph_app.command("snapshot")
def state_graph_snapshot(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Read the complete bounded State Graph from the active gated release."""
    try:
        emit(_active_state_graph(robot))
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@state_graph_app.command("query")
def state_graph_query(
    query: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Search active State Graph nodes and edges using one bounded term."""
    try:
        graph = _active_state_graph(robot)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    needle = query.casefold()
    matched_nodes = [
        item
        for item in graph.nodes
        if needle in json.dumps(item, ensure_ascii=False, sort_keys=True).casefold()
    ]
    matched_edges = [
        item
        for item in graph.edges
        if needle in json.dumps(item, ensure_ascii=False, sort_keys=True).casefold()
    ]
    nodes = matched_nodes[:100]
    edges = matched_edges[:100]
    emit(
        {
            "schema_version": "robot-state-graph-query/v1",
            "robot_id": graph.robot_id,
            "discovery_id": graph.discovery_id,
            "query": query,
            "nodes": nodes,
            "edges": edges,
            "truncated": len(matched_nodes) > 100 or len(matched_edges) > 100,
        }
    )
