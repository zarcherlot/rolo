"""Concise product CLI backed by the canonical robotctl application services."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import typer

from rolo.agent_provider import available_agent_executors
from rolo.commands.common import emit
from rolo.commands.lifecycle import run_adapt_start
from rolo.console import run_console
from rolo.core.config import get_settings
from rolo.core.hashing import canonical_json_sha256
from rolo.device_hardening_evidence import (
    build_device_hardening_bundle,
    write_device_hardening_bundle,
)
from rolo.episode_capture import capture_target_inspection_episode
from rolo.job_service import JobService
from rolo.jobs import JobStatus, JobStore, run_bootstrap_job
from rolo.natural_language import intent_to_argv, parse_natural_language
from rolo.natural_service import NaturalLanguageService
from rolo.query_adapter import ServiceJobQueryAdapter
from rolo.release_check import run_release_check
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.service import coding_agent_config
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode, load_deployment
from rolo.stages.verify.ssh_target_provider import SshTargetHealthProvider
from rolo.target_ref import LocalTargetRef, SshTargetRef, parse_target_ref
from rolo.targets.approvals import (
    BootstrapApprovalDecision,
    BootstrapApprovalRequest,
    approve_bootstrap,
    request_bootstrap_approval,
)
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.executor import create_profile_target_executor, create_target_executor
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan, TargetConnectionState
from rolo.targets.package import build_companion_package
from rolo.targets.profiles import CredentialReference, TargetProfileStore
from rolo.targets.security import validate_bootstrap_security
from rolo.targets.signing import CompanionReleasePolicy, verify_companion_manifest
from rolo.tui import run_tui
from rolo.ui_models import JobUiAdapter

app = typer.Typer(
    help="Adapt a local or remote robot workspace.",
    no_args_is_help=False,
    invoke_without_command=True,
)
job_app = typer.Typer(
    help="Inspect and recover persisted Adapt jobs without auto-resuming mutations."
)
app.add_typer(job_app, name="job")
target_app = typer.Typer(help="Inspect targets and plan approved bootstrap changes.")
app.add_typer(target_app, name="target")
profile_app = typer.Typer(help="Manage non-secret target connection profiles.")
target_app.add_typer(profile_app, name="profile")


@app.callback(invoke_without_command=True)
def product_root(ctx: typer.Context) -> None:
    """Rolo product commands; no arguments open the natural-language console."""
    if ctx.invoked_subcommand is not None:
        return
    if sys.stdin.isatty() and sys.stdout.isatty():
        run_console()
        return
    typer.echo(ctx.get_help())


@app.command("release-check")
def release_check(
    require_artifacts: Annotated[
        bool, typer.Option("--require-artifacts/--allow-missing-artifacts")
    ] = False,
) -> None:
    """Run release smoke checks for product modules and console scripts."""
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


def _job_store() -> JobStore:
    return JobStore(get_settings().rolo_config_dir / "jobs")


def _stream_agent_output(stream: str, line: str) -> None:
    """Keep machine-readable CLI output on stdout and live Agent text on stderr."""
    if line:
        typer.echo(f"[agent{' stderr' if stream != 'stdout' else ''}] {line[:8_000]}", err=True)


@app.command("natural")
def natural(
    request: Annotated[str, typer.Argument(help="Explicit natural-language request")],
    execute: Annotated[
        bool,
        typer.Option("--execute/--parse-only", help="Execute through canonical safe services"),
    ] = False,
    confirmed: Annotated[
        bool,
        typer.Option(
            "--confirm/--no-confirm",
            help="Explicitly authorize a mutating request (required with --execute)",
        ),
    ] = False,
    known_hosts: Annotated[Path | None, typer.Option("--known-hosts")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 10.0,
) -> None:
    """Parse, or explicitly execute, a bounded request through canonical services."""
    try:
        intent = parse_natural_language(request)
        argv = intent_to_argv(intent)
        result = None
        if execute:
            result = NaturalLanguageService(
                JobService(get_settings().rolo_config_dir / "jobs")
            ).execute(
                intent,
                known_hosts=known_hosts,
                timeout_s=timeout,
                confirmed=confirmed,
                on_output=_stream_agent_output,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = {
        "status": "INTENT_EXECUTED" if execute else "INTENT_PARSED",
        "intent": intent.model_dump(mode="json"),
        "argv": argv,
    }
    if execute:
        payload["result"] = (
            result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        )
    emit(payload)


@app.command("run")
def run(
    once: Annotated[
        bool,
        typer.Option(
            "--once",
            help="Render the interactive prompt and exit (useful for smoke checks)",
        ),
    ] = False,
) -> None:
    """Start the Codex-style natural-language Rolo console.

    ``rolo`` without arguments already opens this console on a TTY.  The explicit
    spelling is useful in launchers and makes the two supported entry modes clear:
    canonical subcommands (for example ``rolo adapt ...``) and conversational
    interaction (``rolo run``).
    """
    if once:
        typer.echo("Rolo — natural-language console")
        typer.echo("Type a request, or /help and /quit.")
        return
    run_console()


@app.command("tui")
def tui(
    once: Annotated[
        bool, typer.Option("--once", help="Render the current Job view and exit")
    ] = False,
) -> None:
    """Open the dependency-free, read-only terminal UI."""
    adapter = JobUiAdapter(
        ServiceJobQueryAdapter(JobService(get_settings().rolo_config_dir / "jobs"))
    )
    run_tui(adapter, once=once)


@job_app.command("list")
def job_list(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    offset: Annotated[int, typer.Option("--offset", min=0)] = 0,
) -> None:
    """List bounded Job metadata; payloads and secrets are not resolved."""
    try:
        page = _job_store().job_page(limit=limit, offset=offset)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "JOB_LISTED", **page.model_dump(mode="json")})


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
        page = _job_store().event_page(job_id, limit=limit, offset=offset)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "JOB_EVENTS_LISTED",
            "job_id": job_id,
            "items": [event.model_dump(mode="json") for event in page.items],
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
            "next_offset": page.next_offset,
        }
    )


@target_app.command("inspect")
def target_inspect(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Explicit pinned SSH known_hosts file"),
    ] = None,
    identity_file: Annotated[
        Path | None,
        typer.Option("--identity-file", help="Pinned SSH private key; never a password"),
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
        assessment = _target_executor(target, known_hosts, timeout, identity_file).inspect()
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


@target_app.command("inspect-profile")
def target_inspect_profile(
    profile: Annotated[str, typer.Option("--profile", "--robot", help="Enrolled target profile")],
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0, help="Connection timeout in seconds"),
    ] = 10.0,
) -> None:
    """Inspect an enrolled target using its pinned host key and credential."""
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


@target_app.command("episode-capture")
def target_episode_capture(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
    episode_id: Annotated[str, typer.Option("--episode-id")],
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Explicit pinned SSH known_hosts file"),
    ] = None,
    identity_file: Annotated[
        Path | None,
        typer.Option("--identity-file", help="Pinned SSH private key; never a password"),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0, help="Connection timeout in seconds"),
    ] = 10.0,
) -> None:
    """Capture a metadata-only immutable Episode from a read-only target inspection."""

    try:
        assessment = _target_executor(target, known_hosts, timeout, identity_file).inspect()
        record, episode_ref = capture_target_inspection_episode(
            get_settings().rolo_artifact_dir,
            assessment,
            robot_id=robot_id,
            episode_id=episode_id,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "EPISODE_CAPTURED",
            "episode_ref": episode_ref,
            "episode_id": record.episode_id,
            "revision": record.revision,
            "verification": record.verification,
            "coverage": record.coverage,
            "immutable": record.immutable,
        }
    )


@target_app.command("verify-health")
def target_verify_health(
    target: Annotated[str, typer.Argument(help="ssh:// target workspace URI")],
    robot_id: Annotated[str, typer.Option("--robot", "--robot-id")],
    package_id: Annotated[str, typer.Option("--package-id")],
    package_version: Annotated[str, typer.Option("--package-version")],
    known_hosts: Annotated[Path, typer.Option("--known-hosts")],
) -> None:
    """Run the fixed, read-only canonical Verify health provider over SSH."""

    try:
        settings = get_settings()
        target_ref = parse_target_ref(target)
        if not isinstance(target_ref, SshTargetRef):
            raise ValueError("target verify-health requires an ssh:// target")
        profile_sha256 = canonical_json_sha256(target_ref.model_dump(mode="json"))
        profile_path = TargetProfileStore(settings.rolo_config_dir).path_for(robot_id)
        if profile_path.is_file():
            profile = TargetProfileStore(settings.rolo_config_dir).load(robot_id)
            if profile.target != target_ref:
                raise ValueError("target verify-health does not match the stored target profile")
            if profile.host_key is None or profile.host_key.status != "APPROVED":
                raise ValueError("target verify-health requires an approved SSH host key")
            profile_sha256 = canonical_json_sha256(profile.model_dump(mode="json"))
        report = SshTargetHealthProvider(
            target_ref,
            known_hosts=known_hosts,
            profile_sha256=profile_sha256,
            package_id=package_id,
            package_version=package_version,
        ).run(settings.rolo_artifact_dir, robot_id=robot_id)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(report)
    if report.status != "PASS":
        raise typer.Exit(code=2)


@target_app.command("bootstrap-plan")
def target_bootstrap_plan(
    target: Annotated[str, typer.Argument(help="Local path or ssh:// workspace URI")],
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Explicit pinned SSH known_hosts file"),
    ] = None,
    identity_file: Annotated[
        Path | None,
        typer.Option("--identity-file", help="Pinned SSH private key; never a password"),
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
        plan = _target_executor(target, known_hosts, timeout, identity_file).plan_bootstrap()
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


@target_app.command("bootstrap-plan-profile")
def target_bootstrap_plan_profile(
    profile: Annotated[str, typer.Option("--profile", "--robot", help="Enrolled target profile")],
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0, help="Connection timeout in seconds"),
    ] = 10.0,
) -> None:
    """Plan bootstrap for an enrolled target using its pinned transport."""
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


@target_app.command("bootstrap-execute")
def target_bootstrap_execute(
    plan_file: Annotated[Path, typer.Argument(help="Approval-required plan JSON")],
    request_file: Annotated[Path, typer.Argument(help="Pending approval request JSON")],
    decision_file: Annotated[Path, typer.Argument(help="Approved decision JSON")],
    manifest_file: Annotated[Path, typer.Option("--manifest")],
    package_file: Annotated[Path, typer.Option("--package")],
    verification_key_file: Annotated[Path, typer.Option("--verification-key-file")],
    known_hosts: Annotated[Path, typer.Option("--known-hosts")],
    execute: Annotated[
        bool,
        typer.Option("--execute/--plan-only", help="Perform approved remote mutation"),
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=600.0)] = 60.0,
) -> None:
    """Validate an approved bootstrap, or explicitly execute it through fixed SSH argv."""
    try:
        plan = TargetBootstrapPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
        request = BootstrapApprovalRequest.model_validate_json(
            request_file.read_text(encoding="utf-8")
        )
        decision = BootstrapApprovalDecision.model_validate_json(
            decision_file.read_text(encoding="utf-8")
        )
        if not isinstance(plan.target, SshTargetRef):
            raise ValueError("bootstrap execution requires an SSH target")
        if not execute:
            emit(
                {
                    "status": "BOOTSTRAP_EXECUTION_READY",
                    "plan_sha256": request.plan_sha256,
                    "approval_request_id": request.request_id,
                    "target": plan.target.model_dump(mode="json"),
                    "mutation_started": False,
                }
            )
            return
        if sys.stdin.isatty() and not typer.confirm(
            "This will mutate the approved target and install Rolo. Continue?",
            default=False,
        ):
            emit({"status": "CANCELLED", "mutation_started": False})
            return
        known_hosts, verification_key_file = validate_bootstrap_security(
            known_hosts, verification_key_file
        )
        verification_key = verification_key_file.read_bytes()
        transport = SubprocessBootstrapTransport(plan.target, known_hosts=known_hosts)
        job, result = run_bootstrap_job(
            _job_store(),
            plan,
            request,
            decision,
            manifest_path=manifest_file,
            package_path=package_file,
            verification_key=verification_key,
            transport=transport,
            timeout_s=timeout,
            rollback_on_failure=True,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "BOOTSTRAP_EXECUTED", "job_id": job.job_id, "result": result})
    if result.status == "FAILED":
        raise typer.Exit(code=2)


@target_app.command("companion-build")
def target_companion_build(
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    package_version: Annotated[str, typer.Option("--version")],
    architecture: Annotated[str, typer.Option("--architecture")],
    publisher_id: Annotated[str, typer.Option("--publisher")],
    verification_key_file: Annotated[Path, typer.Option("--verification-key-file")],
) -> None:
    """Build and sign the minimal target companion package offline."""
    try:
        package, manifest, signed = build_companion_package(
            output_dir,
            package_version=package_version,
            architecture=architecture,
            publisher_id=publisher_id,
            verification_key=verification_key_file.read_bytes(),
        )
        verification = verify_companion_manifest(
            manifest, package, verification_key=verification_key_file.read_bytes()
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "COMPANION_BUILT",
            "package": str(package),
            "manifest": str(manifest),
            "verification": verification.model_dump(mode="json"),
            "publisher_id": signed.publisher_id,
        }
    )


@target_app.command("companion-verify")
def target_companion_verify(
    manifest_file: Annotated[Path, typer.Argument(help="Signed manifest JSON")],
    package_file: Annotated[Path, typer.Argument(help="Companion package")],
    verification_key_file: Annotated[Path, typer.Option("--verification-key-file")],
    policy_file: Annotated[Path | None, typer.Option("--policy")] = None,
) -> None:
    """Verify a companion package against its publisher key and revocation policy."""
    try:
        policy = (
            CompanionReleasePolicy.model_validate_json(
                policy_file.read_text(encoding="utf-8")
            )
            if policy_file
            else None
        )
        result = verify_companion_manifest(
            manifest_file,
            package_file,
            verification_key=verification_key_file.read_bytes(),
            release_policy=policy,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "COMPANION_VERIFIED", "verification": result.model_dump(mode="json")})


@target_app.command("export-device-hardening")
def export_device_hardening(
    target_id: Annotated[str, typer.Option("--target-id", help="Producer-owned target profile")],
    release_line: Annotated[str, typer.Option("--release-line", help="Rolo release line")],
    output: Annotated[Path, typer.Option("--output", help="Sanitized bundle output path")],
    rolo_revision: Annotated[str | None, typer.Option("--rolo-revision")] = None,
    evidence_input: Annotated[
        Path | None, typer.Option("--evidence-input", help="Audited external evidence JSON")
    ] = None,
    ledger_output: Annotated[
        Path | None, typer.Option("--ledger-output", help="Optional release ledger output")
    ] = None,
) -> None:
    """Export a sanitized device-hardening bundle for rolo-vis."""
    import subprocess

    revision = rolo_revision
    if revision is None:
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parents[2],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise typer.BadParameter("--rolo-revision is required outside a git checkout") from exc
    try:
        bundle = build_device_hardening_bundle(
            get_settings().rolo_config_dir,
            target_id=target_id,
            release_line=release_line,
            rolo_revision=revision,
            evidence_input=evidence_input,
        )
        bundle_path, ledger_path = write_device_hardening_bundle(
            bundle, output, ledger_output=ledger_output
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "PENDING_EXTERNAL"
            if any(item.status == "PENDING_EXTERNAL" for item in bundle.evidence)
            else "READY_FOR_REVIEW",
            "bundle": str(bundle_path),
            "ledger": str(ledger_path) if ledger_path else None,
            "target_id": bundle.target_id,
            "producer_revision": bundle.producer_revision,
        }
    )


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


@app.command("probe")
def probe(
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
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Local source/workspace root used with an ssh:// target",
        ),
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
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm/--no-confirm",
            help="Explicitly authorize Agent execution and local artifact writes",
        ),
    ] = False,
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
    """Run the shortest safe Probe journey for TARGET."""
    if run_agent and not confirm:
        if sys.stdin.isatty():
            confirm = typer.confirm(
                "Adapt may install/use the configured Agent and write evidence artifacts. "
                "Continue?",
                default=False,
            )
        if not confirm:
            emit(
                {
                    "status": "AUTHORIZATION_REQUIRED",
                    "scope": "adapt.run",
                    "reason": (
                        "Agent execution and artifact publication require explicit confirmation"
                    ),
                    "mutation_started": False,
                    "resume": "rolo adapt ... --confirm",
                }
            )
            raise typer.Exit(code=2)
    try:
        target_ref = parse_target_ref(target)
        if isinstance(target_ref, LocalTargetRef):
            if project_root is not None:
                raise ValueError("--project-root is only valid with an ssh:// target")
            adapt_project_root = target_ref.workspace
            evidence_mode = EvidenceDeploymentMode.LOCAL
        else:
            if project_root is None:
                raise ValueError(
                    "SSH Adapt requires --project-root for the local source workspace"
                )
            deployment_path = (
                get_settings().rolo_config_dir / "target-evidence" / f"{robot_id}.json"
            )
            if not deployment_path.is_file():
                raise ValueError(
                    "SSH Adapt requires an approved target evidence deployment; "
                    "run target-evidence configure first"
                )
            deployment = load_deployment(deployment_path)
            if deployment.mode != EvidenceDeploymentMode.REMOTE:
                raise ValueError("approved target evidence deployment is not remote")
            expected_target = (
                f"{target_ref.user}@{target_ref.host}" if target_ref.user else target_ref.host
            )
            if deployment.ssh_target != expected_target:
                raise ValueError("SSH target does not match the approved evidence deployment")
            expected_port = target_ref.port or 22
            if deployment.ssh_port != expected_port:
                raise ValueError("SSH target port does not match the approved evidence deployment")
            adapt_project_root = project_root.expanduser().resolve()
            evidence_mode = EvidenceDeploymentMode.REMOTE
        result = run_adapt_start(
            robot_id=robot_id,
            project_root=adapt_project_root,
            urdf=urdf,
            active_probe=active_probe,
            run_agent=run_agent,
            scratch_root=scratch_root,
            timeout=timeout,
            evidence_mode=evidence_mode,
            allow_executable=allow_executable,
            collector_descriptor=None,
            verification_secret=None,
            ssh_target=None,
            known_hosts=None,
            collector_config=".rolo/config/target-evidence-collector.json",
            evidence_timeout=evidence_timeout,
            on_output=_stream_agent_output,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)
    if result.status in {"BLOCKED", "WAITING_FOR_AUTH"}:
        raise typer.Exit(code=2)


@app.command("agent-providers")
def agent_providers() -> None:
    """List registered Agent executors and the active secret-free selection."""
    settings = get_settings()
    emit(
        {
            "executors": list(available_agent_executors()),
            "selection": coding_agent_config(settings).model_dump(mode="json"),
            "entry_point_group": "rolo.agent_executors",
        }
    )
