from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings, get_settings
from rolo.core.models import DiscoveryStatus
from rolo.runtime import create_runtime
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService, load_latest_report
from rolo.stages.adapt.heuristic_discovery import (
    CodexDiscoveryPlanningProvider,
    HeuristicAdaptMode,
    HeuristicDiscoveryOrchestrator,
)
from rolo.stages.adapt.proposal_orchestration import CodexOperationMappingProvider
from rolo.stages.adapt.skill_resources import resolve_skill_path
from rolo.stages.adapt.wiki import OpenAIWikiNarrativePolisher
from rolo.stages.adapt.wiki_agent import CodexWikiInsightProvider
from rolo.stages.artifact_paths import resolve_artifact_ref
from rolo.stages.discovery_manifest import load_and_verify_discovery_manifest

discover_app = typer.Typer(help="Discover hardware, Linux, ROS and application capabilities.")


def configured_discovery_service(
    settings: Settings,
    artifacts: ArtifactStore,
) -> DiscoveryService:
    """Build discovery with the configured optional Wiki agents."""
    wiki_model = settings.wiki_polish_model or settings.openai_model
    wiki_polisher = (
        OpenAIWikiNarrativePolisher(
            api_key=settings.openai_api_key or "",
            model=wiki_model or "",
            timeout_s=settings.wiki_polish_timeout_s,
        )
        if settings.wiki_polish_enabled and settings.openai_api_key and wiki_model
        else None
    )
    wiki_insight_provider = (
        CodexWikiInsightProvider(
            skill_path=resolve_skill_path(
                settings.wiki_insights_skill_path, "rolo-wiki-authoring"
            ),
            executable=settings.coding_agent_executable,
            model=settings.coding_agent_model,
            provider=settings.coding_agent_provider,
            base_url=settings.coding_agent_base_url,
            api_key=settings.coding_agent_api_key,
            timeout_s=settings.wiki_insights_agent_timeout_s,
        )
        if settings.wiki_insights_agent_enabled
        else None
    )
    heuristic_mode = HeuristicAdaptMode(settings.adapt_heuristic_agent_mode)
    heuristic_orchestrator = None
    if heuristic_mode != HeuristicAdaptMode.DISABLED:
        common = {
            "executable": settings.coding_agent_executable,
            "model": settings.coding_agent_model,
            "provider": settings.coding_agent_provider,
            "base_url": settings.coding_agent_base_url,
            "api_key": settings.coding_agent_api_key,
            "timeout_s": settings.adapt_heuristic_agent_timeout_s,
        }
        planning_provider = (
            CodexDiscoveryPlanningProvider(
                skill_path=resolve_skill_path(
                    settings.adapt_discovery_skill_path, "rolo-adapt-discovery"
                ),
                **common,
            )
            if settings.adapt_heuristic_agent_provider_enabled
            else None
        )
        mapping_provider = (
            CodexOperationMappingProvider(
                discovery_skill_path=resolve_skill_path(
                    settings.adapt_discovery_skill_path, "rolo-adapt-discovery"
                ),
                mapping_skill_path=resolve_skill_path(
                    settings.adapt_mapping_skill_path, "rolo-operation-mapping"
                ),
                **common,
            )
            if settings.adapt_heuristic_agent_provider_enabled
            else None
        )
        heuristic_orchestrator = HeuristicDiscoveryOrchestrator(
            artifacts,
            mode=heuristic_mode,
            planning_provider=planning_provider,
            mapping_provider=mapping_provider,
            max_actions=settings.adapt_heuristic_agent_max_actions,
            max_operations=settings.adapt_heuristic_agent_max_operations,
        )
    return DiscoveryService(
        artifacts,
        wiki_polisher=wiki_polisher,
        wiki_insight_provider=wiki_insight_provider,
        heuristic_orchestrator=heuristic_orchestrator,
    )


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
    target_evidence_bundle: Annotated[
        Path | None,
        typer.Option(
            "--target-evidence-bundle",
            help="Verified local/remote target evidence bundle; never attributes this host",
        ),
    ] = None,
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
        target_probes = None
        if target_evidence_bundle is not None:
            from rolo.commands.target_evidence import load_verified_probes

            target_probes = load_verified_probes(
                robot_id=robot,
                bundle_path=target_evidence_bundle,
            )
            if active_probe != ActiveProbeMode.RUNTIME_READONLY:
                raise ValueError(
                    "--target-evidence-bundle requires --active-probe runtime-readonly"
                )
        report, artifact = configured_discovery_service(
            runtime.settings,
            runtime.artifacts,
        ).run(
            robot=capability,
            urdf_path=urdf,
            active_inputs=active_inputs,
            target_probes=target_probes,
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
            "heuristic_analysis": report.heuristic_analysis_ref,
            "heuristic_status": report.heuristic_status,
            "heuristic_inferred_operations": report.heuristic_inferred_operation_count,
            "missing_evidence": report.heuristic_missing_evidence_count,
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
