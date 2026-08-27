"""Concise product CLI backed by the canonical robotctl application services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.lifecycle import run_adapt_start
from rolo.core.config import get_settings
from rolo.jobs import JobStatus, JobStore
from rolo.natural_language import intent_to_argv, parse_natural_language
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.target_ref import LocalTargetRef, parse_target_ref
from rolo.targets.approvals import (
    BootstrapApprovalRequest,
    approve_bootstrap,
    request_bootstrap_approval,
)
from rolo.targets.executor import create_target_executor
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan, TargetConnectionState
from rolo.targets.profiles import CredentialReference, TargetProfileStore

app = typer.Typer(
    help="Adapt a local or remote robot workspace.",
    no_args_is_help=True,
)
job_app = typer.Typer(
    help="Inspect and recover persisted Adapt jobs without auto-resuming mutations."
)
app.add_typer(job_app, name="job")
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


def _job_store() -> JobStore:
    return JobStore(get_settings().rolo_config_dir / "jobs")


@app.command("natural")
def natural(
    request: Annotated[str, typer.Argument(help="Explicit natural-language request")],
) -> None:
    """Parse a bounded natural-language request into canonical CLI argv without executing it."""
    try:
        intent = parse_natural_language(request)
        argv = intent_to_argv(intent)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "INTENT_PARSED", "intent": intent.model_dump(mode="json"), "argv": argv})


@job_app.command("list")
def job_list(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    offset: Annotated[int, typer.Option("--offset", min=0)] = 0,
) -> None:
    """List bounded Job metadata; payloads and secrets are not resolved."""
    try:
        items = _job_store().list_jobs(limit=limit, offset=offset)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "JOB_LISTED", "items": [item.model_dump(mode="json") for item in items]})


@job_app.command("recover")
def job_recover(job_id: Annotated[str, typer.Argument(help="Persisted job identifier")]) -> None:
    """Return the latest checkpoint; never resumes host mutation automatically."""
    try:
        recovery = _job_store().recover(job_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(recovery)


@job_app.command("events")
def job_events(
    job_id: Annotated[str, typer.Argument(help="Persisted job identifier")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    offset: Annotated[int, typer.Option("--offset", min=0)] = 0,
) -> None:
    """List a bounded, ordered event page for audit and UI consumers."""
    try:
        events = _job_store().list_events(job_id, limit=limit, offset=offset)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "JOB_EVENTS_LISTED",
            "job_id": job_id,
            "items": [event.model_dump(mode="json") for event in events],
        }
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
    as_job: Annotated[
        bool,
        typer.Option("--job/--direct", help="Persist lifecycle events and a resumable checkpoint"),
    ] = False,
) -> None:
    """Inspect a target without installing or changing anything."""
    try:
        job = _job_store().create("target.inspect", target) if as_job else None
        if job:
            _job_store().append_event(
                job.job_id, "JOB_STARTED", JobStatus.RUNNING, expected_revision=0
            )
        assessment = _target_executor(target, known_hosts, timeout).inspect()
        if job:
            store = _job_store()
            store.save_checkpoint(
                job.job_id,
                {"assessment": assessment.model_dump(mode="json")},
                expected_revision=1,
            )
            store.append_event(
                job.job_id, "TARGET_INSPECTED", JobStatus.SUCCEEDED, expected_revision=1
            )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "JOB_COMPLETED",
            "job_id": job.job_id,
            "result": assessment.model_dump(mode="json"),
        }
        if job
        else assessment
    )
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
    as_job: Annotated[
        bool,
        typer.Option("--job/--direct", help="Persist lifecycle events and a resumable checkpoint"),
    ] = False,
) -> None:
    """Return a typed bootstrap plan without executing host mutations."""
    try:
        job = _job_store().create("target.bootstrap-plan", target) if as_job else None
        if job:
            _job_store().append_event(
                job.job_id, "JOB_STARTED", JobStatus.RUNNING, expected_revision=0
            )
        plan = _target_executor(target, known_hosts, timeout).plan_bootstrap()
        if job:
            store = _job_store()
            store.save_checkpoint(
                job.job_id,
                {"plan": plan.model_dump(mode="json")},
                expected_revision=1,
            )
            final_status = (
                JobStatus.BLOCKED
                if plan.status == BootstrapPlanStatus.BLOCKED
                else JobStatus.SUCCEEDED
            )
            store.append_event(
                job.job_id, "BOOTSTRAP_PLAN_CREATED", final_status, expected_revision=1
            )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "JOB_COMPLETED",
            "job_id": job.job_id,
            "result": plan.model_dump(mode="json"),
        }
        if job
        else plan
    )
    if plan.status == BootstrapPlanStatus.BLOCKED:
        raise typer.Exit(code=2)


@target_app.command("bootstrap-request")
def target_bootstrap_request(
    plan_file: Annotated[
        Path, typer.Argument(help="JSON file containing an approval-required plan")
    ],
    requested_by: Annotated[str, typer.Option("--requested-by")],
    ttl_minutes: Annotated[int, typer.Option("--ttl-minutes", min=1, max=1440)] = 10,
) -> None:
    """Create a plan-bound bootstrap approval request without connecting to a host."""
    try:
        plan = TargetBootstrapPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
        request = request_bootstrap_approval(
            plan,
            requested_by=requested_by,
            ttl=timedelta(minutes=ttl_minutes),
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(request)


@target_app.command("bootstrap-approve")
def target_bootstrap_approve(
    plan_file: Annotated[Path, typer.Argument(help="JSON file containing the approved plan")],
    request_file: Annotated[Path, typer.Argument(help="JSON file containing a pending request")],
    approved_by: Annotated[str, typer.Option("--approved-by")],
) -> None:
    """Approve a pending bootstrap request while preserving plan binding."""
    try:
        plan = TargetBootstrapPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
        request = BootstrapApprovalRequest.model_validate_json(
            request_file.read_text(encoding="utf-8")
        )
        decision = approve_bootstrap(plan, request, approved_by=approved_by)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(decision)


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
