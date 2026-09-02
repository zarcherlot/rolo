"""Small Rolo v2 product entrypoint.

The interactive Agent owns intent and planning. Rolo owns only the trusted
target boundary: enrollment references, fresh signed Probe evidence, a frozen
native Tool Surface, and execution of a digest-bound read-only ToolPlan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from rolo.agent_tools import ToolPlan, conform_tool_surface, create_profile_native_tool_session
from rolo.commands.common import emit
from rolo.commands.lifecycle import run_probe_start
from rolo.core.config import get_settings
from rolo.release_check import run_release_check
from rolo.stages.probe.active_discovery import ActiveProbeMode
from rolo.stages.probe.target_evidence import EvidenceDeploymentMode
from rolo.target_ref import LocalTargetRef, parse_target_ref
from rolo.targets.executor import create_profile_target_executor, create_target_executor
from rolo.targets.models import BootstrapPlanStatus, TargetConnectionState
from rolo.targets.profiles import CredentialReference, TargetProfileStore

app = typer.Typer(help="Probe a local or remote robot target.", no_args_is_help=True)
target_app = typer.Typer(help="Inspect an enrolled target and consume its read-only Tool Surface.")
profile_app = typer.Typer(help="Manage non-secret target connection profiles.")
app.add_typer(target_app, name="target")
target_app.add_typer(profile_app, name="profile")


@app.command("release-check")
def release_check(
    require_artifacts: Annotated[
        bool, typer.Option("--require-artifacts/--allow-missing-artifacts")
    ] = False,
) -> None:
    """Run release smoke checks for the v2 product surface."""
    result = run_release_check(require_artifacts=require_artifacts)
    emit(result)
    if result.status != "PASS":
        raise typer.Exit(code=2)


def _target_executor(
    target: str,
    known_hosts: Path | None,
    timeout: float,
    identity_file: Path | None = None,
):
    return create_target_executor(
        parse_target_ref(target),
        known_hosts=known_hosts,
        identity_file=identity_file,
        timeout_s=timeout,
    )


def _write_conformance(session) -> tuple[object, str]:
    report = conform_tool_surface(session.descriptor, session.runner.list_tools())
    relative = (
        f"native/{session.descriptor.robot_id}/sessions/"
        f"{session.descriptor.session_id}/conformance.json"
    )
    session.artifacts.write_json(relative, report.model_dump(mode="json"))
    return report, f"artifact://{relative}"


@target_app.command("inspect")
def target_inspect(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[Path | None, typer.Option("--known-hosts")] = None,
    identity_file: Annotated[Path | None, typer.Option("--identity-file")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 10.0,
) -> None:
    """Inspect target reachability without installing or changing anything."""
    try:
        assessment = _target_executor(target, known_hosts, timeout, identity_file).inspect()
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(assessment)
    if assessment.state != TargetConnectionState.READY:
        raise typer.Exit(code=2)


@target_app.command("inspect-profile")
def target_inspect_profile(
    profile: Annotated[str, typer.Option("--profile", "--robot")],
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 10.0,
) -> None:
    """Inspect an enrolled target using its pinned host key and identity."""
    try:
        assessment = create_profile_target_executor(
            profile,
            config_root=get_settings().rolo_config_dir,
            timeout_s=timeout,
        ).inspect()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(assessment)
    if assessment.state != TargetConnectionState.READY:
        raise typer.Exit(code=2)


@target_app.command("bootstrap-plan")
def target_bootstrap_plan(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[Path | None, typer.Option("--known-hosts")] = None,
    identity_file: Annotated[Path | None, typer.Option("--identity-file")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 10.0,
) -> None:
    """Return a read-only bootstrap readiness plan; never mutate a host."""
    try:
        plan = _target_executor(target, known_hosts, timeout, identity_file).plan_bootstrap()
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(plan)
    if plan.status == BootstrapPlanStatus.BLOCKED:
        raise typer.Exit(code=2)


@target_app.command("bootstrap-plan-profile")
def target_bootstrap_plan_profile(
    profile: Annotated[str, typer.Option("--profile", "--robot")],
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 10.0,
) -> None:
    """Return a read-only bootstrap readiness plan for an enrolled profile."""
    try:
        plan = create_profile_target_executor(
            profile,
            config_root=get_settings().rolo_config_dir,
            timeout_s=timeout,
        ).plan_bootstrap()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(plan)
    if plan.status == BootstrapPlanStatus.BLOCKED:
        raise typer.Exit(code=2)


@target_app.command("tool-surface")
def target_tool_surface(
    profile: Annotated[str, typer.Option("--profile", "--robot")],
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 15.0,
) -> None:
    """Publish the session-bound read-only Tool Surface for the Agent."""
    session = None
    try:
        session = create_profile_native_tool_session(
            profile,
            config_root=get_settings().rolo_config_dir,
            artifact_root=get_settings().rolo_artifact_dir,
            timeout_s=timeout,
        )
        conformance, conformance_ref = _write_conformance(session)
        emit(
            {
                "status": "TOOL_SURFACE_READY",
                "session": session.descriptor.model_dump(mode="json"),
                "tools": [item.model_dump(mode="json") for item in session.list_tools()],
                "conformance": conformance.model_dump(mode="json"),
                "conformance_ref": conformance_ref,
            }
        )
        if conformance.status != "PASS":
            raise typer.Exit(code=2)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    finally:
        if session is not None:
            session.close()


@target_app.command("tool-plan")
def target_tool_plan(
    profile: Annotated[str, typer.Option("--profile", "--robot")],
    plan_file: Annotated[Path, typer.Argument(help="JSON file containing an Agent ToolPlan")],
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 15.0,
) -> None:
    """Execute one Agent-authored, digest-bound read-only ToolPlan."""
    session = None
    try:
        plan = ToolPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
        session = create_profile_native_tool_session(
            profile,
            config_root=get_settings().rolo_config_dir,
            artifact_root=get_settings().rolo_artifact_dir,
            timeout_s=timeout,
            session_id=plan.session_id,
            session_nonce=plan.session_nonce,
        )
        conformance, conformance_ref = _write_conformance(session)
        results = session.execute_plan(plan)
        emit(
            {
                "status": "TOOL_PLAN_EXECUTED",
                "plan_sha256": plan.plan_sha256,
                "session_id": plan.session_id,
                "results": [item.model_dump(mode="json") for item in results],
                "conformance": conformance.model_dump(mode="json"),
                "conformance_ref": conformance_ref,
            }
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    finally:
        if session is not None:
            session.close()


@profile_app.command("init")
def profile_init(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
    credential_ref: Annotated[
        str,
        typer.Option("--credential-ref", help="Typed reference, never secret material"),
    ] = "ssh-agent:default",
    remote_command_prefix: Annotated[
        list[str] | None,
        typer.Option("--remote-command-prefix", help="Fixed target runtime prefix"),
    ] = None,
    provider_hint: Annotated[
        list[str] | None,
        typer.Option(
            "--provider-hint",
            help="Bounded provider hint as key=value; never put credentials here",
        ),
    ] = None,
) -> None:
    """Create a non-secret target profile without connecting or mutating a host."""
    try:
        target_ref = parse_target_ref(target)
        kind, _, _ = credential_ref.partition(":")
        credential = CredentialReference(kind=kind, reference=credential_ref)
        provider_hints: dict[str, str] = {}
        for item in provider_hint or []:
            key, separator, value = item.partition("=")
            if not separator or not key or not value:
                raise ValueError("--provider-hint must use key=value")
            provider_hints[key] = value
        store = TargetProfileStore(get_settings().rolo_config_dir)
        profile = store.create(
            robot_id=robot_id,
            target=target_ref,
            credential=credential,
            remote_command_prefix=remote_command_prefix,
            provider_hints=provider_hints,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "PROFILE_READY",
            "path": str(store.path_for(profile.profile_id)),
            "profile": profile.model_dump(mode="json"),
        }
    )


@profile_app.command("show")
def profile_show(robot_id: Annotated[str, typer.Option("--robot", "--robot-id")]) -> None:
    """Show a profile while keeping credential references secret-free."""
    try:
        store = TargetProfileStore(get_settings().rolo_config_dir)
        profile = store.load(robot_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "PROFILE_FOUND",
            "path": str(store.path_for(profile.profile_id)),
            "profile": profile.model_dump(mode="json"),
        }
    )


@profile_app.command("approve-host-key")
def profile_approve_host_key(
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
    fingerprint: Annotated[str, typer.Option("--fingerprint")],
    approver: Annotated[str, typer.Option("--approver")],
) -> None:
    """Record an explicit host-key decision without changing known_hosts."""
    try:
        store = TargetProfileStore(get_settings().rolo_config_dir)
        profile = store.load(robot_id)
        if profile.host_key is None:
            raise ValueError("local target profiles do not have an SSH host key decision")
        if profile.host_key.status == "APPROVED" and profile.host_key.fingerprint != fingerprint:
            raise ValueError("changing an approved host key requires explicit rotation")
        host_key = profile.host_key.model_copy(
            update={
                "status": "APPROVED",
                "fingerprint": fingerprint,
                "decided_at": datetime.now(timezone.utc),
                "decided_by": approver,
            }
        )
        updated = profile.model_copy(
            update={"host_key": host_key, "updated_at": datetime.now(timezone.utc)}
        )
        store.save(updated)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "HOST_KEY_APPROVED",
            "path": str(store.path_for(updated.profile_id)),
            "profile": updated.model_dump(mode="json"),
        }
    )


@app.command("probe")
def probe(
    target: Annotated[
        str | None, typer.Argument(help="Optional local workspace path or ssh:// target")
    ] = None,
    robot_id: Annotated[str | None, typer.Option("--robot", "--robot-id")] = None,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    active_probe: Annotated[
        ActiveProbeMode, typer.Option("--active-probe")
    ] = ActiveProbeMode.RUNTIME_READONLY,
    allow_executable: Annotated[list[Path] | None, typer.Option("--allow-executable")] = None,
    evidence_timeout: Annotated[
        float, typer.Option("--evidence-timeout", min=1.0, max=300.0)
    ] = 45.0,
) -> None:
    """Collect fresh signed target evidence; return the next Agent-owned step."""
    try:
        if profile:
            enrolled = TargetProfileStore(get_settings().rolo_config_dir).load(profile)
            if robot_id is not None and robot_id != enrolled.robot_id:
                raise ValueError("--robot does not match --profile")
            robot_id = enrolled.robot_id
            if isinstance(enrolled.target, LocalTargetRef):
                project_root = enrolled.target.workspace
                evidence_mode = EvidenceDeploymentMode.LOCAL
            else:
                project_root = None
                evidence_mode = EvidenceDeploymentMode.REMOTE
        else:
            if not target or not robot_id:
                raise ValueError("provide --profile or both TARGET and --robot")
            target_ref = parse_target_ref(target)
            if isinstance(target_ref, LocalTargetRef):
                project_root = target_ref.workspace
                evidence_mode = EvidenceDeploymentMode.LOCAL
            else:
                project_root = None
                evidence_mode = EvidenceDeploymentMode.REMOTE
        result = run_probe_start(
            robot_id=robot_id,
            project_root=project_root,
            active_probe=active_probe,
            evidence_mode=evidence_mode,
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


if __name__ == "__main__":
    app()
