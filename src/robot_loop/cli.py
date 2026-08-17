from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from robot_loop import __version__
from robot_loop.bundle import build_compatible_bundle
from robot_loop.config import get_settings
from robot_loop.discovery import (
    ApplicationProbe,
    DiscoveryService,
    HardwareProbe,
    LinuxProbe,
    RosProbe,
    load_latest_report,
)
from robot_loop.enrollment import EnrollmentService, list_profiles, resolve_profile_root
from robot_loop.models import (
    DiscoveryReport,
    ImageFrame,
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    ToolDescriptor,
)
from robot_loop.runtime import create_runtime

app = typer.Typer(help="Canonical local CLI for the Robot Loop development harness.")
schema_app = typer.Typer(help="Export and inspect canonical JSON schemas.")
robot_use_app = typer.Typer(help="Run robot_use semantic visual supervision.")
bundle_app = typer.Typer(help="Build independently installable per-robot bundles.")
discover_app = typer.Typer(help="Discover hardware, Linux, ROS and application capabilities.")
tool_app = typer.Typer(help="Inspect the generated canonical tool catalog.")
hw_app = typer.Typer(help="Canonical hardware-layer tools.")
hw_inventory_app = typer.Typer(help="Hardware inventory operations.")
linux_app = typer.Typer(help="Canonical Linux-layer tools.")
linux_host_app = typer.Typer(help="Linux host operations.")
ros_app = typer.Typer(help="Canonical ROS-layer tools.")
ros_graph_app = typer.Typer(help="ROS graph operations.")
application_app = typer.Typer(help="Canonical application-layer tools.")
app_robot_cli = typer.Typer(help="Application robot discovery operations.")
enroll_app = typer.Typer(help="Enroll an arbitrary robot identity from a capability profile.")
app.add_typer(schema_app, name="schema")
app.add_typer(robot_use_app, name="robot-use")
app.add_typer(bundle_app, name="bundle")
app.add_typer(discover_app, name="discover")
app.add_typer(tool_app, name="tool")
app.add_typer(hw_app, name="hw")
hw_app.add_typer(hw_inventory_app, name="inventory")
app.add_typer(linux_app, name="linux")
linux_app.add_typer(linux_host_app, name="host")
app.add_typer(ros_app, name="ros")
ros_app.add_typer(ros_graph_app, name="graph")
app.add_typer(application_app, name="app")
application_app.add_typer(app_robot_cli, name="robot")
app.add_typer(enroll_app, name="enroll")


def emit(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


@app.command()
def doctor() -> None:
    """Check local prerequisites and canonical configuration."""
    settings = get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        runtime = create_runtime(settings)
        robots = len(runtime.registry)
        backend = runtime.robot_use_backend.name
    except Exception as exc:  # doctor must aggregate configuration failures
        errors.append(str(exc))
        robots = 0
        backend = settings.robot_use_backend

    optional_tools = {
        "git": shutil.which("git"),
        "docker": shutil.which("docker"),
        "ros2": shutil.which("ros2"),
        "ffmpeg": shutil.which("ffmpeg"),
    }
    for name in ("docker", "ros2", "ffmpeg"):
        if not optional_tools[name]:
            warnings.append(f"{name} is optional for mock mode and is not installed")

    if backend == "openai":
        if not settings.openai_api_key:
            errors.append("OPENAI_API_KEY is required when ROBOT_USE_BACKEND=openai")
        if not settings.openai_model:
            errors.append("OPENAI_MODEL is required when ROBOT_USE_BACKEND=openai")
    elif not settings.openai_api_key:
        warnings.append("OPENAI_API_KEY is not set; robot_use will remain on the mock backend")

    emit(
        {
            "status": "READY" if not errors else "NOT_READY",
            "version": __version__,
            "python": {"version": sys.version.split()[0], "executable": sys.executable},
            "config_dir": str(settings.robot_loop_config_dir),
            "artifact_dir": str(settings.robot_loop_artifact_dir),
            "robots": robots,
            "robot_use_backend": backend,
            "local_visual_detection": False,
            "optional_tools": optional_tools,
            "warnings": warnings,
            "errors": errors,
        }
    )
    if errors:
        raise typer.Exit(code=1)


@app.command()
def robots() -> None:
    """List normalized robot capability manifests."""
    emit([robot.model_dump(mode="json") for robot in create_runtime().registry.list()])


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind host")] = None,
    port: Annotated[int | None, typer.Option(help="Bind port")] = None,
    reload: Annotated[bool, typer.Option(help="Enable development reload")] = False,
) -> None:
    """Start the local control-plane API."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "robot_loop.api:app",
        host=host or settings.robot_loop_host,
        port=port or settings.robot_loop_port,
        reload=reload,
    )


@app.command()
def agentd(
    robot: Annotated[str, typer.Option("--robot")],
    host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8101,
) -> None:
    """Start a local mock robot-agentd for one configured robot."""
    import uvicorn

    from robot_loop.agentd import create_agentd_app

    uvicorn.run(create_agentd_app(robot), host=host, port=port)


@schema_app.command("export")
def export_schemas(
    output: Annotated[Path, typer.Option(help="Schema output directory")] = Path("schemas"),
) -> None:
    """Export the initial canonical JSON schemas."""
    output.mkdir(parents=True, exist_ok=True)
    models = [
        RobotCapability,
        RobotUseRequest,
        RobotUseSupervision,
        DiscoveryReport,
        ToolDescriptor,
    ]
    written: list[str] = []
    for model in models:
        path = output / f"{model.__name__}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(str(path))
    emit({"status": "SUCCEEDED", "written": written})


@enroll_app.command("profiles")
def enrollment_profiles(
    profile_root: Annotated[Path | None, typer.Option("--profile-root")] = None,
) -> None:
    """List robot structure/sensor profiles available for enrollment."""
    settings = get_settings()
    resolved = resolve_profile_root(settings.robot_loop_config_dir, profile_root)
    emit({"profile_root": str(resolved), "profiles": list_profiles(resolved)})


@enroll_app.command("init")
def enrollment_init(
    robot_id: Annotated[str, typer.Option("--robot-id")],
    profile: Annotated[str, typer.Option("--profile")],
    confirm_safety_profile: Annotated[
        bool,
        typer.Option(
            "--confirm-safety-profile",
            help="Confirm that geometry and hard motion bounds match the physical robot",
        ),
    ] = False,
    profile_root: Annotated[Path | None, typer.Option("--profile-root")] = None,
) -> None:
    """Create the only active robot manifest for this installed instance."""
    settings = get_settings()
    resolved = resolve_profile_root(settings.robot_loop_config_dir, profile_root)
    service = EnrollmentService(config_root=settings.robot_loop_config_dir, profile_root=resolved)
    try:
        result = service.enroll(
            robot_id=robot_id,
            profile_id=profile,
            safety_profile_confirmed=confirm_safety_profile,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": result.status,
            "robot_id": result.robot_id,
            "profile_id": result.profile_id,
            "capability_path": str(result.capability_path),
            "capability_sha256": result.capability_sha256,
        }
    )


@enroll_app.command("show")
def enrollment_show() -> None:
    """Show the robot identity currently owned by this installed instance."""
    robots = create_runtime().registry.list()
    emit([robot.model_dump(mode="json") for robot in robots])


@discover_app.command("run")
def discovery_run(
    robot: Annotated[str, typer.Option("--robot")],
    source_root: Annotated[
        list[Path] | None,
        typer.Option("--source-root", help="Application source root; repeat for overlays"),
    ] = None,
    full: Annotated[bool, typer.Option("--full", help="Print the complete report")] = False,
) -> None:
    """Run all safe discovery probes and persist a versioned report."""
    runtime = create_runtime()
    try:
        capability = runtime.registry.get(robot)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    roots = source_root or [Path.cwd()]
    report, artifact = DiscoveryService(runtime.robot_use.artifacts).run(
        robot=capability, source_roots=roots
    )
    if full:
        emit(report)
        return
    emit(
        {
            "schema_version": report.schema_version,
            "discovery_id": report.discovery_id,
            "robot_id": report.robot_id,
            "status": report.status,
            "probe_status": {name: probe.status for name, probe in report.probes.items()},
            "semantic_bindings": len(report.semantic_bindings),
            "tools": len(report.tool_catalog),
            "artifact": str(artifact),
        }
    )


@discover_app.command("show")
def discovery_show(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show the latest persisted discovery report."""
    settings = get_settings()
    try:
        emit(load_latest_report(settings.robot_loop_artifact_dir, robot))
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc


@hw_inventory_app.command("scan")
def hw_inventory_scan() -> None:
    """Implement canonical `hw inventory scan` with read-only host probes."""
    emit(HardwareProbe().run())


@linux_host_app.command("inspect")
def linux_host_inspect() -> None:
    """Implement canonical `linux host inspect`."""
    result = LinuxProbe().run()
    emit(
        {
            "layer": result.layer,
            "status": result.status,
            "host": result.data["host"],
            "executables": result.data["executables"],
            "warnings": result.warnings,
        }
    )


@ros_graph_app.command("snapshot")
def ros_graph_snapshot() -> None:
    """Implement canonical `ros graph snapshot` using bounded ROS 2 introspection."""
    emit(RosProbe().run())


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
        report = load_latest_report(settings.robot_loop_artifact_dir, robot)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    tools = report.tool_catalog
    if layer:
        tools = [tool for tool in tools if tool.layer == layer]
    emit(
        {
            "schema_version": "robot-tool-catalog/v1",
            "robot_id": robot,
            "discovery_id": report.discovery_id,
            "tools": [tool.model_dump(mode="json") for tool in tools],
        }
    )


@tool_app.command("schema")
def tool_schema(
    operation: Annotated[str, typer.Argument(help="Canonical operation, e.g. hw.inventory.scan")],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show the generated input/output schema for one canonical operation."""
    settings = get_settings()
    try:
        report = load_latest_report(settings.robot_loop_artifact_dir, robot)
        descriptor = next(tool for tool in report.tool_catalog if tool.operation == operation)
    except FileNotFoundError as exc:
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


@bundle_app.command("build")
def bundle_build(
    wheel: Annotated[Path, typer.Option("--wheel", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", help="Bundle output directory")] = Path(
        "dist/release"
    ),
) -> None:
    """Build one checksummed ARM64 archive with no compiled-in robot identity."""
    try:
        result = build_compatible_bundle(wheel=wheel, output_dir=output)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "SUCCEEDED",
            "bundle": str(result.bundle),
            "profile_ids": result.profile_ids,
            "target_arch": result.target_arch,
            "version": result.version,
            "sha256": result.sha256,
        }
    )


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@robot_use_app.command("poll")
def robot_use_poll(
    robot: Annotated[str, typer.Option("--robot")],
    image: Annotated[list[Path], typer.Option("--image", exists=True, dir_okay=False)],
    execution_id: Annotated[str, typer.Option()] = "local-execution",
    task: Annotated[str, typer.Option()] = "Observe whether robot behavior matches the task",
    commanded_speed_mps: Annotated[float, typer.Option()] = 0.0,
    progress_delta: Annotated[float, typer.Option()] = 1.0,
) -> None:
    """Submit a timestamped storyboard to the configured robot_use backend."""
    if not image:
        raise typer.BadParameter("At least one --image is required")
    runtime = create_runtime()
    now = datetime.now(UTC)
    request = RobotUseRequest(
        request_id=f"local-{int(now.timestamp() * 1000)}",
        robot_id=robot,
        execution_id=execution_id,
        window_start=now - timedelta(seconds=max(len(image) - 1, 1)),
        window_end=now,
        frames=[
            ImageFrame(
                timestamp=now - timedelta(seconds=len(image) - index - 1),
                image_url=image_to_data_url(path),
            )
            for index, path in enumerate(image)
        ],
        task_contract={"intent": task},
        telemetry_summary={
            "commanded_speed_mps": commanded_speed_mps,
            "progress_delta": progress_delta,
        },
    )
    result = asyncio.run(runtime.robot_use.poll(request))
    emit(result)


if __name__ == "__main__":
    app()
