from __future__ import annotations

import json
from base64 import b64encode
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.config import get_settings
from rolo.targets import (
    ApprovalAction,
    CredentialPurpose,
    CredentialResolver,
    FileCredentialProvider,
    OrchestratorPlacement,
    SshTargetExecutor,
    TargetConnectionProfile,
    TargetHostProvisioningExecutionError,
    TargetHostProvisioningExecutionResult,
    TargetHostProvisioningExecutionStatus,
    TargetHostProvisioningObservation,
    TargetHostProvisioningObservationStatus,
    TargetHostProvisioningOperation,
    TargetHostProvisioningPlan,
    TargetHostServiceError,
    TargetHostServiceExecutionResult,
    TargetHostServiceOperation,
    TargetHostServiceRequest,
    TargetHostServiceStatus,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    build_target_host_provisioning_plan,
    file_credential_reference,
)
from rolo.targets.executor import _ProcessOutcome, _ProcessSpec


def _public_key(byte: bytes) -> str:
    return "ssh-ed25519 " + b64encode(byte * 32).decode("ascii") + " test-comment"


def _connection(tmp_path: Path) -> TargetConnectionProfile:
    return TargetConnectionProfile(
        connection_profile_id="connection-rover",
        host="192.0.2.20",
        user="rolo",
        credential_ref="file://ssh/rover-bootstrap",
        provisioning_user="operator",
        provisioning_credential_ref="file://ssh/rover-admin",
        runtime_user="rolo",
        runtime_credential_ref="file://ssh/rover-runtime",
        known_hosts_path=str((tmp_path / "known_hosts").absolute()),
        trust_level=TargetTrustLevel.STRICT,
        expected_host_key_sha256="SHA256:" + "A" * 43,
    )


def test_host_provisioning_plan_binds_every_privileged_effect(tmp_path: Path) -> None:
    plan = build_target_host_provisioning_plan(
        target_id="rover",
        target_registration_sha256="a" * 64,
        connection=_connection(tmp_path),
        bootstrap_public_key=_public_key(b"b"),
        runtime_public_key=_public_key(b"r"),
    )

    assert plan.approval_actions == [ApprovalAction.USE_SUDO]
    assert all(step.requires_sudo for step in plan.steps)
    assert [step.operation for step in plan.steps[-2:]] == [
        TargetHostProvisioningOperation.SYSTEMD_DAEMON_RELOAD,
        TargetHostProvisioningOperation.SYSTEMD_ENABLE,
    ]
    assert plan.steps[-1].argv == [
        "systemctl",
        "enable",
        "rolo-bootstrap-agentd@rover.service",
    ]
    assert "--now" not in plan.steps[-1].argv
    assert plan.bootstrap_public_key.endswith(b64encode(b"b" * 32).decode("ascii"))
    assert plan.runtime_public_key.endswith(b64encode(b"r" * 32).decode("ascii"))
    assert "test-comment" not in plan.authorized_keys
    assert plan.canonical_sha256() == build_target_host_provisioning_plan(
        target_id="rover",
        target_registration_sha256="a" * 64,
        connection=_connection(tmp_path),
        bootstrap_public_key=_public_key(b"b"),
        runtime_public_key=_public_key(b"r"),
    ).canonical_sha256()

    changed = plan.model_dump()
    changed["steps"][-1]["argv"].append("--now")
    with pytest.raises(ValidationError, match="not canonical"):
        TargetHostProvisioningPlan.model_validate(changed)


def test_host_provisioning_rejects_identity_collapse(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    with pytest.raises(ValueError, match="distinct bootstrap and runtime keys"):
        build_target_host_provisioning_plan(
            target_id="rover",
            target_registration_sha256="a" * 64,
            connection=connection,
            bootstrap_public_key=_public_key(b"x"),
            runtime_public_key=_public_key(b"x"),
        )
    with pytest.raises(ValueError, match="one runtime user"):
        build_target_host_provisioning_plan(
            target_id="rover",
            target_registration_sha256="a" * 64,
            connection=connection.model_copy(update={"runtime_user": "rolo-runtime"}),
            bootstrap_public_key=_public_key(b"b"),
            runtime_public_key=_public_key(b"r"),
        )


def test_host_plan_cli_is_read_only_and_omits_credential_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    settings = get_settings()
    connection = _connection(tmp_path)
    TargetRegistrationService(TargetProfileRegistry(settings.target_profile_dir)).register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="rover",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id=connection.connection_profile_id,
                workspace_root="/var/lib/rolo/workspace",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            ),
            connection=connection,
        ),
        principal="fixture",
        idempotency_key="host-plan-registration",
    )
    bootstrap_key = tmp_path / "bootstrap.pub"
    runtime_key = tmp_path / "runtime.pub"
    bootstrap_key.write_text(_public_key(b"b") + "\n", encoding="utf-8")
    runtime_key.write_text(_public_key(b"r") + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "target",
            "host",
            "plan",
            "--target",
            "rover",
            "--bootstrap-public-key",
            str(bootstrap_key),
            "--runtime-public-key",
            str(runtime_key),
        ],
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "PLANNED"
    assert payload["plan"]["approval_actions"] == ["USE_SUDO"]
    assert "file://ssh/" not in result.output
    assert not (tmp_path / "artifacts").exists()


class _CapturingRunner:
    def __init__(self, outcome: _ProcessOutcome) -> None:
        self.outcome = outcome
        self.spec: _ProcessSpec | None = None
        self.config_text = ""

    def run(self, spec: _ProcessSpec, **_: object) -> _ProcessOutcome:
        self.spec = spec
        config_path = Path(spec.argv[spec.argv.index("-F") + 1])
        self.config_text = config_path.read_text(encoding="utf-8")
        return self.outcome


def test_ssh_host_provisioner_uses_only_provisioning_identity_and_binds_result(
    tmp_path: Path,
) -> None:
    provisioning_identity = tmp_path / "provisioning.key"
    provisioning_identity.write_text("fixture", encoding="utf-8")
    known_hosts = tmp_path / "known_hosts"
    host_key = b"host-key"
    known_hosts.write_text(
        "192.0.2.20 ssh-ed25519 " + b64encode(host_key).decode() + "\n",
        encoding="utf-8",
    )
    connection = TargetConnectionProfile.model_validate(
        {
            **_connection(tmp_path).model_dump(),
            "known_hosts_path": str(known_hosts.absolute()),
            "expected_host_key_sha256": (
                "SHA256:" + b64encode(sha256(host_key).digest()).decode().rstrip("=")
            ),
            "provisioning_credential_ref": file_credential_reference(
                provisioning_identity
            ),
        }
    )
    plan = build_target_host_provisioning_plan(
        target_id="rover",
        target_registration_sha256="a" * 64,
        connection=connection,
        bootstrap_public_key=_public_key(b"b"),
        runtime_public_key=_public_key(b"r"),
    )
    now = datetime.now(timezone.utc)
    remote = TargetHostProvisioningExecutionResult(
        target_id="rover",
        plan_sha256=plan.canonical_sha256(),
        status=TargetHostProvisioningExecutionStatus.APPLIED,
        current_plan_sha256=plan.canonical_sha256(),
        started_at=now,
        finished_at=now,
    )
    runner = _CapturingRunner(
        _ProcessOutcome(
            error_code=None,
            exit_code=0,
            stdout=remote.model_dump_json(),
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )
    executor = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_PROVISIONING,
    )

    result = executor.provision_host(plan)

    assert result == remote
    assert runner.spec is not None
    assert runner.spec.argv[-1].startswith("sudo -n python3 -c ")
    assert "rover" not in runner.spec.argv[-1]
    assert plan.bootstrap_public_key not in runner.spec.argv[-1]
    assert json.loads(runner.spec.stdin)["target_id"] == "rover"
    assert '  User "operator"' in runner.config_text

    wrong_purpose = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).provision_host(plan)
    assert wrong_purpose.error_code == (
        TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE
    )


def test_ssh_host_observer_is_read_only_and_binds_result(tmp_path: Path) -> None:
    provisioning_identity = tmp_path / "provisioning.key"
    provisioning_identity.write_text("fixture", encoding="utf-8")
    known_hosts = tmp_path / "known_hosts"
    host_key = b"host-key"
    known_hosts.write_text(
        "192.0.2.20 ssh-ed25519 " + b64encode(host_key).decode() + "\n",
        encoding="utf-8",
    )
    connection = TargetConnectionProfile.model_validate(
        {
            **_connection(tmp_path).model_dump(),
            "known_hosts_path": str(known_hosts.absolute()),
            "expected_host_key_sha256": (
                "SHA256:" + b64encode(sha256(host_key).digest()).decode().rstrip("=")
            ),
            "provisioning_credential_ref": file_credential_reference(
                provisioning_identity
            ),
        }
    )
    plan = build_target_host_provisioning_plan(
        target_id="rover",
        target_registration_sha256="a" * 64,
        connection=connection,
        bootstrap_public_key=_public_key(b"b"),
        runtime_public_key=_public_key(b"r"),
    )
    observation = TargetHostProvisioningObservation(
        target_id="rover",
        expected_plan_sha256=plan.canonical_sha256(),
        status=TargetHostProvisioningObservationStatus.EXACT,
        current_plan_sha256=plan.canonical_sha256(),
        observed_at=datetime.now(timezone.utc),
    )
    now = datetime.now(timezone.utc)
    runner = _CapturingRunner(
        _ProcessOutcome(
            error_code=None,
            exit_code=0,
            stdout=observation.model_dump_json(),
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )
    executor = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_PROVISIONING,
    )

    assert executor.observe_host_provisioning(plan) == observation
    assert runner.spec is not None
    assert runner.spec.argv[-1].startswith("sudo -n python3 -c ")
    assert "systemctl is-enabled" not in runner.spec.argv[-1]
    assert "rover" not in runner.spec.argv[-1]
    assert json.loads(runner.spec.stdin)["target_id"] == "rover"
    assert '  User "operator"' in runner.config_text

    wrong_purpose = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).observe_host_provisioning(plan)
    assert wrong_purpose.status == TargetHostProvisioningObservationStatus.FAILED
    assert wrong_purpose.error_code == (
        TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE
    )


def test_ssh_host_service_uses_fixed_protocol_and_provisioning_identity(
    tmp_path: Path,
) -> None:
    provisioning_identity = tmp_path / "provisioning.key"
    provisioning_identity.write_text("fixture", encoding="utf-8")
    known_hosts = tmp_path / "known_hosts"
    host_key = b"host-key"
    known_hosts.write_text(
        "192.0.2.20 ssh-ed25519 " + b64encode(host_key).decode() + "\n",
        encoding="utf-8",
    )
    connection = TargetConnectionProfile.model_validate(
        {
            **_connection(tmp_path).model_dump(),
            "known_hosts_path": str(known_hosts.absolute()),
            "expected_host_key_sha256": (
                "SHA256:" + b64encode(sha256(host_key).digest()).decode().rstrip("=")
            ),
            "provisioning_credential_ref": file_credential_reference(
                provisioning_identity
            ),
        }
    )
    request = TargetHostServiceRequest(
        request_id="start-service-rover",
        operation=TargetHostServiceOperation.START,
        target_id="rover",
        expected_host_plan_sha256="a" * 64,
        expected_runtime_manifest_sha256="b" * 64,
        unit_name="rolo-bootstrap-agentd@rover.service",
    )
    now = datetime.now(timezone.utc)
    remote = TargetHostServiceExecutionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        target_id="rover",
        operation=TargetHostServiceOperation.START,
        status=TargetHostServiceStatus.STARTED,
        active=True,
        observed_host_plan_sha256="a" * 64,
        observed_runtime_manifest_sha256="b" * 64,
        started_at=now,
        finished_at=now,
    )
    runner = _CapturingRunner(
        _ProcessOutcome(
            error_code=None,
            exit_code=0,
            stdout=remote.model_dump_json(),
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )
    executor = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_PROVISIONING,
    )

    assert executor.execute_host_service(request) == remote
    assert runner.spec is not None
    assert runner.spec.argv[-1].startswith("sudo -n python3 -c ")
    assert "rover" not in runner.spec.argv[-1]
    assert json.loads(runner.spec.stdin)["operation"] == "START"
    assert '  User "operator"' in runner.config_text

    wrong_purpose = SshTargetExecutor(
        connection,
        CredentialResolver((FileCredentialProvider(),)),
        runner=runner,  # type: ignore[arg-type]
        credential_purpose=CredentialPurpose.SSH_BOOTSTRAP,
    ).execute_host_service(request)
    assert wrong_purpose.status == TargetHostServiceStatus.FAILED
    assert wrong_purpose.error_code == TargetHostServiceError.CREDENTIAL_UNAVAILABLE

    with pytest.raises(ValidationError, match="unit differs"):
        TargetHostServiceRequest(
            request_id="invalid-unit",
            operation=TargetHostServiceOperation.STATUS,
            target_id="rover",
            expected_host_plan_sha256="a" * 64,
            expected_runtime_manifest_sha256="b" * 64,
            unit_name="rolo-bootstrap-agentd@other.service",
        )
