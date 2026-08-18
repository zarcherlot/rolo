from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import httpx
import typer

from rolo import __version__
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    ImageFrame,
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    ToolDescriptor,
)
from rolo.runtime import create_runtime
from rolo.stages.build.dependencies import CodexDependencyAdapter, CodingAgentDependencyManager
from rolo.stages.build.discovery import (
    ApplicationProbe,
    DiscoveryService,
    HardwareProbe,
    LinuxProbe,
    RosProbe,
    load_latest_report,
)
from rolo.stages.build.enrollment import (
    EnrollmentService,
    list_profiles,
    resolve_profile_root,
)
from rolo.stages.build.executor import CodexBuildExecutor
from rolo.stages.build.inputs import BuildInputs
from rolo.stages.build.models import (
    BuildPlan,
    CodingAgentConfig,
    CodingAgentDependencyReport,
    CodingAgentDependencyStatus,
    CodingAgentResult,
    CodingAgentRun,
)
from rolo.stages.build.service import BuildStageService
from rolo.stages.build.software_inventory import (
    PackageCollectorState,
    PackageInventoryIndex,
    PackageRecord,
    SoftwareInventoryPolicy,
    SoftwareSummary,
    load_software_inventory_policy,
)
from rolo.stages.contracts import PipelineAssessment, StageAssessment, StageName
from rolo.stages.debug.robot_use import create_robot_use_backend
from rolo.stages.pipeline import assess_pipeline, assess_stage

app = typer.Typer(help="Canonical local CLI for the rolo development harness.")
schema_app = typer.Typer(help="Export and inspect canonical JSON schemas.")
robot_use_app = typer.Typer(help="Run robot_use semantic visual supervision.")
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
enroll_app = typer.Typer(help="Inspect the robot identity and available URDF examples.")
build_stage_app = typer.Typer(
    help="Stage 1: register, discover, build canonical CLI adapters and the State Graph."
)
debug_stage_app = typer.Typer(help="Stage 2: diagnose and tune within user constraints.")
test_stage_app = typer.Typer(help="Stage 3: optionally generate and run acceptance tests.")
app.add_typer(build_stage_app, name="build")
app.add_typer(debug_stage_app, name="debug")
app.add_typer(test_stage_app, name="test")
app.add_typer(schema_app, name="schema")
app.add_typer(robot_use_app, name="robot-use")
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
build_stage_app.add_typer(enroll_app, name="enroll")
build_stage_app.add_typer(discover_app, name="discover")
build_stage_app.add_typer(tool_app, name="tool")
debug_stage_app.add_typer(robot_use_app, name="robot-use")


def emit(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def emit_stage_status(stage: StageName, robot: str) -> None:
    settings = get_settings()
    emit(assess_stage(stage, settings.rolo_artifact_dir, robot))


def configured_coding_agent() -> CodingAgentConfig:
    """Return the effective Stage 1 provider configuration without exposing its API key."""
    settings = get_settings()
    return CodingAgentConfig(
        provider=settings.coding_agent_provider.strip() or "codex",
        executor=settings.coding_agent_executor.strip() or "codex",
        base_url=(settings.coding_agent_base_url or "").strip() or None,
        model=(settings.coding_agent_model or "").strip() or None,
        api_key_configured=bool(settings.coding_agent_api_key),
        auto_install=settings.coding_agent_auto_install,
        require_auth=settings.coding_agent_require_auth,
    )


@build_stage_app.command("status")
def build_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show probe, Coding Agent, canonical CLI, and State Graph readiness."""
    emit_stage_status(StageName.BUILD, robot)


@build_stage_app.command("plan")
def build_stage_plan(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Generate the Coding Agent plan from build discovery inputs."""
    settings = get_settings()
    try:
        plan, artifact = BuildStageService(
            ArtifactStore(settings.rolo_artifact_dir),
            coding_agent=configured_coding_agent(),
        ).plan(robot)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"plan": plan.model_dump(mode="json"), "artifact": str(artifact)})


@build_stage_app.command("agent-config")
def build_agent_config() -> None:
    """Show the effective secret-free Coding Agent provider and model selection."""
    emit(configured_coding_agent())


@build_stage_app.command("execute")
def build_stage_execute(
    robot: Annotated[str, typer.Option("--robot")],
    workspace: Annotated[
        Path, typer.Option("--workspace", help="Repository workspace the Coding Agent may edit")
    ] = Path("."),
    timeout: Annotated[
        int | None, typer.Option("--timeout", min=1, help="Maximum execution time in seconds")
    ] = None,
) -> None:
    """Explicitly execute the latest Stage 1 plan with the local Codex CLI."""
    settings = get_settings()
    dependency, _ = CodingAgentDependencyManager(
        ArtifactStore(settings.rolo_artifact_dir)
    ).prepare(
        config=configured_coding_agent(),
        executable=settings.coding_agent_executable,
        auto_install=settings.coding_agent_auto_install,
        require_auth=settings.coding_agent_require_auth,
        install_timeout_s=settings.coding_agent_install_timeout_s,
        install_home=settings.coding_agent_install_home,
        codex_home=settings.coding_agent_home,
    )
    dependency_ready = dependency.status == CodingAgentDependencyStatus.READY or (
        not settings.coding_agent_require_auth
        and dependency.status == CodingAgentDependencyStatus.INSTALLED
    )
    if not dependency_ready:
        emit({"dependency": dependency.model_dump(mode="json")})
        raise typer.Exit(code=1)
    executor = CodexBuildExecutor(
        ArtifactStore(settings.rolo_artifact_dir),
        executable=dependency.executable or settings.coding_agent_executable,
        api_key=settings.coding_agent_api_key,
    )
    try:
        run, artifact = executor.execute(
            robot_id=robot,
            workspace=workspace,
            timeout_s=timeout or settings.coding_agent_timeout_s,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"run": run.model_dump(mode="json"), "artifact": str(artifact)})
    if run.status != "SUCCEEDED":
        raise typer.Exit(code=1)


@build_stage_app.command("agent-prepare")
def build_agent_prepare(
    skip_auth: Annotated[
        bool,
        typer.Option(
            "--skip-auth",
            help="Install and verify the executable without requiring an authenticated session",
        ),
    ] = False,
) -> None:
    """Install and verify the configured Coding Agent dependency."""
    settings = get_settings()
    report, artifact = CodingAgentDependencyManager(
        ArtifactStore(settings.rolo_artifact_dir)
    ).prepare(
        config=configured_coding_agent(),
        executable=settings.coding_agent_executable,
        auto_install=settings.coding_agent_auto_install,
        require_auth=settings.coding_agent_require_auth and not skip_auth,
        install_timeout_s=settings.coding_agent_install_timeout_s,
        install_home=settings.coding_agent_install_home,
        codex_home=settings.coding_agent_home,
    )
    emit({"dependency": report.model_dump(mode="json"), "artifact": str(artifact)})
    accepted = {CodingAgentDependencyStatus.READY}
    if skip_auth:
        accepted.add(CodingAgentDependencyStatus.INSTALLED)
    if report.status not in accepted:
        raise typer.Exit(code=1)


@debug_stage_app.command("status")
def debug_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show the closed-loop debug and tuning gate."""
    emit_stage_status(StageName.DEBUG, robot)


@test_stage_app.command("status")
def test_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show optional autonomous acceptance-test readiness."""
    emit_stage_status(StageName.TEST, robot)


@app.command("pipeline-status")
def pipeline_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show all three lifecycle stages for one robot."""
    settings = get_settings()
    emit(assess_pipeline(settings.rolo_artifact_dir, robot))


def _doctor_report() -> dict[str, object]:
    settings = get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    robot_manifests = (
        sorted(settings.robot_config_dir.glob("*.yaml"))
        if settings.robot_config_dir.is_dir()
        else []
    )
    robots = 0
    enrollment_status = "NOT_ENROLLED"
    if robot_manifests:
        try:
            runtime = create_runtime(settings)
            robots = len(runtime.registry)
            enrolled = runtime.registry.list()
            states = {
                str(robot.features.get("enrollment", {}).get("urdf_status", "REGISTERED"))
                for robot in enrolled
            }
            enrollment_status = states.pop() if len(states) == 1 else "REGISTERED"
        except Exception as exc:  # doctor must aggregate malformed robot configuration
            errors.append(str(exc))
            enrollment_status = "INVALID"
    else:
        warnings.append(
            "No robot is registered; run 'uv run robotctl init --robot-id ...'"
        )

    try:
        backend = create_robot_use_backend(settings).name
    except Exception as exc:  # doctor must aggregate backend configuration failures
        errors.append(str(exc))
        backend = settings.robot_use_backend

    install_home = settings.coding_agent_install_home or Path.home()
    codex_executable = CodexDependencyAdapter().resolve(
        settings.coding_agent_executable, install_home
    )
    optional_tools = {
        "git": shutil.which("git"),
        "codex": str(codex_executable) if codex_executable else None,
        "docker": shutil.which("docker"),
        "ros2": shutil.which("ros2"),
        "ffmpeg": shutil.which("ffmpeg"),
    }
    for name in ("docker", "ros2", "ffmpeg"):
        if not optional_tools[name]:
            warnings.append(f"{name} is optional for mock mode and is not installed")
    if not optional_tools["codex"]:
        warnings.append("codex is not installed; build agent-prepare will attempt installation")

    if backend == "openai":
        if not settings.openai_api_key:
            errors.append("OPENAI_API_KEY is required when ROBOT_USE_BACKEND=openai")
        if not settings.openai_model:
            errors.append("OPENAI_MODEL is required when ROBOT_USE_BACKEND=openai")
    elif not settings.openai_api_key:
        warnings.append("OPENAI_API_KEY is not set; robot_use will remain on the mock backend")

    coding_agent = configured_coding_agent()

    return {
        "status": "READY" if not errors else "NOT_READY",
        "version": __version__,
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "config_dir": str(settings.rolo_config_dir),
        "artifact_dir": str(settings.rolo_artifact_dir),
        "robots": robots,
        "enrollment_status": enrollment_status,
        "robot_use_backend": backend,
        "coding_agent": coding_agent.model_dump(mode="json"),
        "local_visual_detection": False,
        "optional_tools": optional_tools,
        "warnings": warnings,
        "errors": errors,
    }


@app.command()
def doctor() -> None:
    """Check local prerequisites and canonical configuration."""
    report = _doctor_report()
    emit(report)
    if report["status"] != "READY":
        raise typer.Exit(code=1)


def _run_engineering_tests(workspace: Path) -> dict[str, object]:
    tests_root = workspace / "tests"
    if not tests_root.is_dir():
        return {
            "status": "FAILED",
            "exit_code": None,
            "summary": f"engineering tests directory does not exist: {tests_root}",
        }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=workspace,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "exit_code": None, "summary": "pytest timed out after 600s"}
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    return {
        "status": "PASSED" if completed.returncode == 0 else "FAILED",
        "exit_code": completed.returncode,
        "summary": output[-4000:],
    }


@app.command("init")
def initialize(
    robot_id: Annotated[str, typer.Option("--robot-id", help="User-assigned robot identity")],
) -> None:
    """Register identity, validate the environment and run repository engineering tests."""
    settings = get_settings()
    try:
        enrollment = EnrollmentService(config_root=settings.rolo_config_dir).enroll(
            robot_id=robot_id,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    doctor_result = _doctor_report()
    try:
        registered_robots = [
            robot.model_dump(mode="json") for robot in create_runtime(settings).registry.list()
        ]
    except Exception as exc:
        registered_robots = []
        doctor_result["status"] = "NOT_READY"
        doctor_result.setdefault("errors", []).append(str(exc))  # type: ignore[union-attr]
    workspace = Path(__file__).resolve().parents[2]
    engineering_tests = _run_engineering_tests(workspace)
    ready = bool(
        doctor_result["status"] == "READY"
        and engineering_tests["status"] == "PASSED"
        and len(registered_robots) == 1
        and registered_robots[0]["robot_id"] == robot_id
    )
    emit(
        {
            "status": "READY_FOR_DISCOVERY" if ready else "NOT_READY",
            "robot_id": robot_id,
            "registration": {
                "status": enrollment.status,
                "capability_path": str(enrollment.capability_path),
            },
            "doctor": doctor_result,
            "robots": registered_robots,
            "engineering_tests": engineering_tests,
            "next_step": (
                f'uv run robotctl discover run --robot "{robot_id}" '
                "--urdf /path/to/your_robot.urdf "
                "--source-root /path/to/robot-application"
            ),
            "motion_safety_status": "UNAPPROVED",
        }
    )
    if not ready:
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
        "rolo.api:app",
        host=host or settings.rolo_host,
        port=port or settings.rolo_port,
        reload=reload,
    )


@app.command()
def bootstrap_agentd(
    robot: Annotated[str, typer.Option("--robot")],
    host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8100,
) -> None:
    """Start the minimal non-motion daemon required before discovery."""
    import uvicorn

    from rolo.agentd import create_bootstrap_agentd_app

    uvicorn.run(create_bootstrap_agentd_app(robot), host=host, port=port)


@app.command()
def bootstrap_wait(
    robot: Annotated[str, typer.Option("--robot")],
    url: Annotated[str, typer.Option(help="Bootstrap agentd base URL")],
    timeout: Annotated[float, typer.Option(min=0.1, help="Maximum wait in seconds")] = 15.0,
) -> None:
    """Wait until the expected robot's bootstrap daemon is ready for discovery."""
    deadline = time.monotonic() + timeout
    health_url = f"{url.rstrip('/')}/health"
    last_error = "bootstrap agentd did not respond"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(health_url, timeout=min(1.0, timeout))
            payload = response.json()
            if (
                response.status_code == 200
                and payload.get("robot_id") == robot
                and payload.get("phase") == "BOOTSTRAP_READY"
            ):
                emit({"status": "READY", "robot_id": robot, "url": url})
                return
            last_error = f"unexpected bootstrap health response: {response.status_code} {payload}"
        except (httpx.HTTPError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.2)
    emit({"status": "NOT_READY", "robot_id": robot, "url": url, "error": last_error})
    raise typer.Exit(code=1)


@app.command()
def agentd(
    robot: Annotated[str, typer.Option("--robot")],
    host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8101,
) -> None:
    """Start the full robot-agentd after discovery has completed."""
    import uvicorn

    from rolo.agentd import create_agentd_app

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
        BuildInputs,
        BuildPlan,
        CodingAgentDependencyReport,
        CodingAgentResult,
        CodingAgentRun,
        StageAssessment,
        PipelineAssessment,
        PackageRecord,
        PackageCollectorState,
        PackageInventoryIndex,
        SoftwareInventoryPolicy,
        SoftwareSummary,
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
    """List URDF format examples available for discovery."""
    settings = get_settings()
    resolved = resolve_profile_root(settings.rolo_config_dir, profile_root)
    emit({"profile_root": str(resolved), "profiles": list_profiles(resolved)})


@enroll_app.command("show")
def enrollment_show() -> None:
    """Show the robot identity currently owned by this installed instance."""
    robots = create_runtime().registry.list()
    emit([robot.model_dump(mode="json") for robot in robots])


@discover_app.command("run")
def discovery_run(
    robot: Annotated[str, typer.Option("--robot")],
    urdf: Annotated[Path, typer.Option("--urdf", help="URDF path to load and analyze")],
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
    try:
        inventory_policy = load_software_inventory_policy(
            runtime.settings.rolo_discovery_policy_path
        )
        report, artifact = DiscoveryService(
            runtime.robot_use.artifacts,
            inventory_policy=inventory_policy,
        ).run(
            robot=capability, urdf_path=urdf, source_roots=roots
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if full:
        emit(report)
        if report.status == DiscoveryStatus.FAILED:
            raise typer.Exit(code=1)
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
            "software_packages": report.software_summary.get("package_count", 0),
            "software_inventory_complete": report.software_summary.get("complete", False),
            "artifact": str(artifact),
        }
    )
    if report.status == DiscoveryStatus.FAILED:
        raise typer.Exit(code=1)


@discover_app.command("show")
def discovery_show(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show the latest persisted discovery report."""
    settings = get_settings()
    try:
        emit(load_latest_report(settings.rolo_artifact_dir, robot))
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
        report = load_latest_report(settings.rolo_artifact_dir, robot)
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
        report = load_latest_report(settings.rolo_artifact_dir, robot)
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
    now = datetime.now(timezone.utc)
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
