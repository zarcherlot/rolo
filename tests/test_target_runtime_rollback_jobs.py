from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    ApprovalAction,
    BootstrapInstallStatus,
    DeploymentAuthorizationKeyPin,
    DeploymentAuthorizationKeyRegistry,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    LocalTargetExecutor,
    OrchestratorPlacement,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionResult,
    TargetBootstrapInstallResult,
    TargetBootstrapJobSpecStore,
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInstalledRelease,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetRuntimeRollbackFailureCode,
    TargetRuntimeRollbackIntentStore,
    TargetRuntimeRollbackJobArtifact,
    TargetRuntimeRollbackJobRunner,
    TargetRuntimeRollbackJobSpecStore,
    TargetRuntimeRollbackSubmission,
    TargetRuntimeRollbackSubmissionService,
    TargetTransport,
    TargetTrustLevel,
    authorize_deployment_request,
    build_deployment_authorization_key_pin,
    build_target_runtime_rollback_execution_request,
    deployment_request_payload_sha256,
    ed25519_public_key_sha256,
    verify_deployment_request_authorization,
)

CURRENT = "c" * 64
PREVIOUS = "b" * 64


def _services(
    tmp_path: Path,
) -> tuple[
    DeploymentJobStore,
    TargetRegistrationService,
    TargetRuntimeRollbackJobSpecStore,
    TargetRuntimeRollbackSubmissionService,
    Path,
    Path,
    DeploymentAuthorizationKeyPin,
]:
    public_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "release.pub"
    public_path.write_bytes(public_key)
    authorization_private = Ed25519PrivateKey.generate()
    authorization_private_path = tmp_path / "authorization.pem"
    authorization_private_path.write_bytes(
        authorization_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        authorization_private_path.chmod(0o600)
    authorization_public_path = tmp_path / "authorization.pub"
    authorization_public_path.write_bytes(
        authorization_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    authorization_pin = build_deployment_authorization_key_pin(
        target_id="wheeltec",
        key_id="controller-authorization-2026",
        public_key_path=authorization_public_path,
        approval_id="approval-" + "a" * 32,
    )
    registrations = TargetRegistrationService(
        TargetProfileRegistry(tmp_path / "profiles")
    )
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="wheeltec",
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root="/home/robot/wheeltec_ws",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
                release_signing_key_id="release-key-2026",
                release_signing_public_key_path=str(public_path.absolute()),
                release_signing_public_key_sha256=ed25519_public_key_sha256(
                    public_key
                ),
            )
        ),
        principal="operator@example.com",
        idempotency_key="runtime-rollback-register-wheeltec",
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetRuntimeRollbackJobSpecStore(tmp_path / "specs")
    service = TargetRuntimeRollbackSubmissionService(
        store=store,
        specs=specs,
        intents=TargetRuntimeRollbackIntentStore(tmp_path / "intents"),
        registrations=registrations,
    )
    return (
        store,
        registrations,
        specs,
        service,
        authorization_private_path,
        authorization_public_path,
        authorization_pin,
    )


def _submit(
    service: TargetRuntimeRollbackSubmissionService,
    *,
    key: str = "runtime-rollback-wheeltec-0001",
):
    return service.submit(
        target_id="wheeltec",
        submission=TargetRuntimeRollbackSubmission(
            package_id="rolo-target",
            expected_current_manifest_sha256=CURRENT,
            expected_previous_manifest_sha256=PREVIOUS,
            approver_principal="reviewer@example.com",
            approval_ttl_s=600,
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key=key,
    )


def _approve(store: DeploymentJobStore, approval_id: str) -> None:
    store.decide_approval(
        approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Verified exact target, current digest and previous digest.",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        decision_id="decision-" + "d" * 32,
    )


def test_runtime_rollback_submission_is_idempotent_and_requires_r3_approval(
    tmp_path: Path,
) -> None:
    store, _, _, service, _, _, _ = _services(tmp_path)

    first = _submit(service)
    repeated = _submit(service)

    assert repeated == first
    assert first.job.job.state == DeploymentJobState.CREATED
    assert first.approval.risk == "R3"
    assert first.approval.approver_principal == "reviewer@example.com"
    unsigned_request = build_target_runtime_rollback_execution_request(
        first.spec,
        job_id=first.job.job.job_id,
    )
    assert first.approval.authorization_scope_sha256 == (
        deployment_request_payload_sha256(unsigned_request)
    )
    assert store.load_job(first.job.job.job_id).job.command.requested_by == (
        "operator@example.com"
    )
    tui = TargetDeploymentTui(
        service.registrations,
        store,
        TargetBootstrapJobSpecStore(tmp_path / "bootstrap-specs"),
        service.specs,
    )
    job_row = tui.snapshot(
        TargetDeploymentTuiPage.JOB,
        job_id=first.job.job.job_id,
    ).rows[0]
    approval_row = tui.snapshot(
        TargetDeploymentTuiPage.APPROVAL,
        approval_id=first.approval.approval_id,
    ).rows[0]
    approval_fields = {item.name: item.value for item in approval_row.fields}
    assert job_row.canonical_cli is not None
    assert "target runtime rollback" in job_row.canonical_cli
    assert approval_fields["expected_current_manifest_sha256"] == CURRENT
    assert approval_fields["expected_previous_manifest_sha256"] == PREVIOUS

    changed = TargetRuntimeRollbackSubmission(
        package_id="rolo-target",
        expected_current_manifest_sha256="a" * 64,
        expected_previous_manifest_sha256=PREVIOUS,
        approver_principal="reviewer@example.com",
    )
    with pytest.raises(DeploymentJobStateConflict, match="different submission"):
        service.submit(
            target_id="wheeltec",
            submission=changed,
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.API,
            idempotency_key="runtime-rollback-wheeltec-0001",
        )


def test_runtime_rollback_runner_binds_double_cas_and_replays_artifact(
    tmp_path: Path,
) -> None:
    (
        store,
        registrations,
        specs,
        service,
        authorization_private_path,
        authorization_public_path,
        pin,
    ) = _services(tmp_path)
    submission = _submit(service)

    class _Executor:
        calls = 0

        def execute_bootstrap(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            self.calls += 1
            assert request.operation == TargetBootstrapExecutionOperation.ROLLBACK
            assert request.manifest_sha256 == PREVIOUS
            assert request.expected_current_manifest_sha256 == CURRENT
            verify_deployment_request_authorization(
                request,
                authorization=request.authorization,
                pin=pin,
                expected_target_id="wheeltec",
                expected_action=ApprovalAction.ROLLBACK_TARGET_RUNTIME,
                expected_approval_id=request.approval_id,
            )
            installed = TargetInstalledRelease(
                package_id=request.package_id,
                package_version="0.1.0",
                manifest_sha256=PREVIOUS,
                install_path="/opt/rolo/releases/previous",
            )
            return TargetBootstrapExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                operation=request.operation,
                status=TargetExecutionStatus.SUCCEEDED,
                install_result=TargetBootstrapInstallResult(
                    status=BootstrapInstallStatus.ROLLED_BACK,
                    installed=installed,
                    active=installed,
                    previous_preserved=True,
                ),
            )

    executor = _Executor()
    runner = TargetRuntimeRollbackJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=authorization_public_path,
        authorization_private_key_path=authorization_private_path,
        executor_factory=lambda _profile: executor,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="approval decision is unavailable"):
        runner.run(submission.job.job.job_id)
    assert executor.calls == 0

    _approve(store, submission.approval.approval_id)
    with pytest.raises(
        DeploymentJobStateConflict,
        match="authorization signer is unavailable",
    ):
        TargetRuntimeRollbackJobRunner(
            store,
            registrations,
            specs,
            tmp_path / "unsigned-artifacts",
            executor_factory=lambda _profile: executor,  # type: ignore[arg-type]
        ).run(submission.job.job.job_id)
    assert executor.calls == 0
    wrong_private_path = tmp_path / "wrong-authorization.pem"
    wrong_private_path.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        wrong_private_path.chmod(0o600)
    with pytest.raises(
        DeploymentJobStateConflict,
        match="proof could not be issued",
    ):
        TargetRuntimeRollbackJobRunner(
            store,
            registrations,
            specs,
            tmp_path / "wrong-signer-artifacts",
            authorization_signing_key_id="controller-authorization-2026",
            authorization_public_key_path=authorization_public_path,
            authorization_private_key_path=wrong_private_path,
            executor_factory=lambda _profile: executor,  # type: ignore[arg-type]
        ).run(submission.job.job.job_id)
    assert executor.calls == 0
    completed = runner.run(submission.job.job.job_id)
    replayed = runner.run(submission.job.job.job_id)

    assert completed.job.state == DeploymentJobState.COMPLETE
    assert replayed == completed
    assert executor.calls == 1
    artifact = TargetRuntimeRollbackJobArtifact.model_validate_json(
        (
            tmp_path
            / "artifacts"
            / completed.job.job_id
            / "runtime-rollback-result.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact.execution is not None
    assert artifact.execution.manifest_sha256 == PREVIOUS


def test_runtime_rollback_unknown_remote_outcome_requires_reconciliation(
    tmp_path: Path,
) -> None:
    (
        store,
        registrations,
        specs,
        service,
        authorization_private_path,
        authorization_public_path,
        _,
    ) = _services(tmp_path)
    submission = _submit(service, key="runtime-rollback-wheeltec-unknown")
    _approve(store, submission.approval.approval_id)

    class _UnknownExecutor:
        def execute_bootstrap(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("connection lost after dispatch")

    record = TargetRuntimeRollbackJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=authorization_public_path,
        authorization_private_key_path=authorization_private_path,
        executor_factory=lambda _profile: _UnknownExecutor(),  # type: ignore[arg-type]
    ).run(submission.job.job.job_id)

    assert record.job.state == DeploymentJobState.BLOCKED
    artifact = TargetRuntimeRollbackJobArtifact.model_validate_json(
        (
            tmp_path
            / "artifacts"
            / record.job.job_id
            / "runtime-rollback-result.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact.failure_code == (
        TargetRuntimeRollbackFailureCode.REMOTE_OUTCOME_UNKNOWN
    )


def test_target_executor_requires_pinned_proof_before_runtime_rollback(
    tmp_path: Path,
) -> None:
    (
        store,
        _,
        _,
        service,
        authorization_private_path,
        _,
        pin,
    ) = _services(tmp_path)
    submission = _submit(service, key="runtime-rollback-wheeltec-target-proof")
    _approve(store, submission.approval.approval_id)
    unsigned = build_target_runtime_rollback_execution_request(
        submission.spec,
        job_id=submission.job.job.job_id,
    )
    registry = DeploymentAuthorizationKeyRegistry(tmp_path / "target-pins")
    registry.install_initial(pin)
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        install_root=tmp_path / "runtime",
        deployment_authorization_registry=registry,
    )

    missing = executor.execute_bootstrap(unsigned)
    authorized = authorize_deployment_request(
        unsigned,
        store,
        approval_id=submission.approval.approval_id,
        signing_key_id="controller-authorization-2026",
        private_key_path=authorization_private_path,
        authorization_id="authorization-" + "e" * 32,
    )
    accepted = executor.execute_bootstrap(authorized)

    assert missing.status == TargetExecutionStatus.FAILED
    assert missing.transport_error_code == TargetExecutionErrorCode.AUTHORIZATION_FAILED
    assert accepted.status == TargetExecutionStatus.FAILED
    assert accepted.transport_error_code is None
    assert accepted.bootstrap_error_code is not None
