"""Concise product CLI backed by the canonical robotctl application services."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.lifecycle import run_adapt_start
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.target_ref import LocalTargetRef, parse_target_ref

app = typer.Typer(
    help="Adapt a local or remote robot workspace.",
    no_args_is_help=True,
)


@app.callback()
def product_root() -> None:
    """Rolo product commands."""


@app.command("adapt")
def adapt(
    target: Annotated[
        str,
        typer.Argument(help="Local workspace path or ssh:// target workspace URI"),
    ],
    robot_id: Annotated[
        str,
        typer.Option("--robot", "--robot-id", help="Stable identity for this robot"),
    ],
    urdf: Annotated[
        Path | None,
        typer.Option("--urdf", help="Optional explicit local URDF; never guessed"),
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
        typer.Option("--scratch-root", help="Optional parent for the Agent workspace"),
    ] = None,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", min=1, help="Maximum Adapter Agent time in seconds"),
    ] = None,
    allow_executable: Annotated[
        list[Path] | None,
        typer.Option(
            "--allow-executable",
            help="Local executable permitted for bounded --help evidence; repeatable",
        ),
    ] = None,
    evidence_timeout: Annotated[
        float,
        typer.Option("--evidence-timeout", min=1.0, max=300.0),
    ] = 45.0,
) -> None:
    """Run the shortest safe Adapt journey for TARGET."""
    try:
        target_ref = parse_target_ref(target)
        if not isinstance(target_ref, LocalTargetRef):
            raise ValueError(
                "SSH target bootstrap is not available yet; use the expert "
                "'robotctl adapt start --evidence-mode remote' flow"
            )
        result = run_adapt_start(
            robot_id=robot_id,
            project_root=target_ref.workspace,
            urdf=urdf,
            active_probe=active_probe,
            run_agent=run_agent,
            scratch_root=scratch_root,
            timeout=timeout,
            evidence_mode=EvidenceDeploymentMode.LOCAL,
            allow_executable=allow_executable,
            collector_descriptor=None,
            verification_secret=None,
            ssh_target=None,
            known_hosts=None,
            collector_config=".rolo/config/target-evidence-collector.json",
            evidence_timeout=evidence_timeout,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)
    if result.status == "BLOCKED":
        raise typer.Exit(code=2)
