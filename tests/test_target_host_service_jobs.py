from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rolo.targets import (
    ApprovalAction,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    TargetBootstrapJobSpec,
    TargetBootstrapJobSpecStore,
    TargetConnectionProfile,
    TargetHostProvisioningJobSpecStore,
    TargetHostProvisioningJobSubmission,
    TargetHostProvisioningSubmissionIntentStore,
    TargetHostProvisioningSubmissionService,
    TargetHostServiceError,
    TargetHostServiceExecutionResult,
    TargetHostServiceJobRunner,
    TargetHostServiceJobSpecStore,
    TargetHostServiceJobSubmission,
    TargetHostServiceOperation,
    TargetHostServiceReconciliationJobRunner,
    TargetHostServiceReconciliationJobSpecStore,
    TargetHostServiceReconciliationJobSubmission,
    TargetHostServiceReconciliationSubmissionIntentStore,
    TargetHostServiceReconciliationSubmissionService,
    TargetHostServiceStatus,
    TargetHostServiceSubmissionIntentStore,
    TargetHostServiceSubmissionService,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    ed25519_public_key_sha256,
    target_service_reconciliation_outcome,
)

NOW = datetime.now(timezone.utc) - timedelta(minutes=10)


def _status_execution(
    *,
    status: TargetHostServiceStatus,
    error: TargetHostServiceError | None = None,
) -> TargetHostServiceExecutionResult:
    active = (
        True
        if status == TargetHostServiceStatus.ACTIVE
        else False
        if status == TargetHostServiceStatus.INACTIVE
        else None
    )
    return TargetHostServiceExecutionResult(
        request_id="service-status-mapping",
        request_sha256="a" * 64,
        target_id="rover",
        operation=TargetHostServiceOperation.STATUS,
        status=status,
        active=active,
        error_code=error,
        observed_host_plan_sha256="b" * 64 if active is not None else None,
        observed_runtime_manifest_sha256="c" * 64 if active is not None else None,
        started_at=NOW,
        finished_at=NOW,
    )


def test_target_service_reconciliation_outcomes_are_fail_closed() -> None:
    assert target_service_reconciliation_outcome(
        _status_execution(status=TargetHostServiceStatus.ACTIVE)
    ).value == "EXACT"
    assert target_service_reconciliation_outcome(
        _status_execution(status=TargetHostServiceStatus.INACTIVE)
    ).value == "NOT_COMMITTED"
    assert target_service_reconciliation_outcome(
        _status_execution(
            status=TargetHostServiceStatus.FAILED,
            error=TargetHostServiceError.RUNTIME_MISMATCH,
        )
    ).value == "DIVERGED"
    assert (
        target_service_reconciliation_outcome(
            _status_execution(
                status=TargetHostServiceStatus.FAILED,
                error=TargetHostServiceError.CONNECTION_FAILED,
            )
        )
        is None
    )


def _public_key(value: bytes) -> str:
    return "ssh-ed25519 " + b64encode(value * 32).decode()


def _complete_fixture_job(
    store: DeploymentJobStore,
    job_id: str,
    *,
    step_id: str,
    state: DeploymentJobState,
) -> None:
    store.start_step(
        job_id,
        step_id=step_id,
        state=state,
        remote=False,
        now=NOW + timedelta(minutes=1),
    )
    store.complete_step(
        job_id,
        step_id=step_id,
        outcome_sha256="a" * 64,
        artifact_refs=[f"artifact://fixture/{job_id}.json"],
        now=NOW + timedelta(minutes=2),
    )
    store.complete_job(
        job_id,
        artifact_refs=[f"artifact://fixture/{job_id}.json"],
        now=NOW + timedelta(minutes=3),
    )


def test_host_service_start_binds_completed_host_and_runtime_jobs(
    tmp_path: Path,
) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    registrations = TargetRegistrationService(registry)
    connection = TargetConnectionProfile(
        connection_profile_id="connection-rover",
        host="192.0.2.20",
        user="rolo",
        credential_ref="file://ssh/rover-bootstrap",
        provisioning_user="operator",
        provisioning_credential_ref="file://ssh/rover-admin",
        runtime_user="rolo",
        runtime_credential_ref="file://ssh/rover-runtime",
        known_hosts_path=str((tmp_path / "known_hosts").absolute()),
        trust_level=TargetTrustLevel.STRICT,
        expected_host_key_sha256="SHA256:" + "A" * 43,
    )
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="rover",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id=connection.connection_profile_id,
                workspace_root="/var/lib/rolo/workspace",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            ),
            connection=connection,
        ),
        principal="fixture",
        idempotency_key="host-service-registration",
        now=NOW,
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    spec_root = tmp_path / "specs"
    host_specs = TargetHostProvisioningJobSpecStore(spec_root)
    host = TargetHostProvisioningSubmissionService(
        store=store,
        specs=host_specs,
        intents=TargetHostProvisioningSubmissionIntentStore(tmp_path / "host-intents"),
        registrations=registrations,
    ).submit(
        target_id="rover",
        submission=TargetHostProvisioningJobSubmission(
            bootstrap_public_key=_public_key(b"b"),
            runtime_public_key=_public_key(b"r"),
            approver_principal="reviewer@example.com",
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-service-host-config",
        now=NOW,
    )
    _complete_fixture_job(
        store,
        host.job.job.job_id,
        step_id="provision-host",
        state=DeploymentJobState.BOOTSTRAPPING,
    )

    release_key = b"k" * 32
    bootstrap_spec = TargetBootstrapJobSpec(
        target_id="rover",
        target_registration_sha256=host.spec.plan.target_registration_sha256,
        workspace_root="/var/lib/rolo/workspace",
        package_root=str((tmp_path / "package").absolute()),
        package_id="rolo-target",
        manifest_sha256="b" * 64,
        release_signing_key_id="release-key",
        release_signing_public_key_base64=b64encode(release_key).decode(),
        release_signing_public_key_sha256=ed25519_public_key_sha256(release_key),
        approval_id="approval-" + "1" * 32,
        approval_action=ApprovalAction.INSTALL_TARGET_RUNTIME,
        approver_principal="reviewer@example.com",
        approval_expires_at=NOW + timedelta(hours=1),
        expect_current_present=False,
    )
    bootstrap_job = store.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.BOOTSTRAP,
            target_id="rover",
            workspace_root="/var/lib/rolo/workspace",
            active_probe="none",
            run_adapter_agent=False,
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="host-service-bootstrap",
            parameters_sha256=bootstrap_spec.canonical_sha256(),
        ),
        now=NOW,
    )
    bootstrap_specs = TargetBootstrapJobSpecStore(spec_root)
    bootstrap_specs.persist(bootstrap_job.job.job_id, bootstrap_spec)
    _complete_fixture_job(
        store,
        bootstrap_job.job.job_id,
        step_id="bootstrap-runtime",
        state=DeploymentJobState.BOOTSTRAPPING,
    )

    service_specs = TargetHostServiceJobSpecStore(spec_root)
    submitted = TargetHostServiceSubmissionService(
        store=store,
        specs=service_specs,
        intents=TargetHostServiceSubmissionIntentStore(tmp_path / "service-intents"),
        host_specs=host_specs,
        bootstrap_specs=bootstrap_specs,
        registrations=registrations,
    ).submit(
            submission=TargetHostServiceJobSubmission(
                host_configuration_job_id=host.job.job.job_id,
                bootstrap_job_id=bootstrap_job.job.job_id,
                approver_principal="reviewer@example.com",
                approval_ttl_s=86_400,
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-service-start-rover",
        now=NOW + timedelta(minutes=4),
    )
    assert submitted.approval.action == ApprovalAction.START_TARGET_SERVICE
    assert submitted.approval.risk == "R2"
    assert submitted.spec.request.expected_host_plan_sha256 == (
        host.spec.plan.canonical_sha256()
    )
    assert submitted.spec.request.expected_runtime_manifest_sha256 == "b" * 64
    store.decide_approval(
        submitted.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Start the reviewed loopback-only service.",
        now=NOW + timedelta(minutes=5),
        decision_id="decision-" + "2" * 32,
    )

    class Executor:
        calls = 0

        def execute_host_service(self, request, **_):  # type: ignore[no-untyped-def]
            self.calls += 1
            return TargetHostServiceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                operation=TargetHostServiceOperation.START,
                status=TargetHostServiceStatus.STARTED,
                active=True,
                observed_host_plan_sha256=request.expected_host_plan_sha256,
                observed_runtime_manifest_sha256=(
                    request.expected_runtime_manifest_sha256
                ),
                started_at=NOW + timedelta(minutes=6),
                finished_at=NOW + timedelta(minutes=6),
            )

    executor = Executor()
    runner = TargetHostServiceJobRunner(
        store=store,
        registrations=registrations,
        specs=service_specs,
        host_specs=host_specs,
        bootstrap_specs=bootstrap_specs,
        artifact_root=tmp_path / "artifacts",
        executor_factory=lambda _profile: executor,  # type: ignore[arg-type]
    )
    completed = runner.run(submitted.job.job.job_id)
    replayed = runner.run(submitted.job.job.job_id)

    assert completed == replayed
    assert completed.job.state == DeploymentJobState.COMPLETE
    assert executor.calls == 1

    unknown = TargetHostServiceSubmissionService(
        store=store,
        specs=service_specs,
        intents=TargetHostServiceSubmissionIntentStore(
            tmp_path / "service-intents-unknown"
        ),
        host_specs=host_specs,
        bootstrap_specs=bootstrap_specs,
        registrations=registrations,
    ).submit(
        submission=TargetHostServiceJobSubmission(
            host_configuration_job_id=host.job.job.job_id,
            bootstrap_job_id=bootstrap_job.job.job_id,
            approver_principal="reviewer@example.com",
            approval_ttl_s=86_400,
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-service-start-rover-unknown",
        now=NOW + timedelta(minutes=7),
    )
    store.decide_approval(
        unknown.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approve a second bounded service start test.",
        now=NOW + timedelta(minutes=8),
        decision_id="decision-" + "3" * 32,
    )

    class DisconnectedExecutor:
        def execute_host_service(self, request, **_):  # type: ignore[no-untyped-def]
            return TargetHostServiceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                operation=TargetHostServiceOperation.START,
                status=TargetHostServiceStatus.FAILED,
                error_code=TargetHostServiceError.CONNECTION_FAILED,
                started_at=NOW + timedelta(minutes=9),
                finished_at=NOW + timedelta(minutes=9),
            )

    blocked = TargetHostServiceJobRunner(
        store=store,
        registrations=registrations,
        specs=service_specs,
        host_specs=host_specs,
        bootstrap_specs=bootstrap_specs,
        artifact_root=tmp_path / "artifacts",
        executor_factory=lambda _profile: DisconnectedExecutor(),  # type: ignore[arg-type]
    ).run(unknown.job.job.job_id)
    assert blocked.job.state == DeploymentJobState.BLOCKED
    assert blocked.recovery_disposition.value == "REQUIRES_RECONCILIATION"
    assert blocked.checkpoints[0].status.value == "UNKNOWN"

    reconciliation_specs = TargetHostServiceReconciliationJobSpecStore(spec_root)
    reconciliation = TargetHostServiceReconciliationSubmissionService(
        store=store,
        specs=reconciliation_specs,
        intents=TargetHostServiceReconciliationSubmissionIntentStore(
            tmp_path / "service-reconciliation-intents"
        ),
        service_specs=service_specs,
    ).submit(
        submission=TargetHostServiceReconciliationJobSubmission(
            original_job_id=unknown.job.job.job_id,
            approver_principal="reviewer@example.com",
            approval_ttl_s=86_400,
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-service-reconcile-rover",
        now=NOW + timedelta(minutes=10),
    )
    assert reconciliation.approval.action == ApprovalAction.RECONCILE_TARGET_SERVICE
    assert reconciliation.spec.request.operation == TargetHostServiceOperation.STATUS
    store.decide_approval(
        reconciliation.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Read only the digest-bound service status.",
        now=NOW + timedelta(minutes=11),
        decision_id="decision-" + "4" * 32,
    )

    class ActiveObserver:
        calls = 0

        def execute_host_service(self, request, **_):  # type: ignore[no-untyped-def]
            self.calls += 1
            return TargetHostServiceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                operation=TargetHostServiceOperation.STATUS,
                status=TargetHostServiceStatus.ACTIVE,
                active=True,
                observed_host_plan_sha256=request.expected_host_plan_sha256,
                observed_runtime_manifest_sha256=(
                    request.expected_runtime_manifest_sha256
                ),
                started_at=NOW + timedelta(minutes=12),
                finished_at=NOW + timedelta(minutes=12),
            )

    observer = ActiveObserver()
    reconciliation_runner = TargetHostServiceReconciliationJobRunner(
        store=store,
        registrations=registrations,
        specs=reconciliation_specs,
        service_specs=service_specs,
        artifact_root=tmp_path / "artifacts",
        executor_factory=lambda _profile: observer,  # type: ignore[arg-type]
    )
    reconciled = reconciliation_runner.run(reconciliation.job.job.job_id)
    replayed_reconciliation = reconciliation_runner.run(
        reconciliation.job.job.job_id
    )
    assert reconciled == replayed_reconciliation
    assert reconciled.job.state == DeploymentJobState.COMPLETE
    assert observer.calls == 1
    assert store.load_job(unknown.job.job.job_id).job.state == (
        DeploymentJobState.COMPLETE
    )
