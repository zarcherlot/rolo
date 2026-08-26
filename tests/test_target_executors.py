from __future__ import annotations

import json
import sys
import threading
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.stages.adapt.target_evidence import new_request
from rolo.targets import (
    AdapterReleaseActivationExecutionResult,
    AdapterReleaseActivationOperation,
    AdapterReleaseActivationRequest,
    AdapterReleaseDescribeExecutionResult,
    AdapterReleaseDescribeRequest,
    AdapterReleaseDesiredState,
    AdapterReleaseGateReceipt,
    AdapterReleaseGateSignature,
    AdapterReleaseStageExecutionResult,
    AdapterReleaseStageRequest,
    AdapterReleaseStatusExecutionResult,
    AdapterReleaseStatusRequest,
    ApprovalAction,
    BoundedProcessRunner,
    CollectorConfigurationV4,
    CredentialPurpose,
    CredentialResolver,
    DeploymentAuthorizationGrant,
    DeploymentAuthorizationProof,
    DeploymentAuthorizationSignature,
    FileCredentialProvider,
    LocalTargetExecutor,
    SshTargetExecutor,
    TargetBootstrapExecutionErrorCode,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetBootstrapExecutionResult,
    TargetConnectionProfile,
    TargetDescribeRequest,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentResult,
    TargetEnrollmentService,
    TargetEnrollmentStatus,
    TargetEvidenceCollectionRequestV4,
    TargetEvidenceCollectionResultV4,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
    TargetPackageTransferOperation,
    TargetPackageTransferRequest,
    TargetPackageTransferResult,
    TargetPlatformFacts,
    TargetProjectEvidenceCandidate,
    TargetProjectEvidenceExecutionResult,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceRequest,
    TargetSourceDiscoveryExecutionResult,
    TargetSourceDiscoveryRequest,
    TargetWorkspaceRef,
    build_adapter_release_status_request,
    deployment_request_payload_sha256,
    ed25519_public_key_sha256,
    file_credential_reference,
)
from rolo.targets.executor import _ProcessOutcome, _ProcessSpec


def _request(**updates: object) -> TargetInspectionRequest:
    values: dict[str, object] = {
        "request_id": "inspect-platform-0001",
        "tool": TargetInspectionTool.PLATFORM,
        "timeout_s": 5.0,
    }
    values.update(updates)
    return TargetInspectionRequest.model_validate(values)


def _enrollment_request(
    operation: TargetEnrollmentOperation,
    *,
    request_id: str,
    expected_collector_id: str | None = None,
) -> TargetEnrollmentRequest:
    now = datetime.now(timezone.utc)
    mutation = operation != TargetEnrollmentOperation.STATUS
    configuration = CollectorConfigurationV4() if mutation else None
    return TargetEnrollmentRequest(
        request_id=request_id,
        operation=operation,
        target_id="rover-target",
        robot_id="rover",
        challenge_nonce="9" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        configuration_sha256=(
            configuration.canonical_sha256() if configuration is not None else None
        ),
        configuration=configuration,
        expected_collector_id=expected_collector_id,
        approval_id="approval-" + "f" * 32 if mutation else None,
    )


def _authorized_runtime_evidence_request() -> TargetEvidenceCollectionRequestV4:
    now = datetime.now(timezone.utc)
    unsigned = TargetEvidenceCollectionRequestV4(
        request_id="collect-v4-runtime-0001",
        target_id="rover-target",
        evidence_request=new_request("rover"),
        approval_id="approval-" + "7" * 32,
    )
    grant = DeploymentAuthorizationGrant(
        authorization_id="authorization-" + "8" * 32,
        approval_id=unsigned.approval_id,
        decision_id="decision-" + "9" * 32,
        job_id="deployment-" + "a" * 32,
        target_id=unsigned.target_id,
        command_sha256="b" * 64,
        action=ApprovalAction.COLLECT_RUNTIME_EVIDENCE,
        approver_principal="reviewer@example.com",
        request_schema_version=unsigned.schema_version,
        request_payload_sha256=deployment_request_payload_sha256(unsigned),
        issued_at=now,
        expires_at=now + timedelta(minutes=1),
    )
    proof = DeploymentAuthorizationProof(
        grant=grant,
        signature=DeploymentAuthorizationSignature(
            key_id="controller-authorization-2026",
            grant_sha256=grant.canonical_sha256(),
            signature_base64=b64encode(b"s" * 64).decode("ascii"),
        ),
    )
    return TargetEvidenceCollectionRequestV4.model_validate(
        {**unsigned.model_dump(mode="json"), "authorization": proof.model_dump(mode="json")}
    )


def _adapter_release_stage_request() -> AdapterReleaseStageRequest:
    public_key = b"p" * 32
    return AdapterReleaseStageRequest(
        request_id="stage-adapter-release-0001",
        target_id="rover-target",
        robot_id="rover",
        release_id="release-r1",
        package_id="ar-0123456789abcdef",
        manifest_sha256="a" * 64,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "e" * 32,
    )


def _adapter_release_activation_request() -> AdapterReleaseActivationRequest:
    public_key = b"p" * 32
    now = datetime.now(timezone.utc)
    receipt = AdapterReleaseGateReceipt(
        target_id="rover-target",
        robot_id="rover",
        collector_id="collector-" + "1" * 32,
        descriptor_sha256="2" * 64,
        release_id="release-r1",
        transfer_manifest_sha256="a" * 64,
        release_manifest_sha256="3" * 64,
        bundle_manifest_sha256="4" * 64,
        runtime_context_sha256="5" * 64,
        sandbox_profile_sha256="6" * 64,
        describe_request_sha256="7" * 64,
        describe_attestation_sha256="8" * 64,
        describe_payload_sha256="9" * 64,
        describe_output_sha256="a" * 64,
        gate_report_sha256="b" * 64,
        verified_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    return AdapterReleaseActivationRequest(
        request_id="activate-adapter-release-0001",
        operation=AdapterReleaseActivationOperation.ACTIVATE,
        target_id=receipt.target_id,
        robot_id=receipt.robot_id,
        release_id=receipt.release_id,
        transfer_manifest_sha256=receipt.transfer_manifest_sha256,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "d" * 32,
        gate_receipt=receipt,
        gate_signature=AdapterReleaseGateSignature(
            key_id="release-key-2026",
            receipt_sha256=receipt.canonical_sha256(),
            signature_base64=b64encode(b"s" * 64).decode("ascii"),
        ),
        expect_current_present=False,
    )


def _adapter_release_describe_request() -> AdapterReleaseDescribeRequest:
    public_key = b"p" * 32
    now = datetime.now(timezone.utc)
    return AdapterReleaseDescribeRequest(
        request_id="execute-adapter-describe-0001",
        transfer_manifest_sha256="a" * 64,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        describe=TargetDescribeRequest(
            request_id="target-describe-0001",
            target_id="rover-target",
            robot_id="rover",
            collector_id="collector-" + "1" * 32,
            release_id="release-r1",
            release_manifest_sha256="2" * 64,
            bundle_manifest_sha256="3" * 64,
            runtime_context_sha256="4" * 64,
            sandbox_profile_sha256="5" * 64,
            nonce="6" * 32,
            issued_at=now,
            expires_at=now + timedelta(minutes=2),
        ),
    )


def _adapter_release_status_request() -> AdapterReleaseStatusRequest:
    public_key = b"p" * 32
    desired = AdapterReleaseDesiredState(
        target_id="rover-target",
        robot_id="rover",
        release_id="release-r1",
        controller_release_index_sha256="1" * 64,
        transfer_manifest_sha256="2" * 64,
        release_manifest_sha256="3" * 64,
        bundle_manifest_sha256="4" * 64,
        runtime_context_sha256="5" * 64,
    )
    return build_adapter_release_status_request(
        request_id="status-adapter-release-0001",
        desired=desired,
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    )


def _project_evidence_request() -> TargetProjectEvidenceRequest:
    return TargetProjectEvidenceRequest(
        request_id="project-evidence-0001",
        workspace=TargetWorkspaceRef(
            workspace_id="rover-workspace",
            target_id="rover-target",
            robot_id="rover",
            root="/opt/robot/workspace",
        ),
        candidates=[
            TargetProjectEvidenceCandidate(
                path="pyproject.toml",
                kind=TargetProjectEvidenceKind.BUILD_METADATA,
            )
        ],
        approval_id="approval-" + "c" * 32,
    )


def _source_discovery_request() -> TargetSourceDiscoveryRequest:
    return TargetSourceDiscoveryRequest(
        request_id="source-discovery-0001",
        workspace=TargetWorkspaceRef(
            workspace_id="rover-workspace",
            target_id="rover-target",
            robot_id="rover",
            root="/opt/robot/workspace",
        ),
        scan_roots=["."],
        approval_id="approval-" + "b" * 32,
    )


def _connection(
    tmp_path: Path,
    *,
    profile_id: str = "conn-target",
    host: str = "target.example",
    port: int = 2222,
    proxy: str | None = None,
) -> TargetConnectionProfile:
    identity = tmp_path / f"{profile_id}.key"
    identity.write_text("not-a-real-private-key", encoding="utf-8")
    known_hosts = tmp_path / f"{profile_id}.known_hosts"
    key = f"test-key-{profile_id}".encode()
    encoded_key = b64encode(key).decode("ascii")
    known_host = host if port == 22 else f"[{host}]:{port}"
    known_hosts.write_text(
        f"{known_host} ssh-ed25519 {encoded_key}\n",
        encoding="utf-8",
    )
    fingerprint = "SHA256:" + b64encode(sha256(key).digest()).decode("ascii").rstrip("=")
    return TargetConnectionProfile(
        connection_profile_id=profile_id,
        host=host,
        port=port,
        user="rolo-runtime",
        credential_ref=file_credential_reference(identity),
        known_hosts_path=str(known_hosts.resolve()),
        expected_host_key_sha256=fingerprint,
        proxy_jump_profile_id=proxy,
    )


def _outcome(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    error_code: TargetExecutionErrorCode | None = None,
) -> _ProcessOutcome:
    now = datetime.now(timezone.utc)
    return _ProcessOutcome(
        error_code=error_code,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        started_at=now,
        finished_at=now,
    )


class CapturingRunner:
    def __init__(self, outcome: _ProcessOutcome) -> None:
        self.outcome = outcome
        self.spec: _ProcessSpec | None = None
        self.config_text = ""

    def run(
        self,
        spec: _ProcessSpec,
        *,
        cancel_event: threading.Event | None = None,
    ) -> _ProcessOutcome:
        self.spec = spec
        config_path = Path(spec.argv[spec.argv.index("-F") + 1])
        self.config_text = config_path.read_text(encoding="utf-8")
        return self.outcome


def _success_result(request: TargetInspectionRequest) -> TargetInspectionResult:
    now = datetime.now(timezone.utc)
    return TargetInspectionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        executor_kind=TargetExecutorKind.LOCAL,
        status=TargetExecutionStatus.SUCCEEDED,
        exit_code=0,
        stdout='{"ok":true}',
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_local_executor_runs_registered_platform_and_path_inspections(tmp_path: Path) -> None:
    executor = LocalTargetExecutor()
    platform_result = executor.inspect(_request())
    path_result = executor.inspect(
        _request(
            request_id="inspect-path-0001",
            tool=TargetInspectionTool.PATH_STAT,
            operand=str(tmp_path.resolve()),
        )
    )

    assert platform_result.status == TargetExecutionStatus.SUCCEEDED
    assert platform_result.executor_kind == TargetExecutorKind.LOCAL
    assert set(json.loads(platform_result.stdout)) == {
        "machine",
        "os",
        "os_release",
        "python",
        "python_executable",
        "uid",
    }
    assert json.loads(path_result.stdout)["is_dir"] is True


def test_bounded_runner_has_deterministic_timeout_cancel_limit_and_exit_codes() -> None:
    runner = BoundedProcessRunner()
    common = {
        "stdin": "",
        "max_stdout_bytes": 100,
        "max_stderr_bytes": 100,
    }
    timeout = runner.run(
        _ProcessSpec(
            argv=[sys.executable, "-c", "import time; time.sleep(2)"],
            timeout_s=0.05,
            **common,
        )
    )
    cancel = threading.Event()
    cancel.set()
    cancelled = runner.run(
        _ProcessSpec(
            argv=[sys.executable, "-c", "import time; time.sleep(2)"],
            timeout_s=5,
            **common,
        ),
        cancel_event=cancel,
    )
    limited = runner.run(
        _ProcessSpec(
            argv=[sys.executable, "-c", "print('x' * 10000)"],
            timeout_s=5,
            **common,
        )
    )
    non_zero = runner.run(
        _ProcessSpec(
            argv=[sys.executable, "-c", "raise SystemExit(7)"],
            timeout_s=5,
            **common,
        )
    )

    assert timeout.error_code == TargetExecutionErrorCode.TIMEOUT
    assert cancelled.error_code == TargetExecutionErrorCode.CANCELLED
    assert limited.error_code == TargetExecutionErrorCode.OUTPUT_LIMIT
    assert len(limited.stdout.encode("utf-8")) <= 100
    assert non_zero.error_code == TargetExecutionErrorCode.NON_ZERO_EXIT
    assert non_zero.exit_code == 7


def test_bounded_runner_redacts_executor_only_material() -> None:
    material = "never-log-this-private-material"
    outcome = BoundedProcessRunner().run(
        _ProcessSpec(
            argv=[
                sys.executable,
                "-c",
                f"import sys; sys.stderr.write({material!r}); raise SystemExit(1)",
            ],
            stdin="",
            timeout_s=5,
            max_stdout_bytes=100,
            max_stderr_bytes=100,
            redactions=(material,),
        )
    )

    assert material not in outcome.stderr
    assert "<redacted>" in outcome.stderr


def test_ssh_executor_uses_fixed_protocol_and_forced_security_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_TEST_SSH_SECRET", "must-not-reach-ssh-environment")
    proxy = _connection(
        tmp_path,
        profile_id="conn-proxy",
        host="jump.example",
        port=2200,
    )
    target = _connection(tmp_path, proxy=proxy.connection_profile_id)
    request = _request(
        request_id="inspect-help-0001",
        tool=TargetInspectionTool.EXECUTABLE_HELP,
        operand="vendor-tool;not-a-shell-command",
    )
    remote = _success_result(request)
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    executor = SshTargetExecutor(
        target,
        CredentialResolver((FileCredentialProvider(),)),
        proxy_connection=proxy,
        runner=runner,  # type: ignore[arg-type]
    )

    result = executor.inspect(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == ["robotctl", "target-executor", "inspect"]
    assert request.operand not in runner.spec.argv
    assert json.loads(runner.spec.stdin)["operand"] == request.operand
    assert "BatchMode yes" in runner.config_text
    assert "StrictHostKeyChecking yes" in runner.config_text
    assert "ForwardAgent no" in runner.config_text
    assert "ClearAllForwardings yes" in runner.config_text
    assert "ProxyJump rolo-proxy" in runner.config_text
    assert "Port 2222" in runner.config_text
    assert "Port 2200" in runner.config_text
    assert "-oBatchMode=yes" in runner.spec.argv
    assert "-oStrictHostKeyChecking=yes" in runner.spec.argv
    assert runner.spec.environment is not None
    assert "ROLO_TEST_SSH_SECRET" not in runner.spec.environment


def test_ssh_executor_selects_runtime_identity_without_exposing_it_to_bootstrap(
    tmp_path: Path,
) -> None:
    bootstrap_identity = tmp_path / "bootstrap.key"
    runtime_identity = tmp_path / "runtime.key"
    bootstrap_identity.write_text("bootstrap", encoding="utf-8")
    runtime_identity.write_text("runtime", encoding="utf-8")
    base = _connection(tmp_path)
    connection = TargetConnectionProfile.model_validate(
        {
            **base.model_dump(),
            "credential_ref": file_credential_reference(bootstrap_identity),
            "user": "admin",
            "runtime_user": "rolo",
            "runtime_credential_ref": file_credential_reference(runtime_identity),
        }
    )
    request = _request(request_id="identity-split", tool=TargetInspectionTool.PLATFORM)
    remote = _success_result(request)

    runtime_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    runtime = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    )
    assert runtime.inspect(request).status == TargetExecutionStatus.SUCCEEDED
    assert "  User \"rolo\"" in runtime_runner.config_text
    assert str(runtime_identity).replace("\\", "/") in runtime_runner.config_text
    assert str(bootstrap_identity).replace("\\", "/") not in runtime_runner.config_text

    bootstrap_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    bootstrap = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=bootstrap_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    )
    assert bootstrap.inspect(request).status == TargetExecutionStatus.SUCCEEDED
    assert "  User \"admin\"" in bootstrap_runner.config_text
    assert str(bootstrap_identity).replace("\\", "/") in bootstrap_runner.config_text
    assert str(runtime_identity).replace("\\", "/") not in bootstrap_runner.config_text


def test_ssh_executor_requires_and_selects_explicit_provisioning_identity(
    tmp_path: Path,
) -> None:
    provisioning_identity = tmp_path / "provisioning.key"
    provisioning_identity.write_text("provisioning", encoding="utf-8")
    base = _connection(tmp_path)
    connection = TargetConnectionProfile.model_validate(
        {
            **base.model_dump(),
            "provisioning_user": "operator",
            "provisioning_credential_ref": file_credential_reference(
                provisioning_identity
            ),
        }
    )
    request = _request(request_id="provisioning-split", tool=TargetInspectionTool.PLATFORM)
    remote = _success_result(request)
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    executor = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_PROVISIONING,
    )

    assert executor.inspect(request).status == TargetExecutionStatus.SUCCEEDED
    assert "  User \"operator\"" in runner.config_text
    assert str(provisioning_identity).replace("\\", "/") in runner.config_text

    unavailable = SshTargetExecutor(
        base,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_PROVISIONING,
    )
    assert unavailable.inspect(request).error_code == (
        TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE
    )


def test_ssh_runtime_capability_probe_uses_fixed_bootstrap_dispatch_protocol(
    tmp_path: Path,
) -> None:
    request = _request(
        request_id="runtime-capabilities-0001",
        tool=TargetInspectionTool.RUNTIME_CAPABILITIES,
    )
    facts = TargetPlatformFacts(
        os="linux",
        architecture="aarch64",
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
    runner = CapturingRunner(_outcome(stdout=facts.model_dump_json()))

    class PurposeRecorder:
        schemes = FileCredentialProvider.schemes

        def __init__(self) -> None:
            self.delegate = FileCredentialProvider()
            self.purposes: list[CredentialPurpose] = []

        def resolve(self, reference: str, *, purpose: CredentialPurpose):  # type: ignore[no-untyped-def]
            self.purposes.append(purpose)
            return self.delegate.resolve(reference, purpose=purpose)

    provider = PurposeRecorder()
    executor = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((provider,)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    )

    result = executor.inspect(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert TargetPlatformFacts.model_validate_json(result.stdout) == facts
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "runtime-capabilities",
    ]
    assert runner.spec.stdin == ""
    assert provider.purposes == [CredentialPurpose.SSH_BOOTSTRAP]


def test_ssh_package_transfer_uses_fixed_preinstall_protocol_and_binds_response(
    tmp_path: Path,
) -> None:
    chunk = b"typed-package-chunk"
    request = TargetPackageTransferRequest(
        request_id="transfer-package-0001",
        operation=TargetPackageTransferOperation.WRITE,
        package_id="rolo-target",
        manifest_sha256="a" * 64,
        path="share/rolo/runtime.bin",
        file_sha256=sha256(chunk).hexdigest(),
        file_size_bytes=len(chunk),
        chunk_size_bytes=len(chunk),
        chunk_sha256=sha256(chunk).hexdigest(),
        chunk_base64=b64encode(chunk).decode("ascii"),
    )
    remote = TargetPackageTransferResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        executor_kind=TargetExecutorKind.LOCAL,
        status=TargetExecutionStatus.SUCCEEDED,
        received_size_bytes=len(chunk),
        file_size_bytes=len(chunk),
        complete=True,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    executor = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    )

    result = executor.transfer_package_chunk(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert result.request_sha256 == request.canonical_sha256()
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "package-transfer",
    ]
    assert request.path not in runner.spec.argv
    assert TargetPackageTransferRequest.model_validate_json(runner.spec.stdin) == request


def test_ssh_package_transfer_rejects_unbound_remote_response(tmp_path: Path) -> None:
    request = TargetPackageTransferRequest(
        request_id="transfer-query-0001",
        operation=TargetPackageTransferOperation.QUERY,
        package_id="rolo-target",
        manifest_sha256="a" * 64,
        path="target-package.json",
        file_sha256="b" * 64,
        file_size_bytes=100,
    )
    remote = TargetPackageTransferResult(
        request_id=request.request_id,
        request_sha256="c" * 64,
        executor_kind=TargetExecutorKind.LOCAL,
        status=TargetExecutionStatus.SUCCEEDED,
        received_size_bytes=0,
        file_size_bytes=100,
        complete=False,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))

    result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
    ).transfer_package_chunk(request)

    assert result.status == TargetExecutionStatus.FAILED
    assert result.error_code == TargetExecutionErrorCode.PROTOCOL_ERROR


def test_ssh_bootstrap_status_uses_fixed_digest_bound_launcher(tmp_path: Path) -> None:
    request = TargetBootstrapExecutionRequest(
        request_id="bootstrap-status-0001",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
    )
    remote = TargetBootstrapExecutionResult(
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
        install_index=None,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    executor = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    )

    result = executor.execute_bootstrap(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    remote_command = runner.spec.argv[-3:]
    assert remote_command == ["robotctl", "target-executor", "bootstrap"]
    assert request.package_id not in remote_command
    assert request.manifest_sha256 not in remote_command
    assert TargetBootstrapExecutionRequest.model_validate_json(runner.spec.stdin) == request


def test_ssh_runtime_status_uses_only_installed_forced_command(tmp_path: Path) -> None:
    request = TargetBootstrapExecutionRequest(
        request_id="runtime-bootstrap-status-0001",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
    )
    remote = TargetBootstrapExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.target_id,
        package_id=request.package_id,
        manifest_sha256=request.manifest_sha256,
        executor_kind=TargetExecutorKind.LOCAL,
        operation=request.operation,
        status=TargetExecutionStatus.SUCCEEDED,
        install_index=None,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))

    result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).execute_bootstrap(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == ["robotctl", "target-executor", "bootstrap"]
    assert all(not value.startswith("python3") for value in runner.spec.argv)


def test_ssh_runtime_capability_probe_uses_installed_forced_command(
    tmp_path: Path,
) -> None:
    request = _request(
        request_id="runtime-capabilities-installed-0001",
        tool=TargetInspectionTool.RUNTIME_CAPABILITIES,
    )
    remote = TargetInspectionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        executor_kind=TargetExecutorKind.LOCAL,
        status=TargetExecutionStatus.SUCCEEDED,
        exit_code=0,
        stdout="{}",
        stderr="",
        started_at=_outcome().started_at,
        finished_at=_outcome().finished_at,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))

    result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).inspect(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == ["robotctl", "target-executor", "inspect"]
    assert all(not value.startswith("python3") for value in runner.spec.argv)


def test_local_enrollment_uses_target_local_state_machine_and_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "d" * 64,
    )
    executor = LocalTargetExecutor(enrollment_root=tmp_path / "enrollment")
    request = _enrollment_request(
        TargetEnrollmentOperation.ENROLL,
        request_id="local-enroll-0001",
    )

    result = executor.execute_enrollment(request)

    assert result.execution_status == TargetExecutionStatus.SUCCEEDED
    assert result.enrollment_status == TargetEnrollmentStatus.ENROLLED
    assert result.executor_kind == TargetExecutorKind.LOCAL
    assert result.descriptor is not None
    assert (tmp_path / "enrollment" / "current.json").is_file()

    cancelled = threading.Event()
    cancelled.set()
    cancelled_result = executor.execute_enrollment(request, cancel_event=cancelled)
    assert cancelled_result.execution_status == TargetExecutionStatus.FAILED
    assert cancelled_result.transport_error_code == TargetExecutionErrorCode.CANCELLED


def test_ssh_enrollment_uses_installed_fixed_command_and_bootstrap_credential(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    request = TargetEnrollmentRequest(
        request_id="ssh-enroll-0001",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="rover-target",
        robot_id="rover",
        challenge_nonce="8" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        configuration_sha256=CollectorConfigurationV4().canonical_sha256(),
        configuration=CollectorConfigurationV4(),
        approval_id="approval-" + "f" * 32,
    )
    remote = TargetEnrollmentService(
        tmp_path / "remote-enrollment",
        host_fingerprint_provider=lambda: "d" * 64,
        clock=lambda: now,
    ).execute(request)
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))

    result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).execute_enrollment(request)

    assert result.execution_status == TargetExecutionStatus.SUCCEEDED
    assert result.enrollment_status == TargetEnrollmentStatus.ENROLLED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == ["robotctl", "target-executor", "enroll"]
    assert TargetEnrollmentRequest.model_validate_json(runner.spec.stdin) == request
    assert all(not value.startswith("python3") for value in runner.spec.argv)


def test_ssh_runtime_rejects_enrollment_mutation_but_allows_status(
    tmp_path: Path,
) -> None:
    mutation = _enrollment_request(
        TargetEnrollmentOperation.ENROLL,
        request_id="runtime-enroll-rejected",
    )
    rejected_runner = CapturingRunner(_outcome())
    runtime = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=rejected_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    )

    rejected = runtime.execute_enrollment(mutation)

    assert rejected.execution_status == TargetExecutionStatus.FAILED
    assert rejected.transport_error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert rejected_runner.spec is None

    now = datetime.now(timezone.utc)
    status_request = TargetEnrollmentRequest(
        request_id="runtime-enrollment-status",
        operation=TargetEnrollmentOperation.STATUS,
        target_id="rover-target",
        robot_id="rover",
        challenge_nonce="7" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    remote = TargetEnrollmentService(
        tmp_path / "empty-enrollment",
        host_fingerprint_provider=lambda: "d" * 64,
        clock=lambda: now,
    ).execute(status_request)
    status_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    status = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-status"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=status_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).execute_enrollment(status_request)

    assert status.execution_status == TargetExecutionStatus.SUCCEEDED
    assert status.enrollment_status == TargetEnrollmentStatus.NOT_ENROLLED
    assert status_runner.spec is not None
    assert status_runner.spec.argv[-3:] == ["robotctl", "target-executor", "enroll"]


def test_ssh_enrollment_rejects_unbound_response(tmp_path: Path) -> None:
    request = _enrollment_request(
        TargetEnrollmentOperation.ENROLL,
        request_id="ssh-enroll-unbound",
    )
    invalid = TargetEnrollmentResult(
        request_id=request.request_id,
        request_sha256="0" * 64,
        operation=request.operation,
        target_id=request.target_id,
        robot_id=request.robot_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        transport_error_code=TargetExecutionErrorCode.CONNECTION_FAILED,
    )
    runner = CapturingRunner(_outcome(stdout=invalid.model_dump_json()))

    result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).execute_enrollment(request)

    assert result.execution_status == TargetExecutionStatus.FAILED
    assert result.transport_error_code == TargetExecutionErrorCode.PROTOCOL_ERROR


def test_ssh_v4_evidence_requires_scoped_authorization_for_runtime_credential(
    tmp_path: Path,
) -> None:
    evidence_request = new_request("rover")
    request = TargetEvidenceCollectionRequestV4(
        request_id="collect-v4-0001",
        target_id="rover-target",
        evidence_request=evidence_request,
    )
    runtime_runner = CapturingRunner(_outcome())
    runtime_result = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).collect_evidence_v4(request)

    assert runtime_result.execution_status == TargetExecutionStatus.FAILED
    assert runtime_result.error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert runtime_runner.spec is None

    authorized = _authorized_runtime_evidence_request()
    runtime_remote = TargetEvidenceCollectionResultV4(
        request_id=authorized.request_id,
        request_sha256=authorized.canonical_sha256(),
        target_id=authorized.target_id,
        robot_id=authorized.evidence_request.robot_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    authorized_runner = CapturingRunner(
        _outcome(stdout=runtime_remote.model_dump_json())
    )
    authorized_result = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-evidence"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=authorized_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).collect_evidence_v4(authorized)

    assert authorized_result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert authorized_runner.spec is not None
    assert authorized_runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "evidence-v4",
    ]
    assert TargetEvidenceCollectionRequestV4.model_validate_json(
        authorized_runner.spec.stdin
    ) == authorized

    remote = TargetEvidenceCollectionResultV4(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.target_id,
        robot_id=request.evidence_request.robot_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    bootstrap_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    bootstrap_result = SshTargetExecutor(
        _connection(tmp_path, profile_id="bootstrap-evidence"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=bootstrap_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).collect_evidence_v4(request)

    assert bootstrap_result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert bootstrap_runner.spec is not None
    assert bootstrap_runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "evidence-v4",
    ]
    assert TargetEvidenceCollectionRequestV4.model_validate_json(
        bootstrap_runner.spec.stdin
    ) == request


def test_ssh_adapter_release_stage_is_bootstrap_only_and_uses_fixed_command(
    tmp_path: Path,
) -> None:
    request = _adapter_release_stage_request()
    runtime_runner = CapturingRunner(_outcome())
    runtime = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).stage_adapter_release(request)

    assert runtime.execution_status == TargetExecutionStatus.FAILED
    assert runtime.error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert runtime_runner.spec is None

    remote = AdapterReleaseStageExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.target_id,
        robot_id=request.robot_id,
        release_id=request.release_id,
        package_id=request.package_id,
        manifest_sha256=request.manifest_sha256,
        signing_key_id=request.signing_key_id,
        signing_public_key_sha256=request.signing_public_key_sha256,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    bootstrap_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    bootstrap = SshTargetExecutor(
        _connection(tmp_path, profile_id="bootstrap-adapter-stage"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=bootstrap_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).stage_adapter_release(request)

    assert bootstrap.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert bootstrap.executor_kind == TargetExecutorKind.SSH
    assert bootstrap_runner.spec is not None
    assert bootstrap_runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "adapter-release-stage",
    ]
    assert AdapterReleaseStageRequest.model_validate_json(
        bootstrap_runner.spec.stdin
    ) == request


def test_ssh_adapter_release_activation_is_bootstrap_only_and_bound(
    tmp_path: Path,
) -> None:
    request = _adapter_release_activation_request()
    runtime_runner = CapturingRunner(_outcome())
    runtime = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).activate_adapter_release(request)

    assert runtime.execution_status == TargetExecutionStatus.FAILED
    assert runtime.transport_error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert runtime_runner.spec is None

    remote = AdapterReleaseActivationExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        operation=request.operation,
        target_id=request.target_id,
        robot_id=request.robot_id,
        release_id=request.release_id,
        transfer_manifest_sha256=request.transfer_manifest_sha256,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        transport_error_code=TargetExecutionErrorCode.CONNECTION_FAILED,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    result = SshTargetExecutor(
        _connection(tmp_path, profile_id="bootstrap-adapter-activation"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).activate_adapter_release(request)

    assert result.transport_error_code == TargetExecutionErrorCode.CONNECTION_FAILED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "adapter-release-activate",
    ]
    assert AdapterReleaseActivationRequest.model_validate_json(runner.spec.stdin) == request


def test_ssh_adapter_release_describe_is_bootstrap_only_until_scoped_auth(
    tmp_path: Path,
) -> None:
    request = _adapter_release_describe_request()
    runtime_runner = CapturingRunner(_outcome())
    runtime = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).describe_adapter_release(request)

    assert runtime.execution_status == TargetExecutionStatus.FAILED
    assert runtime.error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert runtime_runner.spec is None

    describe = request.describe
    remote = AdapterReleaseDescribeExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=describe.target_id,
        robot_id=describe.robot_id,
        release_id=describe.release_id,
        transfer_manifest_sha256=request.transfer_manifest_sha256,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    result = SshTargetExecutor(
        _connection(tmp_path, profile_id="bootstrap-adapter-describe"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).describe_adapter_release(request)

    assert result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "adapter-release-describe",
    ]
    assert AdapterReleaseDescribeRequest.model_validate_json(runner.spec.stdin) == request


def test_ssh_adapter_release_status_is_runtime_read_only_and_request_bound(
    tmp_path: Path,
) -> None:
    request = _adapter_release_status_request()
    remote = AdapterReleaseStatusExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.desired.target_id,
        robot_id=request.desired.robot_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    result = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-adapter-status"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).status_adapter_release(request)

    assert result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "adapter-release-status",
    ]
    assert AdapterReleaseStatusRequest.model_validate_json(runner.spec.stdin) == request

    mismatched = remote.model_copy(update={"target_id": "other-target"})
    mismatch_runner = CapturingRunner(_outcome(stdout=mismatched.model_dump_json()))
    rejected = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-adapter-status-mismatch"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=mismatch_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).status_adapter_release(request)
    assert rejected.error_code == TargetExecutionErrorCode.PROTOCOL_ERROR


def test_ssh_project_evidence_accepts_runtime_credential_and_uses_fixed_command(
    tmp_path: Path,
) -> None:
    request = _project_evidence_request()
    workspace = request.workspace
    remote = TargetProjectEvidenceExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=workspace.target_id,
        robot_id=workspace.robot_id,
        workspace_id=workspace.workspace_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
    )
    runtime_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    runtime = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-project-evidence"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runtime_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).detect_project_evidence(request)
    assert runtime.error_code == TargetExecutionErrorCode.AUTHORIZATION_FAILED
    assert runtime_runner.spec is not None
    assert runtime_runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "project-evidence",
    ]

    bootstrap_remote = TargetProjectEvidenceExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=workspace.target_id,
        robot_id=workspace.robot_id,
        workspace_id=workspace.workspace_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
    )
    runner = CapturingRunner(_outcome(stdout=bootstrap_remote.model_dump_json()))
    result = SshTargetExecutor(
        _connection(tmp_path, profile_id="bootstrap-project-evidence"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).detect_project_evidence(request)

    assert result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "project-evidence",
    ]
    assert TargetProjectEvidenceRequest.model_validate_json(runner.spec.stdin) == request


def test_ssh_source_discovery_accepts_runtime_credential_and_uses_fixed_command(
    tmp_path: Path,
) -> None:
    request = _source_discovery_request()
    workspace = request.workspace
    remote = TargetSourceDiscoveryExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=workspace.target_id,
        robot_id=workspace.robot_id,
        workspace_id=workspace.workspace_id,
        executor_kind=TargetExecutorKind.LOCAL,
        execution_status=TargetExecutionStatus.FAILED,
        error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
    )
    runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    result = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-source-discovery"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).discover_source(request)

    assert result.error_code == TargetExecutionErrorCode.AUTHORIZATION_FAILED
    assert result.executor_kind == TargetExecutorKind.SSH
    assert runner.spec is not None
    assert runner.spec.argv[-3:] == [
        "robotctl",
        "target-executor",
        "source-discovery",
    ]
    assert TargetSourceDiscoveryRequest.model_validate_json(runner.spec.stdin) == request

    mismatched = remote.model_copy(update={"workspace_id": "other-workspace"})
    mismatch_runner = CapturingRunner(_outcome(stdout=mismatched.model_dump_json()))
    rejected = SshTargetExecutor(
        _connection(tmp_path, profile_id="runtime-source-discovery-mismatch"),
        CredentialResolver((FileCredentialProvider(),)),
        runner=mismatch_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).discover_source(request)
    assert rejected.error_code == TargetExecutionErrorCode.PROTOCOL_ERROR


def test_ssh_bootstrap_mutation_requires_bootstrap_credential_purpose(
    tmp_path: Path,
) -> None:
    public_key = b"p" * 32
    request = TargetBootstrapExecutionRequest(
        request_id="bootstrap-install-0001",
        operation=TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "b" * 32,
    )
    runner = CapturingRunner(_outcome())

    rejected = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_RUNTIME,
    ).execute_bootstrap(request)

    assert rejected.status == TargetExecutionStatus.FAILED
    assert rejected.transport_error_code == (
        TargetExecutionErrorCode.CONFIGURATION_ERROR
    )
    assert runner.spec is None

    remote = TargetBootstrapExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id=request.target_id,
        package_id=request.package_id,
        manifest_sha256=request.manifest_sha256,
        signing_key_id=request.signing_key_id,
        signing_public_key_sha256=request.signing_public_key_sha256,
        executor_kind=TargetExecutorKind.LOCAL,
        operation=request.operation,
        status=TargetExecutionStatus.FAILED,
        bootstrap_error_code=TargetBootstrapExecutionErrorCode.PACKAGE_INVALID,
    )
    bootstrap_runner = CapturingRunner(_outcome(stdout=remote.model_dump_json()))
    accepted = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=bootstrap_runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).execute_bootstrap(request)

    assert accepted.bootstrap_error_code == (
        TargetBootstrapExecutionErrorCode.PACKAGE_INVALID
    )
    assert bootstrap_runner.spec is not None


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (
            "Host key verification failed.",
            TargetExecutionErrorCode.HOST_KEY_VERIFICATION_FAILED,
        ),
        ("Permission denied (publickey).", TargetExecutionErrorCode.AUTHENTICATION_FAILED),
        ("ssh: connect to host failed", TargetExecutionErrorCode.CONNECTION_FAILED),
        ("fixed target command exited 7", TargetExecutionErrorCode.NON_ZERO_EXIT),
    ],
)
def test_ssh_transport_failures_have_deterministic_codes(
    tmp_path: Path,
    stderr: str,
    expected: TargetExecutionErrorCode,
) -> None:
    connection = _connection(tmp_path)
    exit_code = 7 if expected == TargetExecutionErrorCode.NON_ZERO_EXIT else 255
    runner = CapturingRunner(
        _outcome(
            stderr=stderr,
            exit_code=exit_code,
            error_code=TargetExecutionErrorCode.NON_ZERO_EXIT,
        )
    )
    result = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
    ).inspect(_request())

    assert result.status == TargetExecutionStatus.FAILED
    assert result.error_code == expected


def test_ssh_executor_rejects_known_hosts_that_do_not_match_profile_pin(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    known_hosts = Path(connection.known_hosts_path)
    known_hosts.write_text(
        "[target.example]:2222 ssh-ed25519 QUFBQUFBQUFBQUFBQUFBQQ==\n",
        encoding="utf-8",
    )
    runner = CapturingRunner(_outcome(stdout=_success_result(_request()).model_dump_json()))

    result = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
    ).inspect(_request())

    assert result.status == TargetExecutionStatus.FAILED
    assert result.error_code == TargetExecutionErrorCode.CONFIGURATION_ERROR
    assert "fingerprint is absent" in result.stderr
    assert runner.spec is None


def test_local_and_ssh_executors_share_the_same_result_contract(tmp_path: Path) -> None:
    request = _request()
    local = LocalTargetExecutor().inspect(request)
    runner = CapturingRunner(_outcome(stdout=local.model_dump_json()))
    remote = SshTargetExecutor(
        _connection(tmp_path),
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
    ).inspect(request)

    local_payload = local.model_dump(mode="json", exclude={"executor_kind"})
    remote_payload = remote.model_dump(mode="json", exclude={"executor_kind"})
    assert local_payload == remote_payload
    assert remote.executor_kind == TargetExecutorKind.SSH


def test_target_executor_cli_accepts_only_strict_bounded_json() -> None:
    request = _request()
    result = CliRunner().invoke(
        app,
        ["target-executor", "inspect"],
        input=request.model_dump_json(),
    )

    assert result.exit_code == 0, result.output
    payload = TargetInspectionResult.model_validate_json(result.output)
    assert payload.request_sha256 == request.canonical_sha256()

    invalid = CliRunner().invoke(
        app,
        ["target-executor", "inspect"],
        input=json.dumps({**request.model_dump(mode="json"), "ssh_option": "BatchMode=no"}),
    )
    assert invalid.exit_code == 2
    assert "extra_forbidden" in invalid.output
    assert "BatchMode=no" not in invalid.output


def test_inspection_models_fail_closed_on_unknown_fields_and_relative_paths() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TargetInspectionRequest.model_validate(
            {
                "request_id": "bad-extra",
                "tool": "PLATFORM",
                "ssh_option": "StrictHostKeyChecking=no",
            }
        )
    with pytest.raises(ValidationError, match="must be absolute"):
        _request(tool=TargetInspectionTool.PATH_STAT, operand="relative/path")
