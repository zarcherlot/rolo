from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rolo.targets import (
    ApprovalAction,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    TargetConnectionProfile,
    TargetHostProvisioningExecutionResult,
    TargetHostProvisioningExecutionStatus,
    TargetHostProvisioningJobRunner,
    TargetHostProvisioningJobSpecStore,
    TargetHostProvisioningJobSubmission,
    TargetHostProvisioningObservation,
    TargetHostProvisioningObservationStatus,
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
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
)

NOW = datetime.now(timezone.utc) - timedelta(minutes=5)


def _public_key(value: bytes) -> str:
    return "ssh-ed25519 " + b64encode(value * 32).decode()


def _services(tmp_path: Path):  # type: ignore[no-untyped-def]
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
    target = TargetProfile(
        target_id="rover",
        orchestrator_placement=OrchestratorPlacement.CONTROLLER,
        transport=TargetTransport.SSH,
        connection_profile_id=connection.connection_profile_id,
        workspace_root="/var/lib/rolo/workspace",
        desired_rolo_version="0.2.0",
        trust_level=TargetTrustLevel.STRICT,
    )
    registrations.register(
        TargetRegistrationRequest(target=target, connection=connection),
        principal="fixture",
        idempotency_key="host-provisioning-register",
        now=NOW,
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetHostProvisioningJobSpecStore(tmp_path / "specs")
    service = TargetHostProvisioningSubmissionService(
        store=store,
        specs=specs,
        intents=TargetHostProvisioningSubmissionIntentStore(tmp_path / "intents"),
        registrations=registrations,
    )
    return store, specs, registrations, service


def _submission() -> TargetHostProvisioningJobSubmission:
    return TargetHostProvisioningJobSubmission(
        bootstrap_public_key=_public_key(b"b"),
        runtime_public_key=_public_key(b"r"),
        approver_principal="reviewer@example.com",
        approval_ttl_s=3600,
    )


def _submit(service):  # type: ignore[no-untyped-def]
    return service.submit(
        target_id="rover",
        submission=_submission(),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-provisioning-rover-0001",
        now=NOW,
    )


def test_host_provisioning_submission_is_retry_stable_and_approval_bound(
    tmp_path: Path,
) -> None:
    store, specs, _, service = _services(tmp_path)

    first = _submit(service)
    repeated = _submit(service)

    assert first == repeated
    assert first.job.job.command.command.value == "PROVISION_HOST"
    assert first.approval.action == ApprovalAction.USE_SUDO
    assert first.approval.authorization_scope_sha256 == first.spec.canonical_sha256()
    assert specs.load(first.job.job.job_id) == first.spec
    with pytest.raises(DeploymentJobStateConflict, match="idempotency key"):
        service.submit(
            target_id="rover",
            submission=_submission().model_copy(
                update={"runtime_public_key": _public_key(b"x")}
            ),
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="host-provisioning-rover-0001",
            now=NOW + timedelta(minutes=1),
        )
    assert store.load_job(first.job.job.job_id).job.state == DeploymentJobState.CREATED


def test_approved_host_provisioning_job_executes_once_and_replays_artifact(
    tmp_path: Path,
) -> None:
    store, specs, registrations, service = _services(tmp_path)
    submission = _submit(service)
    store.decide_approval(
        submission.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Reviewed every sudo path, mode, digest and forced-command key.",
        now=NOW + timedelta(minutes=1),
        decision_id="decision-" + "a" * 32,
    )

    class Provisioner:
        calls = 0

        def provision_host(self, plan, **_):  # type: ignore[no-untyped-def]
            self.calls += 1
            return TargetHostProvisioningExecutionResult(
                target_id=plan.target_id,
                plan_sha256=plan.canonical_sha256(),
                status=TargetHostProvisioningExecutionStatus.APPLIED,
                current_plan_sha256=plan.canonical_sha256(),
                started_at=NOW + timedelta(minutes=2),
                finished_at=NOW + timedelta(minutes=2),
            )

    provisioner = Provisioner()
    runner = TargetHostProvisioningJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: provisioner,  # type: ignore[arg-type]
    )

    completed = runner.run(submission.job.job.job_id)
    replayed = runner.run(submission.job.job.job_id)

    assert completed == replayed
    assert completed.job.state == DeploymentJobState.COMPLETE
    assert provisioner.calls == 1
    assert completed.final_artifact_refs == [
        f"artifact://deployment-jobs/{completed.job.job_id}/host-provisioning-result.json"
    ]


def test_host_provisioning_unknown_remote_outcome_requires_reconciliation(
    tmp_path: Path,
) -> None:
    store, specs, registrations, service = _services(tmp_path)
    submission = _submit(service)
    store.decide_approval(
        submission.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Reviewed exact host plan.",
        now=NOW + timedelta(minutes=1),
        decision_id="decision-" + "b" * 32,
    )

    class FailingProvisioner:
        def provision_host(self, plan, **_):  # type: ignore[no-untyped-def]
            raise RuntimeError("connection dropped after sudo started")

    result = TargetHostProvisioningJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: FailingProvisioner(),  # type: ignore[arg-type]
    ).run(submission.job.job.job_id)

    assert result.job.state == DeploymentJobState.BLOCKED
    assert result.recovery_disposition.value == "REQUIRES_RECONCILIATION"
    assert result.checkpoints[0].remote_state.value == "UNKNOWN"


def test_approved_host_reconciliation_observes_without_replaying_and_closes_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, provisioning_specs, registrations, provisioning_service = _services(tmp_path)
    provisioning = _submit(provisioning_service)
    store.decide_approval(
        provisioning.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Reviewed exact host plan.",
        now=NOW + timedelta(minutes=1),
        decision_id="decision-" + "c" * 32,
    )

    class UnknownProvisioner:
        def provision_host(self, plan, **_):  # type: ignore[no-untyped-def]
            raise RuntimeError("connection dropped after sudo started")

    original = TargetHostProvisioningJobRunner(
        store,
        registrations,
        provisioning_specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: UnknownProvisioner(),  # type: ignore[arg-type]
    ).run(provisioning.job.job.job_id)
    assert original.job.state == DeploymentJobState.BLOCKED

    reconciliation_specs = TargetHostReconciliationJobSpecStore(tmp_path / "specs")
    reconciliation_service = TargetHostReconciliationSubmissionService(
        store=store,
        specs=reconciliation_specs,
        provisioning_specs=provisioning_specs,
        intents=TargetHostReconciliationSubmissionIntentStore(tmp_path / "intents"),
    )
    request = TargetHostReconciliationJobSubmission(
        original_job_id=original.job.job_id,
        approver_principal="reviewer@example.com",
        approval_ttl_s=3600,
    )
    submitted = reconciliation_service.submit(
        submission=request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-reconcile-rover-0001",
        now=NOW + timedelta(minutes=2),
    )
    repeated = reconciliation_service.submit(
        submission=request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-reconcile-rover-0001",
        now=NOW + timedelta(minutes=3),
    )
    assert repeated == submitted
    assert submitted.approval.risk == "R2"
    store.decide_approval(
        submitted.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approved privileged read-only state comparison.",
        now=NOW + timedelta(minutes=3),
        decision_id="decision-" + "d" * 32,
    )

    class Observer:
        calls = 0

        def observe_host_provisioning(self, plan, **_):  # type: ignore[no-untyped-def]
            self.calls += 1
            return TargetHostProvisioningObservation(
                target_id=plan.target_id,
                expected_plan_sha256=plan.canonical_sha256(),
                status=TargetHostProvisioningObservationStatus.EXACT,
                current_plan_sha256=plan.canonical_sha256(),
                observed_at=NOW + timedelta(minutes=4),
            )

    observer = Observer()
    runner = TargetHostReconciliationJobRunner(
        store=store,
        registrations=registrations,
        specs=reconciliation_specs,
        provisioning_specs=provisioning_specs,
        artifact_root=tmp_path / "artifacts",
        executor_factory=lambda _profile: observer,  # type: ignore[arg-type]
    )
    reconcile_remote_step = store.reconcile_remote_step

    def crash_before_original_update(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("controller crashed after persisting observation")

    monkeypatch.setattr(store, "reconcile_remote_step", crash_before_original_update)
    with pytest.raises(RuntimeError, match="controller crashed"):
        runner.run(submitted.job.job.job_id)
    monkeypatch.setattr(store, "reconcile_remote_step", reconcile_remote_step)
    reconciliation = runner.run(submitted.job.job.job_id)
    replayed = runner.run(submitted.job.job.job_id)

    assert reconciliation == replayed
    assert reconciliation.job.state == DeploymentJobState.COMPLETE
    assert observer.calls == 1
    closed_original = store.load_job(original.job.job_id)
    assert closed_original.job.state == DeploymentJobState.COMPLETE
    assert closed_original.checkpoints[0].status.value == "COMPLETE"


def test_host_rollback_restores_prior_keys_with_current_plan_cas(tmp_path: Path) -> None:
    store, specs, registrations, service = _services(tmp_path)

    class Provisioner:
        plans = []

        def provision_host(self, plan, **_):  # type: ignore[no-untyped-def]
            self.plans.append(plan)
            return TargetHostProvisioningExecutionResult(
                target_id=plan.target_id,
                plan_sha256=plan.canonical_sha256(),
                status=TargetHostProvisioningExecutionStatus.APPLIED,
                current_plan_sha256=plan.canonical_sha256(),
                started_at=NOW + timedelta(minutes=2),
                finished_at=NOW + timedelta(minutes=2),
            )

    provisioner = Provisioner()
    runner = TargetHostProvisioningJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: provisioner,  # type: ignore[arg-type]
    )

    first = _submit(service)
    store.decide_approval(
        first.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approve initial host configuration.",
        now=NOW + timedelta(minutes=1),
        decision_id="decision-" + "e" * 32,
    )
    runner.run(first.job.job.job_id)

    second = service.submit(
        target_id="rover",
        submission=TargetHostProvisioningJobSubmission(
            bootstrap_public_key=_public_key(b"c"),
            runtime_public_key=_public_key(b"s"),
            approver_principal="reviewer@example.com",
            approval_ttl_s=3600,
            expected_current_plan_sha256=first.spec.plan.canonical_sha256(),
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-provisioning-rover-0002",
        now=NOW + timedelta(minutes=3),
    )
    store.decide_approval(
        second.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approve updated host keys.",
        now=NOW + timedelta(minutes=4),
        decision_id="decision-" + "f" * 32,
    )
    runner.run(second.job.job.job_id)

    rollback_service = TargetHostRollbackSubmissionService(
        store=store,
        specs=specs,
        intents=TargetHostRollbackSubmissionIntentStore(
            tmp_path / "host-rollback-intents"
        ),
        registrations=registrations,
    )
    rollback_request = TargetHostRollbackJobSubmission(
        current_host_job_id=second.job.job.job_id,
        rollback_to_host_job_id=first.job.job.job_id,
        approver_principal="reviewer@example.com",
        approval_ttl_s=3600,
    )
    rollback = rollback_service.submit(
        submission=rollback_request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-rollback-rover-0001",
        now=NOW + timedelta(minutes=5),
    )
    repeated = rollback_service.submit(
        submission=rollback_request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="host-rollback-rover-0001",
        now=NOW + timedelta(minutes=6),
    )

    assert repeated == rollback
    assert rollback.job.job.command.command.value == "ROLLBACK_HOST"
    assert rollback.approval.action.value == "ROLLBACK_HOST_CONFIGURATION"
    assert rollback.approval.risk == "R3"
    assert rollback.spec.plan.bootstrap_public_key == first.spec.plan.bootstrap_public_key
    assert rollback.spec.plan.runtime_public_key == first.spec.plan.runtime_public_key
    assert rollback.spec.plan.expected_current_plan_sha256 == (
        second.spec.plan.canonical_sha256()
    )

    store.decide_approval(
        rollback.approval.approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Restore the reviewed prior host configuration.",
        now=NOW + timedelta(minutes=7),
        decision_id="decision-" + "1" * 32,
    )
    completed = runner.run(rollback.job.job.job_id)
    replayed = runner.run(rollback.job.job.job_id)
    assert completed == replayed
    assert completed.job.state == DeploymentJobState.COMPLETE
    assert len(provisioner.plans) == 3
