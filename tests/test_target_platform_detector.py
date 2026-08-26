from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner

from rolo.cli import app
from rolo.commands import target as target_commands
from rolo.core.config import Settings
from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    Ed25519TargetPackageVerifier,
    OrchestratorPlacement,
    TargetArchitecture,
    TargetBootstrapPlanner,
    TargetCapabilityDetectionError,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPlatformFacts,
    TargetPreflightStatus,
    TargetProfile,
    TargetProfileRegistry,
    TargetRuntimeCapabilityDetector,
    TargetTransport,
    bind_target_package_sbom,
    ed25519_public_key_sha256,
    sign_target_package,
)


class StaticExecutor:
    def __init__(
        self,
        *,
        stdout: str,
        error_code: TargetExecutionErrorCode | None = None,
    ) -> None:
        self.stdout = stdout
        self.error_code = error_code
        self.requests: list[TargetInspectionRequest] = []

    def inspect(
        self,
        request: TargetInspectionRequest,
        *,
        cancel_event: object | None = None,
    ) -> TargetInspectionResult:
        self.requests.append(request)
        now = datetime.now(timezone.utc)
        return TargetInspectionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            executor_kind=TargetExecutorKind.LOCAL,
            status=(
                TargetExecutionStatus.FAILED
                if self.error_code is not None
                else TargetExecutionStatus.SUCCEEDED
            ),
            error_code=self.error_code,
            exit_code=1 if self.error_code is not None else 0,
            stdout=self.stdout,
            stderr="",
            timed_out=self.error_code == TargetExecutionErrorCode.TIMEOUT,
            output_limited=self.error_code == TargetExecutionErrorCode.OUTPUT_LIMIT,
            cancelled=self.error_code == TargetExecutionErrorCode.CANCELLED,
            started_at=now,
            finished_at=now,
        )


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


def _signed_package(
    tmp_path: Path,
) -> tuple[Path, TargetPackageManifest, Path, str]:
    package = tmp_path / "package"
    entrypoint = package / "bin/robotctl"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho rolo\n")
    payload = entrypoint.read_bytes()
    manifest = TargetPackageManifest(
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        files=[
            TargetPackageFile(
                path="bin/robotctl",
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                mode=0o755,
                role=TargetPackageFileRole.ENTRYPOINT,
            )
        ],
    )
    manifest, _, sbom_payload = bind_target_package_sbom(manifest)
    (package / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release-key.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_path = tmp_path / "release-key.pub.pem"
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    key_id = "release-key-2026"
    signature = sign_target_package(
        manifest,
        key_id=key_id,
        private_key_path=private_path,
    )
    (package / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (package / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return package, manifest, public_path, key_id


def test_detector_parses_only_the_fixed_runtime_capability_contract() -> None:
    executor = StaticExecutor(stdout=_facts().model_dump_json())

    facts = TargetRuntimeCapabilityDetector(executor).detect(
        request_id="capability-detect-0001"
    )

    assert facts == _facts()
    assert len(executor.requests) == 1
    request = executor.requests[0]
    assert request.tool == TargetInspectionTool.RUNTIME_CAPABILITIES
    assert request.operand is None
    assert request.max_stdout_bytes == 64 * 1024


@pytest.mark.parametrize(
    ("stdout", "transport_error", "expected"),
    [
        ("not-json", None, TargetExecutionErrorCode.PROTOCOL_ERROR),
        ("", TargetExecutionErrorCode.TIMEOUT, TargetExecutionErrorCode.TIMEOUT),
    ],
)
def test_detector_maps_invalid_protocol_and_transport_failure_without_remote_detail(
    stdout: str,
    transport_error: TargetExecutionErrorCode | None,
    expected: TargetExecutionErrorCode,
) -> None:
    detector = TargetRuntimeCapabilityDetector(
        StaticExecutor(stdout=stdout, error_code=transport_error)
    )

    with pytest.raises(TargetCapabilityDetectionError) as raised:
        detector.detect(request_id="capability-failure-0001")

    assert raised.value.error_code == expected
    if stdout:
        assert stdout not in str(raised.value)


def test_planner_verifies_package_and_uses_target_observed_facts(tmp_path: Path) -> None:
    package, manifest, public_key, key_id = _signed_package(tmp_path)
    executor = StaticExecutor(stdout=_facts().model_dump_json())
    planner = TargetBootstrapPlanner(
        executor,
        Ed25519TargetPackageVerifier({key_id: public_key}),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )

    plan = planner.plan(
        target_id="rover",
        package_root=package,
        request_id="bootstrap-rover",
        install_requires_sudo=True,
    )

    assert plan.manifest_sha256 == manifest.canonical_sha256()
    assert plan.preflight.status == TargetPreflightStatus.READY
    assert plan.preflight.facts == _facts()
    assert plan.approval_actions == ["INSTALL_TARGET_RUNTIME", "USE_SUDO"]
    assert all("sudo" not in step.sanitized_summary.casefold() for step in plan.steps)


def test_planner_rejects_tampered_package_before_contacting_target(tmp_path: Path) -> None:
    package, _, public_key, key_id = _signed_package(tmp_path)
    (package / "bin/robotctl").write_bytes(b"tampered")
    executor = StaticExecutor(stdout=_facts().model_dump_json())
    planner = TargetBootstrapPlanner(
        executor,
        Ed25519TargetPackageVerifier({key_id: public_key}),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )

    with pytest.raises(ValueError, match="size mismatch"):
        planner.plan(
            target_id="rover",
            package_root=package,
            request_id="bootstrap-rover",
        )

    assert executor.requests == []


def test_target_bootstrap_dry_run_cli_uses_registered_local_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, manifest, public_key, key_id = _signed_package(tmp_path)
    settings = Settings(_env_file=None, rolo_config_dir=tmp_path / "config")
    registry = TargetProfileRegistry(settings.target_profile_dir)
    registry.save_target(
        TargetProfile(
            target_id="local-rover",
            orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
            transport=TargetTransport.LOCAL,
            workspace_root="/opt/robot/ws",
            desired_rolo_version="0.2.0",
            release_signing_key_id=key_id,
            release_signing_public_key_path=str(public_key.resolve()),
            release_signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        )
    )
    monkeypatch.setattr(target_commands, "get_settings", lambda: settings)

    result = CliRunner().invoke(
        app,
        [
            "target",
            "bootstrap",
            "dry-run",
            "--target",
            "local-rover",
            "--package-root",
            str(package),
            "--public-key",
            str(public_key),
            "--signing-key-id",
            key_id,
            "--install-requires-sudo",
        ],
    )

    assert result.exit_code == 0, result.output
    assert manifest.canonical_sha256() in result.output
    assert '"INSTALL_TARGET_RUNTIME"' in result.output
    assert '"USE_SUDO"' in result.output
    assert '"RUNTIME_CAPABILITIES"' not in result.output
