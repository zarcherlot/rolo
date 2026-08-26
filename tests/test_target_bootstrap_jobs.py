from __future__ import annotations

import hashlib
import os
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    DeploymentAuthorizationKeyPin,
    DeploymentAuthorizationKeyRegistry,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    TargetArchitecture,
    TargetBootstrapExecutionService,
    TargetBootstrapJobRunner,
    TargetBootstrapJobSpecStore,
    TargetBootstrapJobSubmission,
    TargetBootstrapJobSubmissionIntentStore,
    TargetBootstrapJobSubmissionService,
    TargetBootstrapPublicSubmissionService,
    TargetPackageChunkStore,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageRegistry,
    TargetPlatformFacts,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    bind_target_package_sbom,
    build_target_bootstrap_job_spec,
    ed25519_public_key_sha256,
    sign_target_package,
)


class _Health:
    def check(self, entrypoint: Path, manifest: TargetPackageManifest) -> bool:
        return entrypoint.is_file() and manifest.package_version == "0.2.0"


def _facts() -> TargetPlatformFacts:
    return TargetPlatformFacts(
        os="linux",
        architecture="x86_64",
        python_version="3.12.4",
        bubblewrap_available=True,
        user_namespace_available=True,
        mount_namespace_available=True,
        network_namespace_available=True,
        available_address_space_bytes=8 * 1024 * 1024 * 1024,
        available_processes=256,
        runtime_path_available=True,
        explicit_pythonpath_supported=True,
        virtualenv_supported=True,
    )


def _package(tmp_path: Path) -> tuple[Path, Path, bytes, TargetPackageManifest]:
    root = tmp_path / "package"
    entrypoint = root / "bin" / "robotctl"
    runtime = root / "share" / "runtime.json"
    entrypoint.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho healthy\n")
    runtime.write_text('{"version":"0.2.0"}', encoding="utf-8")

    def declared(path: Path, role: TargetPackageFileRole, mode: int) -> TargetPackageFile:
        payload = path.read_bytes()
        return TargetPackageFile(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mode=mode,
            role=role,
        )

    manifest = TargetPackageManifest(
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        files=sorted(
            [
                declared(entrypoint, TargetPackageFileRole.ENTRYPOINT, 0o755),
                declared(runtime, TargetPackageFileRole.RUNTIME, 0o644),
            ],
            key=lambda item: item.path,
        ),
    )
    manifest, _, sbom_payload = bind_target_package_sbom(manifest)
    (root / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
    key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release.pem"
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "release.pub"
    public_path.write_bytes(public)
    signature = sign_target_package(
        manifest,
        key_id="release-key-2026",
        private_key_path=private_path,
    )
    (root / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return root, public_path, public, manifest


def _pin(approval_id: str, now: datetime) -> DeploymentAuthorizationKeyPin:
    raw = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return DeploymentAuthorizationKeyPin(
        target_id="wheeltec",
        key_id="controller-authorization-2026",
        public_key_base64=b64encode(raw).decode("ascii"),
        public_key_sha256=ed25519_public_key_sha256(raw),
        installed_by_approval_id=approval_id,
        installed_at=now,
    )


def test_public_bootstrap_submission_freezes_registry_ref_and_retry_times(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    package_root, public_path, public_key, _ = _package(tmp_path)
    registry = TargetProfileRegistry(tmp_path / "profiles")
    registrations = TargetRegistrationService(registry)
    target = TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.2.0",
        trust_level=TargetTrustLevel.STRICT,
        release_signing_key_id="release-key-2026",
        release_signing_public_key_path=str(public_path.absolute()),
        release_signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )
    registrations.register(
        TargetRegistrationRequest(target=target),
        principal="operator@example.com",
        idempotency_key="bootstrap-public-register-wheeltec",
        now=now,
    )
    packages = TargetPackageRegistry(tmp_path / "package-registry")
    package_entry = packages.import_package(package_root, profile=target, now=now)
    authorization_private = Ed25519PrivateKey.generate()
    authorization_public_path = tmp_path / "authorization.pub"
    authorization_public_path.write_bytes(
        authorization_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetBootstrapJobSpecStore(tmp_path / "specs")
    service = TargetBootstrapPublicSubmissionService(
        store=store,
        specs=specs,
        intents=TargetBootstrapJobSubmissionIntentStore(tmp_path / "intents"),
        registrations=registrations,
        packages=packages,
        authorization_key_id="controller-authorization-2026",
        authorization_public_key_path=authorization_public_path,
    )
    request = TargetBootstrapJobSubmission(
        package_ref=package_entry.record.package_ref,
        approver_principal="reviewer@example.com",
        approval_ttl_s=600,
        expect_current_present=False,
    )

    first = service.submit(
        target_id="wheeltec",
        submission=request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="bootstrap-public-wheeltec-0001",
        now=now,
    )
    repeated = service.submit(
        target_id="wheeltec",
        submission=request,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.API,
        idempotency_key="bootstrap-public-wheeltec-0001",
        now=now + timedelta(minutes=2),
    )

    assert repeated.job.job.job_id == first.job.job.job_id
    assert repeated.spec == first.spec
    assert repeated.spec.package_root == package_entry.package_root
    assert repeated.spec.approval_expires_at == now + timedelta(minutes=10)
    assert repeated.spec.authorization_key_pin is not None
    assert repeated.spec.authorization_key_pin.installed_at == now
    with pytest.raises(DeploymentJobStateConflict, match="different submission"):
        service.submit(
            target_id="wheeltec",
            submission=request.model_copy(update={"approval_ttl_s": 601}),
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.API,
            idempotency_key="bootstrap-public-wheeltec-0001",
            now=now,
        )
def test_bootstrap_job_requires_bound_approval_and_recovers_after_checkpoint_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    package_root, public_path, public_key, manifest = _package(tmp_path)
    registry = TargetProfileRegistry(tmp_path / "profiles")
    registrations = TargetRegistrationService(registry)
    target = TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.2.0",
        trust_level=TargetTrustLevel.STRICT,
        release_signing_key_id="release-key-2026",
        release_signing_public_key_path=str(public_path.absolute()),
        release_signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )
    registrations.register(
        TargetRegistrationRequest(target=target),
        principal="operator@example.com",
        idempotency_key="bootstrap-job-register-wheeltec",
        now=now,
    )
    approval_id = "approval-" + "b" * 32
    spec = build_target_bootstrap_job_spec(
        registrations.load("wheeltec"),
        package_root=package_root,
        approval_id=approval_id,
        approver_principal="reviewer@example.com",
        approval_expires_at=now + timedelta(hours=1),
        authorization_key_pin=_pin(approval_id, now),
        expect_current_present=False,
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetBootstrapJobSpecStore(tmp_path / "specs")
    submission = TargetBootstrapJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="bootstrap-job-wheeltec-0001",
        now=now,
    )
    repeated = TargetBootstrapJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.API,
        idempotency_key="bootstrap-job-wheeltec-0001",
        now=now,
    )
    assert repeated.job.job.job_id == submission.job.job.job_id
    assert repeated.spec == spec

    incoming = tmp_path / "target-incoming"
    authorization_registry = DeploymentAuthorizationKeyRegistry(
        tmp_path / "target-authorization"
    )
    execution_service = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "target-runtime",
        facts_provider=_facts,
        health_checker=_Health(),
        authorization_key_registry=authorization_registry,
    )
    chunks = TargetPackageChunkStore(incoming)

    class _Executor:
        execute_calls = 0
        crash_after_execute = False

        def transfer_package_chunk(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            return chunks.apply(request)

        def execute_bootstrap(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            self.execute_calls += 1
            result = execution_service.execute(request)
            if self.crash_after_execute:
                raise RuntimeError("simulated unknown remote outcome")
            return result

    executor = _Executor()
    runner = TargetBootstrapJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: executor,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="approval decision is unavailable"):
        runner.run(submission.job.job.job_id)
    assert store.load_job(submission.job.job.job_id).job.state == DeploymentJobState.CREATED
    assert executor.execute_calls == 0

    store.decide_approval(
        approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Verified package, target and authorization pin digests.",
        now=now + timedelta(minutes=1),
        decision_id="decision-" + "b" * 32,
    )
    complete_step = store.complete_step
    crashed = False

    def complete_then_crash(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal crashed
        result = complete_step(*args, **kwargs)
        if not crashed:
            crashed = True
            raise RuntimeError("simulated Controller checkpoint interruption")
        return result

    monkeypatch.setattr(store, "complete_step", complete_then_crash)
    with pytest.raises(RuntimeError, match="checkpoint interruption"):
        runner.run(submission.job.job.job_id)
    monkeypatch.setattr(store, "complete_step", complete_step)

    completed = runner.run(submission.job.job.job_id)

    assert completed.job.state == DeploymentJobState.COMPLETE
    assert completed.checkpoints[0].status.value == "COMPLETE"
    assert executor.execute_calls == 1
    assert authorization_registry.load("wheeltec") == spec.authorization_key_pin
    assert completed.final_artifact_refs == [
        f"artifact://deployment-jobs/{completed.job.job_id}/bootstrap-result.json"
    ]
    assert execution_service._installer.status().current.manifest_sha256 == (  # noqa: SLF001
        manifest.canonical_sha256()
    )
    result_path = (
        tmp_path / "artifacts" / completed.job.job_id / "bootstrap-result.json"
    )
    assert '"status":"SUCCEEDED"' in result_path.read_text(encoding="utf-8").replace(
        " ", ""
    )

    upgrade_approval_id = "approval-" + "d" * 32
    upgrade_spec = build_target_bootstrap_job_spec(
        registrations.load("wheeltec"),
        package_root=package_root,
        approval_id=upgrade_approval_id,
        approver_principal="reviewer@example.com",
        approval_expires_at=now + timedelta(hours=1),
        expect_current_present=True,
        expected_current_manifest_sha256=manifest.canonical_sha256(),
    )
    upgrade = TargetBootstrapJobSubmissionService(store, specs).submit(
        upgrade_spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="bootstrap-job-wheeltec-upgrade-0001",
        now=now,
    )
    store.decide_approval(
        upgrade_approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approved exact upgrade request.",
        now=now + timedelta(minutes=2),
        decision_id="decision-" + "d" * 32,
    )
    executor.crash_after_execute = True
    with pytest.raises(RuntimeError, match="unknown remote outcome"):
        runner.run(upgrade.job.job.job_id)
    calls_after_unknown = executor.execute_calls
    with pytest.raises(DeploymentJobStateConflict, match="requires reconciliation"):
        runner.run(upgrade.job.job.job_id)
    assert executor.execute_calls == calls_after_unknown


def test_bootstrap_job_registration_drift_fails_before_remote_write(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    package_root, public_path, public_key, _ = _package(tmp_path)
    registry = TargetProfileRegistry(tmp_path / "profiles")
    registrations = TargetRegistrationService(registry)
    target = TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.2.0",
        release_signing_key_id="release-key-2026",
        release_signing_public_key_path=str(public_path.absolute()),
        release_signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )
    registrations.register(
        TargetRegistrationRequest(target=target),
        principal="operator@example.com",
        idempotency_key="bootstrap-drift-register-wheeltec",
        now=now,
    )
    approval_id = "approval-" + "c" * 32
    spec = build_target_bootstrap_job_spec(
        registrations.load("wheeltec"),
        package_root=package_root,
        approval_id=approval_id,
        approver_principal="reviewer@example.com",
        approval_expires_at=now + timedelta(hours=1),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetBootstrapJobSpecStore(tmp_path / "specs")
    submitted = TargetBootstrapJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="bootstrap-drift-wheeltec-0001",
        now=now,
    )
    store.decide_approval(
        approval_id,
        principal="reviewer@example.com",
        approve=True,
        reason="Approved exact original registration.",
        now=now + timedelta(minutes=1),
        decision_id="decision-" + "c" * 32,
    )
    registry.save_target(target.model_copy(update={"desired_rolo_version": "0.3.0"}))

    class _NeverExecutor:
        def __getattribute__(self, name: str):
            if name.startswith("_"):
                return object.__getattribute__(self, name)
            raise AssertionError("remote executor must not be used after registration drift")

    record = TargetBootstrapJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: _NeverExecutor(),  # type: ignore[arg-type]
    ).run(submitted.job.job.job_id)

    assert record.job.state == DeploymentJobState.FAILED
    assert record.checkpoints[0].status.value == "FAILED"
