from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    DeploymentAuthorizationKeyRegistry,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    LocalTargetExecutor,
    OrchestratorPlacement,
    TargetProfile,
    TargetProfileRegistry,
    TargetProjectEvidenceCandidate,
    TargetProjectEvidenceIntentStore,
    TargetProjectEvidenceJobArtifact,
    TargetProjectEvidenceJobArtifactStatus,
    TargetProjectEvidenceJobFailureCode,
    TargetProjectEvidenceJobRunner,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceJobSubmission,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceStatus,
    TargetProjectEvidenceSubmissionService,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    build_deployment_authorization_key_pin,
    build_target_project_evidence_execution_request,
    deployment_request_payload_sha256,
)


def _services(
    tmp_path: Path,
) -> tuple[
    DeploymentJobStore,
    TargetRegistrationService,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceSubmissionService,
    Path,
    Path,
    DeploymentAuthorizationKeyRegistry,
    Path,
]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Wheeltec\n", encoding="utf-8")

    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "authorization.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_path = tmp_path / "authorization.pub"
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    pin = build_deployment_authorization_key_pin(
        target_id="wheeltec",
        key_id="controller-authorization-2026",
        public_key_path=public_path,
        approval_id="approval-" + "a" * 32,
    )
    pin_registry = DeploymentAuthorizationKeyRegistry(tmp_path / "target-pins")
    pin_registry.install_initial(pin)

    registrations = TargetRegistrationService(
        TargetProfileRegistry(tmp_path / "profiles")
    )
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="wheeltec",
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root=str(workspace.absolute()),
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="operator@example.com",
        idempotency_key="project-evidence-register-wheeltec",
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetProjectEvidenceJobSpecStore(tmp_path / "specs")
    service = TargetProjectEvidenceSubmissionService(
        store=store,
        specs=specs,
        intents=TargetProjectEvidenceIntentStore(tmp_path / "intents"),
        registrations=registrations,
    )
    return (
        store,
        registrations,
        specs,
        service,
        private_path,
        public_path,
        pin_registry,
        workspace,
    )


def _submission(
    *,
    required_missing: bool = False,
) -> TargetProjectEvidenceJobSubmission:
    return TargetProjectEvidenceJobSubmission(
        candidates=[
            TargetProjectEvidenceCandidate(
                path=("missing.txt" if required_missing else "README.md"),
                kind=TargetProjectEvidenceKind.DOCUMENTATION,
                required=required_missing,
            )
        ],
        approver_principal="reviewer@example.com",
    )


def _submit(
    service: TargetProjectEvidenceSubmissionService,
    *,
    submission: TargetProjectEvidenceJobSubmission | None = None,
    key: str = "project-evidence-wheeltec-0001",
):
    return service.submit(
        target_id="wheeltec",
        submission=submission or _submission(),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key=key,
    )


def _approve(store: DeploymentJobStore, approval_id: str) -> None:
    store.decide_approval(
        approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Verified the exact bounded project evidence file list.",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        decision_id="decision-" + "e" * 32,
    )


def test_project_evidence_submission_is_idempotent_and_exactly_scoped(
    tmp_path: Path,
) -> None:
    store, _, _, service, _, _, _, _ = _services(tmp_path)

    first = _submit(service)
    repeated = _submit(service)

    assert repeated == first
    assert first.job.job.state == DeploymentJobState.CREATED
    assert first.approval.risk == "R2"
    assert first.approval.approver_principal == "reviewer@example.com"
    unsigned = build_target_project_evidence_execution_request(
        first.spec,
        job_id=first.job.job.job_id,
    )
    assert first.approval.authorization_scope_sha256 == (
        deployment_request_payload_sha256(unsigned)
    )
    with pytest.raises(DeploymentJobStateConflict, match="another request"):
        _submit(
            service,
            submission=_submission(required_missing=True),
        )
    assert store.load_job(first.job.job.job_id) == first.job


def test_project_evidence_job_issues_proof_and_persists_verified_snapshot(
    tmp_path: Path,
) -> None:
    (
        store,
        registrations,
        specs,
        service,
        private_path,
        public_path,
        pin_registry,
        _,
    ) = _services(tmp_path)
    submitted = _submit(service)
    _approve(store, submitted.approval.approval_id)

    completed = TargetProjectEvidenceJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=public_path,
        authorization_private_key_path=private_path,
        executor_factory=lambda _: LocalTargetExecutor(
            deployment_authorization_registry=pin_registry
        ),
    ).run(submitted.job.job.job_id)

    assert completed.job.state == DeploymentJobState.COMPLETE
    artifact = TargetProjectEvidenceJobArtifact.model_validate_json(
        (
            tmp_path
            / "artifacts"
            / submitted.job.job.job_id
            / "project-evidence-result.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact.status == TargetProjectEvidenceJobArtifactStatus.SUCCEEDED
    assert artifact.execution is not None
    assert artifact.execution.snapshot is not None
    assert artifact.execution.snapshot.status == TargetProjectEvidenceStatus.OBSERVED
    assert [item.path for item in artifact.execution.snapshot.hits] == ["README.md"]
    assert artifact.execution.snapshot.manifest is not None
    assert artifact.execution.snapshot.manifest.files[0].sha256


def test_project_evidence_runner_fails_closed_before_dispatch_without_signer(
    tmp_path: Path,
) -> None:
    store, registrations, specs, service, _, _, _, _ = _services(tmp_path)
    submitted = _submit(service)
    _approve(store, submitted.approval.approval_id)
    called = False

    def executor_factory(_: TargetProfile):
        nonlocal called
        called = True
        return LocalTargetExecutor()

    runner = TargetProjectEvidenceJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "unsigned-artifacts",
        executor_factory=executor_factory,
    )
    with pytest.raises(
        DeploymentJobStateConflict,
        match="authorization signer is unavailable",
    ):
        runner.run(submitted.job.job.job_id)
    assert called is False
    assert store.load_job(submitted.job.job.job_id).job.state == DeploymentJobState.CREATED


def test_project_evidence_required_missing_file_fails_with_bounded_artifact(
    tmp_path: Path,
) -> None:
    (
        store,
        registrations,
        specs,
        service,
        private_path,
        public_path,
        pin_registry,
        _,
    ) = _services(tmp_path)
    submitted = _submit(
        service,
        submission=_submission(required_missing=True),
        key="project-evidence-wheeltec-missing",
    )
    _approve(store, submitted.approval.approval_id)

    failed = TargetProjectEvidenceJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "failed-artifacts",
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=public_path,
        authorization_private_key_path=private_path,
        executor_factory=lambda _: LocalTargetExecutor(
            deployment_authorization_registry=pin_registry
        ),
    ).run(submitted.job.job.job_id)

    assert failed.job.state == DeploymentJobState.FAILED
    artifact = TargetProjectEvidenceJobArtifact.model_validate_json(
        (
            tmp_path
            / "failed-artifacts"
            / submitted.job.job.job_id
            / "project-evidence-result.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact.failure_code == TargetProjectEvidenceJobFailureCode.EXECUTION_FAILED
    assert artifact.execution is not None
    assert artifact.execution.error_code is not None
