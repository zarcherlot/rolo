from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.core.models import ProbeResult
from rolo.targets import (
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    DeploymentAuthorizationKeyRegistry,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    LocalTargetExecutor,
    OrchestratorPlacement,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetRuntimeEvidenceArtifactStore,
    TargetRuntimeEvidenceIntentStore,
    TargetRuntimeEvidenceJobArtifactStatus,
    TargetRuntimeEvidenceJobRunner,
    TargetRuntimeEvidenceJobSpecStore,
    TargetRuntimeEvidenceJobSubmission,
    TargetRuntimeEvidenceSubmissionService,
    TargetTransport,
    TargetTrustLevel,
    build_deployment_authorization_key_pin,
    deployment_request_payload_sha256,
)


def _stub_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Hardware:
        def run(self, *, robot_id: str):  # type: ignore[no-untyped-def]
            return ProbeResult(layer="hw", status="SUCCEEDED", data={"robot": robot_id})

    class Linux:
        def run(self):  # type: ignore[no-untyped-def]
            return ProbeResult(layer="linux", status="SUCCEEDED", data={"arch": "arm64"})

    class Ros:
        def run(self):  # type: ignore[no-untyped-def]
            return ProbeResult(
                layer="ros",
                status="SUCCEEDED",
                data={"nodes": [], "topics": [], "services": [], "actions": []},
            )

    monkeypatch.setattr("rolo.stages.adapt.target_evidence.HardwareProbe", Hardware)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.LinuxProbe", Linux)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.RosProbe", Ros)


def _services(tmp_path: Path):  # type: ignore[no-untyped-def]
    now = datetime.now(timezone.utc)
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
    authorization_pins = DeploymentAuthorizationKeyRegistry(tmp_path / "target-pins")
    authorization_pins.install_initial(
        build_deployment_authorization_key_pin(
            target_id="wheeltec",
            key_id="controller-authorization-2026",
            public_key_path=public_path,
            approval_id="approval-" + "a" * 32,
        )
    )

    target_enrollment_root = tmp_path / "target-enrollment"
    enrollment_service = TargetEnrollmentService(
        target_enrollment_root,
        host_fingerprint_provider=lambda: "b" * 64,
        clock=lambda: now,
    )
    configuration = CollectorConfigurationV4()
    enrollment_request = TargetEnrollmentRequest(
        request_id="runtime-evidence-enroll",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="wheeltec",
        robot_id="wheeltec",
        challenge_nonce="c" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        configuration_sha256=configuration.canonical_sha256(),
        configuration=configuration,
        approval_id="approval-" + "b" * 32,
    )
    enrollment_result = enrollment_service.execute(enrollment_request)
    collector_pins = CollectorEnrollmentPinRegistry(tmp_path / "controller-enrollment")
    collector_pins.apply(enrollment_request, enrollment_result, now=now)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
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
        idempotency_key="runtime-evidence-register-wheeltec",
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetRuntimeEvidenceJobSpecStore(tmp_path / "specs")
    service = TargetRuntimeEvidenceSubmissionService(
        store=store,
        specs=specs,
        intents=TargetRuntimeEvidenceIntentStore(tmp_path / "intents"),
        registrations=registrations,
        pins=collector_pins,
    )
    return (
        store,
        registrations,
        specs,
        service,
        collector_pins,
        authorization_pins,
        target_enrollment_root,
        public_path,
        private_path,
    )


def _submit(service: TargetRuntimeEvidenceSubmissionService):  # type: ignore[no-untyped-def]
    return service.submit(
        target_id="wheeltec",
        submission=TargetRuntimeEvidenceJobSubmission(
            approver_principal="reviewer@example.com"
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="runtime-evidence-wheeltec-0001",
    )


def _approve(store: DeploymentJobStore, approval_id: str) -> None:
    store.decide_approval(
        approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Verified exact target, collector pin, layers and collection window.",
        decision_id="decision-" + "d" * 32,
    )


def test_runtime_evidence_submission_is_idempotent_and_exactly_scoped(
    tmp_path: Path,
) -> None:
    store, _, _, service, _, _, _, _, _ = _services(tmp_path)

    first = _submit(service)
    repeated = _submit(service)

    assert repeated == first
    assert first.job.job.state == DeploymentJobState.CREATED
    assert first.approval.risk == "R2"
    assert first.approval.authorization_scope_sha256 == (
        deployment_request_payload_sha256(first.spec.collection_request)
    )
    assert first.spec.collection_request.authorization is None
    assert first.spec.collection_request.evidence_request.requested_layers == [
        "hw",
        "linux",
        "ros",
    ]
    with pytest.raises(DeploymentJobStateConflict, match="another request"):
        service.submit(
            target_id="wheeltec",
            submission=TargetRuntimeEvidenceJobSubmission(
                approver_principal="another-reviewer@example.com"
            ),
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="runtime-evidence-wheeltec-0001",
        )
    assert store.load_job(first.job.job.job_id) == first.job


def test_runtime_evidence_job_uses_target_verified_proof_and_signed_collector_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "b" * 64,
    )
    (
        store,
        registrations,
        specs,
        service,
        collector_pins,
        authorization_pins,
        enrollment_root,
        public_path,
        private_path,
    ) = _services(tmp_path)
    submitted = _submit(service)
    _approve(store, submitted.approval.approval_id)

    completed = TargetRuntimeEvidenceJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        collector_pins,
        authorization_signing_key_id="controller-authorization-2026",
        authorization_public_key_path=public_path,
        authorization_private_key_path=private_path,
        executor_factory=lambda _: LocalTargetExecutor(
            enrollment_root=enrollment_root,
            deployment_authorization_registry=authorization_pins,
        ),
    ).run(submitted.job.job.job_id)

    artifact = TargetRuntimeEvidenceArtifactStore(tmp_path / "artifacts").load(
        submitted.job.job.job_id
    )
    assert completed.job.state == DeploymentJobState.COMPLETE, artifact.model_dump(
        mode="json"
    )
    assert artifact.status == TargetRuntimeEvidenceJobArtifactStatus.SUCCEEDED
    assert artifact.execution is not None
    assert artifact.execution.bundle is not None
    assert set(artifact.execution.bundle.probes) == {"hw", "linux", "ros"}
    assert artifact.execution.bundle.signature_ed25519_base64
    assert artifact.authorized_request_sha256 == artifact.execution.request_sha256


def test_runtime_evidence_runner_fails_closed_before_dispatch_without_signer(
    tmp_path: Path,
) -> None:
    store, registrations, specs, service, pins, _, _, _, _ = _services(tmp_path)
    submitted = _submit(service)
    _approve(store, submitted.approval.approval_id)
    called = False

    def executor_factory(_: TargetProfile):
        nonlocal called
        called = True
        return LocalTargetExecutor()

    runner = TargetRuntimeEvidenceJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        pins,
        executor_factory=executor_factory,
    )
    with pytest.raises(
        DeploymentJobStateConflict,
        match="authorization signer is unavailable",
    ):
        runner.run(submitted.job.job.job_id)
    assert called is False
    assert store.load_job(submitted.job.job.job_id).job.state == DeploymentJobState.CREATED
