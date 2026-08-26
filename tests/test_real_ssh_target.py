"""Opt-in W10 acceptance against a real sshd and installed target runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rolo.targets import (
    CredentialPurpose,
    CredentialResolver,
    FileCredentialProvider,
    SshTargetExecutor,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetConnectionProfile,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionTool,
    file_credential_reference,
)


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} is required for real SSH acceptance")
    return value


@pytest.fixture
def real_ssh_connection() -> TargetConnectionProfile:
    provisioning_identity = Path(
        _required_environment("ROLO_REAL_SSH_PROVISIONING_IDENTITY_FILE")
    ).resolve()
    bootstrap_identity = Path(
        _required_environment("ROLO_REAL_SSH_BOOTSTRAP_IDENTITY_FILE")
    ).resolve()
    runtime_identity = Path(_required_environment("ROLO_REAL_SSH_RUNTIME_IDENTITY_FILE")).resolve()
    known_hosts = Path(_required_environment("ROLO_REAL_SSH_KNOWN_HOSTS")).resolve()
    required_files = (
        provisioning_identity,
        bootstrap_identity,
        runtime_identity,
        known_hosts,
    )
    if any(not path.is_file() for path in required_files):
        pytest.fail("all three real SSH identities and known_hosts must be existing files")
    return TargetConnectionProfile(
        connection_profile_id="w10-real-ssh",
        host=_required_environment("ROLO_REAL_SSH_HOST"),
        port=int(os.environ.get("ROLO_REAL_SSH_PORT", "22")),
        user=_required_environment("ROLO_REAL_SSH_BOOTSTRAP_USER"),
        credential_ref=file_credential_reference(bootstrap_identity),
        provisioning_user=_required_environment("ROLO_REAL_SSH_PROVISIONING_USER"),
        provisioning_credential_ref=file_credential_reference(provisioning_identity),
        runtime_user=_required_environment("ROLO_REAL_SSH_RUNTIME_USER"),
        runtime_credential_ref=file_credential_reference(runtime_identity),
        known_hosts_path=str(known_hosts),
        expected_host_key_sha256=_required_environment("ROLO_REAL_SSH_HOST_KEY_SHA256"),
    )


def _executor(
    connection: TargetConnectionProfile,
    *,
    purpose: CredentialPurpose,
) -> SshTargetExecutor:
    return SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        connect_timeout_s=10,
        credential_purpose=purpose,
    )


@pytest.mark.skipif(
    os.getenv("ROLO_RUN_REAL_SSH_ACCEPTANCE") != "1",
    reason="set ROLO_RUN_REAL_SSH_ACCEPTANCE=1 for the opt-in real sshd tests",
)
def test_real_sshd_bootstrap_capabilities_are_strict_and_secret_closed(
    real_ssh_connection: TargetConnectionProfile,
) -> None:
    result = _executor(
        real_ssh_connection,
        purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).inspect(
        TargetInspectionRequest(
            request_id="w10-real-ssh-bootstrap-capabilities",
            tool=TargetInspectionTool.RUNTIME_CAPABILITIES,
            timeout_s=10,
        )
    )

    assert result.status == TargetExecutionStatus.SUCCEEDED, result.error_code
    assert result.executor_kind == TargetExecutorKind.SSH
    capabilities = json.loads(result.stdout)
    assert capabilities["python3"] is True
    serialized = result.model_dump_json()
    assert str(real_ssh_connection.credential_ref) not in serialized
    assert str(real_ssh_connection.known_hosts_path) not in serialized


@pytest.mark.skipif(
    os.getenv("ROLO_RUN_REAL_SSH_ACCEPTANCE") != "1",
    reason="set ROLO_RUN_REAL_SSH_ACCEPTANCE=1 for the opt-in real sshd tests",
)
def test_real_sshd_provisioning_identity_executes_only_typed_inspection(
    real_ssh_connection: TargetConnectionProfile,
) -> None:
    result = _executor(
        real_ssh_connection,
        purpose=CredentialPurpose.SSH_PROVISIONING,
    ).inspect(
        TargetInspectionRequest(
            request_id="w10-real-ssh-provisioning-platform",
            tool=TargetInspectionTool.PLATFORM,
            timeout_s=10,
        )
    )

    assert result.status == TargetExecutionStatus.SUCCEEDED, result.error_code
    assert result.executor_kind == TargetExecutorKind.SSH
    platform_payload = json.loads(result.stdout)
    assert {"machine", "os", "os_release", "python", "uid"}.issubset(platform_payload)


@pytest.mark.skipif(
    os.getenv("ROLO_RUN_REAL_SSH_ACCEPTANCE") != "1",
    reason="set ROLO_RUN_REAL_SSH_ACCEPTANCE=1 for the opt-in real sshd tests",
)
def test_real_sshd_installed_runtime_executes_only_typed_inspection(
    real_ssh_connection: TargetConnectionProfile,
) -> None:
    result = _executor(
        real_ssh_connection,
        purpose=CredentialPurpose.SSH_RUNTIME,
    ).inspect(
        TargetInspectionRequest(
            request_id="w10-real-ssh-platform",
            tool=TargetInspectionTool.PLATFORM,
            timeout_s=10,
        )
    )

    assert result.status == TargetExecutionStatus.SUCCEEDED, result.error_code
    assert result.executor_kind == TargetExecutorKind.SSH
    platform_payload = json.loads(result.stdout)
    assert {"machine", "os", "python", "python_executable", "uid"}.issubset(platform_payload)
    banner_token = os.environ.get("ROLO_REAL_SSH_HOSTILE_BANNER_TOKEN")
    if banner_token:
        assert banner_token not in result.stdout


@pytest.mark.skipif(
    os.getenv("ROLO_RUN_REAL_SSH_ACCEPTANCE") != "1",
    reason="set ROLO_RUN_REAL_SSH_ACCEPTANCE=1 for the opt-in real sshd tests",
)
def test_real_sshd_runtime_status_matches_the_declared_package(
    real_ssh_connection: TargetConnectionProfile,
) -> None:
    request = TargetBootstrapExecutionRequest(
        request_id="w10-real-ssh-runtime-installation",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id=_required_environment("ROLO_REAL_SSH_TARGET_ID"),
        package_id=_required_environment("ROLO_REAL_SSH_PACKAGE_ID"),
        manifest_sha256=_required_environment("ROLO_REAL_SSH_PACKAGE_MANIFEST_SHA256"),
        timeout_s=20,
    )
    result = _executor(
        real_ssh_connection,
        purpose=CredentialPurpose.SSH_RUNTIME,
    ).execute_bootstrap(request)

    assert result.status == TargetExecutionStatus.SUCCEEDED, (
        result.transport_error_code or result.bootstrap_error_code
    )
    assert result.executor_kind == TargetExecutorKind.SSH
    assert result.install_index is not None
    assert result.install_index.current.package_id == request.package_id
    assert result.install_index.current.manifest_sha256 == request.manifest_sha256
