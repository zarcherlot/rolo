from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.targets import (
    ApplicationCommandBus,
    ApprovalStatus,
    CodexSessionAgentProvider,
    CollectorConfigurationDiscoveryV4,
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    CommandEnvelope,
    CredentialResolver,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentEventPage,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentJobSubmission,
    Ed25519TargetPackageVerifier,
    FileCredentialProvider,
    InteractionSurface,
    OrchestratorPlacement,
    SessionAgentBroker,
    SessionAgentProductionReadinessReport,
    SessionAgentRuntime,
    SessionAgentSessionStore,
    SessionAgentSubject,
    SessionAgentTurnRequest,
    TargetAdaptJobRunner,
    TargetAdaptJobSpecStore,
    TargetAdaptJobSubmission,
    TargetAdaptJobSubmissionService,
    TargetArchitecture,
    TargetBootstrapJobRunner,
    TargetBootstrapJobSpecStore,
    TargetBootstrapJobSubmission,
    TargetBootstrapJobSubmissionIntentStore,
    TargetBootstrapPlanner,
    TargetBootstrapPublicSubmissionService,
    TargetCapabilityDetectionError,
    TargetConnectionAssessmentSubmission,
    TargetConnectionProfile,
    TargetDeploymentJobRunner,
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetExecutionStatus,
    TargetHostProvisioningJobRunner,
    TargetHostProvisioningJobSpecStore,
    TargetHostProvisioningJobSubmission,
    TargetHostProvisioningPlan,
    TargetHostProvisioningSubmissionIntentStore,
    TargetHostProvisioningSubmissionService,
    TargetHostReconciliationJobRunner,
    TargetHostReconciliationJobSpecStore,
    TargetHostReconciliationJobSubmission,
    TargetHostReconciliationSubmissionIntentStore,
    TargetHostReconciliationSubmissionService,
    TargetHostRollbackJobSubmission,
    TargetHostRollbackSubmissionIntentStore,
    TargetHostRollbackSubmissionService,
    TargetHostServiceJobRunner,
    TargetHostServiceJobSpecStore,
    TargetHostServiceJobSubmission,
    TargetHostServiceReconciliationJobRunner,
    TargetHostServiceReconciliationJobSpecStore,
    TargetHostServiceReconciliationJobSubmission,
    TargetHostServiceReconciliationSubmissionIntentStore,
    TargetHostServiceReconciliationSubmissionService,
    TargetHostServiceSubmissionIntentStore,
    TargetHostServiceSubmissionService,
    TargetPackageRegistry,
    TargetProfile,
    TargetProfileRegistry,
    TargetProjectEvidenceArtifactStore,
    TargetProjectEvidenceIntentStore,
    TargetProjectEvidenceJobRunner,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceJobSubmission,
    TargetProjectEvidenceSubmissionService,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetRuntimeEvidenceArtifactStore,
    TargetRuntimeEvidenceIntentStore,
    TargetRuntimeEvidenceJobRunner,
    TargetRuntimeEvidenceJobSpecStore,
    TargetRuntimeEvidenceJobSubmission,
    TargetRuntimeEvidenceSubmissionService,
    TargetRuntimeRollbackIntentStore,
    TargetRuntimeRollbackJobRunner,
    TargetRuntimeRollbackJobSpecStore,
    TargetRuntimeRollbackSubmission,
    TargetRuntimeRollbackSubmissionService,
    TargetSourceDiscoveryArtifactStore,
    TargetSourceDiscoveryIntentStore,
    TargetSourceDiscoveryJobRunner,
    TargetSourceDiscoveryJobSpecStore,
    TargetSourceDiscoveryJobSubmission,
    TargetSourceDiscoverySubmissionService,
    TargetTransport,
    TargetTrustLevel,
    W10AutomatedResult,
    W10RealSshAcceptanceRequest,
    W10RealSshAcceptanceRunner,
    build_deployment_command,
    build_session_agent_production_readiness,
    build_session_agent_tool_catalog,
    build_target_adapt_job_spec,
    build_target_host_provisioning_plan,
    ed25519_public_key_sha256,
    parse_w10_junit_report,
    render_target_deployment_tui,
    resolve_target_adapt_project_evidence_binding,
    resolve_target_adapt_runtime_evidence_binding,
    resolve_target_adapt_source_discovery_binding,
    sanitize_deployment_summary,
    target_connection_binding_sha256,
    target_executor_for_profile,
    w10_acceptance_file_sha256,
    write_w10_real_ssh_acceptance_receipt,
)

target_app = typer.Typer(help="Inspect, bootstrap, and enroll registered local or SSH targets.")
target_bootstrap_app = typer.Typer(help="Plan and execute target runtime bootstrap.")
target_adapt_app = typer.Typer(help="Create and inspect target Adapt jobs.")
target_job_app = typer.Typer(help="Inspect and control persistent deployment jobs.")
target_connect_app = typer.Typer(help="Assess registered target connections.")
target_package_app = typer.Typer(help="Import and inspect verified Controller packages.")
target_approval_app = typer.Typer(help="Decide persistent deployment approvals.")
target_agent_app = typer.Typer(help="Run bounded natural-language deployment sessions.")
target_runtime_app = typer.Typer(help="Control the installed target runtime.")
target_project_evidence_app = typer.Typer(
    help="Submit approval-bound target project evidence observations."
)
target_source_discovery_app = typer.Typer(help="Submit approval-bound target source analysis Jobs.")
target_runtime_evidence_app = typer.Typer(
    help="Submit approval-bound signed target runtime evidence Jobs."
)
target_host_app = typer.Typer(help="Plan privileged target host provisioning.")
target_acceptance_app = typer.Typer(
    help="Collect secret-closed external acceptance evidence without self-signing readiness."
)
target_app.add_typer(target_bootstrap_app, name="bootstrap")
target_app.add_typer(target_adapt_app, name="adapt")
target_app.add_typer(target_job_app, name="job")
target_app.add_typer(target_connect_app, name="connect")
target_app.add_typer(target_package_app, name="package")
target_app.add_typer(target_approval_app, name="approval")
target_app.add_typer(target_agent_app, name="agent")
target_app.add_typer(target_runtime_app, name="runtime")
target_app.add_typer(target_project_evidence_app, name="project-evidence")
target_app.add_typer(target_source_discovery_app, name="source-discovery")
target_app.add_typer(target_runtime_evidence_app, name="runtime-evidence")
target_app.add_typer(target_host_app, name="host")
target_app.add_typer(target_acceptance_app, name="acceptance")


def _session_agent_readiness() -> SessionAgentProductionReadinessReport:
    settings = get_settings()
    return build_session_agent_production_readiness(
        enabled=settings.rolo_session_agent_enabled,
        provider_api_key_configured=settings.rolo_session_agent_api_key is not None,
        base_url=settings.rolo_session_agent_base_url,
        executable=settings.rolo_session_agent_executable,
        model=settings.rolo_session_agent_model,
        provider_timeout_s=settings.rolo_session_agent_provider_timeout_s,
        catalog_sha256=build_session_agent_tool_catalog().canonical_sha256(),
    )


def _deployment_job_store() -> DeploymentJobStore:
    return DeploymentJobStore(get_settings().rolo_artifact_dir / "deployment-jobs")


def _target_registration_service() -> TargetRegistrationService:
    settings = get_settings()
    return TargetRegistrationService(TargetProfileRegistry(settings.target_profile_dir))


def _deployment_job_runner() -> TargetDeploymentJobRunner:
    settings = get_settings()
    store = _deployment_job_store()
    registrations = _target_registration_service()
    artifact_root = settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
    bootstrap_runner = TargetBootstrapJobRunner(
        store,
        registrations,
        TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        artifact_root,
    )
    adapt_runner = TargetAdaptJobRunner(
        store,
        registrations,
        TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        artifact_root,
        settings=settings,
        project_evidence_artifacts=TargetProjectEvidenceArtifactStore(artifact_root),
        source_discovery_artifacts=TargetSourceDiscoveryArtifactStore(artifact_root),
        runtime_evidence_artifacts=TargetRuntimeEvidenceArtifactStore(artifact_root),
        collector_pins=CollectorEnrollmentPinRegistry(
            settings.target_profile_dir / "enrollment-v4"
        ),
    )
    return TargetDeploymentJobRunner(
        store,
        registrations,
        artifact_root,
        bootstrap_runner=bootstrap_runner,
        adapt_runner=adapt_runner,
        rollback_runner=TargetRuntimeRollbackJobRunner(
            store,
            registrations,
            TargetRuntimeRollbackJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        project_evidence_runner=TargetProjectEvidenceJobRunner(
            store,
            registrations,
            TargetProjectEvidenceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        source_discovery_runner=TargetSourceDiscoveryJobRunner(
            store,
            registrations,
            TargetSourceDiscoveryJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        runtime_evidence_runner=TargetRuntimeEvidenceJobRunner(
            store,
            registrations,
            TargetRuntimeEvidenceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        host_provisioning_runner=TargetHostProvisioningJobRunner(
            store,
            registrations,
            TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
        ),
        host_reconciliation_runner=TargetHostReconciliationJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostReconciliationJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            provisioning_specs=TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
        host_service_runner=TargetHostServiceJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostServiceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            host_specs=TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            bootstrap_specs=TargetBootstrapJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
        host_service_reconciliation_runner=TargetHostServiceReconciliationJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostServiceReconciliationJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            service_specs=TargetHostServiceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
    )


def _target_package_registry() -> TargetPackageRegistry:
    return TargetPackageRegistry(get_settings().target_package_registry_dir)


def _host_provisioning_submission_service() -> TargetHostProvisioningSubmissionService:
    settings = get_settings()
    return TargetHostProvisioningSubmissionService(
        store=_deployment_job_store(),
        specs=TargetHostProvisioningJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetHostProvisioningSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-provisioning-intents"
        ),
        registrations=_target_registration_service(),
    )


def _host_reconciliation_submission_service() -> TargetHostReconciliationSubmissionService:
    settings = get_settings()
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostReconciliationSubmissionService(
        store=_deployment_job_store(),
        specs=TargetHostReconciliationJobSpecStore(spec_root),
        provisioning_specs=TargetHostProvisioningJobSpecStore(spec_root),
        intents=TargetHostReconciliationSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-reconciliation-intents"
        ),
    )


def _host_rollback_submission_service() -> TargetHostRollbackSubmissionService:
    settings = get_settings()
    return TargetHostRollbackSubmissionService(
        store=_deployment_job_store(),
        specs=TargetHostProvisioningJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetHostRollbackSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-rollback-intents"
        ),
        registrations=_target_registration_service(),
    )


def _host_service_submission_service() -> TargetHostServiceSubmissionService:
    settings = get_settings()
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostServiceSubmissionService(
        store=_deployment_job_store(),
        specs=TargetHostServiceJobSpecStore(spec_root),
        intents=TargetHostServiceSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-service-intents"
        ),
        host_specs=TargetHostProvisioningJobSpecStore(spec_root),
        bootstrap_specs=TargetBootstrapJobSpecStore(spec_root),
        registrations=_target_registration_service(),
    )


def _host_service_reconciliation_submission_service() -> (
    TargetHostServiceReconciliationSubmissionService
):
    settings = get_settings()
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostServiceReconciliationSubmissionService(
        store=_deployment_job_store(),
        specs=TargetHostServiceReconciliationJobSpecStore(spec_root),
        intents=TargetHostServiceReconciliationSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-service-reconciliation-intents"
        ),
        service_specs=TargetHostServiceJobSpecStore(spec_root),
    )


def _bootstrap_submission_service() -> TargetBootstrapPublicSubmissionService:
    settings = get_settings()
    store = _deployment_job_store()
    return TargetBootstrapPublicSubmissionService(
        store=store,
        specs=TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        intents=TargetBootstrapJobSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "bootstrap-intents"
        ),
        registrations=_target_registration_service(),
        packages=_target_package_registry(),
        authorization_key_id=settings.rolo_deployment_authorization_key_id,
        authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
    )


def _runtime_rollback_submission_service() -> TargetRuntimeRollbackSubmissionService:
    settings = get_settings()
    return TargetRuntimeRollbackSubmissionService(
        store=_deployment_job_store(),
        specs=TargetRuntimeRollbackJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetRuntimeRollbackIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "runtime-rollback-intents"
        ),
        registrations=_target_registration_service(),
    )


def _project_evidence_submission_service() -> TargetProjectEvidenceSubmissionService:
    settings = get_settings()
    return TargetProjectEvidenceSubmissionService(
        store=_deployment_job_store(),
        specs=TargetProjectEvidenceJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetProjectEvidenceIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "project-evidence-intents"
        ),
        registrations=_target_registration_service(),
    )


def _source_discovery_submission_service() -> TargetSourceDiscoverySubmissionService:
    settings = get_settings()
    return TargetSourceDiscoverySubmissionService(
        store=_deployment_job_store(),
        specs=TargetSourceDiscoveryJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetSourceDiscoveryIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "source-discovery-intents"
        ),
        registrations=_target_registration_service(),
    )


def _runtime_evidence_submission_service() -> TargetRuntimeEvidenceSubmissionService:
    settings = get_settings()
    return TargetRuntimeEvidenceSubmissionService(
        store=_deployment_job_store(),
        specs=TargetRuntimeEvidenceJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetRuntimeEvidenceIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "runtime-evidence-intents"
        ),
        registrations=_target_registration_service(),
        pins=CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
    )


def _deployment_tui() -> TargetDeploymentTui:
    settings = get_settings()
    return TargetDeploymentTui(
        _target_registration_service(),
        _deployment_job_store(),
        TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetRuntimeRollbackJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetProjectEvidenceJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetSourceDiscoveryJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetRuntimeEvidenceJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
    )


def _session_agent_runtime_cli() -> tuple[SessionAgentRuntime, SessionAgentSubject]:
    settings = get_settings()
    if not settings.rolo_session_agent_enabled:
        raise ValueError("Session Agent is disabled")
    if settings.rolo_session_agent_api_key is None:
        raise ValueError("Session Agent requires ROLO_SESSION_AGENT_API_KEY")
    if settings.rolo_api_token_principal is None:
        raise ValueError("Session Agent requires ROLO_API_TOKEN_PRINCIPAL")
    bound_permissions = {
        item.strip() for item in settings.rolo_api_token_permissions.split(",") if item.strip()
    }
    subject = SessionAgentSubject(
        principal=settings.rolo_api_token_principal,
        permissions=sorted(bound_permissions.intersection({"target:write"})),
    )
    jobs = _deployment_job_store()
    registrations = _target_registration_service()
    broker = SessionAgentBroker(
        sessions=SessionAgentSessionStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "agent-sessions"
        ),
        registrations=registrations,
        jobs=jobs,
        adapt_specs=TargetAdaptJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        bootstrap_submissions=_bootstrap_submission_service(),
        rollback_submissions=_runtime_rollback_submission_service(),
        project_evidence_submissions=_project_evidence_submission_service(),
        project_evidence_artifacts=TargetProjectEvidenceArtifactStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
        ),
        source_discovery_submissions=_source_discovery_submission_service(),
        source_discovery_artifacts=TargetSourceDiscoveryArtifactStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
        ),
        runtime_evidence_submissions=_runtime_evidence_submission_service(),
        runtime_evidence_artifacts=TargetRuntimeEvidenceArtifactStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
        ),
        collector_pins=CollectorEnrollmentPinRegistry(
            settings.target_profile_dir / "enrollment-v4"
        ),
        job_runner=_deployment_job_runner(),
        workbench=_deployment_tui(),
    )
    return (
        SessionAgentRuntime(
            broker,
            CodexSessionAgentProvider(
                api_key=settings.rolo_session_agent_api_key,
                model=settings.rolo_session_agent_model,
                base_url=settings.rolo_session_agent_base_url,
                executable=settings.rolo_session_agent_executable,
                timeout_s=settings.rolo_session_agent_provider_timeout_s,
            ),
        ),
        subject,
    )


@target_agent_app.command("run")
def run_session_agent(
    message: Annotated[str, typer.Argument(help="Natural-language deployment request")],
    target_ids: Annotated[
        list[str],
        typer.Option("--target", help="Repeatable explicit target allowlist"),
    ],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    max_tool_calls: Annotated[
        int,
        typer.Option("--max-tool-calls", min=1, max=8),
    ] = 4,
    timeout_s: Annotated[int, typer.Option("--timeout-s", min=10, max=1800)] = 120,
) -> None:
    """Run Codex command selection through the authenticated broker; no free shell."""

    try:
        runtime, subject = _session_agent_runtime_cli()
        result = runtime.run(
            subject,
            SessionAgentTurnRequest(
                message=message,
                allowed_target_ids=sorted(set(target_ids)),
                max_tool_calls=max_tool_calls,
                timeout_s=timeout_s,
            ),
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, PermissionError, RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_agent_app.command("readiness")
def session_agent_readiness() -> None:
    """Report static controls and unresolved W10 external acceptance gates."""

    emit(_session_agent_readiness())


@target_acceptance_app.command("real-ssh")
def collect_real_ssh_acceptance(
    target_id: Annotated[str, typer.Option("--target")],
    environment_id: Annotated[str, typer.Option("--environment")],
    expected_architecture: Annotated[
        str,
        typer.Option("--architecture", help="Expected x86_64 or aarch64 architecture."),
    ],
    os_image_sha256: Annotated[str, typer.Option("--os-image-sha256")],
    package_id: Annotated[str, typer.Option("--package-id")],
    package_manifest_sha256: Annotated[
        str,
        typer.Option("--package-manifest-sha256"),
    ],
    acceptance_suite: Annotated[
        Path,
        typer.Option(
            "--acceptance-suite",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    test_report: Annotated[
        Path,
        typer.Option(
            "--test-report",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    output: Annotated[Path, typer.Option("--output", resolve_path=True)],
    timeout_s: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=300.0),
    ] = 20.0,
) -> None:
    """Probe all three SSH identities and save a non-production W10 receipt."""

    try:
        settings = get_settings()
        registry = TargetProfileRegistry(settings.target_profile_dir)
        target = registry.get_target(target_id)
        if target.connection_profile_id is None:
            raise ValueError("W10 real SSH acceptance requires a registered SSH target")
        connection = registry.get_connection(target.connection_profile_id)
        resolver = CredentialResolver((FileCredentialProvider(),))
        runner = W10RealSshAcceptanceRunner(
            target=target,
            connection=connection,
            executor_factory=lambda purpose: target_executor_for_profile(
                target,
                registry=registry,
                credential_resolver=resolver,
                credential_purpose=purpose,
            ),
        )
        report_summary = parse_w10_junit_report(test_report)
        request = W10RealSshAcceptanceRequest(
            target_id=target_id,
            environment_id=environment_id,
            expected_architecture=TargetArchitecture(expected_architecture.casefold()),
            os_image_sha256=os_image_sha256,
            package_id=package_id,
            package_manifest_sha256=package_manifest_sha256,
            acceptance_suite_sha256=w10_acceptance_file_sha256(acceptance_suite),
            test_report_sha256=report_summary.report_sha256,
            timeout_s=timeout_s,
        )
        receipt = runner.run(request, test_report=report_summary)
        write_w10_real_ssh_acceptance_receipt(output, receipt)
    except (FileNotFoundError, OSError, PermissionError, RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(receipt)
    if receipt.automated_result != W10AutomatedResult.PASSED:
        raise typer.Exit(code=1)


@target_app.command("add")
def add_target(
    target_id: Annotated[str, typer.Argument()],
    workspace_root: Annotated[str, typer.Option("--workspace")],
    desired_rolo_version: Annotated[str, typer.Option("--desired-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    ssh_endpoint: Annotated[
        str | None,
        typer.Option("--ssh", help="Strict user@host endpoint; port is separate"),
    ] = None,
    local: Annotated[bool, typer.Option("--local")] = False,
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 22,
    credential_ref: Annotated[
        str | None,
        typer.Option(
            "--credential-ref",
            help="Opaque credential reference for package bootstrap SSH.",
        ),
    ] = None,
    provisioning_user: Annotated[
        str | None,
        typer.Option(
            "--provisioning-user",
            help="Existing admin SSH user used only for host provisioning.",
        ),
    ] = None,
    provisioning_credential_ref: Annotated[
        str | None,
        typer.Option(
            "--provisioning-credential-ref",
            help="Opaque admin credential reference used only for host provisioning.",
        ),
    ] = None,
    runtime_user: Annotated[
        str | None,
        typer.Option(
            "--runtime-user",
            help="Final least-privilege forced-command SSH user.",
        ),
    ] = None,
    runtime_credential_ref: Annotated[
        str | None,
        typer.Option(
            "--runtime-credential-ref",
            help="Opaque credential reference for the final runtime SSH identity.",
        ),
    ] = None,
    known_hosts_path: Annotated[
        Path | None,
        typer.Option("--known-hosts", resolve_path=True),
    ] = None,
    expected_host_key_sha256: Annotated[
        str | None,
        typer.Option("--host-key-sha256"),
    ] = None,
    release_signing_key_id: Annotated[
        str | None,
        typer.Option("--release-signing-key-id"),
    ] = None,
    release_signing_public_key: Annotated[
        Path | None,
        typer.Option(
            "--release-signing-public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    trust_level: Annotated[str, typer.Option("--trust-level")] = "STRICT",
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
) -> None:
    """Register secret-free Local or SSH target metadata without connecting."""

    try:
        if local == (ssh_endpoint is not None):
            raise ValueError("exactly one of --local or --ssh is required")
        if local and any(
            value is not None
            for value in (
                provisioning_user,
                provisioning_credential_ref,
                runtime_user,
                runtime_credential_ref,
            )
        ):
            raise ValueError("SSH identity options require --ssh")
        if (release_signing_key_id is None) != (release_signing_public_key is None):
            raise ValueError(
                "--release-signing-key-id and --release-signing-public-key are required together"
            )
        release_public_key_path = (
            str(release_signing_public_key.absolute())
            if release_signing_public_key is not None
            else None
        )
        release_public_key_sha256 = (
            ed25519_public_key_sha256(release_signing_public_key)
            if release_signing_public_key is not None
            else None
        )
        trust = TargetTrustLevel(trust_level.upper())
        connection: TargetConnectionProfile | None = None
        if ssh_endpoint is not None:
            if ssh_endpoint.count("@") != 1:
                raise ValueError("--ssh must use strict user@host form")
            user, host = ssh_endpoint.split("@", 1)
            if not user or not host or credential_ref is None or known_hosts_path is None:
                raise ValueError(
                    "SSH target requires user, host, --credential-ref and --known-hosts"
                )
            connection_id = f"connection-{target_id}"
            connection = TargetConnectionProfile(
                connection_profile_id=connection_id,
                host=host,
                port=port,
                user=user,
                credential_ref=credential_ref,
                provisioning_user=provisioning_user,
                provisioning_credential_ref=provisioning_credential_ref,
                runtime_user=runtime_user,
                runtime_credential_ref=runtime_credential_ref,
                known_hosts_path=str(known_hosts_path.absolute()),
                trust_level=trust,
                expected_host_key_sha256=expected_host_key_sha256,
            )
            target = TargetProfile(
                target_id=target_id,
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id=connection_id,
                workspace_root=workspace_root,
                desired_rolo_version=desired_rolo_version,
                trust_level=trust,
                release_signing_key_id=release_signing_key_id,
                release_signing_public_key_path=release_public_key_path,
                release_signing_public_key_sha256=release_public_key_sha256,
            )
        else:
            target = TargetProfile(
                target_id=target_id,
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root=workspace_root,
                desired_rolo_version=desired_rolo_version,
                trust_level=trust,
                release_signing_key_id=release_signing_key_id,
                release_signing_public_key_path=release_public_key_path,
                release_signing_public_key_sha256=release_public_key_sha256,
            )
        result = _target_registration_service().register(
            TargetRegistrationRequest(target=target, connection=connection),
            principal=requested_by,
            idempotency_key=idempotency_key,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


def _read_ssh_public_key(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024:
        raise ValueError("SSH public key file is unavailable or exceeds its size limit")
    return path.read_text(encoding="utf-8")


@target_host_app.command("plan")
def plan_target_host_provisioning(
    target_id: Annotated[str, typer.Option("--target")],
    bootstrap_public_key: Annotated[
        Path,
        typer.Option(
            "--bootstrap-public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    runtime_public_key: Annotated[
        Path,
        typer.Option(
            "--runtime-public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    expected_current_plan_sha256: Annotated[
        str | None,
        typer.Option(
            "--expected-current-plan-sha256",
            help="Optional CAS digest for replacing an existing host plan.",
        ),
    ] = None,
) -> None:
    """Render the exact USE_SUDO scope; this command never mutates the target."""

    try:
        registration = _target_registration_service().load(target_id)
        connection = registration.connection
        if connection is None:
            raise ValueError("host provisioning requires a registered SSH target")
        plan: TargetHostProvisioningPlan = build_target_host_provisioning_plan(
            target_id=target_id,
            target_registration_sha256=target_connection_binding_sha256(
                registration.target,
                connection,
            ),
            connection=connection,
            bootstrap_public_key=_read_ssh_public_key(bootstrap_public_key),
            runtime_public_key=_read_ssh_public_key(runtime_public_key),
            expected_current_plan_sha256=expected_current_plan_sha256,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "PLANNED",
            "plan_sha256": plan.canonical_sha256(),
            "plan": plan.model_dump(mode="json"),
        }
    )


@target_host_app.command("submit")
def submit_target_host_provisioning(
    target_id: Annotated[str, typer.Option("--target")],
    bootstrap_public_key: Annotated[
        Path,
        typer.Option(
            "--bootstrap-public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    runtime_public_key: Annotated[
        Path,
        typer.Option(
            "--runtime-public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
    expected_current_plan_sha256: Annotated[
        str | None,
        typer.Option("--expected-current-plan-sha256"),
    ] = None,
) -> None:
    """Submit one persistent R3 USE_SUDO Job; execution remains a separate action."""

    try:
        result = _host_provisioning_submission_service().submit(
            target_id=target_id,
            submission=TargetHostProvisioningJobSubmission(
                bootstrap_public_key=_read_ssh_public_key(bootstrap_public_key),
                runtime_public_key=_read_ssh_public_key(runtime_public_key),
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
                expected_current_plan_sha256=expected_current_plan_sha256,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (OSError, UnicodeError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_host_app.command("reconcile")
def submit_target_host_reconciliation(
    original_job_id: Annotated[str, typer.Option("--job-id")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
) -> None:
    """Submit an R2 read-only reconciliation Job for an unknown host apply."""

    try:
        result = _host_reconciliation_submission_service().submit(
            submission=TargetHostReconciliationJobSubmission(
                original_job_id=original_job_id,
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_host_app.command("rollback")
def submit_target_host_rollback(
    current_host_job_id: Annotated[str, typer.Option("--current-job-id")],
    rollback_to_host_job_id: Annotated[str, typer.Option("--rollback-to-job-id")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
) -> None:
    """Submit an R3 CAS rollback to a prior completed host configuration Job."""

    try:
        result = _host_rollback_submission_service().submit(
            submission=TargetHostRollbackJobSubmission(
                current_host_job_id=current_host_job_id,
                rollback_to_host_job_id=rollback_to_host_job_id,
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_host_app.command("service-start")
def submit_target_host_service_start(
    host_configuration_job_id: Annotated[
        str,
        typer.Option("--host-job-id"),
    ],
    bootstrap_job_id: Annotated[str, typer.Option("--bootstrap-job-id")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
) -> None:
    """Submit an R2 digest-bound first start of the activated target service."""

    try:
        result = _host_service_submission_service().submit(
            submission=TargetHostServiceJobSubmission(
                host_configuration_job_id=host_configuration_job_id,
                bootstrap_job_id=bootstrap_job_id,
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_host_app.command("service-reconcile")
def submit_target_host_service_reconciliation(
    original_job_id: Annotated[str, typer.Option("--job-id")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
) -> None:
    """Submit an R2 STATUS-only reconciliation for an unknown service start."""

    try:
        result = _host_service_reconciliation_submission_service().submit(
            submission=TargetHostServiceReconciliationJobSubmission(
                original_job_id=original_job_id,
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_app.command("tui")
def show_deployment_tui(
    page: Annotated[str, typer.Option("--page")] = "fleet",
    target_id: Annotated[str | None, typer.Option("--target")] = None,
    job_id: Annotated[str | None, typer.Option("--job-id")] = None,
    approval_id: Annotated[str | None, typer.Option("--approval-id")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
    watch: Annotated[bool, typer.Option("--watch/--once")] = False,
    refresh_s: Annotated[
        float,
        typer.Option("--refresh-s", min=0.5, max=60.0),
    ] = 2.0,
    submit_runtime_rollback: Annotated[
        bool,
        typer.Option(
            "--submit-runtime-rollback",
            help="Open a bounded interactive R3 rollback submission form.",
        ),
    ] = False,
    requested_by: Annotated[str, typer.Option("--requested-by")] = "tui-user",
    idempotency_key: Annotated[
        str | None,
        typer.Option("--idempotency-key"),
    ] = None,
) -> None:
    """Show deployment state or explicitly open one bounded interactive action."""

    try:
        selected_page = TargetDeploymentTuiPage(page.casefold())
        workbench = _deployment_tui()
        if submit_runtime_rollback:
            if watch:
                raise ValueError("interactive rollback submission cannot use --watch")
            selected_target = target_id or typer.prompt("Target ID")
            package_id = typer.prompt("Previous package ID")
            current_digest = typer.prompt("Expected current manifest SHA-256")
            previous_digest = typer.prompt("Expected previous manifest SHA-256")
            approver = typer.prompt("Independent approver principal")
            canonical_key = idempotency_key or (f"tui:runtime-rollback:{uuid4().hex}")
            typer.echo("This creates an R3 Approval only; it does not execute rollback.")
            if not typer.confirm(
                "Freeze this exact target/current/previous scope for review?",
                default=False,
            ):
                typer.echo("Rollback submission cancelled; no Job was created.")
                return
            result = _runtime_rollback_submission_service().submit(
                target_id=selected_target,
                submission=TargetRuntimeRollbackSubmission(
                    package_id=package_id,
                    expected_current_manifest_sha256=current_digest,
                    expected_previous_manifest_sha256=previous_digest,
                    approver_principal=approver,
                ),
                requested_by=requested_by,
                interaction_surface=InteractionSurface.TUI,
                idempotency_key=canonical_key,
            )
            snapshot = workbench.snapshot(
                TargetDeploymentTuiPage.APPROVAL,
                approval_id=result.approval.approval_id,
            )
            typer.echo(f"Job {result.job.job.job_id} created; idempotency_key={canonical_key}")
            typer.echo(render_target_deployment_tui(snapshot), nl=False)
            return
        while True:
            snapshot = workbench.snapshot(
                selected_page,
                target_id=target_id,
                job_id=job_id,
                approval_id=approval_id,
                limit=limit,
            )
            rendered = render_target_deployment_tui(snapshot)
            if watch:
                typer.echo("\x1b[2J\x1b[H" + rendered, nl=False)
                time.sleep(refresh_s)
            else:
                typer.echo(rendered, nl=False)
                break
    except KeyboardInterrupt:
        return
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@target_connect_app.command("assess")
def assess_target_connection(
    target_id: Annotated[str, typer.Option("--target")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    active_probe: Annotated[str, typer.Option("--active-probe")] = "runtime-readonly",
) -> None:
    """Create a profile-bound assessment Job without executing SSH inline."""

    try:
        registration = _target_registration_service().load(target_id)
        assessment = TargetConnectionAssessmentSubmission(active_probe=active_probe)
        submission = DeploymentJobSubmission(
            active_probe=assessment.active_probe,
            run_adapter_agent=False,
            parameters_sha256=target_connection_binding_sha256(
                registration.target,
                registration.connection,
            ),
        )
        command = build_deployment_command(
            target_id=target_id,
            command_kind=DeploymentCommandKind.ASSESS_CONNECTION,
            submission=submission,
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
        record = _deployment_job_store().create_job(command)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "ACCEPTED",
            "job": record.model_dump(mode="json"),
            "command_sha256": record.job.command_sha256,
        }
    )


@target_package_app.command("import")
def import_target_package(
    target_id: Annotated[str, typer.Option("--target")],
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Verify a local package against the target pin and import immutable bytes."""

    try:
        registration = _target_registration_service().load(target_id)
        entry = _target_package_registry().import_package(
            source,
            profile=registration.target,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(entry)


@target_bootstrap_app.command("submit")
def submit_bootstrap_job(
    target_id: Annotated[str, typer.Option("--target")],
    package_ref: Annotated[str, typer.Option("--package-ref")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
    expected_current_state: Annotated[
        str,
        typer.Option(
            "--expected-current-state",
            help="Runtime CAS expectation: absent, present, or any.",
        ),
    ] = "absent",
    expected_current_manifest_sha256: Annotated[
        str | None,
        typer.Option("--expected-current-manifest-sha256"),
    ] = None,
    install_authorization_key: Annotated[
        bool,
        typer.Option("--install-authorization-key/--no-install-authorization-key"),
    ] = True,
    expected_authorization_key_sha256: Annotated[
        str | None,
        typer.Option("--expected-authorization-key-sha256"),
    ] = None,
    timeout_s: Annotated[
        float,
        typer.Option("--timeout-s", min=10.0, max=1800.0),
    ] = 300.0,
) -> None:
    """Create an approved Bootstrap Job from one immutable Controller package ref."""

    try:
        current_expectations = {"absent": False, "present": True, "any": None}
        try:
            expect_current_present = current_expectations[expected_current_state.casefold()]
        except KeyError as exc:
            raise ValueError("--expected-current-state must be absent, present, or any") from exc
        result = _bootstrap_submission_service().submit(
            target_id=target_id,
            submission=TargetBootstrapJobSubmission(
                package_ref=package_ref,
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
                expect_current_present=expect_current_present,
                expected_current_manifest_sha256=expected_current_manifest_sha256,
                install_authorization_key=install_authorization_key,
                expected_authorization_key_sha256=(expected_authorization_key_sha256),
                timeout_s=timeout_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_runtime_app.command("rollback")
def submit_target_runtime_rollback_job(
    target_id: Annotated[str, typer.Option("--target")],
    package_id: Annotated[str, typer.Option("--package-id")],
    expected_current_manifest_sha256: Annotated[
        str,
        typer.Option("--expected-current-manifest-sha256"),
    ],
    expected_previous_manifest_sha256: Annotated[
        str,
        typer.Option("--expected-previous-manifest-sha256"),
    ],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
    timeout_s: Annotated[
        float,
        typer.Option("--timeout-s", min=10.0, max=1800.0),
    ] = 300.0,
) -> None:
    """Submit an R3-approved, double-CAS target runtime rollback Job."""

    try:
        result = _runtime_rollback_submission_service().submit(
            target_id=target_id,
            submission=TargetRuntimeRollbackSubmission(
                package_id=package_id,
                expected_current_manifest_sha256=(expected_current_manifest_sha256),
                expected_previous_manifest_sha256=(expected_previous_manifest_sha256),
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
                timeout_s=timeout_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_adapt_app.command("submit")
def submit_adapt_job(
    target_id: Annotated[str, typer.Option("--target")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    active_probe: Annotated[str, typer.Option("--active-probe")] = "runtime-readonly",
    run_adapter_agent: Annotated[
        bool,
        typer.Option("--run-adapter-agent/--no-run-adapter-agent"),
    ] = False,
    timeout_s: Annotated[int, typer.Option("--timeout-s", min=1, max=86_400)] = 1800,
    evidence_timeout_s: Annotated[
        float,
        typer.Option("--evidence-timeout-s", min=1.0, max=300.0),
    ] = 45.0,
    urdf_path: Annotated[
        Path | None,
        typer.Option("--urdf", exists=True, file_okay=True, resolve_path=True),
    ] = None,
    scratch_root: Annotated[
        Path | None,
        typer.Option("--scratch-root", file_okay=False, resolve_path=True),
    ] = None,
    project_evidence_job_id: Annotated[
        str | None,
        typer.Option(
            "--project-evidence-job-id",
            help="Completed proof-bound project-evidence Job required for SSH Adapt",
        ),
    ] = None,
    project_evidence_max_age_s: Annotated[
        int,
        typer.Option("--project-evidence-max-age-s", min=60, max=86_400),
    ] = 900,
    source_discovery_job_id: Annotated[
        str | None,
        typer.Option(
            "--source-discovery-job-id",
            help="Completed proof-bound source-discovery Job for SSH source analysis",
        ),
    ] = None,
    source_discovery_max_age_s: Annotated[
        int,
        typer.Option("--source-discovery-max-age-s", min=60, max=86_400),
    ] = 900,
    runtime_evidence_job_id: Annotated[
        str | None,
        typer.Option(
            "--runtime-evidence-job-id",
            help="Completed proof-bound runtime-evidence Job for SSH probes",
        ),
    ] = None,
    runtime_evidence_max_age_s: Annotated[
        int,
        typer.Option("--runtime-evidence-max-age-s", min=60, max=300),
    ] = 300,
) -> None:
    """Create a discovery-only Local or proof-bound SSH Adapt Job."""

    try:
        registration = _target_registration_service().load(target_id)
        settings = get_settings()
        submission = TargetAdaptJobSubmission(
            active_probe=active_probe,
            run_adapter_agent=run_adapter_agent,
            timeout_s=timeout_s,
            evidence_timeout_s=evidence_timeout_s,
            urdf_path=str(urdf_path) if urdf_path is not None else None,
            scratch_root=str(scratch_root) if scratch_root is not None else None,
            project_evidence_job_id=project_evidence_job_id,
            project_evidence_max_age_s=project_evidence_max_age_s,
            source_discovery_job_id=source_discovery_job_id,
            source_discovery_max_age_s=source_discovery_max_age_s,
            runtime_evidence_job_id=runtime_evidence_job_id,
            runtime_evidence_max_age_s=runtime_evidence_max_age_s,
        )
        binding = None
        if project_evidence_job_id is not None:
            binding = resolve_target_adapt_project_evidence_binding(
                job_id=project_evidence_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                jobs=_deployment_job_store(),
                artifacts=TargetProjectEvidenceArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                max_age_s=project_evidence_max_age_s,
            )
        source_binding = None
        if source_discovery_job_id is not None:
            if binding is None:
                raise ValueError(
                    "source discovery binding requires project evidence workspace binding"
                )
            source_binding = resolve_target_adapt_source_discovery_binding(
                job_id=source_discovery_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                workspace_sha256=binding.workspace_sha256,
                jobs=_deployment_job_store(),
                artifacts=TargetSourceDiscoveryArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                max_age_s=source_discovery_max_age_s,
            )
        runtime_binding = None
        if runtime_evidence_job_id is not None:
            runtime_binding = resolve_target_adapt_runtime_evidence_binding(
                job_id=runtime_evidence_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                jobs=_deployment_job_store(),
                artifacts=TargetRuntimeEvidenceArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                pins=CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
                max_age_s=runtime_evidence_max_age_s,
            )
        spec = build_target_adapt_job_spec(
            registration,
            submission,
            project_evidence=binding,
            source_discovery=source_binding,
            runtime_evidence=runtime_binding,
        )
        record = TargetAdaptJobSubmissionService(
            _deployment_job_store(),
            TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        ).submit(
            spec,
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "ACCEPTED",
            "job": record.model_dump(mode="json"),
            "command_sha256": record.job.command_sha256,
        }
    )


@target_project_evidence_app.command("submit")
def submit_project_evidence_job(
    target_id: Annotated[str, typer.Option("--target")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    candidates_json: Annotated[
        str | None,
        typer.Option(
            "--candidates-json",
            help=(
                "Strict JSON array of relative project evidence candidates; "
                "defaults to a conservative root-level metadata set"
            ),
        ),
    ] = None,
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
    timeout_s: Annotated[
        float,
        typer.Option("--timeout-s", min=1.0, max=300.0),
    ] = 60.0,
) -> None:
    """Create an R2-approved Job that reads only explicitly listed target files."""

    try:
        values: dict[str, object] = {
            "approver_principal": approver_principal,
            "approval_ttl_s": approval_ttl_s,
            "timeout_s": timeout_s,
        }
        if candidates_json is not None:
            values["candidates"] = json.loads(candidates_json)
        submission = TargetProjectEvidenceJobSubmission.model_validate(values)
        result = _project_evidence_submission_service().submit(
            target_id=target_id,
            submission=submission,
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        DeploymentJobStateConflict,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_source_discovery_app.command("submit")
def submit_source_discovery_job(
    target_id: Annotated[str, typer.Option("--target")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    scan_root: Annotated[
        list[str] | None,
        typer.Option(
            "--scan-root",
            help="Approved workspace-relative root; repeat for multiple roots (default: .)",
        ),
    ] = None,
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=86_400),
    ] = 900,
    timeout_s: Annotated[
        float,
        typer.Option("--timeout-s", min=1.0, max=300.0),
    ] = 120.0,
) -> None:
    """Create an R2 Job for bounded recursive source parsing on the target."""

    try:
        result = _source_discovery_submission_service().submit(
            target_id=target_id,
            submission=TargetSourceDiscoveryJobSubmission(
                scan_roots=scan_root or ["."],
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
                timeout_s=timeout_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_runtime_evidence_app.command("submit")
def submit_runtime_evidence_job(
    target_id: Annotated[str, typer.Option("--target")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    approver_principal: Annotated[str, typer.Option("--approver")],
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
    approval_ttl_s: Annotated[
        int,
        typer.Option("--approval-ttl-s", min=60, max=300),
    ] = 300,
    timeout_s: Annotated[
        float,
        typer.Option("--timeout-s", min=1.0, max=300.0),
    ] = 45.0,
) -> None:
    """Create an R2 Job for signed hw/Linux/ROS target evidence."""

    try:
        result = _runtime_evidence_submission_service().submit(
            target_id=target_id,
            submission=TargetRuntimeEvidenceJobSubmission(
                approver_principal=approver_principal,
                approval_ttl_s=approval_ttl_s,
                timeout_s=timeout_s,
            ),
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=idempotency_key,
        )
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(result)


@target_job_app.command("get")
def get_deployment_job(
    job_id: Annotated[str, typer.Option("--job-id")],
) -> None:
    try:
        record = _deployment_job_store().load_job(job_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(record)


@target_job_app.command("run")
def run_deployment_job(
    job_id: Annotated[str, typer.Option("--job-id")],
) -> None:
    """Run one supported Job handler under its per-target lease."""

    try:
        record = _deployment_job_runner().run(job_id)
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(record)
    if record.job.state != DeploymentJobState.COMPLETE:
        raise typer.Exit(code=1)


@target_job_app.command("events")
def get_deployment_job_events(
    job_id: Annotated[str, typer.Option("--job-id")],
    after_sequence: Annotated[int, typer.Option("--after-sequence", min=0)] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
) -> None:
    try:
        store = _deployment_job_store()
        store.load_job(job_id)
        items = store.read_events(
            job_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        page = DeploymentEventPage(
            job_id=job_id,
            after_sequence=after_sequence,
            next_sequence=items[-1].sequence if items else after_sequence,
            items=items,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(page)


@target_job_app.command("cancel")
def cancel_deployment_job(
    job_id: Annotated[str, typer.Option("--job-id")],
) -> None:
    try:
        record = _deployment_job_store().request_cancel(job_id)
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(record)


@target_approval_app.command("decide")
def decide_deployment_approval(
    approval_id: Annotated[str, typer.Option("--approval-id")],
    principal: Annotated[str, typer.Option("--principal")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    reason: Annotated[str, typer.Option("--reason")],
    approve: Annotated[
        bool,
        typer.Option("--approve/--reject"),
    ] = True,
) -> None:
    """Persist one approver-bound R3 decision with idempotent retry semantics."""

    store = _deployment_job_store()
    decision_id = (
        "decision-" + hashlib.sha256(f"{approval_id}:{idempotency_key}".encode()).hexdigest()[:32]
    )
    try:
        try:
            decision = store.decide_approval(
                approval_id,
                principal=principal,
                approve=approve,
                reason=reason,
                decision_id=decision_id,
            )
        except FileExistsError:
            decision = store.load_approval_decision(approval_id)
            expected = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
            if (
                decision.decision_id != decision_id
                or decision.principal != principal
                or decision.status != expected
                or decision.sanitized_reason != sanitize_deployment_summary(reason)
            ):
                raise DeploymentJobStateConflict(
                    "approval already has a different decision"
                ) from None
    except (FileNotFoundError, OSError, DeploymentJobStateConflict, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(decision)


def _parse_enrollment_timestamp(value: str | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _render_enrollment_cli(envelope: CommandEnvelope) -> list[str]:
    request = envelope.parameters
    if not isinstance(request, TargetEnrollmentRequest):
        raise ValueError("target enrollment command requires enrollment parameters")
    argv = [
        "robotctl",
        "target",
        "enroll",
        "--target",
        request.target_id,
        "--robot-id",
        request.robot_id,
        "--request-id",
        request.request_id,
        "--challenge-nonce",
        request.challenge_nonce,
        "--issued-at",
        request.issued_at.isoformat(),
        "--expires-at",
        request.expires_at.isoformat(),
        "--requested-by",
        envelope.command.requested_by,
    ]
    if request.configuration is not None:
        argv.extend(("--configuration-json", request.configuration.model_dump_json()))
    elif request.configuration_discovery is not None:
        argv.append("--auto-configuration")
        if not request.configuration_discovery.ros_auto_source:
            argv.append("--no-ros-auto-source")
        for relative in request.configuration_discovery.help_executable_relative_paths:
            argv.extend(("--help-executable-relative-path", relative))
    if request.approval_id is not None:
        argv.extend(("--approval-id", request.approval_id))
    if request.expected_collector_id is not None:
        argv.extend(("--expected-collector-id", request.expected_collector_id))
    return argv


@target_app.command("enroll")
def enroll_target(
    target_id: Annotated[str, typer.Option("--target")],
    robot_id: Annotated[str, typer.Option("--robot-id", "--robot")],
    approval_id: Annotated[str, typer.Option("--approval-id")],
    configuration_json: Annotated[
        str,
        typer.Option(
            "--configuration-json",
            help="Strict v4 collector configuration JSON; defaults to no optional pins",
        ),
    ] = "{}",
    auto_configuration: Annotated[
        bool,
        typer.Option(
            "--auto-configuration",
            help="Discover pinned ROS setup and approved relative executables on the target",
        ),
    ] = False,
    help_executable_relative_path: Annotated[
        list[str] | None,
        typer.Option(
            "--help-executable-relative-path",
            help="Approved workspace-relative executable; repeatable with auto configuration",
        ),
    ] = None,
    ros_auto_source: Annotated[
        bool,
        typer.Option("--ros-auto-source/--no-ros-auto-source"),
    ] = True,
    expected_collector_id: Annotated[
        str | None,
        typer.Option("--expected-collector-id", help="Old collector pin for rotation"),
    ] = None,
    request_id: Annotated[str | None, typer.Option("--request-id")] = None,
    challenge_nonce: Annotated[str | None, typer.Option("--challenge-nonce")] = None,
    issued_at: Annotated[str | None, typer.Option("--issued-at")] = None,
    expires_at: Annotated[str | None, typer.Option("--expires-at")] = None,
    requested_by: Annotated[str, typer.Option("--requested-by")] = "cli-user",
) -> None:
    """Create or explicitly rotate a target-local Ed25519 Collector identity."""

    settings = get_settings()
    registry = TargetProfileRegistry(settings.target_profile_dir)
    try:
        issued = _parse_enrollment_timestamp(
            issued_at,
            field_name="issued_at",
        ) or datetime.now(timezone.utc)
        expires = _parse_enrollment_timestamp(
            expires_at,
            field_name="expires_at",
        ) or issued + timedelta(minutes=5)
        operation = (
            TargetEnrollmentOperation.ROTATE
            if expected_collector_id is not None
            else TargetEnrollmentOperation.ENROLL
        )
        profile = registry.get_target(target_id)
        if auto_configuration:
            if configuration_json != "{}":
                raise ValueError(
                    "--auto-configuration cannot be combined with --configuration-json"
                )
            configuration = None
            configuration_discovery = CollectorConfigurationDiscoveryV4(
                workspace_root=profile.workspace_root,
                help_executable_relative_paths=(help_executable_relative_path or []),
                ros_auto_source=ros_auto_source,
            )
        else:
            if help_executable_relative_path is not None or not ros_auto_source:
                raise ValueError(
                    "relative executable and ROS discovery options require --auto-configuration"
                )
            configuration = CollectorConfigurationV4.model_validate_json(configuration_json)
            configuration_discovery = None
        request = TargetEnrollmentRequest(
            request_id=request_id or f"enroll-{uuid4().hex}",
            operation=operation,
            target_id=target_id,
            robot_id=robot_id,
            challenge_nonce=challenge_nonce or secrets.token_hex(16),
            issued_at=issued,
            expires_at=expires,
            configuration_sha256=(
                configuration.canonical_sha256() if configuration is not None else None
            ),
            configuration=configuration,
            configuration_discovery=configuration_discovery,
            expected_collector_id=expected_collector_id,
            approval_id=approval_id,
        )
        executor = target_executor_for_profile(
            profile,
            registry=registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
        )
        pins = CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4")
        command = DeploymentCommand(
            command=(
                DeploymentCommandKind.ROTATE_ENROLLMENT
                if operation == TargetEnrollmentOperation.ROTATE
                else DeploymentCommandKind.ENROLL
            ),
            target_id=target_id,
            requested_by=requested_by,
            interaction_surface=InteractionSurface.CLI,
            idempotency_key=f"enrollment:{request.canonical_sha256()[:32]}",
            parameters_sha256=request.canonical_sha256(),
        )
        bus = ApplicationCommandBus()

        def execute(envelope: CommandEnvelope) -> dict[str, object]:
            parameters = envelope.parameters
            if not isinstance(parameters, TargetEnrollmentRequest):
                raise ValueError("target enrollment parameters are unavailable")
            result = executor.execute_enrollment(parameters)
            pin = (
                pins.apply(parameters, result)
                if result.execution_status == TargetExecutionStatus.SUCCEEDED
                else None
            )
            return {
                "execution": result.model_dump(mode="json"),
                "controller_pin": pin.model_dump(mode="json") if pin else None,
            }

        bus.register(command.command, execute, renderer=_render_enrollment_cli)
        execution = bus.dispatch(CommandEnvelope(command=command, parameters=request))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    result_payload = execution.result
    succeeded = (
        isinstance(result_payload, dict)
        and isinstance(result_payload.get("execution"), dict)
        and result_payload["execution"].get("execution_status")
        == TargetExecutionStatus.SUCCEEDED.value
    )
    emit(
        {
            "status": "SUCCEEDED" if succeeded else "FAILED",
            "command": execution.command.model_dump(mode="json"),
            "command_sha256": execution.command_sha256,
            "canonical_cli": execution.canonical_cli,
            "result": execution.result,
        }
    )
    if not succeeded:
        raise typer.Exit(code=1)


@target_bootstrap_app.command("dry-run")
def bootstrap_dry_run(
    target_id: Annotated[str, typer.Option("--target")],
    package_root: Annotated[
        Path,
        typer.Option(
            "--package-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ],
    public_key: Annotated[
        Path,
        typer.Option(
            "--public-key",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    signing_key_id: Annotated[str, typer.Option("--signing-key-id")],
    current_package_version: Annotated[
        str | None,
        typer.Option("--current-package-version"),
    ] = None,
    current_manifest_sha256: Annotated[
        str | None,
        typer.Option("--current-manifest-sha256"),
    ] = None,
    install_requires_sudo: Annotated[
        bool,
        typer.Option("--install-requires-sudo"),
    ] = False,
) -> None:
    """Verify a package and produce a read-only, target-observed bootstrap plan."""

    settings = get_settings()
    registry = TargetProfileRegistry(settings.target_profile_dir)
    try:
        profile = registry.get_target(target_id)
        executor = target_executor_for_profile(
            profile,
            registry=registry,
            credential_resolver=CredentialResolver((FileCredentialProvider(),)),
        )
        public_key_sha256 = ed25519_public_key_sha256(public_key)
        if profile.release_signing_key_id is not None:
            if profile.release_signing_key_id != signing_key_id:
                raise ValueError("release signing key ID differs from TargetProfile pin")
            pinned_path = Path(profile.release_signing_public_key_path or "").resolve()
            if pinned_path != public_key.resolve():
                raise ValueError("release signing public key path differs from TargetProfile pin")
            if profile.release_signing_public_key_sha256 != public_key_sha256:
                raise ValueError("release signing public key digest differs from TargetProfile pin")
        planner = TargetBootstrapPlanner(
            executor,
            Ed25519TargetPackageVerifier({signing_key_id: public_key}),
            signing_public_key_sha256=public_key_sha256,
        )
        plan = planner.plan(
            target_id=target_id,
            package_root=package_root,
            request_id=f"bootstrap-{target_id}",
            current_package_version=current_package_version,
            current_manifest_sha256=current_manifest_sha256,
            install_requires_sudo=install_requires_sudo,
        )
    except (
        FileNotFoundError,
        OSError,
        TargetCapabilityDetectionError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(plan)
