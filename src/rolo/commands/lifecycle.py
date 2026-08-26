from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.commands.discovery import configured_discovery_service
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings, prepare_runtime_directories
from rolo.core.models import ProbeResult
from rolo.runtime import create_runtime
from rolo.stages.adapt.acceptance import write_adapt_acceptance_pack
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.journey import (
    AdaptJourneyService,
    ProjectEvidence,
    TargetEvidenceJourneySummary,
    TargetEvidenceV4Deployment,
    detect_project_evidence,
)
from rolo.stages.adapt.ros_environment import select_ros_setup_files
from rolo.stages.adapt.service import (
    AdaptRunService,
    coding_agent_config,
)
from rolo.stages.adapt.slice_observability import build_slice_stability_report
from rolo.stages.adapt.target_evidence import (
    CollectorDescriptor,
    EvidenceDeploymentMode,
    configure_deployment,
    ensure_local_deployment,
    load_deployment,
)
from rolo.stages.contracts import StageName
from rolo.stages.pipeline import assess_pipeline, assess_stage
from rolo.targets import (
    AdaptStartParameters,
    ApplicationCommandBus,
    CollectorEnrollmentPinRegistry,
    CommandEnvelope,
    CommandExecution,
    CredentialPurpose,
    CredentialResolver,
    DeploymentCommand,
    DeploymentCommandKind,
    FileCredentialProvider,
    InteractionSurface,
    TargetProfileRegistry,
    TargetTransport,
    build_adapt_start_envelope,
    file_credential_reference,
    render_adapt_start_cli,
    target_executor_for_profile,
)

adapt_stage_app = typer.Typer(
    help="Stage 1: discover, adapt, conform, and publish the canonical control surface."
)
diagnose_stage_app = typer.Typer(help="Stage 2: diagnose and tune within user constraints.")
verify_stage_app = typer.Typer(help="Stage 3: optionally verify acceptance and regression.")
enroll_app = typer.Typer(help="Inspect the robot identity owned by this installation.")
adapt_stage_app.add_typer(enroll_app, name="enroll")


def run_adapt_start_parameters(
    *,
    command: DeploymentCommand,
    parameters: AdaptStartParameters,
    settings: object,
    project_evidence: ProjectEvidence | None = None,
    target_application_probe: ProbeResult | None = None,
    target_runtime_probes: dict[str, ProbeResult] | None = None,
    target_runtime_evidence: TargetEvidenceJourneySummary | None = None,
) -> object:
    from rolo.core.config import Settings

    if not isinstance(settings, Settings):
        raise TypeError("adapt command requires Settings")
    parameters.validate_command(command)
    active_probe = ActiveProbeMode(command.active_probe)
    evidence_mode = EvidenceDeploymentMode(parameters.evidence_mode)
    project_root = Path(parameters.project_root)
    urdf = Path(parameters.urdf_path) if parameters.urdf_path is not None else None
    scratch_root = (
        Path(parameters.scratch_root) if parameters.scratch_root is not None else None
    )
    allow_executable = [Path(path) for path in parameters.allowed_executables]
    collector_descriptor = (
        Path(parameters.collector_descriptor_path)
        if parameters.collector_descriptor_path is not None
        else None
    )
    verification_secret = None
    if parameters.verification_secret_ref is not None:
        credential = CredentialResolver((FileCredentialProvider(),)).resolve(
            parameters.verification_secret_ref,
            purpose=CredentialPurpose.LEGACY_COLLECTOR_VERIFICATION,
        )
        verification_secret = credential.secret_path
    known_hosts = (
        Path(parameters.known_hosts_path)
        if parameters.known_hosts_path is not None
        else None
    )

    prepare_runtime_directories(settings)
    if project_evidence is None:
        evidence = detect_project_evidence(project_root)
    else:
        if project_evidence.observation_mode != "TARGET_METADATA":
            raise ValueError("precomputed project evidence must be target metadata")
        if parameters.project_root_location != "TARGET":
            raise ValueError("target project evidence requires a target-located root")
        if project_evidence.target_project_root != parameters.project_root:
            raise ValueError("target project evidence root differs from Adapt parameters")
        evidence = project_evidence
    evidence_deployment = None
    evidence_v4_deployment = None
    remote_options = (
        collector_descriptor,
        verification_secret,
        parameters.ssh_target,
        known_hosts,
    )
    if target_runtime_probes is not None or target_runtime_evidence is not None:
        if target_runtime_probes is None or target_runtime_evidence is None:
            raise ValueError(
                "preverified target runtime evidence requires probes and summary together"
            )
        if active_probe != ActiveProbeMode.RUNTIME_READONLY:
            raise ValueError(
                "preverified target runtime evidence requires active_probe=runtime-readonly"
            )
        if allow_executable or any(value is not None for value in remote_options):
            raise ValueError(
                "preverified target runtime evidence does not accept collection options"
            )
    elif active_probe == ActiveProbeMode.RUNTIME_READONLY:
        profile_registry = TargetProfileRegistry(settings.target_profile_dir)
        enrollment_pin = CollectorEnrollmentPinRegistry(
            settings.target_profile_dir / "enrollment-v4"
        ).get_optional(command.target_id)
        if enrollment_pin is not None:
            if any(value is not None for value in remote_options):
                raise ValueError("v4 target evidence does not accept legacy HMAC options")
            if allow_executable:
                raise ValueError(
                    "v4 executable pins are fixed during target enrollment; rotate the "
                    "collector configuration instead of passing --allow-executable"
                )
            if (
                enrollment_pin.descriptor.target_id != command.target_id
                or enrollment_pin.descriptor.robot_id != command.target_id
            ):
                raise ValueError(
                    "v4 enrollment target/robot identity differs from Adapt target"
                )
            profile = profile_registry.get_target(command.target_id)
            expected_transport = (
                TargetTransport.LOCAL
                if evidence_mode == EvidenceDeploymentMode.LOCAL
                else TargetTransport.SSH
            )
            if profile.transport != expected_transport:
                raise ValueError("v4 evidence mode differs from registered target transport")
            evidence_v4_deployment = TargetEvidenceV4Deployment(
                mode=evidence_mode,
                pin=enrollment_pin,
                executor=target_executor_for_profile(
                    profile,
                    registry=profile_registry,
                    credential_resolver=CredentialResolver((FileCredentialProvider(),)),
                    credential_purpose=CredentialPurpose.SSH_RUNTIME,
                ),
            )
        elif evidence_mode == EvidenceDeploymentMode.LOCAL:
            if any(value is not None for value in remote_options):
                raise ValueError("local evidence mode does not accept remote collector options")
            _, ros_setup_files = select_ros_setup_files(
                auto_source=settings.ros_auto_source,
                configured=settings.ros_setup_files,
                project_root=evidence.project_root,
                install_roots=evidence.install_roots,
            )
            evidence_deployment, _ = ensure_local_deployment(
                robot_id=command.target_id,
                config_root=settings.rolo_config_dir,
                help_executables=allow_executable,
                ros_setup_files=ros_setup_files,
            )
        else:
            if allow_executable:
                raise ValueError(
                    "remote executable allowlists must be established on the target collector"
                )
            deployment_path = (
                settings.rolo_config_dir / "target-evidence" / f"{command.target_id}.json"
            )
            if deployment_path.is_file() and not any(
                value is not None for value in remote_options
            ):
                evidence_deployment = load_deployment(deployment_path)
                if evidence_deployment.mode != EvidenceDeploymentMode.REMOTE:
                    raise ValueError("existing target evidence deployment is not remote")
            else:
                if not all(value is not None for value in remote_options):
                    raise ValueError(
                        "remote evidence mode requires an existing deployment or "
                        "--collector-descriptor, --verification-secret, --ssh-target, "
                        "and --known-hosts"
                    )
                if collector_descriptor is None or verification_secret is None:
                    raise ValueError("remote collector credential references did not resolve")
                descriptor = CollectorDescriptor.model_validate_json(
                    collector_descriptor.read_text(encoding="utf-8")
                )
                evidence_deployment = configure_deployment(
                    robot_id=command.target_id,
                    mode=EvidenceDeploymentMode.REMOTE,
                    descriptor=descriptor,
                    verification_secret_path=verification_secret,
                    output_path=deployment_path,
                    ssh_target=parameters.ssh_target,
                    known_hosts_path=known_hosts,
                    collector_config=parameters.collector_config,
                )
    elif (
        evidence_mode == EvidenceDeploymentMode.REMOTE
        and project_evidence is None
    ) or allow_executable or any(value is not None for value in remote_options):
        raise ValueError("target evidence options require --active-probe runtime-readonly")
    return AdaptJourneyService(
        settings,
        configured_discovery_service(
            settings,
            ArtifactStore(settings.rolo_artifact_dir),
        ),
    ).start(
        robot_id=command.target_id,
        evidence=evidence,
        urdf_path=urdf,
        active_probe=active_probe,
        run_agent=command.run_adapter_agent,
        scratch_root=scratch_root if scratch_root is not None else settings.rolo_scratch_dir,
        timeout_s=parameters.timeout_s,
        evidence_deployment=evidence_deployment,
        evidence_v4_deployment=evidence_v4_deployment,
        evidence_timeout_s=parameters.evidence_timeout_s,
        target_application_probe=target_application_probe,
        preverified_target_probes=target_runtime_probes,
        preverified_target_evidence=target_runtime_evidence,
    )


def _run_adapt_start(
    envelope: CommandEnvelope,
    *,
    settings: object,
) -> object:
    if not isinstance(envelope.parameters, AdaptStartParameters):
        raise ValueError("ADAPT command requires AdaptStartParameters")
    return run_adapt_start_parameters(
        command=envelope.command,
        parameters=envelope.parameters,
        settings=settings,
    )


def execute_adapt_start_command(
    *,
    target_id: str,
    parameters: AdaptStartParameters,
    active_probe: ActiveProbeMode = ActiveProbeMode.RUNTIME_READONLY,
    run_adapter_agent: bool = True,
    requested_by: str = "local-user",
    interaction_surface: InteractionSurface = InteractionSurface.CLI,
    settings: object | None = None,
) -> CommandExecution:
    selected_settings = settings or get_settings()
    envelope = build_adapt_start_envelope(
        target_id=target_id,
        parameters=parameters,
        active_probe=active_probe.value,
        run_adapter_agent=run_adapter_agent,
        requested_by=requested_by,
        interaction_surface=interaction_surface,
    )
    bus = ApplicationCommandBus()
    bus.register(
        DeploymentCommandKind.ADAPT,
        lambda item: _run_adapt_start(item, settings=selected_settings),
        renderer=render_adapt_start_cli,
    )
    return bus.dispatch(envelope)


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
    collector_config: Annotated[
        str,
        typer.Option("--collector-config", help="Collector state path on the remote target"),
    ] = ".rolo/config/target-evidence-collector.json",
    evidence_timeout: Annotated[
        float,
        typer.Option("--evidence-timeout", min=1.0, max=300.0),
    ] = 45.0,
) -> None:
    """Run the shortest safe path from a robot project to an Adapt release."""
    settings = get_settings()
    try:
        parameters = AdaptStartParameters(
            project_root=str((project_root or Path.cwd()).expanduser().resolve()),
            urdf_path=str(urdf.expanduser().resolve()) if urdf is not None else None,
            scratch_root=(
                str(scratch_root.expanduser().resolve()) if scratch_root is not None else None
            ),
            timeout_s=timeout or settings.coding_agent_timeout_s,
            evidence_mode=evidence_mode.value,
            allowed_executables=[
                str(path.expanduser().resolve()) for path in (allow_executable or [])
            ],
            collector_descriptor_path=(
                str(collector_descriptor.expanduser().resolve())
                if collector_descriptor is not None
                else None
            ),
            verification_secret_ref=(
                file_credential_reference(verification_secret)
                if verification_secret is not None
                else None
            ),
            ssh_target=ssh_target,
            known_hosts_path=(
                str(known_hosts.expanduser().resolve()) if known_hosts is not None else None
            ),
            collector_config=collector_config,
            evidence_timeout_s=evidence_timeout,
        )
        execution = execute_adapt_start_command(
            target_id=robot_id,
            parameters=parameters,
            active_probe=active_probe,
            run_adapter_agent=run_agent,
            settings=settings,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    result = execution.result
    emit(result)
    if getattr(result, "status", None) == "BLOCKED":
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
