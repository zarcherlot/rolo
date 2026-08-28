from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.discovery import configured_discovery_service
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings, prepare_runtime_directories
from rolo.runtime import create_runtime
from rolo.stages.adapt.acceptance import write_adapt_acceptance_pack
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.journey import (
    AdaptJourneyResult,
    AdaptJourneyService,
    detect_project_evidence,
)
from rolo.stages.adapt.ros_environment import select_ros_setup_files
from rolo.stages.adapt.service import (
    AdaptRunService,
    coding_agent_config,
)
from rolo.stages.adapt.shadow_observation import build_capability_shadow_stability_report
from rolo.stages.adapt.slice_observability import build_slice_stability_report
from rolo.stages.adapt.target_evidence import (
    CollectorDescriptor,
    EvidenceDeploymentMode,
    configure_deployment,
    ensure_local_deployment,
    load_deployment,
)
from rolo.stages.contracts import StageName
from rolo.stages.diagnose.service import build_diagnosis_task
from rolo.stages.downstream import DownstreamStageService
from rolo.stages.pipeline import assess_pipeline, assess_stage
from rolo.stages.verify.acceptance import VerificationPlan
from rolo.stages.verify.service import build_verification_task, publish_verification_plan

adapt_stage_app = typer.Typer(
    help="Stage 1: discover, adapt, conform, and publish the canonical control surface."
)
diagnose_stage_app = typer.Typer(help="Stage 2: diagnose and tune within user constraints.")
verify_stage_app = typer.Typer(help="Stage 3: optionally verify acceptance and regression.")
enroll_app = typer.Typer(help="Inspect the robot identity owned by this installation.")
adapt_stage_app.add_typer(enroll_app, name="enroll")


def run_adapt_start(
    *,
    robot_id: str,
    project_root: Path | None,
    urdf: Path | None,
    active_probe: ActiveProbeMode,
    run_agent: bool,
    scratch_root: Path | None,
    timeout: int | None,
    evidence_mode: EvidenceDeploymentMode,
    allow_executable: list[Path] | None,
    collector_descriptor: Path | None,
    verification_secret: Path | None,
    ssh_target: str | None,
    known_hosts: Path | None,
    collector_config: str,
    evidence_timeout: float,
    collector_executable: str | None = None,
    ssh_port: int | None = None,
    ssh_identity_file: Path | None = None,
    evidence_attempts: int = 2,
    on_output: Callable[[str, str], None] | None = None,
) -> AdaptJourneyResult:
    """Run the shared Adapt start application service used by product and expert CLIs."""
    settings = get_settings()
    prepare_runtime_directories(settings)
    evidence = detect_project_evidence(project_root or Path.cwd())
    evidence_deployment = None
    remote_options = (
        collector_descriptor,
        verification_secret,
        ssh_target,
        known_hosts,
    )
    if active_probe == ActiveProbeMode.RUNTIME_READONLY:
        if evidence_mode == EvidenceDeploymentMode.LOCAL:
            if (
                collector_executable is not None
                or ssh_port is not None
                or ssh_identity_file is not None
                or any(value is not None for value in remote_options)
            ):
                raise ValueError("local evidence mode does not accept remote collector options")
            _, ros_setup_files = select_ros_setup_files(
                auto_source=settings.ros_auto_source,
                configured=settings.ros_setup_files,
                project_root=evidence.project_root,
                install_roots=evidence.install_roots,
            )
            evidence_deployment, _ = ensure_local_deployment(
                robot_id=robot_id,
                config_root=settings.rolo_config_dir,
                help_executables=allow_executable or (),
                ros_setup_files=ros_setup_files,
            )
        else:
            if allow_executable:
                raise ValueError(
                    "remote executable allowlists must be established on the target collector"
                )
            deployment_path = settings.rolo_config_dir / "target-evidence" / f"{robot_id}.json"
            if deployment_path.is_file() and not any(
                value is not None for value in remote_options
            ):
                evidence_deployment = load_deployment(deployment_path)
                if evidence_deployment.mode != EvidenceDeploymentMode.REMOTE:
                    raise ValueError("existing target evidence deployment is not remote")
                if (
                    collector_executable is not None
                    and collector_executable != evidence_deployment.collector_executable
                ):
                    raise ValueError(
                        "target collector executable is already pinned; use explicit "
                        "re-enrollment to change it"
                    )
                if ssh_port is not None and ssh_port != evidence_deployment.ssh_port:
                    raise ValueError(
                        "SSH port is already pinned; use explicit re-enrollment to change it"
                    )
                if ssh_identity_file is not None and str(
                    ssh_identity_file.expanduser().resolve()
                ) != evidence_deployment.ssh_identity_file:
                    raise ValueError(
                        "SSH identity is already pinned; use explicit re-enrollment to change it"
                    )
            else:
                if not all(value is not None for value in remote_options):
                    raise ValueError(
                        "remote evidence mode requires an existing deployment or "
                        "--collector-descriptor, --verification-secret, --ssh-target, "
                        "and --known-hosts"
                    )
                descriptor = CollectorDescriptor.model_validate_json(
                    collector_descriptor.read_text(encoding="utf-8")
                )
                evidence_deployment = configure_deployment(
                    robot_id=robot_id,
                    mode=EvidenceDeploymentMode.REMOTE,
                    descriptor=descriptor,
                    verification_secret_path=verification_secret,
                    output_path=deployment_path,
                    ssh_target=ssh_target,
                    known_hosts_path=known_hosts,
                    ssh_port=ssh_port,
                    ssh_identity_file=ssh_identity_file,
                    collector_config=collector_config,
                    collector_executable=collector_executable or "robotctl",
                )
    elif (
        evidence_mode == EvidenceDeploymentMode.REMOTE
        or allow_executable
        or collector_executable is not None
        or ssh_port is not None
        or ssh_identity_file is not None
        or any(value is not None for value in remote_options)
    ):
        raise ValueError("target evidence options require --active-probe runtime-readonly")
    return AdaptJourneyService(
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
        scratch_root=scratch_root if scratch_root is not None else settings.rolo_scratch_dir,
        timeout_s=timeout or settings.coding_agent_timeout_s,
        evidence_deployment=evidence_deployment,
        evidence_timeout_s=evidence_timeout,
        evidence_max_attempts=evidence_attempts,
        on_output=on_output,
    )


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
    evidence_mode: Annotated[
        EvidenceDeploymentMode,
        typer.Option(
            "--evidence-mode",
            help="local collects signed evidence here; remote uses a pinned SSH collector",
        ),
    ] = EvidenceDeploymentMode.LOCAL,
    allow_executable: Annotated[
        list[Path] | None,
        typer.Option(
            "--allow-executable",
            help="Local target executable permitted for bounded --help evidence; repeatable",
        ),
    ] = None,
    collector_descriptor: Annotated[
        Path | None,
        typer.Option("--collector-descriptor", help="Remote collector descriptor JSON"),
    ] = None,
    verification_secret: Annotated[
        Path | None,
        typer.Option("--verification-secret", help="Remotely provisioned collector secret"),
    ] = None,
    ssh_target: Annotated[str | None, typer.Option("--ssh-target")] = None,
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Pinned SSH known_hosts file"),
    ] = None,
    ssh_port: Annotated[int | None, typer.Option("--ssh-port", min=1, max=65535)] = None,
    ssh_identity_file: Annotated[
        Path | None,
        typer.Option("--ssh-identity-file", help="Pinned controller-side SSH private key"),
    ] = None,
    collector_config: Annotated[
        str,
        typer.Option("--collector-config", help="Collector state path on the remote target"),
    ] = ".rolo/config/target-evidence-collector.json",
    collector_executable: Annotated[
        str | None,
        typer.Option(
            "--collector-executable",
            help="Pinned robotctl executable name or absolute path on the remote target",
        ),
    ] = None,
    evidence_timeout: Annotated[
        float,
        typer.Option("--evidence-timeout", min=1.0, max=300.0),
    ] = 45.0,
    evidence_attempts: Annotated[
        int,
        typer.Option("--evidence-attempts", min=1, max=3),
    ] = 2,
) -> None:
    """Run the shortest safe path from a robot project to an Adapt release."""
    try:
        result = run_adapt_start(
            robot_id=robot_id,
            project_root=project_root,
            urdf=urdf,
            active_probe=active_probe,
            run_agent=run_agent,
            scratch_root=scratch_root,
            timeout=timeout,
            evidence_mode=evidence_mode,
            allow_executable=allow_executable,
            collector_descriptor=collector_descriptor,
            verification_secret=verification_secret,
            ssh_target=ssh_target,
            known_hosts=known_hosts,
            collector_config=collector_config,
            evidence_timeout=evidence_timeout,
            collector_executable=collector_executable,
            ssh_port=ssh_port,
            ssh_identity_file=ssh_identity_file,
            evidence_attempts=evidence_attempts,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)
    if result.status in {"BLOCKED", "WAITING_FOR_AUTH"}:
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
            scratch_root=scratch_root if scratch_root is not None else settings.rolo_scratch_dir,
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


@adapt_stage_app.command("capability-observability")
def adapt_capability_observability(
    robot: Annotated[str, typer.Option("--robot")],
    max_runs: Annotated[int, typer.Option("--max-runs", min=1, max=500)] = 50,
) -> None:
    """Read capability-resolution shadow stability without changing release authority."""
    settings = get_settings()
    try:
        report = build_capability_shadow_stability_report(
            settings.rolo_artifact_dir,
            robot,
            max_runs=max_runs,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(report)


@adapt_stage_app.command("acceptance-pack")
def adapt_acceptance_pack(
    robot: Annotated[str, typer.Option("--robot")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Optional destination for the secret-free Adapt acceptance JSON",
        ),
    ] = None,
) -> None:
    """Export a secret-free, digest-bound snapshot for real-device Adapt review."""
    settings = get_settings()
    try:
        pack, path, digest = write_adapt_acceptance_pack(
            settings.rolo_artifact_dir,
            settings.rolo_output_dir,
            robot,
            output,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "pack": pack.model_dump(mode="json"),
            "artifact": str(path),
            "sha256": digest,
        }
    )


@diagnose_stage_app.command("status")
def diagnose_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show the closed-loop diagnosis and tuning gate."""
    emit_stage_status(StageName.DIAGNOSE, robot)


@diagnose_stage_app.command("plan")
def diagnose_stage_plan(
    robot: Annotated[str, typer.Option("--robot")],
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    executor: Annotated[str | None, typer.Option("--executor")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
) -> None:
    """Build a provider-neutral Diagnose Agent task without executing it."""
    settings = get_settings()
    try:
        task = build_diagnosis_task(
            settings.rolo_artifact_dir,
            robot,
            provider=provider or settings.coding_agent_provider,
            executor=executor or settings.coding_agent_executor,
            model=model if model is not None else settings.coding_agent_model,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(task)


@diagnose_stage_app.command("run")
def diagnose_stage_run(
    robot: Annotated[str, typer.Option("--robot")],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Explicitly authorize this Agent execution")
    ] = False,
    authorization_ref: Annotated[
        str | None,
        typer.Option("--authorization-ref", help="Resume a pending artifact authorization request"),
    ] = None,
) -> None:
    """Execute a provider-neutral Diagnose Agent and validate its handoff."""
    if sys.stdin.isatty() and not confirm:
        confirm = typer.confirm(
            "Diagnose may invoke the configured Agent and write frozen artifacts. Continue?",
            default=False,
        )
    try:
        run = DownstreamStageService(get_settings(), "diagnose").run(
            robot,
            confirmed=confirm,
            authorization_ref=authorization_ref,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(run)
    if run.status in {"WAITING_FOR_AUTH", "FAILED"}:
        raise typer.Exit(code=2)


@verify_stage_app.command("status")
def verify_stage_status(robot: Annotated[str, typer.Option("--robot")]) -> None:
    """Show optional autonomous verification readiness."""
    emit_stage_status(StageName.VERIFY, robot)


@verify_stage_app.command("plan")
def verify_stage_plan(
    robot: Annotated[str, typer.Option("--robot")],
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    executor: Annotated[str | None, typer.Option("--executor")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
) -> None:
    """Build a provider-neutral Verify Agent task without executing it."""
    settings = get_settings()
    try:
        task = build_verification_task(
            settings.rolo_artifact_dir,
            robot,
            provider=provider or settings.coding_agent_provider,
            executor=executor or settings.coding_agent_executor,
            model=model if model is not None else settings.coding_agent_model,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(task)


@verify_stage_app.command("acceptance-plan")
def verify_acceptance_plan(
    robot: Annotated[str, typer.Option("--robot")],
    plan_file: Annotated[Path, typer.Option("--plan-file", exists=True, readable=True)],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Explicitly publish this acceptance plan")
    ] = False,
) -> None:
    """Validate and publish a bounded, read-only Verify acceptance plan."""
    if sys.stdin.isatty() and not confirm:
        confirm = typer.confirm(
            "Publish this acceptance plan for Verify?",
            default=False,
        )
    if not confirm:
        emit({"status": "CANCELLED", "mutation_started": False})
        return
    settings = get_settings()
    try:
        plan = VerificationPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
        reference = publish_verification_plan(settings.rolo_artifact_dir, robot, plan)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit({"status": "PUBLISHED", "robot_id": robot, "plan_ref": reference})


@verify_stage_app.command("run")
def verify_stage_run(
    robot: Annotated[str, typer.Option("--robot")],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Explicitly authorize this Agent execution")
    ] = False,
    authorization_ref: Annotated[
        str | None,
        typer.Option("--authorization-ref", help="Resume a pending artifact authorization request"),
    ] = None,
) -> None:
    """Execute a provider-neutral Verify Agent and validate its handoff."""
    if sys.stdin.isatty() and not confirm:
        confirm = typer.confirm(
            "Verify may run declared regression checks and write evidence. Continue?",
            default=False,
        )
    try:
        run = DownstreamStageService(get_settings(), "verify").run(
            robot,
            confirmed=confirm,
            authorization_ref=authorization_ref,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(run)
    if run.status in {"WAITING_FOR_AUTH", "FAILED"}:
        raise typer.Exit(code=2)


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
