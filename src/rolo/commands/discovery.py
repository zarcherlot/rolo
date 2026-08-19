from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.core.models import DiscoveryStatus
from rolo.runtime import create_runtime
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService, load_latest_report
from rolo.stages.adapt.wiki import OpenAIWikiNarrativePolisher
from rolo.stages.artifact_paths import resolve_artifact_ref
from rolo.stages.discovery_manifest import load_and_verify_discovery_manifest

discover_app = typer.Typer(help="Discover hardware, Linux, ROS and application capabilities.")


@discover_app.command("run")
def discovery_run(
    robot: Annotated[str, typer.Option("--robot")],
    urdf: Annotated[
        Path | None,
        typer.Option(
            "--urdf",
            help="Optional URDF path; omit to continue with registered/default hardware context",
        ),
    ] = None,
    source_root: Annotated[
        list[Path] | None,
        typer.Option(
            "--source-root",
            help="Supporting application source root; repeat for bounded gap analysis",
        ),
    ] = None,
    build_root: Annotated[
        list[Path] | None,
        typer.Option("--build-root", help="Primary build-artifact root; repeat as needed"),
    ] = None,
    install_root: Annotated[
        list[Path] | None,
        typer.Option(
            "--install-root", help="Primary installed artifact/package root; repeat as needed"
        ),
    ] = None,
    executable: Annotated[
        list[Path] | None,
        typer.Option("--executable", help="Primary explicit executable; repeat as needed"),
    ] = None,
    doc_root: Annotated[
        list[Path] | None,
        typer.Option("--doc-root", help="Primary documentation root; repeat as needed"),
    ] = None,
    launch_root: Annotated[
        list[Path] | None,
        typer.Option("--launch-root", help="Launch/configuration root; repeat as needed"),
    ] = None,
    active_probe: Annotated[
        ActiveProbeMode,
        typer.Option("--active-probe", help="none, help, or runtime-readonly"),
    ] = ActiveProbeMode.NONE,
    full: Annotated[bool, typer.Option("--full", help="Print the complete report")] = False,
) -> None:
    """Run all safe discovery probes and persist a versioned report."""
    runtime = create_runtime()
    try:
        capability = runtime.registry.get(robot)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        active_inputs = ActiveDiscoveryInputs(
            source_roots=source_root or [],
            build_roots=build_root or [],
            install_roots=install_root or [],
            executables=executable or [],
            document_roots=doc_root or [],
            launch_roots=launch_root or [],
            active_probe=active_probe,
        )
        wiki_model = runtime.settings.wiki_polish_model or runtime.settings.openai_model
        wiki_polisher = (
            OpenAIWikiNarrativePolisher(
                api_key=runtime.settings.openai_api_key or "",
                model=wiki_model or "",
                timeout_s=runtime.settings.wiki_polish_timeout_s,
            )
            if runtime.settings.wiki_polish_enabled
            and runtime.settings.openai_api_key
            and wiki_model
            else None
        )
        report, artifact = DiscoveryService(
            runtime.robot_use.artifacts,
            wiki_polisher=wiki_polisher,
        ).run(
            robot=capability,
            urdf_path=urdf,
            active_inputs=active_inputs,
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
            "operation_candidates": len(report.operation_candidates),
            "dependency_resolution_complete": (
                report.software_summary.get("status") == "SUCCEEDED"
            ),
            "direct_dependencies": report.software_summary.get("direct_dependency_count", 0),
            "missing_dependencies": report.software_summary.get("missing_dependency_count", 0),
            "conflicting_dependencies": report.software_summary.get(
                "conflicting_dependency_count", 0
            ),
            "dependency_report": report.dependency_report_ref,
            "discovery_mode": report.discovery_mode,
            "active_discovery_report": report.active_discovery_report_ref,
            "wiki": report.review_ref,
            "next": f"robotctl adapt discover review --robot {report.robot_id}",
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
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@discover_app.command("review")
def discovery_review(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Print the editable whole-stack robot Wiki for the latest discovery run."""
    settings = get_settings()
    try:
        report = load_latest_report(settings.rolo_artifact_dir, robot)
        load_and_verify_discovery_manifest(settings.rolo_artifact_dir, robot, report.discovery_id)
        review_path = resolve_artifact_ref(settings.rolo_artifact_dir, report.review_ref)
        typer.echo(review_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
