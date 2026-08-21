from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.adapt.workset import (
    OperationApplicability,
    OperationImplementation,
    OperationRegistration,
    build_operation_workset,
    candidate_detail,
    evidence_metadata,
    evidence_snippet,
    executable_detail,
    load_active_discovery,
    operation_detail,
    wiki_search,
    wiki_section,
)

operations_app = typer.Typer(help="Query the joined Registry, discovery and gated-release workset.")
candidates_app = typer.Typer(help="Inspect operation candidates and their focused evidence.")
executable_app = typer.Typer(help="Inspect discovered executable entrypoints on demand.")
launch_app = typer.Typer(help="Inspect launch evidence without loading the whole discovery report.")
dependency_app = typer.Typer(help="Inspect dependency evidence on demand.")
evidence_app = typer.Typer(help="Resolve and read bounded discovery evidence.")
wiki_app = typer.Typer(help="Search the robot Wiki or read one section at a time.")


def register_adapt_query_commands(parent: typer.Typer) -> None:
    """Attach the same bounded read-only query surface to a CLI parent."""
    for name, command in (
        ("operations", operations_app),
        ("candidates", candidates_app),
        ("executable", executable_app),
        ("launch", launch_app),
        ("dependency", dependency_app),
        ("evidence", evidence_app),
        ("wiki", wiki_app),
    ):
        parent.add_typer(command, name=name)


def _settings() -> tuple[Path, Path]:
    settings = get_settings()
    return settings.rolo_artifact_dir, settings.rolo_output_dir


def _discovery_id() -> str | None:
    """Pin Agent queries while normal interactive queries continue to use latest."""
    return os.environ.get("ROLO_AGENT_DISCOVERY_ID") or None


def _report(artifact_root: Path, robot: str) -> DiscoveryReport:
    discovery_id = _discovery_id()
    return (
        load_report(artifact_root, robot, discovery_id)
        if discovery_id
        else load_latest_report(artifact_root, robot)
    )


@operations_app.command("summary")
def operations_summary(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show compact operation counts and current release alignment."""
    artifact_root, output_root = _settings()
    try:
        workset = build_operation_workset(artifact_root, output_root, robot, _discovery_id())
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(workset.model_dump(mode="json", exclude={"operations"}))


@operations_app.command("list")
def operations_list(
    robot: Annotated[str, typer.Option("--robot")],
    applicability: Annotated[OperationApplicability | None, typer.Option()] = None,
    implementation: Annotated[OperationImplementation | None, typer.Option()] = None,
    registration: Annotated[OperationRegistration | None, typer.Option()] = None,
    layer: Annotated[str | None, typer.Option()] = None,
) -> None:
    """List operations using orthogonal applicability, implementation and registration filters."""
    artifact_root, output_root = _settings()
    try:
        workset = build_operation_workset(artifact_root, output_root, robot, _discovery_id())
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    items = workset.operations
    if applicability:
        items = [item for item in items if item.applicability == applicability]
    if implementation:
        items = [item for item in items if item.implementation == implementation]
    if registration:
        items = [item for item in items if item.registration == registration]
    if layer:
        items = [item for item in items if item.layer == layer]
    emit(
        {
            "robot_id": robot,
            "discovery_id": workset.discovery_id,
            "operations": [item.model_dump(mode="json") for item in items],
        }
    )


@operations_app.command("inspect")
def operations_inspect(
    operation: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show one product contract, candidate, registration state and follow-up queries."""
    artifact_root, output_root = _settings()
    try:
        emit(operation_detail(artifact_root, output_root, robot, operation, _discovery_id()))
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@candidates_app.command("inspect")
def candidates_inspect(
    operation: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show one candidate and only the executables related to its evidence."""
    artifact_root, _ = _settings()
    try:
        emit(candidate_detail(artifact_root, robot, operation, _discovery_id()))
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@executable_app.command("list")
def executable_list(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """List compact executable identities and entrypoints."""
    artifact_root, _ = _settings()
    try:
        report = _report(artifact_root, robot)
        active = load_active_discovery(artifact_root, report)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "robot_id": robot,
            "discovery_id": report.discovery_id,
            "executables": [
                {
                    "executable_id": item.executable_id,
                    "name": item.name,
                    "origin": item.origin,
                    "path": item.path,
                    "entrypoint": item.invocation.entrypoint,
                    "has_launch": item.launch_analysis.available,
                }
                for item in active.executables
            ],
        }
    )


@executable_app.command("inspect")
def executable_inspect(
    executable_id: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show the complete bounded record for one discovered executable."""
    artifact_root, _ = _settings()
    try:
        emit(executable_detail(artifact_root, robot, executable_id, _discovery_id()))
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@launch_app.command("inspect")
def launch_inspect(
    executable_id: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Show launch topology and invocation data for one executable."""
    artifact_root, _ = _settings()
    try:
        executable = executable_detail(artifact_root, robot, executable_id, _discovery_id())
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "executable_id": executable.executable_id,
            "launch": executable.launch_analysis,
            "invocation": executable.invocation,
            "communication": executable.communication,
        }
    )


@dependency_app.command("inspect")
def dependency_inspect(
    robot: Annotated[str, typer.Option("--robot")],
    executable_id: Annotated[str | None, typer.Option("--executable-id")] = None,
) -> None:
    """Show global dependency status or the dependency set for one executable."""
    artifact_root, _ = _settings()
    try:
        report = _report(artifact_root, robot)
        if executable_id:
            executable = executable_detail(artifact_root, robot, executable_id, _discovery_id())
            emit({"executable_id": executable_id, "dependencies": executable.dependencies})
        else:
            active = load_active_discovery(artifact_root, report)
            emit(
                {
                    "robot_id": robot,
                    "discovery_id": report.discovery_id,
                    "software_summary": report.software_summary,
                    "dependency_summary": active.dependency_summary,
                    "dependency_report_ref": report.dependency_report_ref,
                }
            )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@evidence_app.command("resolve")
def evidence_resolve(
    reference: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
) -> None:
    """Resolve one artifact reference or declared discovery-input path."""
    artifact_root, _ = _settings()
    try:
        emit(evidence_metadata(artifact_root, robot, reference, _discovery_id()))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@evidence_app.command("snippet")
def evidence_read_snippet(
    reference: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
    start_line: Annotated[int, typer.Option("--start-line", min=1)] = 1,
    lines: Annotated[int, typer.Option("--lines", min=1, max=200)] = 80,
) -> None:
    """Read a bounded text slice from trusted discovery evidence."""
    artifact_root, _ = _settings()
    try:
        emit(
            evidence_snippet(
                artifact_root,
                robot,
                reference,
                start_line=start_line,
                line_count=lines,
                discovery_id=_discovery_id(),
            )
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@wiki_app.command("section")
def robot_wiki_section(
    heading: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
    cursor: Annotated[int, typer.Option("--cursor", min=0)] = 0,
) -> None:
    """Read one heading-bounded section from the editable high-authority Wiki."""
    artifact_root, _ = _settings()
    try:
        emit(wiki_section(artifact_root, robot, heading, _discovery_id(), cursor))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@wiki_app.command("search")
def robot_wiki_search(
    query: Annotated[str, typer.Argument()],
    robot: Annotated[str, typer.Option("--robot")],
    cursor: Annotated[int, typer.Option("--cursor", min=0)] = 0,
) -> None:
    """Search Wiki lines without injecting the whole document into the Agent prompt."""
    artifact_root, _ = _settings()
    try:
        emit(wiki_search(artifact_root, robot, query, _discovery_id(), cursor))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
