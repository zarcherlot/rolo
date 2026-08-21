from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.discovery import configured_discovery_service
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.runtime import create_runtime
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.journey import AdaptJourneyService, detect_project_evidence
from rolo.stages.adapt.service import (
    AdaptRunService,
    coding_agent_config,
)
from rolo.stages.adapt.slice_observability import build_slice_stability_report
from rolo.stages.contracts import StageName
from rolo.stages.pipeline import assess_pipeline, assess_stage

adapt_stage_app = typer.Typer(
    help="Stage 1: discover, adapt, conform, and publish the canonical control surface."
)
diagnose_stage_app = typer.Typer(help="Stage 2: diagnose and tune within user constraints.")
verify_stage_app = typer.Typer(help="Stage 3: optionally verify acceptance and regression.")
enroll_app = typer.Typer(help="Inspect the robot identity owned by this installation.")
adapt_stage_app.add_typer(enroll_app, name="enroll")


@adapt_stage_app.command("start")
def adapt_stage_start(
    robot_id: Annotated[
        str,
        typer.Option("--robot-id", "--robot", help="Stable identity for this robot"),
    ],
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Robot application/workspace root used to find build, install, docs, and launch",
        ),
    ] = None,
    urdf: Annotated[
        Path | None,
        typer.Option("--urdf", help="Optional explicit URDF; never guessed when omitted"),
    ] = None,
    active_probe: Annotated[
        ActiveProbeMode,
        typer.Option("--active-probe", help="none, help, or runtime-readonly"),
    ] = ActiveProbeMode.RUNTIME_READONLY,
    run_agent: Annotated[
        bool,
        typer.Option(
            "--run-agent/--discover-only",
            help="Continue through Adapter Agent, independent gate, and release",
        ),
    ] = True,
    scratch_root: Annotated[
        Path | None,
        typer.Option(
            "--scratch-root",
            help="Optional parent for the automatically deleted Agent workspace",
        ),
    ] = None,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", min=1, help="Maximum Adapter Agent time in seconds"),
    ] = None,
) -> None:
    """Run the shortest safe path from a robot project to an Adapt release."""
    settings = get_settings()
    try:
        evidence = detect_project_evidence(project_root or Path.cwd())
        result = AdaptJourneyService(
            settings,
            configured_discovery_service(
                settings,
                ArtifactStore(settings.rolo_artifact_dir),
            ),
        ).start(
            robot_id=robot_id,
            evidence=evidence,
            urdf_path=urdf,
            active_probe=active_probe,
            run_agent=run_agent,
            scratch_root=scratch_root,
            timeout_s=timeout or settings.coding_agent_timeout_s,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)
    if result.status == "BLOCKED":
        raise typer.Exit(code=2)


def emit_stage_status(stage: StageName, robot: str) -> None:
    settings = get_settings()
    emit(assess_stage(stage, settings.rolo_artifact_dir, robot))


@adapt_stage_app.command("status")
def adapt_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show discovery, Adapter Agent, conformance, and handoff readiness."""
    emit_stage_status(StageName.ADAPT, robot)


@adapt_stage_app.command("run")
def adapt_stage_run(
    robot: Annotated[str, typer.Option("--robot")],
    scratch_root: Annotated[
        Path | None,
        typer.Option(
            "--scratch-root",
            help="Optional parent for an automatically deleted Agent workspace outside rolo",
        ),
    ] = None,
    timeout: Annotated[
        int | None, typer.Option("--timeout", min=1, help="Maximum Agent time in seconds")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the derived plan without starting the Agent")
    ] = False,
    slice_canary: Annotated[
        bool,
        typer.Option(
            "--slice-canary",
            help=(
                "Canary the bounded Slice for this run's Agent context only; "
                "Bundle/release authority remains unchanged"
            ),
        ),
    ] = False,
) -> None:
    """Plan, execute, freeze outputs, independently gate, and publish one Adapt run."""
    settings = get_settings()
    service = AdaptRunService(ArtifactStore(settings.rolo_artifact_dir), settings)
    try:
        if dry_run:
            emit(service.dry_run(robot))
            return
        summary, artifact = service.run(
            robot_id=robot,
            scratch_root=scratch_root,
            timeout_s=timeout or settings.coding_agent_timeout_s,
            slice_canary=slice_canary,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"run": summary.model_dump(mode="json"), "artifact": str(artifact)})


@adapt_stage_app.command("agent-config")
def adapt_agent_config() -> None:
    """Show the effective secret-free Adapter Agent provider and model selection."""
    emit(coding_agent_config(get_settings()))


@adapt_stage_app.command("slice-observability")
def adapt_slice_observability(
    robot: Annotated[str, typer.Option("--robot")],
    max_runs: Annotated[int, typer.Option("--max-runs", min=1, max=500)] = 50,
    min_successful_canary_runs: Annotated[
        int,
        typer.Option("--min-successful-canary-runs", min=1, max=500),
    ] = 10,
) -> None:
    """Read Shadow/Canary stability metrics without changing activation settings."""
    settings = get_settings()
    try:
        report = build_slice_stability_report(
            settings.rolo_artifact_dir,
            robot,
            max_runs=max_runs,
            min_successful_canary_runs=min_successful_canary_runs,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(report)


@diagnose_stage_app.command("status")
def diagnose_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show the closed-loop diagnosis and tuning gate."""
    emit_stage_status(StageName.DIAGNOSE, robot)


@verify_stage_app.command("status")
def verify_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show optional autonomous verification readiness."""
    emit_stage_status(StageName.VERIFY, robot)


@enroll_app.command("show")
def enrollment_show() -> None:
    """Show the robot identity currently owned by this installed instance."""
    robots = create_runtime().registry.list()
    emit([robot.model_dump(mode="json") for robot in robots])


def register_lifecycle_commands(root: typer.Typer) -> None:
    root.add_typer(adapt_stage_app, name="adapt")
    root.add_typer(diagnose_stage_app, name="diagnose")
    root.add_typer(verify_stage_app, name="verify")

    @root.command("pipeline-status")
    def pipeline_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
        """Show all three lifecycle stages for one robot."""
        settings = get_settings()
        emit(assess_pipeline(settings.rolo_artifact_dir, robot))
