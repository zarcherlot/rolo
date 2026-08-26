from __future__ import annotations

import os
import stat
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from rolo.adapter_runner import AdapterProcessResult
from rolo.core.hashing import sha256_file
from rolo.stages.adapt.models import (
    AdapterBundleManifest,
    AdapterReleaseIndex,
    AdapterReleaseManifest,
    PublishedAdapterFile,
)
from rolo.stages.adapt.target_evidence import target_host_fingerprint
from rolo.targets import LocalTargetExecutor
from rolo.targets import adapter_release_transfer as release_transfer
from rolo.targets.adapter_release_activation import (
    AdapterReleaseActivationOperation,
    AdapterReleaseActivationRequest,
    AdapterReleaseActivationStateConflict,
    AdapterReleaseActivationStatus,
    AdapterReleaseActivator,
    issue_adapter_release_gate_receipt,
)
from rolo.targets.adapter_release_reconciliation import (
    AdapterReleaseConsistencyStatus,
    AdapterReleaseDesiredStageStatus,
    AdapterReleaseReconciliationAction,
    build_adapter_release_desired_state,
    build_adapter_release_status_request,
    reconcile_adapter_release,
)
from rolo.targets.adapter_release_transfer import (
    ADAPTER_RUNTIME_CONTEXT,
    AdapterReleaseDeploymentOperator,
    AdapterReleaseStager,
    AdapterReleaseStageRequest,
    AdapterReleaseStageStatus,
    AdapterReleaseTransferFile,
    AdapterReleaseTransferFileRole,
    AdapterReleaseTransferManifest,
    AdapterReleaseUploader,
    Ed25519AdapterReleaseVerifier,
    load_verified_adapter_release_transfer,
    prepare_adapter_release_transfer,
)
from rolo.targets.enrollment import (
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
)
from rolo.targets.package_signing import ed25519_public_key_sha256
from rolo.targets.runtime_deployment import (
    AdapterReleaseDescribeRequest,
    LocatedRuntimeContext,
    TargetDescribeOutput,
    TargetDescribeRequest,
    attest_target_describe,
    target_sandbox_profile_sha256,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _key_pair(tmp_path: Path) -> tuple[Path, bytes]:
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release-private.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_path, public


def _release(
    tmp_path: Path,
    *,
    release_id: str = "release-r1",
) -> tuple[Path, AdapterReleaseManifest]:
    root = tmp_path / "release"
    adapter = root / "adapter"
    adapter.mkdir(parents=True)
    entrypoint = adapter / "adapter.py"
    helper = adapter / "support.py"
    entrypoint.write_text("# adapter\n", encoding="utf-8")
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    bundle = AdapterBundleManifest(
        bundle_id="wheeltec-bundle",
        bundle_version="1.0.0",
        robot_id="wheeltec",
        discovery_id="discovery-1",
        package_file="adapter.py",
        package_sha256=sha256_file(entrypoint),
        files=[
            {
                "path": "adapter.py",
                "sha256": sha256_file(entrypoint),
                "role": "ENTRYPOINT",
            },
            {
                "path": "support.py",
                "sha256": sha256_file(helper),
                "role": "SUPPORT",
            },
        ],
        operations=[
            {
                "operation": "ros.topic.list",
                "entrypoint": "adapter.py",
                "contract_version": "1.1.0",
                "contract_sha256": "7" * 64,
            }
        ],
    )
    bundle_path = adapter / "adapter-manifest.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    artifacts: dict[str, Path] = {}
    for name in (
        "tool-catalog.json",
        "state-graph.json",
        "conformance-report.json",
        "gate-report.json",
    ):
        artifacts[name] = root / name
        artifacts[name].write_text("{}\n", encoding="utf-8")
    release = AdapterReleaseManifest(
        release_id=release_id,
        robot_id="wheeltec",
        discovery_id="discovery-1",
        target_fingerprint_sha256="8" * 64,
        bundle_manifest="adapter/adapter-manifest.json",
        bundle_manifest_sha256=sha256_file(bundle_path),
        adapter_package="adapter/adapter.py",
        adapter_package_sha256=sha256_file(entrypoint),
        adapter_files=[
            PublishedAdapterFile(
                path="adapter/adapter.py",
                sha256=sha256_file(entrypoint),
                role="ENTRYPOINT",
            ),
            PublishedAdapterFile(
                path="adapter/support.py",
                sha256=sha256_file(helper),
                role="SUPPORT",
            ),
        ],
        tool_catalog="tool-catalog.json",
        tool_catalog_sha256=sha256_file(artifacts["tool-catalog.json"]),
        state_graph="state-graph.json",
        state_graph_sha256=sha256_file(artifacts["state-graph.json"]),
        conformance_report="conformance-report.json",
        conformance_report_sha256=sha256_file(artifacts["conformance-report.json"]),
        gate_report="gate-report.json",
        gate_report_sha256=sha256_file(artifacts["gate-report.json"]),
    )
    (root / "manifest.json").write_text(
        release.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return root, release


def _prepared(
    tmp_path: Path,
    *,
    release_id: str = "release-r1",
    install_root: Path | None = None,
    private_path: Path | None = None,
    public_key: bytes | None = None,
) -> tuple[
    Path,
    AdapterReleaseTransferManifest,
    Ed25519AdapterReleaseVerifier,
    Path,
    bytes,
    Path,
]:
    release_root, release = _release(tmp_path, release_id=release_id)
    if (private_path is None) != (public_key is None):
        raise ValueError("test key pair inputs must be complete")
    if private_path is None or public_key is None:
        private_path, public_key = _key_pair(tmp_path)
    install_root = install_root or (tmp_path / "target-install")
    release_sha = sha256_file(release_root / "manifest.json")
    target_stage = (
        install_root
        / "robots"
        / "wheeltec"
        / "staged"
        / f"{release.release_id}-{release_sha[:16]}"
    )
    context = LocatedRuntimeContext(
        target_id="wheeltec-target",
        robot_id="wheeltec",
        workspace_id="wheeltec-workspace",
        workspace_sha256="a" * 64,
        adapter_entrypoint=str(target_stage / "release" / release.adapter_package),
    )
    prepared, manifest, _ = prepare_adapter_release_transfer(
        release_root,
        output_root=tmp_path / "prepared-transfer",
        target_id="wheeltec-target",
        context=context,
        key_id="release-key-2026",
        private_key_path=private_path,
    )
    verifier = Ed25519AdapterReleaseVerifier({"release-key-2026": public_key})
    return prepared, manifest, verifier, install_root, public_key, private_path


def _collector(tmp_path: Path):  # type: ignore[no-untyped-def]
    fingerprint = target_host_fingerprint()
    service = TargetEnrollmentService(
        tmp_path / "enrollment",
        host_fingerprint_provider=lambda: fingerprint,
        clock=lambda: NOW,
    )
    configuration = CollectorConfigurationV4()
    request = TargetEnrollmentRequest(
        request_id="enroll-wheeltec-gate",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="wheeltec-target",
        robot_id="wheeltec",
        challenge_nonce="1" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        configuration_sha256=configuration.canonical_sha256(),
        configuration=configuration,
        approval_id="approval-" + "a" * 32,
    )
    result = service.execute(request)
    pin = CollectorEnrollmentPinRegistry(tmp_path / "pins").apply(
        request,
        result,
        now=NOW,
    )
    return service, pin


def _gate(
    *,
    manifest: AdapterReleaseTransferManifest,
    service: TargetEnrollmentService,
    pin,  # type: ignore[no-untyped-def]
    private_path: Path,
):  # type: ignore[no-untyped-def]
    request = TargetDescribeRequest(
        request_id=f"describe-{manifest.release_id}",
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        collector_id=pin.descriptor.collector_id,
        release_id=manifest.release_id,
        release_manifest_sha256=manifest.release_manifest_sha256,
        bundle_manifest_sha256=manifest.bundle_manifest_sha256,
        runtime_context_sha256=manifest.runtime_context_sha256,
        sandbox_profile_sha256="4" * 64,
        nonce="5" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    output = TargetDescribeOutput(
        operations={"ros.topic.list": "adapter.py"},
    )
    attestation = attest_target_describe(
        request,
        output=output,
        service=service,
        now=NOW + timedelta(seconds=1),
    )
    receipt, signature = issue_adapter_release_gate_receipt(
        request=request,
        attestation=attestation,
        pin=pin,
        expected_operations=output.operations,
        output=output,
        transfer_manifest=manifest,
        gate_report_sha256="9" * 64,
        signing_key_id="release-key-2026",
        private_key_path=private_path,
        now=NOW + timedelta(seconds=2),
    )
    return receipt, signature


def _status_request(
    manifest: AdapterReleaseTransferManifest,
    public_key: bytes,
    *,
    request_id: str = "status-wheeltec-release",
):  # type: ignore[no-untyped-def]
    controller_index = AdapterReleaseIndex(
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        manifest="manifest.json",
        manifest_sha256=manifest.release_manifest_sha256,
        published_at=NOW,
    )
    desired = build_adapter_release_desired_state(
        target_id=manifest.target_id,
        controller_index=controller_index,
        transfer_manifest=manifest,
    )
    return build_adapter_release_status_request(
        request_id=request_id,
        desired=desired,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    )


def test_transfer_manifest_rejects_traversal_and_noncanonical_files() -> None:
    context = AdapterReleaseTransferFile(
        path=ADAPTER_RUNTIME_CONTEXT,
        sha256="1" * 64,
        size_bytes=1,
        role=AdapterReleaseTransferFileRole.RUNTIME_CONTEXT,
    )
    release = AdapterReleaseTransferFile(
        path="release/manifest.json",
        sha256="2" * 64,
        size_bytes=1,
        role=AdapterReleaseTransferFileRole.RELEASE,
    )
    with pytest.raises(ValidationError, match="unique and sorted"):
        AdapterReleaseTransferManifest(
            package_id="adapter-release-1",
            target_id="target-1",
            robot_id="robot-1",
            release_id="release-1",
            release_manifest_sha256="3" * 64,
            bundle_manifest_sha256="4" * 64,
            runtime_context_sha256="5" * 64,
            files=[release, context],
            total_size_bytes=2,
        )
    with pytest.raises(ValidationError, match="normalized and relative"):
        AdapterReleaseTransferFile(
            path="../escape",
            sha256="1" * 64,
            size_bytes=1,
            role=AdapterReleaseTransferFileRole.RELEASE,
        )


def test_prepare_signs_only_frozen_release_and_context_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    prepared, manifest, verifier, _, _, _ = _prepared(tmp_path)

    _, loaded, signature, context = load_verified_adapter_release_transfer(
        prepared,
        verifier,
    )

    assert loaded == manifest
    assert signature.key_id == "release-key-2026"
    assert context.target_id == "wheeltec-target"
    assert {item.role for item in manifest.files} == {
        AdapterReleaseTransferFileRole.RELEASE,
        AdapterReleaseTransferFileRole.RUNTIME_CONTEXT,
    }
    assert all(
        item.path == ADAPTER_RUNTIME_CONTEXT or item.path.startswith("release/")
        for item in manifest.files
    )

    (prepared / "release" / "adapter" / "adapter.py").write_text(
        "# tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="digest or size mismatch"):
        load_verified_adapter_release_transfer(prepared, verifier)


def test_upload_is_resumable_and_stage_is_atomic_read_only_and_non_active(
    tmp_path: Path,
) -> None:
    prepared, manifest, verifier, install_root, public_key, _ = _prepared(tmp_path)
    incoming = tmp_path / "incoming"
    executor = LocalTargetExecutor(transfer_root=incoming)

    first = AdapterReleaseUploader(
        executor,
        verifier,
        chunk_size_bytes=32,
    ).upload(prepared, request_prefix="adapter-upload-first")
    repeated = AdapterReleaseUploader(
        executor,
        verifier,
        chunk_size_bytes=32,
    ).upload(prepared, request_prefix="adapter-upload-repeat")

    assert first.bytes_uploaded == first.bytes_total
    assert repeated.bytes_uploaded == 0
    assert repeated.bytes_resumed == repeated.bytes_total
    request = AdapterReleaseStageRequest(
        request_id="stage-wheeltec-release-r1",
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        package_id=manifest.package_id,
        manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=verifier.public_key_sha256("release-key-2026"),
        approval_id="approval-" + "b" * 32,
    )
    stager = AdapterReleaseStager(incoming_root=incoming, install_root=install_root)
    staged = stager.stage(request, verifier=verifier)
    repeated_stage = stager.stage(request, verifier=verifier)

    assert staged.status == AdapterReleaseStageStatus.STAGED
    assert repeated_stage.status == AdapterReleaseStageStatus.ALREADY_STAGED
    assert Path(staged.release_root, "manifest.json").is_file()
    assert Path(staged.runtime_context_path).is_file()
    assert not (install_root / "robots" / "wheeltec" / "current.json").exists()
    assert not list((install_root / "robots" / "wheeltec" / "staged").glob(".staging-*"))
    if os.name == "posix":
        assert stat.S_IMODE(Path(staged.staged_root).stat().st_mode) == 0o555
        assert stat.S_IMODE(Path(staged.runtime_context_path).stat().st_mode) == 0o444


def test_stage_rejects_request_key_and_identity_mismatch(tmp_path: Path) -> None:
    prepared, manifest, verifier, install_root, public_key, private_path = _prepared(
        tmp_path
    )
    incoming = tmp_path / "incoming"
    AdapterReleaseUploader(LocalTargetExecutor(transfer_root=incoming), verifier).upload(
        prepared,
        request_prefix="adapter-upload",
    )
    other_public_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    request = AdapterReleaseStageRequest(
        request_id="stage-wheeltec-release-r1",
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        package_id=manifest.package_id,
        manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(other_public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(other_public_key),
        approval_id="approval-" + "c" * 32,
    )

    with pytest.raises(ValueError, match="binding mismatch"):
        AdapterReleaseStager(
            incoming_root=incoming,
            install_root=install_root,
        ).stage(request, verifier=verifier)
    assert not (install_root / "robots" / "wheeltec" / "current.json").exists()


def test_deployment_operator_binds_upload_and_local_stage(tmp_path: Path) -> None:
    prepared, manifest, _, install_root, public_key, _ = _prepared(tmp_path)
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=install_root,
    )

    result = AdapterReleaseDeploymentOperator(
        executor,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
        chunk_size_bytes=32,
    ).upload_and_stage(
        prepared,
        target_id="wheeltec-target",
        request_id="deploy-wheeltec-release-r1",
        approval_id="approval-" + "e" * 32,
    )

    assert result.upload.manifest_sha256 == manifest.canonical_sha256()
    assert result.execution.execution_status.value == "SUCCEEDED"
    assert result.execution.stage is not None
    assert result.execution.stage.status == AdapterReleaseStageStatus.STAGED
    assert not (install_root / "robots" / "wheeltec" / "current.json").exists()


def test_local_executor_derives_staged_context_and_runs_describe_only(
    tmp_path: Path,
) -> None:
    prepared, manifest, verifier, install_root, public_key, private_path = _prepared(
        tmp_path
    )
    incoming = tmp_path / "incoming"
    AdapterReleaseDeploymentOperator(
        LocalTargetExecutor(
            transfer_root=incoming,
            adapter_install_root=install_root,
        ),
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    ).upload_and_stage(
        prepared,
        target_id=manifest.target_id,
        request_id="stage-for-describe",
        approval_id="approval-" + "7" * 32,
    )
    _, pin = _collector(tmp_path)
    _, _, _, context = load_verified_adapter_release_transfer(prepared, verifier)
    launcher = tmp_path / "sandbox-launcher"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    describe = TargetDescribeRequest(
        request_id="target-describe-release-r1",
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        collector_id=pin.descriptor.collector_id,
        release_id=manifest.release_id,
        release_manifest_sha256=manifest.release_manifest_sha256,
        bundle_manifest_sha256=manifest.bundle_manifest_sha256,
        runtime_context_sha256=manifest.runtime_context_sha256,
        sandbox_profile_sha256=target_sandbox_profile_sha256(
            launcher,
            context.sandbox_budget,
        ),
        nonce="8" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=2),
    )
    request = AdapterReleaseDescribeRequest(
        request_id="execute-target-describe-r1",
        transfer_manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        describe=describe,
    )

    class DescribeRunner:
        def __init__(self) -> None:
            self.commands: list[list[str]] = []

        def run(self, command, **kwargs):  # type: ignore[no-untyped-def]
            self.commands.append(command)
            assert kwargs["runtime_environment"] == {}
            return AdapterProcessResult(
                returncode=0,
                stdout='{"operations":{"ros.topic.list":"adapter.py"}}',
                stderr="",
            )

    runner = DescribeRunner()
    result = LocalTargetExecutor(
        transfer_root=incoming,
        enrollment_root=tmp_path / "enrollment",
        adapter_install_root=install_root,
        adapter_runner=runner,  # type: ignore[arg-type]
        adapter_sandbox_launcher=launcher,
    ).describe_adapter_release(request)

    assert result.execution_status.value == "SUCCEEDED", result.model_dump_json()
    assert result.describe is not None
    assert result.describe.attestation.release_id == manifest.release_id
    assert len(runner.commands) == 1
    assert runner.commands[0][-1] == "describe"
    assert "invoke" not in runner.commands[0]

    gate_now = datetime.now(timezone.utc)
    receipt, gate_signature = issue_adapter_release_gate_receipt(
        request=describe,
        attestation=result.describe.attestation,
        pin=pin,
        expected_operations=result.describe.output.operations,
        output=result.describe.output,
        transfer_manifest=manifest,
        gate_report_sha256="9" * 64,
        signing_key_id="release-key-2026",
        private_key_path=private_path,
        now=gate_now,
    )
    activation = AdapterReleaseActivationRequest(
        request_id="activate-after-target-describe",
        operation=AdapterReleaseActivationOperation.ACTIVATE,
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        transfer_manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "8" * 32,
        gate_receipt=receipt,
        gate_signature=gate_signature,
        expect_current_present=False,
    )
    activation_result = LocalTargetExecutor(
        adapter_install_root=install_root,
    ).activate_adapter_release(activation)
    assert activation_result.execution_status.value == "SUCCEEDED"
    assert activation_result.result is not None
    assert activation_result.result.status == AdapterReleaseActivationStatus.ACTIVATED


def test_stage_rename_interruption_leaves_no_stage_or_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, manifest, verifier, install_root, public_key, _ = _prepared(tmp_path)
    incoming = tmp_path / "incoming"
    AdapterReleaseUploader(LocalTargetExecutor(transfer_root=incoming), verifier).upload(
        prepared,
        request_prefix="adapter-upload",
    )
    request = AdapterReleaseStageRequest(
        request_id="stage-wheeltec-interrupted",
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        package_id=manifest.package_id,
        manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=verifier.public_key_sha256("release-key-2026"),
        approval_id="approval-" + "d" * 32,
    )
    original_replace = release_transfer.os.replace

    def interrupt(source: object, destination: object) -> None:
        if ".staging-" in Path(source).name and "staged" in Path(destination).parts:
            raise OSError("simulated stage rename interruption")
        original_replace(source, destination)  # type: ignore[arg-type]

    monkeypatch.setattr(release_transfer.os, "replace", interrupt)
    with pytest.raises(OSError, match="rename interruption"):
        AdapterReleaseStager(
            incoming_root=incoming,
            install_root=install_root,
        ).stage(request, verifier=verifier)

    robot_root = install_root / "robots" / "wheeltec"
    assert not (robot_root / "current.json").exists()
    assert not list(robot_root.rglob(".staging-*"))
    assert not [path for path in (robot_root / "staged").glob("*") if path.is_dir()]


def test_gate_receipt_is_required_and_activation_is_atomic_and_idempotent(
    tmp_path: Path,
) -> None:
    prepared, manifest, _, install_root, public_key, private_path = _prepared(tmp_path)
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=install_root,
    )
    AdapterReleaseDeploymentOperator(
        executor,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    ).upload_and_stage(
        prepared,
        target_id=manifest.target_id,
        request_id="stage-before-gate",
        approval_id="approval-" + "1" * 32,
    )
    service, pin = _collector(tmp_path)
    receipt, gate_signature = _gate(
        manifest=manifest,
        service=service,
        pin=pin,
        private_path=private_path,
    )
    request = AdapterReleaseActivationRequest(
        request_id="activate-wheeltec-release-r1",
        operation=AdapterReleaseActivationOperation.ACTIVATE,
        target_id=manifest.target_id,
        robot_id=manifest.robot_id,
        release_id=manifest.release_id,
        transfer_manifest_sha256=manifest.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "2" * 32,
        gate_receipt=receipt,
        gate_signature=gate_signature,
        expect_current_present=False,
    )
    activator = AdapterReleaseActivator(install_root)

    activated = activator.execute(request, now=NOW + timedelta(seconds=3))
    repeated = activator.execute(request, now=NOW + timedelta(seconds=4))

    assert activated.status == AdapterReleaseActivationStatus.ACTIVATED
    assert repeated.status == AdapterReleaseActivationStatus.ALREADY_ACTIVE
    assert activated.index.current.transfer_manifest_sha256 == manifest.canonical_sha256()
    current_path = install_root / "robots" / "wheeltec" / "current.json"
    assert current_path.is_file()
    before_tamper = current_path.read_bytes()

    tampered_receipt = receipt.model_copy(update={"gate_report_sha256": "0" * 64})
    tampered = request.model_copy(update={"gate_receipt": tampered_receipt})
    with pytest.raises(ValueError, match="receipt digest mismatch|signature verification"):
        activator.execute(tampered, now=NOW + timedelta(seconds=5))
    assert current_path.read_bytes() == before_tamper

    with pytest.raises(ValueError, match="expired"):
        activator.execute(request, now=NOW + timedelta(minutes=20))
    assert current_path.read_bytes() == before_tamper


def test_second_activation_preserves_previous_and_rollback_uses_cas(
    tmp_path: Path,
) -> None:
    private_path, public_key = _key_pair(tmp_path)
    install_root = tmp_path / "target-install"
    prepared1, manifest1, _, _, _, _ = _prepared(
        tmp_path / "first",
        release_id="release-r1",
        install_root=install_root,
        private_path=private_path,
        public_key=public_key,
    )
    prepared2, manifest2, _, _, _, _ = _prepared(
        tmp_path / "second",
        release_id="release-r2",
        install_root=install_root,
        private_path=private_path,
        public_key=public_key,
    )
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=install_root,
    )
    operator = AdapterReleaseDeploymentOperator(
        executor,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    )
    operator.upload_and_stage(
        prepared1,
        target_id=manifest1.target_id,
        request_id="stage-release-r1",
        approval_id="approval-" + "3" * 32,
    )
    operator.upload_and_stage(
        prepared2,
        target_id=manifest2.target_id,
        request_id="stage-release-r2",
        approval_id="approval-" + "4" * 32,
    )
    service, pin = _collector(tmp_path)
    receipt1, signature1 = _gate(
        manifest=manifest1,
        service=service,
        pin=pin,
        private_path=private_path,
    )
    receipt2, signature2 = _gate(
        manifest=manifest2,
        service=service,
        pin=pin,
        private_path=private_path,
    )

    def activation(
        manifest: AdapterReleaseTransferManifest,
        receipt,  # type: ignore[no-untyped-def]
        signature,  # type: ignore[no-untyped-def]
        *,
        request_id: str,
        expect_current_present: bool,
        expected_current: str | None = None,
    ) -> AdapterReleaseActivationRequest:
        return AdapterReleaseActivationRequest(
            request_id=request_id,
            operation=AdapterReleaseActivationOperation.ACTIVATE,
            target_id=manifest.target_id,
            robot_id=manifest.robot_id,
            release_id=manifest.release_id,
            transfer_manifest_sha256=manifest.canonical_sha256(),
            signing_key_id="release-key-2026",
            signing_public_key_base64=b64encode(public_key).decode("ascii"),
            signing_public_key_sha256=ed25519_public_key_sha256(public_key),
            approval_id="approval-" + "5" * 32,
            gate_receipt=receipt,
            gate_signature=signature,
            expect_current_present=expect_current_present,
            expected_current_transfer_manifest_sha256=expected_current,
        )

    activator = AdapterReleaseActivator(install_root)
    first = activator.execute(
        activation(
            manifest1,
            receipt1,
            signature1,
            request_id="activate-release-r1",
            expect_current_present=False,
        ),
        now=NOW + timedelta(seconds=3),
    )
    second = activator.execute(
        activation(
            manifest2,
            receipt2,
            signature2,
            request_id="activate-release-r2",
            expect_current_present=True,
            expected_current=manifest1.canonical_sha256(),
        ),
        now=NOW + timedelta(seconds=4),
    )

    assert first.index.previous is None
    assert second.index.previous is not None
    assert second.index.previous.release_id == "release-r1"
    rollback = AdapterReleaseActivationRequest(
        request_id="rollback-to-release-r1",
        operation=AdapterReleaseActivationOperation.ROLLBACK,
        target_id=manifest1.target_id,
        robot_id=manifest1.robot_id,
        release_id=manifest1.release_id,
        transfer_manifest_sha256=manifest1.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "6" * 32,
        expected_current_transfer_manifest_sha256=manifest2.canonical_sha256(),
    )
    rolled_back = activator.execute(rollback, now=NOW + timedelta(seconds=5))
    assert rolled_back.status == AdapterReleaseActivationStatus.ROLLED_BACK
    assert rolled_back.index.current.release_id == "release-r1"

    stale = rollback.model_copy(
        update={"expected_current_transfer_manifest_sha256": "0" * 64}
    )
    with pytest.raises(AdapterReleaseActivationStateConflict, match="CAS"):
        activator.execute(stale, now=NOW + timedelta(seconds=6))


def test_prepare_rejects_undeclared_release_files(tmp_path: Path) -> None:
    release_root, release = _release(tmp_path)
    (release_root / "undeclared.txt").write_text("unexpected", encoding="utf-8")
    private_path, _ = _key_pair(tmp_path)
    context = LocatedRuntimeContext(
        target_id="wheeltec-target",
        robot_id="wheeltec",
        workspace_id="workspace-1",
        workspace_sha256="a" * 64,
        adapter_entrypoint=str(tmp_path / "target" / release.adapter_package),
    )

    with pytest.raises(ValueError, match="file set differs"):
        prepare_adapter_release_transfer(
            release_root,
            output_root=tmp_path / "prepared",
            target_id="wheeltec-target",
            context=context,
            key_id="release-key-2026",
            private_key_path=private_path,
        )


def test_release_status_and_reconciliation_cover_stage_active_and_previous(
    tmp_path: Path,
) -> None:
    private_path, public_key = _key_pair(tmp_path)
    install_root = tmp_path / "target-install"
    prepared1, manifest1, _, _, _, _ = _prepared(
        tmp_path / "first",
        release_id="release-r1",
        install_root=install_root,
        private_path=private_path,
        public_key=public_key,
    )
    prepared2, manifest2, _, _, _, _ = _prepared(
        tmp_path / "second",
        release_id="release-r2",
        install_root=install_root,
        private_path=private_path,
        public_key=public_key,
    )
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=install_root,
    )
    operator = AdapterReleaseDeploymentOperator(
        executor,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    )
    operator.upload_and_stage(
        prepared1,
        target_id=manifest1.target_id,
        request_id="stage-status-r1",
        approval_id="approval-" + "1" * 32,
    )
    request1 = _status_request(manifest1, public_key, request_id="status-staged-r1")

    staged_execution = executor.status_adapter_release(request1)
    staged_report = reconcile_adapter_release(request1, staged_execution)

    assert staged_execution.snapshot is not None
    assert staged_execution.snapshot.current is None
    assert (
        staged_execution.snapshot.desired_stage_status
        == AdapterReleaseDesiredStageStatus.VERIFIED
    )
    assert staged_report.status == AdapterReleaseConsistencyStatus.TARGET_EMPTY
    assert (
        staged_report.action
        == AdapterReleaseReconciliationAction.ACTIVATE_STAGED_DESIRED
    )
    assert staged_report.expect_current_present is False

    service, pin = _collector(tmp_path)
    receipt1, signature1 = _gate(
        manifest=manifest1,
        service=service,
        pin=pin,
        private_path=private_path,
    )
    activation1 = AdapterReleaseActivationRequest(
        request_id="activate-status-r1",
        operation=AdapterReleaseActivationOperation.ACTIVATE,
        target_id=manifest1.target_id,
        robot_id=manifest1.robot_id,
        release_id=manifest1.release_id,
        transfer_manifest_sha256=manifest1.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "2" * 32,
        gate_receipt=receipt1,
        gate_signature=signature1,
        expect_current_present=False,
    )
    AdapterReleaseActivator(install_root).execute(
        activation1,
        now=NOW + timedelta(seconds=3),
    )

    in_sync_execution = executor.status_adapter_release(request1)
    in_sync_report = reconcile_adapter_release(request1, in_sync_execution)
    assert in_sync_report.status == AdapterReleaseConsistencyStatus.IN_SYNC
    assert in_sync_report.action == AdapterReleaseReconciliationAction.NONE
    assert in_sync_report.requires_reconciliation is False

    operator.upload_and_stage(
        prepared2,
        target_id=manifest2.target_id,
        request_id="stage-status-r2",
        approval_id="approval-" + "3" * 32,
    )
    receipt2, signature2 = _gate(
        manifest=manifest2,
        service=service,
        pin=pin,
        private_path=private_path,
    )
    activation2 = AdapterReleaseActivationRequest(
        request_id="activate-status-r2",
        operation=AdapterReleaseActivationOperation.ACTIVATE,
        target_id=manifest2.target_id,
        robot_id=manifest2.robot_id,
        release_id=manifest2.release_id,
        transfer_manifest_sha256=manifest2.canonical_sha256(),
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "4" * 32,
        gate_receipt=receipt2,
        gate_signature=signature2,
        expect_current_present=True,
        expected_current_transfer_manifest_sha256=manifest1.canonical_sha256(),
    )
    AdapterReleaseActivator(install_root).execute(
        activation2,
        now=NOW + timedelta(seconds=4),
    )

    previous_execution = executor.status_adapter_release(request1)
    previous_report = reconcile_adapter_release(request1, previous_execution)
    assert previous_report.status == AdapterReleaseConsistencyStatus.DESIRED_IS_PREVIOUS
    assert (
        previous_report.action == AdapterReleaseReconciliationAction.ROLLBACK_TO_DESIRED
    )
    assert (
        previous_report.expected_current_transfer_manifest_sha256
        == manifest2.canonical_sha256()
    )


def test_release_status_fails_closed_on_tamper_and_reconciliation_is_blocked(
    tmp_path: Path,
) -> None:
    prepared, manifest, _, install_root, public_key, _ = _prepared(tmp_path)
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=install_root,
    )
    AdapterReleaseDeploymentOperator(
        executor,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    ).upload_and_stage(
        prepared,
        target_id=manifest.target_id,
        request_id="stage-before-status-tamper",
        approval_id="approval-" + "5" * 32,
    )
    stage_root = (
        install_root
        / "robots"
        / manifest.robot_id
        / "staged"
        / f"{manifest.release_id}-{manifest.release_manifest_sha256[:16]}"
    )
    tampered = stage_root / "release" / "adapter" / "support.py"
    if os.name == "posix":
        tampered.chmod(0o600)
    tampered.write_text("VALUE = 'tampered'\n", encoding="utf-8")
    request = _status_request(manifest, public_key, request_id="status-after-tamper")

    execution = executor.status_adapter_release(request)
    report = reconcile_adapter_release(request, execution)

    assert execution.execution_status.value == "FAILED"
    assert execution.error_code is not None
    assert execution.error_code.value == "INTEGRITY_ERROR"
    assert report.status == AdapterReleaseConsistencyStatus.BLOCKED
    assert report.action == AdapterReleaseReconciliationAction.MANUAL_REVIEW
    assert report.requires_reconciliation is True
