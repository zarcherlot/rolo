from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.commands import target_executor as target_executor_commands
from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    BootstrapInstallStatus,
    DeploymentAuthorizationKeyPin,
    DeploymentAuthorizationKeyRegistry,
    TargetArchitecture,
    TargetBootstrapAuthorizationKeyStatus,
    TargetBootstrapExecutionErrorCode,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetBootstrapExecutionResult,
    TargetBootstrapExecutionService,
    TargetBootstrapOperator,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetPackageChunkStore,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPlatformFacts,
    bind_target_package_sbom,
    ed25519_public_key_sha256,
    sign_target_package,
)
from rolo.targets.bootstrap_execution import _PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT

APPROVAL_ID = "approval-" + "a" * 32
KEY_ID = "release-key-2026"
NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class VersionHealthChecker:
    def __init__(self, healthy: set[str]) -> None:
        self.healthy = healthy
        self.checked: list[str] = []

    def check(self, entrypoint: Path, manifest: TargetPackageManifest) -> bool:
        assert entrypoint.is_file()
        self.checked.append(manifest.package_version)
        return manifest.package_version in self.healthy


def _facts(**updates: object) -> TargetPlatformFacts:
    values: dict[str, object] = {
        "os": "linux",
        "architecture": "x86_64",
        "python_version": "3.12.4",
        "bubblewrap_available": True,
        "user_namespace_available": True,
        "mount_namespace_available": True,
        "network_namespace_available": True,
        "available_address_space_bytes": 8 * 1024 * 1024 * 1024,
        "available_processes": 256,
        "runtime_path_available": True,
        "explicit_pythonpath_supported": True,
        "virtualenv_supported": True,
    }
    values.update(updates)
    return TargetPlatformFacts.model_validate(values)


def _key_pair(tmp_path: Path) -> tuple[Path, bytes]:
    key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release-key.pem"
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_path, public


def _authorization_pin(
    *,
    key_id: str,
    approval_id: str = APPROVAL_ID,
) -> DeploymentAuthorizationKeyPin:
    public_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return DeploymentAuthorizationKeyPin(
        target_id="rover",
        key_id=key_id,
        public_key_base64=b64encode(public_key).decode("ascii"),
        public_key_sha256=ed25519_public_key_sha256(public_key),
        installed_by_approval_id=approval_id,
        installed_at=NOW,
    )


def _incoming_package(
    tmp_path: Path,
    incoming: Path,
    private_key: Path,
    version: str,
) -> TargetPackageManifest:
    source = tmp_path / f"source-{version}"
    entrypoint = source / "bin/robotctl"
    runtime = source / "share/rolo/runtime.json"
    entrypoint.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    entrypoint.write_bytes(f"#!/bin/sh\necho {version}\n".encode())
    runtime.write_text(f'{{"version":"{version}"}}', encoding="utf-8")

    def item(path: Path, role: TargetPackageFileRole, mode: int) -> TargetPackageFile:
        payload = path.read_bytes()
        return TargetPackageFile(
            path=path.relative_to(source).as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mode=mode,
            role=role,
        )

    manifest = TargetPackageManifest(
        package_id="rolo-target",
        package_version=version,
        rolo_version=version,
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        files=sorted(
            [
                item(entrypoint, TargetPackageFileRole.ENTRYPOINT, 0o755),
                item(runtime, TargetPackageFileRole.RUNTIME, 0o644),
            ],
            key=lambda value: value.path,
        ),
    )
    manifest, _, sbom_payload = bind_target_package_sbom(manifest)
    (source / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
    signature = sign_target_package(
        manifest,
        key_id=KEY_ID,
        private_key_path=private_key,
    )
    (source / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (source / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    destination = (
        incoming
        / "packages"
        / manifest.package_id
        / manifest.canonical_sha256()
    )
    shutil.copytree(source, destination)
    return manifest


def _request(
    operation: TargetBootstrapExecutionOperation,
    manifest: TargetPackageManifest,
    public_key: bytes,
    **updates: object,
) -> TargetBootstrapExecutionRequest:
    values: dict[str, object] = {
        "request_id": f"bootstrap-{operation.value.casefold().replace('_', '-')}",
        "operation": operation,
        "target_id": "rover",
        "package_id": manifest.package_id,
        "manifest_sha256": manifest.canonical_sha256(),
    }
    if operation != TargetBootstrapExecutionOperation.STATUS:
        values.update(
            {
                "signing_key_id": KEY_ID,
                "signing_public_key_base64": b64encode(public_key).decode("ascii"),
                "signing_public_key_sha256": ed25519_public_key_sha256(public_key),
            }
        )
    if operation in {
        TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
        TargetBootstrapExecutionOperation.ROLLBACK,
    }:
        values["approval_id"] = APPROVAL_ID
    values.update(updates)
    return TargetBootstrapExecutionRequest.model_validate(values)


def test_execution_request_requires_key_approval_and_operation_specific_cas(
    tmp_path: Path,
) -> None:
    private_key, public_key = _key_pair(tmp_path)
    manifest = _incoming_package(tmp_path, tmp_path / "incoming", private_key, "0.2.0")
    install = _request(
        TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
        manifest,
        public_key,
    )

    with pytest.raises(ValidationError, match="approval reference"):
        TargetBootstrapExecutionRequest.model_validate(
            {**install.model_dump(), "approval_id": None}
        )
    with pytest.raises(ValidationError, match="signing-key inputs"):
        TargetBootstrapExecutionRequest.model_validate(
            {**install.model_dump(), "signing_public_key_base64": None}
        )
    with pytest.raises(ValidationError, match="public key digest mismatch"):
        TargetBootstrapExecutionRequest.model_validate(
            {**install.model_dump(), "signing_public_key_sha256": "0" * 64}
        )
    with pytest.raises(ValidationError, match="requires expected current digest"):
        _request(
            TargetBootstrapExecutionOperation.ROLLBACK,
            manifest,
            public_key,
        )
    pin = _authorization_pin(key_id="controller-authorization-2026")
    with pytest.raises(ValidationError, match="pin binding mismatch"):
        TargetBootstrapExecutionRequest.model_validate(
            {
                **install.model_dump(mode="json"),
                "authorization_key_pin": pin.model_copy(
                    update={"target_id": "other-target"}
                ).model_dump(mode="json"),
            }
        )
    with pytest.raises(ValidationError, match="requires install activation"):
        _request(
            TargetBootstrapExecutionOperation.HEALTH,
            manifest,
            public_key,
            authorization_key_pin=pin,
        )


def test_bootstrap_installs_rotates_and_idempotently_recovers_authorization_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incoming = tmp_path / "incoming"
    private_key, package_public_key = _key_pair(tmp_path)
    manifest = _incoming_package(tmp_path, incoming, private_key, "0.2.0")
    registry = DeploymentAuthorizationKeyRegistry(tmp_path / "authorization-pins")
    service = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "install",
        facts_provider=_facts,
        health_checker=VersionHealthChecker({"0.2.0"}),
        authorization_key_registry=registry,
    )
    initial_pin = _authorization_pin(key_id="controller-authorization-2026")
    initial_request = _request(
        TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
        manifest,
        package_public_key,
        expect_current_present=False,
        authorization_key_pin=initial_pin,
    )
    apply_update = registry.apply_bootstrap_update
    crashed = False

    def crash_after_runtime(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal crashed
        if not crashed:
            crashed = True
            raise RuntimeError("simulated controller interruption")
        return apply_update(*args, **kwargs)

    monkeypatch.setattr(registry, "apply_bootstrap_update", crash_after_runtime)
    with pytest.raises(RuntimeError, match="simulated controller interruption"):
        service.execute(initial_request)
    with pytest.raises(ValueError, match="unavailable"):
        registry.load("rover")
    monkeypatch.setattr(registry, "apply_bootstrap_update", apply_update)

    recovered = service.execute(initial_request)
    repeated = service.execute(initial_request)

    assert recovered.status == TargetExecutionStatus.SUCCEEDED
    assert recovered.install_result is not None
    assert recovered.install_result.status == BootstrapInstallStatus.ALREADY_ACTIVE
    assert recovered.authorization_key_status == (
        TargetBootstrapAuthorizationKeyStatus.INSTALLED
    )
    assert repeated.authorization_key_status == (
        TargetBootstrapAuthorizationKeyStatus.ALREADY_CURRENT
    )
    assert registry.load("rover") == initial_pin

    rotated_pin = _authorization_pin(key_id="controller-authorization-2027")
    rotation = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            package_public_key,
            expect_current_present=True,
            expected_current_manifest_sha256=manifest.canonical_sha256(),
            authorization_key_pin=rotated_pin,
            expected_authorization_key_sha256=initial_pin.public_key_sha256,
        )
    )
    stale = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            package_public_key,
            expect_current_present=True,
            expected_current_manifest_sha256=manifest.canonical_sha256(),
            authorization_key_pin=_authorization_pin(
                key_id="controller-authorization-stale"
            ),
            expected_authorization_key_sha256=initial_pin.public_key_sha256,
        )
    )

    assert rotation.status == TargetExecutionStatus.SUCCEEDED
    assert rotation.authorization_key_status == (
        TargetBootstrapAuthorizationKeyStatus.INSTALLED
    )
    assert registry.load("rover") == rotated_pin
    assert stale.status == TargetExecutionStatus.FAILED
    assert stale.bootstrap_error_code == (
        TargetBootstrapExecutionErrorCode.AUTHORIZATION_KEY_CONFLICT
    )
    assert stale.authorization_key_status == (
        TargetBootstrapAuthorizationKeyStatus.FAILED
    )
    assert registry.load("rover") == rotated_pin


def test_service_installs_health_checks_upgrades_and_rolls_back(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    private_key, public_key = _key_pair(tmp_path)
    first = _incoming_package(tmp_path, incoming, private_key, "0.2.0")
    second = _incoming_package(tmp_path, incoming, private_key, "0.3.0")
    health = VersionHealthChecker({"0.2.0", "0.3.0"})
    service = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "install",
        facts_provider=_facts,
        health_checker=health,
    )

    first_result = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            first,
            public_key,
            expect_current_present=False,
        )
    )
    status = service.execute(
        _request(TargetBootstrapExecutionOperation.STATUS, first, public_key)
    )
    healthy = service.execute(
        _request(TargetBootstrapExecutionOperation.HEALTH, first, public_key)
    )
    second_result = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            second,
            public_key,
            expect_current_present=True,
            expected_current_manifest_sha256=first.canonical_sha256(),
        )
    )
    rollback = service.execute(
        _request(
            TargetBootstrapExecutionOperation.ROLLBACK,
            first,
            public_key,
            expected_current_manifest_sha256=second.canonical_sha256(),
        )
    )

    assert first_result.status == TargetExecutionStatus.SUCCEEDED
    assert first_result.install_result is not None
    assert first_result.install_result.status == BootstrapInstallStatus.ACTIVATED
    assert status.install_index is not None
    assert status.install_index.current.manifest_sha256 == first.canonical_sha256()
    assert healthy.status == TargetExecutionStatus.SUCCEEDED
    assert healthy.healthy is True
    assert second_result.install_result is not None
    assert second_result.install_result.active is not None
    assert second_result.install_result.active.manifest_sha256 == second.canonical_sha256()
    assert rollback.install_result is not None
    assert rollback.install_result.status == BootstrapInstallStatus.ROLLED_BACK
    assert rollback.install_result.active is not None
    assert rollback.install_result.active.manifest_sha256 == first.canonical_sha256()


def test_service_preflight_blocker_and_health_failure_do_not_activate(
    tmp_path: Path,
) -> None:
    incoming = tmp_path / "incoming"
    private_key, public_key = _key_pair(tmp_path)
    manifest = _incoming_package(tmp_path, incoming, private_key, "0.2.0")
    blocked = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "blocked-install",
        facts_provider=lambda: _facts(available_processes=1),
        health_checker=VersionHealthChecker({"0.2.0"}),
    ).execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            public_key,
        )
    )
    unhealthy_service = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "unhealthy-install",
        facts_provider=_facts,
        health_checker=VersionHealthChecker(set()),
    )
    unhealthy = unhealthy_service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            public_key,
        )
    )
    status = unhealthy_service.execute(
        _request(TargetBootstrapExecutionOperation.STATUS, manifest, public_key)
    )

    assert blocked.status == TargetExecutionStatus.FAILED
    assert blocked.bootstrap_error_code == (
        TargetBootstrapExecutionErrorCode.PREFLIGHT_BLOCKED
    )
    assert blocked.blockers == ["TARGET_PROCESS_BUDGET_INSUFFICIENT"]
    assert unhealthy.status == TargetExecutionStatus.FAILED
    assert unhealthy.bootstrap_error_code == (
        TargetBootstrapExecutionErrorCode.HEALTH_CHECK_FAILED
    )
    assert status.install_index is None


def test_service_maps_compare_and_swap_and_package_tamper(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    private_key, public_key = _key_pair(tmp_path)
    manifest = _incoming_package(tmp_path, incoming, private_key, "0.2.0")
    service = TargetBootstrapExecutionService(
        incoming_root=incoming,
        install_root=tmp_path / "install",
        facts_provider=_facts,
        health_checker=VersionHealthChecker({"0.2.0"}),
    )
    first = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            public_key,
            expect_current_present=False,
        )
    )
    conflict = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            public_key,
            expect_current_present=False,
        )
    )
    package_root = (
        incoming / "packages" / manifest.package_id / manifest.canonical_sha256()
    )
    (package_root / "bin/robotctl").write_bytes(b"tampered")
    tampered = service.execute(
        _request(
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            manifest,
            public_key,
            expect_current_present=True,
            expected_current_manifest_sha256=manifest.canonical_sha256(),
        )
    )

    assert first.status == TargetExecutionStatus.SUCCEEDED
    assert conflict.bootstrap_error_code == TargetBootstrapExecutionErrorCode.STATE_CONFLICT
    assert tampered.bootstrap_error_code == TargetBootstrapExecutionErrorCode.PACKAGE_INVALID


def test_unified_operator_uploads_executes_and_repeats_idempotently(
    tmp_path: Path,
) -> None:
    source_incoming = tmp_path / "source-incoming"
    target_incoming = tmp_path / "target-incoming"
    private_key, public_key = _key_pair(tmp_path)
    manifest = _incoming_package(
        tmp_path,
        source_incoming,
        private_key,
        "0.2.0",
    )
    package = (
        source_incoming
        / "packages"
        / manifest.package_id
        / manifest.canonical_sha256()
    )
    service = TargetBootstrapExecutionService(
        incoming_root=target_incoming,
        install_root=tmp_path / "install",
        facts_provider=_facts,
        health_checker=VersionHealthChecker({"0.2.0"}),
    )
    store = TargetPackageChunkStore(target_incoming)

    class CompositeExecutor:
        def transfer_package_chunk(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            return store.apply(request)

        def execute_bootstrap(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            return service.execute(request)

    operator = TargetBootstrapOperator(
        CompositeExecutor(),  # type: ignore[arg-type]
        signing_key_id=KEY_ID,
        signing_public_key=public_key,
        chunk_size_bytes=64,
    )

    first = operator.install_and_activate(
        package,
        target_id="rover",
        request_id="bootstrap-rover-first",
        approval_id=APPROVAL_ID,
        expect_current_present=False,
    )
    repeated = operator.install_and_activate(
        package,
        target_id="rover",
        request_id="bootstrap-rover-repeat",
        approval_id=APPROVAL_ID,
        expect_current_present=True,
        expected_current_manifest_sha256=manifest.canonical_sha256(),
    )

    assert first.execution.status == TargetExecutionStatus.SUCCEEDED
    assert first.execution.install_result is not None
    assert first.execution.install_result.status == BootstrapInstallStatus.ACTIVATED
    assert first.upload.bytes_uploaded == first.upload.bytes_total
    assert repeated.execution.install_result is not None
    assert repeated.execution.install_result.status == (
        BootstrapInstallStatus.ALREADY_ACTIVE
    )
    assert repeated.upload.bytes_uploaded == 0
    assert repeated.upload.bytes_resumed == repeated.upload.bytes_total


def test_hidden_bootstrap_companion_accepts_only_strict_bounded_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = TargetBootstrapExecutionRequest(
        request_id="bootstrap-status-cli",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
    )

    class FakeLocalExecutor:
        def __init__(self, **_: object) -> None:
            pass

        def execute_bootstrap(self, value):  # type: ignore[no-untyped-def]
            assert value == request
            return TargetBootstrapExecutionResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.target_id,
                package_id=value.package_id,
                manifest_sha256=value.manifest_sha256,
                signing_key_id=value.signing_key_id,
                signing_public_key_sha256=value.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                operation=value.operation,
                status=TargetExecutionStatus.SUCCEEDED,
                install_index=None,
            )

    monkeypatch.setattr(
        target_executor_commands,
        "LocalTargetExecutor",
        FakeLocalExecutor,
    )
    result = CliRunner().invoke(
        app,
        ["target-executor", "bootstrap"],
        input=request.model_dump_json(),
    )

    assert result.exit_code == 0, result.output
    assert '"status": "SUCCEEDED"' in result.output

    invalid = CliRunner().invoke(
        app,
        ["target-executor", "bootstrap"],
        input=json.dumps(
            {
                **request.model_dump(mode="json"),
                "sudo_command": "must-not-be-echoed",
            }
        ),
    )
    assert invalid.exit_code == 2
    assert "extra_forbidden" in invalid.output
    assert "must-not-be-echoed" not in invalid.output


@pytest.mark.skipif(os.name != "posix", reason="preinstall launcher targets Linux")
def test_preinstall_launcher_binds_manifest_entrypoint_argv_and_stdin(
    tmp_path: Path,
) -> None:
    entrypoint_payload = b"""#!/usr/bin/env python3
import hashlib,json,sys
if sys.argv[1:] != ['target-executor','bootstrap']:
    raise SystemExit(3)
request=json.load(sys.stdin)
payload=json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
print(json.dumps({
    'schema_version':'rolo-target-bootstrap-execution-result/v1',
    'request_id':request['request_id'],
    'request_sha256':hashlib.sha256(payload).hexdigest(),
    'target_id':request['target_id'],
    'package_id':request['package_id'],
    'manifest_sha256':request['manifest_sha256'],
    'signing_key_id':request['signing_key_id'],
    'signing_public_key_sha256':request['signing_public_key_sha256'],
    'executor_kind':'LOCAL',
    'operation':request['operation'],
    'status':'SUCCEEDED',
    'transport_error_code':None,
    'bootstrap_error_code':None,
    'blockers':[],
    'install_result':None,
    'install_index':None,
    'healthy':None,
},sort_keys=True,separators=(',',':')))
"""
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
                sha256=hashlib.sha256(entrypoint_payload).hexdigest(),
                size_bytes=len(entrypoint_payload),
                mode=0o755,
                role=TargetPackageFileRole.ENTRYPOINT,
            )
        ],
    )
    package = (
        tmp_path
        / ".local/share/rolo/bootstrap/incoming/packages/rolo-target"
        / manifest.canonical_sha256()
    )
    (package / "bin").mkdir(parents=True)
    (package / "bin/robotctl").write_bytes(entrypoint_payload)
    (package / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    request = TargetBootstrapExecutionRequest(
        request_id="bootstrap-launcher-status",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id="rover",
        package_id=manifest.package_id,
        manifest_sha256=manifest.canonical_sha256(),
    )
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-c", _PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT],
        input=request.model_dump_json(),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    result = TargetBootstrapExecutionResult.model_validate_json(completed.stdout)
    assert result.request_sha256 == request.canonical_sha256()
    assert result.operation == request.operation

    (package / "bin/robotctl").write_bytes(b"tampered")
    rejected = subprocess.run(
        [sys.executable, "-c", _PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT],
        input=request.model_dump_json(),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
        env=environment,
    )
    assert rejected.returncode == 2
    assert rejected.stdout == ""
