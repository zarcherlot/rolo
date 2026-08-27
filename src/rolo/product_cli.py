"""Concise product CLI backed by the canonical robotctl application services."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.lifecycle import run_adapt_start
from rolo.core.config import get_settings
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.target_ref import LocalTargetRef, parse_target_ref
from rolo.targets.executor import create_target_executor
from rolo.targets.models import BootstrapPlanStatus, TargetConnectionState
from rolo.targets.profiles import CredentialReference, TargetProfileStore

app = typer.Typer(
    help="Adapt a local or remote robot workspace.",
    no_args_is_help=True,
)
target_app = typer.Typer(help="Inspect targets and plan approved bootstrap changes.")
app.add_typer(target_app, name="target")
profile_app = typer.Typer(help="Manage non-secret target connection profiles.")
target_app.add_typer(profile_app, name="profile")


@app.callback()
def product_root() -> None:
    """Rolo product commands."""


def _target_executor(target: str, known_hosts: Path | None, timeout: float):
    return create_target_executor(
        parse_target_ref(target),
        known_hosts=known_hosts,
        timeout_s=timeout,
    )


@target_app.command("inspect")
def target_inspect(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Explicit pinned SSH known_hosts file"),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0, help="Connection timeout in seconds"),
    ] = 10.0,
) -> None:
    """Inspect a target without installing or changing anything."""
    try:
        assessment = _target_executor(target, known_hosts, timeout).inspect()
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(assessment)
    if assessment.state != TargetConnectionState.READY:
        raise typer.Exit(code=2)


@target_app.command("bootstrap-plan")
def target_bootstrap_plan(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Explicit pinned SSH known_hosts file"),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0, help="Connection timeout in seconds"),
    ] = 10.0,
) -> None:
    """Return a typed bootstrap plan without executing host mutations."""
    try:
        plan = _target_executor(target, known_hosts, timeout).plan_bootstrap()
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(plan)
    if plan.status == BootstrapPlanStatus.BLOCKED:
        raise typer.Exit(code=2)


@profile_app.command("init")
def profile_init(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    robot_id: Annotated[
        str,
        typer.Option("--robot", "--robot-id", help="Stable identity for this target profile"),
    ],
    credential_ref: Annotated[
        str,
        typer.Option(
            "--credential-ref",
            help="Typed reference only, for example ssh-agent:default; never a secret",
        ),
    ] = "ssh-agent:default",
) -> None:
    """Create or validate a target profile without connecting or mutating a host."""
    try:
        target_ref = parse_target_ref(target)
        credential = CredentialReference(
            kind=credential_ref.split(":", 1)[0],
            reference=credential_ref,
        )
        store = TargetProfileStore(get_settings().rolo_config_dir)
        profile = store.create(robot_id=robot_id, target=target_ref, credential=credential)
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
def profile_show(
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
) -> None:
    """Show a target profile; credential references never contain secret material."""
    try:
        store = TargetProfileStore(get_settings().rolo_config_dir)
        profile = store.load(robot_id)
        emit(
            {
                "status": "PROFILE_FOUND",
                "path": str(store.path_for(profile.profile_id)),
                "profile": profile.model_dump(mode="json"),
            }
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@profile_app.command("approve-host-key")
def profile_approve_host_key(
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
    fingerprint: Annotated[
        str,
        typer.Option("--fingerprint", help="Independently verified SHA256 host-key fingerprint"),
    ],
    approver: Annotated[
        str,
        typer.Option("--approver", help="Human or policy actor approving this host key"),
    ],
) -> None:
    """Record an explicit host-key decision without changing SSH known_hosts."""
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
