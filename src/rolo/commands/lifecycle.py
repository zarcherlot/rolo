from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.runtime import create_runtime
from rolo.stages.adapt.service import (
    AdaptRunService,
    coding_agent_config,
)
from rolo.stages.contracts import StageName
from rolo.stages.pipeline import assess_pipeline, assess_stage

adapt_stage_app = typer.Typer(
    help="Stage 1: discover, adapt, conform, and publish the canonical control surface."
)
diagnose_stage_app = typer.Typer(help="Stage 2: diagnose and tune within user constraints.")
verify_stage_app = typer.Typer(help="Stage 3: optionally verify acceptance and regression.")
enroll_app = typer.Typer(help="Inspect the robot identity owned by this installation.")
adapt_stage_app.add_typer(enroll_app, name="enroll")


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
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"run": summary.model_dump(mode="json"), "artifact": str(artifact)})


@adapt_stage_app.command("agent-config")
def adapt_agent_config() -> None:
    """Show the effective secret-free Adapter Agent provider and model selection."""
    emit(coding_agent_config(get_settings()))


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
