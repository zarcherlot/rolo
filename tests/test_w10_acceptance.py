from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.config import get_settings
from rolo.targets import (
    CredentialPurpose,
    OrchestratorPlacement,
    SshTargetExecutor,
    TargetArchitecture,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionResult,
    TargetConnectionProfile,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
    TargetInstalledRelease,
    TargetInstallIndex,
    TargetPlatformFacts,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    W10AcceptanceGateId,
    W10AutomatedResult,
    W10RealSshAcceptanceRequest,
    W10RealSshAcceptanceRunner,
    file_credential_reference,
    parse_w10_junit_report,
    write_w10_real_ssh_acceptance_receipt,
)


def _target_and_connection(tmp_path: Path) -> tuple[TargetProfile, TargetConnectionProfile]:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("target ssh-ed25519 public-key\n", encoding="utf-8")
    credentials = []
    for name in ("provisioning", "bootstrap", "runtime"):
        path = tmp_path / f"{name}.key"
        path.write_text(f"secret-{name}", encoding="utf-8")
        credentials.append(file_credential_reference(path))
    connection = TargetConnectionProfile(
        connection_profile_id="w10-connection",
        host="target.internal",
        user="bootstrap",
        credential_ref=credentials[1],
        provisioning_user="operator",
        provisioning_credential_ref=credentials[0],
        runtime_user="rolo",
        runtime_credential_ref=credentials[2],
        known_hosts_path=str(known_hosts.resolve()),
        expected_host_key_sha256=f"SHA256:{'A' * 43}",
    )
    target = TargetProfile(
        target_id="w10-target",
        orchestrator_placement=OrchestratorPlacement.CONTROLLER,
        transport=TargetTransport.SSH,
        connection_profile_id=connection.connection_profile_id,
        workspace_root="/srv/robot",
        desired_rolo_version="0.1.0",
    )
    return target, connection


class _AcceptanceExecutor:
    def __init__(
        self,
        purpose: CredentialPurpose,
        *,
        invalid_runtime: bool = False,
        runtime_manifest_override: str | None = None,
    ) -> None:
        self.purpose = purpose
        self.invalid_runtime = invalid_runtime
        self.runtime_manifest_override = runtime_manifest_override

    def inspect(self, request: TargetInspectionRequest, **_: object) -> TargetInspectionResult:
        now = datetime.now(timezone.utc)
        if request.tool == TargetInspectionTool.RUNTIME_CAPABILITIES:
            assert self.purpose == CredentialPurpose.SSH_BOOTSTRAP
            stdout = TargetPlatformFacts(
                os="linux",
                architecture="x86_64",
                python_version="3.12.4",
                bubblewrap_available=True,
                user_namespace_available=True,
                mount_namespace_available=True,
                network_namespace_available=True,
                available_address_space_bytes=8_000_000_000,
                available_processes=512,
                runtime_path_available=True,
                explicit_pythonpath_supported=True,
                virtualenv_supported=True,
            ).model_dump_json()
        else:
            assert self.purpose in {
                CredentialPurpose.SSH_PROVISIONING,
                CredentialPurpose.SSH_RUNTIME,
            }
            if self.invalid_runtime and self.purpose == CredentialPurpose.SSH_RUNTIME:
                stdout = "not-json"
            else:
                stdout = json.dumps(
                    {
                        "machine": "x86_64",
                        "os": "linux",
                        "os_release": "6.8.0",
                        "python": "3.12.4",
                        "python_executable": "/usr/bin/python3",
                        "uid": (
                            1000 if self.purpose == CredentialPurpose.SSH_PROVISIONING else 1001
                        ),
                    }
                )
        return TargetInspectionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            executor_kind=TargetExecutorKind.SSH,
            status=TargetExecutionStatus.SUCCEEDED,
            exit_code=0,
            stdout=stdout,
            stderr="",
            started_at=now,
            finished_at=now,
        )

    def execute_bootstrap(self, request, **_):  # type: ignore[no-untyped-def]
        assert self.purpose == CredentialPurpose.SSH_RUNTIME
        assert request.operation == TargetBootstrapExecutionOperation.STATUS
        now = datetime.now(timezone.utc)
        return TargetBootstrapExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=request.target_id,
            package_id=request.package_id,
            manifest_sha256=request.manifest_sha256,
            executor_kind=TargetExecutorKind.SSH,
            operation=TargetBootstrapExecutionOperation.STATUS,
            status=TargetExecutionStatus.SUCCEEDED,
            install_index=TargetInstallIndex(
                current=TargetInstalledRelease(
                    package_id=request.package_id,
                    package_version="0.1.0",
                    manifest_sha256=(self.runtime_manifest_override or request.manifest_sha256),
                    install_path="/var/lib/rolo/runtime/versions/current",
                ),
                activated_at=now,
            ),
        )


def _test_report(tmp_path: Path, *, skipped: int = 0, failures: int = 0):
    report = tmp_path / f"report-{skipped}-{failures}.xml"
    report.write_text(
        (
            '<testsuites tests="4" failures="'
            f'{failures}" errors="0" skipped="{skipped}" time="1.25">'
            '<testsuite name="real-ssh" tests="4" failures="'
            f'{failures}" errors="0" skipped="{skipped}" time="1.25" />'
            "</testsuites>"
        ),
        encoding="utf-8",
    )
    return parse_w10_junit_report(report)


def _request(
    *,
    report_sha256: str,
    architecture: TargetArchitecture = TargetArchitecture.X86_64,
):
    return W10RealSshAcceptanceRequest(
        target_id="w10-target",
        environment_id="ubuntu-2404-x86",
        expected_architecture=architecture,
        os_image_sha256="1" * 64,
        package_id="rolo-runtime",
        package_manifest_sha256="2" * 64,
        acceptance_suite_sha256="3" * 64,
        test_report_sha256=report_sha256,
    )


def test_w10_receipt_binds_three_identities_without_self_signing_readiness(
    tmp_path: Path,
) -> None:
    target, connection = _target_and_connection(tmp_path)
    purposes: list[CredentialPurpose] = []

    def factory(purpose: CredentialPurpose) -> _AcceptanceExecutor:
        purposes.append(purpose)
        return _AcceptanceExecutor(purpose)

    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=factory,
    ).run(
        _request(report_sha256=(report := _test_report(tmp_path)).report_sha256),
        test_report=report,
    )

    assert purposes == [
        CredentialPurpose.SSH_PROVISIONING,
        CredentialPurpose.SSH_BOOTSTRAP,
        CredentialPurpose.SSH_RUNTIME,
    ]
    assert receipt.automated_result == W10AutomatedResult.PASSED
    assert receipt.matrix_status == "NOT_VERIFIED"
    assert receipt.manual_review_required is True
    assert receipt.production_ready is False
    assert receipt.runtime_installation is not None
    assert receipt.runtime_installation.current_manifest_sha256 == "2" * 64
    assert {gate.gate_id for gate in receipt.gates} == set(W10AcceptanceGateId)
    serialized = receipt.model_dump_json()
    assert "secret-provisioning" not in serialized
    assert "file-credential://" not in serialized
    assert str(tmp_path) not in serialized
    assert "target.internal" not in serialized


def test_w10_architecture_mismatch_fails_only_automated_platform_gate(
    tmp_path: Path,
) -> None:
    target, connection = _target_and_connection(tmp_path)
    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=lambda purpose: _AcceptanceExecutor(purpose),
    ).run(
        _request(
            report_sha256=(report := _test_report(tmp_path)).report_sha256,
            architecture=TargetArchitecture.AARCH64,
        ),
        test_report=report,
    )

    assert receipt.automated_result == W10AutomatedResult.FAILED
    platform_gate = next(
        gate for gate in receipt.gates if gate.gate_id == W10AcceptanceGateId.PLATFORM_BINDING
    )
    assert platform_gate.error_code == "PLATFORM_ARCHITECTURE_MISMATCH"
    assert receipt.matrix_status == "NOT_VERIFIED"


def test_w10_invalid_typed_platform_is_a_protocol_failure(tmp_path: Path) -> None:
    target, connection = _target_and_connection(tmp_path)
    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=lambda purpose: _AcceptanceExecutor(
            purpose,
            invalid_runtime=True,
        ),
    ).run(
        _request(report_sha256=(report := _test_report(tmp_path)).report_sha256),
        test_report=report,
    )

    runtime_gate = next(
        gate
        for gate in receipt.gates
        if gate.gate_id == W10AcceptanceGateId.RUNTIME_TYPED_INSPECTION
    )
    assert runtime_gate.automated_result == W10AutomatedResult.FAILED
    assert runtime_gate.error_code == "PROTOCOL_ERROR"
    assert receipt.automated_result == W10AutomatedResult.FAILED


def test_w10_runtime_installation_mismatch_fails_closed(tmp_path: Path) -> None:
    target, connection = _target_and_connection(tmp_path)
    report = _test_report(tmp_path)
    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=lambda purpose: _AcceptanceExecutor(
            purpose,
            runtime_manifest_override=(
                "9" * 64 if purpose == CredentialPurpose.SSH_RUNTIME else None
            ),
        ),
    ).run(
        _request(report_sha256=report.report_sha256),
        test_report=report,
    )

    runtime_gate = next(
        gate
        for gate in receipt.gates
        if gate.gate_id == W10AcceptanceGateId.RUNTIME_INSTALLATION_BINDING
    )
    assert runtime_gate.error_code == "RUNTIME_PACKAGE_MISMATCH"
    assert receipt.automated_result == W10AutomatedResult.FAILED
    assert receipt.runtime_installation is not None
    assert receipt.runtime_installation.current_manifest_sha256 == "9" * 64
    assert "install_path" not in receipt.model_dump_json()


def test_w10_all_skipped_junit_report_cannot_pass_acceptance(tmp_path: Path) -> None:
    target, connection = _target_and_connection(tmp_path)
    report = _test_report(tmp_path, skipped=4)
    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=lambda purpose: _AcceptanceExecutor(purpose),
    ).run(
        _request(report_sha256=report.report_sha256),
        test_report=report,
    )

    report_gate = next(
        gate for gate in receipt.gates if gate.gate_id == W10AcceptanceGateId.REAL_SSH_TEST_REPORT
    )
    assert report_gate.error_code == "TEST_REPORT_INSUFFICIENT_EXECUTION"
    assert receipt.automated_result == W10AutomatedResult.FAILED


def test_w10_junit_parser_rejects_entity_declarations(tmp_path: Path) -> None:
    report = tmp_path / "hostile.xml"
    report.write_text(
        '<!DOCTYPE testsuite [<!ENTITY leak SYSTEM "file:///etc/passwd">]>'
        '<testsuite tests="4" failures="0" errors="0" skipped="0" time="0" />',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="DTD or entity"):
        parse_w10_junit_report(report)


def test_w10_runner_rejects_collapsed_identity_configuration(tmp_path: Path) -> None:
    target, connection = _target_and_connection(tmp_path)
    collapsed = connection.model_copy(
        update={
            "runtime_user": None,
            "runtime_credential_ref": None,
        }
    )

    with pytest.raises(ValueError, match="explicit SSH_RUNTIME identity"):
        W10RealSshAcceptanceRunner(
            target=target,
            connection=collapsed,
            executor_factory=lambda purpose: _AcceptanceExecutor(purpose),
        )


def test_w10_receipt_writer_persists_only_secret_closed_contract(tmp_path: Path) -> None:
    target, connection = _target_and_connection(tmp_path)
    receipt = W10RealSshAcceptanceRunner(
        target=target,
        connection=connection,
        executor_factory=lambda purpose: _AcceptanceExecutor(purpose),
    ).run(
        _request(report_sha256=(report := _test_report(tmp_path)).report_sha256),
        test_report=report,
    )
    output = tmp_path / "evidence" / "receipt.json"

    write_w10_real_ssh_acceptance_receipt(output, receipt)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["request_sha256"] == receipt.request_sha256
    assert loaded["production_ready"] is False
    assert "file-credential://" not in output.read_text(encoding="utf-8")


def test_w10_real_ssh_cli_hashes_suite_and_binds_junit_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    target, connection = _target_and_connection(tmp_path)
    registry = TargetProfileRegistry(get_settings().target_profile_dir)
    TargetRegistrationService(registry).register(
        TargetRegistrationRequest(target=target, connection=connection),
        principal="fixture",
        idempotency_key="w10-cli-registration-0001",
    )
    suite = tmp_path / "real_ssh_suite.py"
    suite.write_text("# immutable acceptance suite\n", encoding="utf-8")
    report_path = tmp_path / "real-ssh.junit.xml"
    report_path.write_text(
        '<testsuites tests="4" failures="0" errors="0" skipped="0" time="1.25" />',
        encoding="utf-8",
    )
    expected_report = parse_w10_junit_report(report_path)

    def inspect(self, request, **_):  # type: ignore[no-untyped-def]
        purpose = self._credential_purpose
        return _AcceptanceExecutor(purpose).inspect(request)

    def execute_bootstrap(self, request, **_):  # type: ignore[no-untyped-def]
        purpose = self._credential_purpose
        return _AcceptanceExecutor(purpose).execute_bootstrap(request)

    monkeypatch.setattr(SshTargetExecutor, "inspect", inspect)
    monkeypatch.setattr(SshTargetExecutor, "execute_bootstrap", execute_bootstrap)
    output = tmp_path / "evidence" / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "target",
            "acceptance",
            "real-ssh",
            "--target",
            target.target_id,
            "--environment",
            "ubuntu-2404-x86",
            "--architecture",
            "x86_64",
            "--os-image-sha256",
            "1" * 64,
            "--package-manifest-sha256",
            "2" * 64,
            "--package-id",
            "rolo-runtime",
            "--acceptance-suite",
            str(suite),
            "--test-report",
            str(report_path),
            "--output",
            str(output),
        ],
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_report"]["report_sha256"] == expected_report.report_sha256
    assert payload["request"]["acceptance_suite_sha256"] != "3" * 64
    assert payload["automated_result"] == "PASSED"
    assert payload["production_ready"] is False
    assert output.is_file()
    assert str(tmp_path) not in result.stdout
