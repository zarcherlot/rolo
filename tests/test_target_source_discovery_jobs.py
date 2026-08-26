from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    ApprovalAction,
    DeploymentAuthorizationKeyRegistry,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    LocalTargetExecutor,
    OrchestratorPlacement,
    TargetBootstrapJobSpecStore,
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    build_deployment_authorization_key_pin,
    deployment_request_payload_sha256,
)
from rolo.targets.source_discovery_jobs import (
    TargetSourceDiscoveryIntentStore,
    TargetSourceDiscoveryJobArtifact,
    TargetSourceDiscoveryJobArtifactStatus,
    TargetSourceDiscoveryJobRunner,
    TargetSourceDiscoveryJobSpecStore,
    TargetSourceDiscoveryJobSubmission,
    TargetSourceDiscoverySubmissionService,
    build_target_source_discovery_execution_request,
)


def _services(tmp_path: Path):  # type: ignore[no-untyped-def]
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "pyproject.toml").write_text(
        "[project]\nname='wheeltec-driver'\n",
        encoding="utf-8",
    )
    (workspace / "src" / "driver.py").write_text(
        "node.create_publisher(Twist, '/cmd_vel', 10)\n",
        encoding="utf-8",
    )
    (workspace / "README.md").write_text(
        "PRIVATE-SOURCE-TEXT-MUST-NOT-CROSS-PROTOCOL",
        encoding="utf-8",
    )

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
    pin_registry = DeploymentAuthorizationKeyRegistry(tmp_path / "target-pins")
    pin_registry.install_initial(
        build_deployment_authorization_key_pin(
            target_id="wheeltec",
            key_id="controller-authorization-2026",
            public_key_path=public_path,
            approval_id="approval-" + "a" * 32,
        )
    )

    registrations = TargetRegistrationService(TargetProfileRegistry(tmp_path / "profiles"))
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
        idempotency_key="source-discovery-register-wheeltec",
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetSourceDiscoveryJobSpecStore(tmp_path / "specs")
    service = TargetSourceDiscoverySubmissionService(
        store=store,
        specs=specs,
        intents=TargetSourceDiscoveryIntentStore(tmp_path / "intents"),
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
    )


def _submit(service: TargetSourceDiscoverySubmissionService, *, key: str):
    return service.submit(
        target_id="wheeltec",
        submission=TargetSourceDiscoveryJobSubmission(
            approver_principal="reviewer@example.com"
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
        reason="Approved bounded recursive source analysis without source-text export.",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        decision_id="decision-" + "d" * 32,
    )


def test_source_discovery_submission_is_idempotent_and_separately_r2_scoped(
    tmp_path: Path,
) -> None:
    store, _, _, service, _, _, _ = _services(tmp_path)

    first = _submit(service, key="source-discovery-wheeltec-0001")
    repeated = _submit(service, key="source-discovery-wheeltec-0001")

    assert repeated == first
    assert first.job.job.state == DeploymentJobState.CREATED
    assert first.approval.action == ApprovalAction.ANALYZE_PROJECT_SOURCE
    assert first.approval.risk == "R2"
    assert "without source text" in first.approval.sanitized_summary
    unsigned = build_target_source_discovery_execution_request(
        first.spec,
        job_id=first.job.job.job_id,
    )
    assert first.approval.authorization_scope_sha256 == (
        deployment_request_payload_sha256(unsigned)
    )
    with pytest.raises(DeploymentJobStateConflict, match="another request"):
        service.submit(
            target_id="wheeltec",
            submission=TargetSourceDiscoveryJobSubmission(
                scan_roots=["src"],
                approver_principal="reviewer@example.com",
            ),
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="source-discovery-wheeltec-0001",
        )
    assert store.load_job(first.job.job.job_id) == first.job
    tui = TargetDeploymentTui(
        service.registrations,
        store,
        TargetBootstrapJobSpecStore(tmp_path / "bootstrap-specs"),
        source_discovery_specs=service.specs,
    )
    job_page = tui.snapshot(
        TargetDeploymentTuiPage.JOB,
        job_id=first.job.job.job_id,
    )
    approval_page = tui.snapshot(
        TargetDeploymentTuiPage.APPROVAL,
        approval_id=first.approval.approval_id,
    )
    assert "target source-discovery submit" in job_page.rows[0].canonical_cli
    assert "--scan-root ." in job_page.rows[0].canonical_cli
    assert any(
        field.name == "scan_root_count" and field.value == "1"
        for field in approval_page.rows[0].fields
    )


def test_source_discovery_job_issues_proof_and_persists_secret_closed_snapshot(
    tmp_path: Path,
) -> None:
    store, registrations, specs, service, private_path, public_path, pins = _services(
        tmp_path
    )
    submitted = _submit(service, key="source-discovery-wheeltec-0002")
    _approve(store, submitted.approval.approval_id)

    completed = TargetSourceDiscoveryJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=public_path,
        authorization_private_key_path=private_path,
        executor_factory=lambda _: LocalTargetExecutor(
            deployment_authorization_registry=pins
        ),
    ).run(submitted.job.job.job_id)

    assert completed.job.state == DeploymentJobState.COMPLETE
    artifact_path = (
        tmp_path
        / "artifacts"
        / submitted.job.job.job_id
        / "source-discovery-result.json"
    )
    artifact = TargetSourceDiscoveryJobArtifact.model_validate_json(
        artifact_path.read_text(encoding="utf-8")
    )
    assert artifact.status == TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED
    assert artifact.execution is not None
    assert artifact.execution.snapshot is not None
    assert artifact.execution.snapshot.projects[0].packages == ["wheeltec-driver"]
    assert artifact.execution.snapshot.projects[0].ros_interfaces[0].source == (
        "src/driver.py"
    )
    encoded = artifact_path.read_text(encoding="utf-8")
    assert "PRIVATE-SOURCE-TEXT-MUST-NOT-CROSS-PROTOCOL" not in encoded
    assert str((tmp_path / "workspace").absolute()) not in encoded


def test_source_discovery_runner_fails_closed_before_dispatch_without_signer(
    tmp_path: Path,
) -> None:
    store, registrations, specs, service, _, _, _ = _services(tmp_path)
    submitted = _submit(service, key="source-discovery-wheeltec-0003")
    _approve(store, submitted.approval.approval_id)
    called = False

    def executor_factory(_: TargetProfile):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        return LocalTargetExecutor()

    runner = TargetSourceDiscoveryJobRunner(
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
