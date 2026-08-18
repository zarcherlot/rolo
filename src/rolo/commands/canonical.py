from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo import host_introspection
from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.stages.adapt.discovery import (
    ApplicationProbe,
    HardwareProbe,
    RosProbe,
    load_latest_report,
)
from rolo.stages.adapt.models import ToolCatalog

tool_app = typer.Typer(help="Inspect the generated canonical tool catalog.")
hw_app = typer.Typer(help="Canonical hardware-layer tools.")
hw_inventory_app = typer.Typer(help="Hardware inventory operations.")
linux_app = typer.Typer(help="Canonical Linux-layer tools.")
linux_host_app = typer.Typer(help="Linux host operations.")
linux_service_app = typer.Typer(help="Read-only service discovery operations.")
linux_container_app = typer.Typer(help="Read-only local container discovery operations.")
linux_schedule_app = typer.Typer(help="Read-only scheduled-task discovery operations.")
linux_process_app = typer.Typer(help="Read-only process discovery operations.")
linux_binary_app = typer.Typer(help="Static binary inspection operations.")
linux_cli_app = typer.Typer(help="Bounded CLI self-description probes.")
linux_config_app = typer.Typer(help="Configuration-location operations.")
linux_network_app = typer.Typer(help="Read-only network discovery operations.")
middleware_app = typer.Typer(help="Canonical middleware discovery tools.")
ros_app = typer.Typer(help="Canonical ROS-layer tools.")
ros_graph_app = typer.Typer(help="ROS graph operations.")
ros_node_app = typer.Typer(help="ROS node inspection operations.")
application_app = typer.Typer(help="Canonical application-layer tools.")
app_robot_cli = typer.Typer(help="Application robot discovery operations.")

hw_app.add_typer(hw_inventory_app, name="inventory")
linux_app.add_typer(linux_host_app, name="host")
linux_app.add_typer(linux_service_app, name="service")
linux_app.add_typer(linux_container_app, name="container")
linux_app.add_typer(linux_schedule_app, name="schedule")
linux_app.add_typer(linux_process_app, name="process")
linux_app.add_typer(linux_binary_app, name="binary")
linux_app.add_typer(linux_cli_app, name="cli")
linux_app.add_typer(linux_config_app, name="config")
linux_app.add_typer(linux_network_app, name="network")
ros_app.add_typer(ros_graph_app, name="graph")
ros_app.add_typer(ros_node_app, name="node")
application_app.add_typer(app_robot_cli, name="robot")


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


@linux_binary_app.command("describe")
def linux_binary_describe(path: Annotated[Path, typer.Argument()]) -> None:
    """Describe a binary statically without invoking its operational interface."""
    emit(host_introspection.binary_describe(path))


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


@linux_network_app.command("listeners")
def linux_network_listeners() -> None:
    """List bounded local listening sockets and owning processes when available."""
    emit(host_introspection.network_listeners())


@middleware_app.command("inspect")
def middleware_inspect() -> None:
    """Identify ROS and non-ROS middleware candidates from host evidence."""
    emit(host_introspection.middleware_inspect())


@ros_graph_app.command("snapshot")
def ros_graph_snapshot() -> None:
    """Implement canonical `ros graph snapshot` using bounded ROS 2 introspection."""
    emit(RosProbe().run())


@ros_node_app.command("status")
def ros_node_status(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect one existing ROS 1 or ROS 2 node without changing graph state."""
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
    """List canonical tools produced by the latest discovery run."""
    settings = get_settings()
    try:
        report = load_latest_report(settings.rolo_artifact_dir, robot)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    tools = report.tool_catalog
    if layer:
        tools = [tool for tool in tools if tool.layer == layer]
    emit(
        ToolCatalog(
            robot_id=robot,
            discovery_id=report.discovery_id,
            tools=tools,
        )
    )


@tool_app.command("schema")
def tool_schema(
    operation: Annotated[str, typer.Argument(help="Canonical operation, e.g. hw.inventory.scan")],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show the generated input/output schema for one canonical operation."""
    settings = get_settings()
    try:
        report = load_latest_report(settings.rolo_artifact_dir, robot)
        descriptor = next(tool for tool in report.tool_catalog if tool.operation == operation)
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
