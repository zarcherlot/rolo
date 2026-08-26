from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.stages.adapt.target_evidence import new_request
from rolo.targets import (
    AdapterReleaseDesiredState,
    AdapterReleaseStatusExecutionResult,
    AdapterReleaseStatusRequest,
    CollectorConfigurationV4,
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetBootstrapExecutionResult,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentResult,
    TargetEnrollmentStatus,
    TargetEvidenceCollectionRequestV4,
    TargetEvidenceCollectionResultV4,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetHostTemplateBundle,
    TargetProjectEvidenceCandidate,
    TargetProjectEvidenceExecutionResult,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceRequest,
    TargetSourceDiscoveryExecutionResult,
    TargetSourceDiscoveryRequest,
    TargetWorkspaceRef,
    build_adapter_release_status_request,
    ed25519_public_key_sha256,
    render_target_host_templates,
)


def _status_request() -> TargetBootstrapExecutionRequest:
    return TargetBootstrapExecutionRequest(
        request_id="forced-status-0001",
        operation=TargetBootstrapExecutionOperation.STATUS,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
    )


def _adapter_status_request() -> AdapterReleaseStatusRequest:
    public_key = b"p" * 32
    return build_adapter_release_status_request(
        request_id="forced-adapter-status-0001",
        desired=AdapterReleaseDesiredState(
            target_id="rover-target",
            robot_id="rover",
            release_id="release-r1",
            controller_release_index_sha256="1" * 64,
            transfer_manifest_sha256="2" * 64,
            release_manifest_sha256="3" * 64,
            bundle_manifest_sha256="4" * 64,
            runtime_context_sha256="5" * 64,
        ),
        signing_key_id="release-key-2026",
        signing_public_key=public_key,
    )


def _project_evidence_request() -> TargetProjectEvidenceRequest:
    return TargetProjectEvidenceRequest(
        request_id="forced-project-evidence-0001",
        workspace=TargetWorkspaceRef(
            workspace_id="workspace-rover",
            target_id="rover-target",
            robot_id="rover-target",
            root="/home/robot/rover_ws",
        ),
        candidates=[
            TargetProjectEvidenceCandidate(
                path="README.md",
                kind=TargetProjectEvidenceKind.DOCUMENTATION,
            )
        ],
        approval_id="approval-" + "c" * 32,
    )


def _source_discovery_request() -> TargetSourceDiscoveryRequest:
    return TargetSourceDiscoveryRequest(
        request_id="forced-source-discovery-0001",
        workspace=TargetWorkspaceRef(
            workspace_id="workspace-rover",
            target_id="rover-target",
            robot_id="rover-target",
            root="/home/robot/rover_ws",
        ),
        scan_roots=["."],
        approval_id="approval-" + "b" * 32,
    )


def test_host_templates_are_deterministic_and_least_privilege() -> None:
    bundle = render_target_host_templates(target_id="rover")

    assert bundle.systemd_unit_name == "rolo-bootstrap-agentd@rover.service"
    assert (
        "ExecStart=/opt/rolo/bin/robotctl bootstrap-agentd --robot rover "
        "--host 127.0.0.1 --port 8100\n"
    ) in bundle.systemd_unit
    for hardening in (
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=strict",
        "ProtectHome=true",
        "ReadWritePaths=/var/lib/rolo",
        "IPAddressDeny=any",
        "IPAddressAllow=localhost",
    ):
        assert hardening in bundle.systemd_unit
    assert bundle.authorized_keys_options == (
        'restrict,command="/opt/rolo/bin/robotctl target-executor dispatch"'
    )
    assert bundle.bootstrap_authorized_keys_options == (
        'restrict,command="/opt/rolo/libexec/rolo-bootstrap-dispatch"'
    )
    assert bundle.bootstrap_dispatcher.startswith("#!/usr/bin/python3\n")
    assert bundle.runtime_launcher.startswith("#!/usr/bin/python3\n")
    compile(bundle.bootstrap_dispatcher, "<bootstrap-dispatcher>", "exec")
    compile(bundle.runtime_launcher, "<runtime-launcher>", "exec")
    for command in (
        "robotctl target-executor runtime-capabilities",
        "robotctl target-executor package-transfer",
        "robotctl target-executor bootstrap",
    ):
        assert command in bundle.bootstrap_dispatcher
    assert "sudo" not in bundle.systemd_unit
    assert "sudo" not in bundle.authorized_keys_options
    assert "sudo" not in bundle.bootstrap_authorized_keys_options
    assert bundle.bootstrap_dispatcher_sha256 == hashlib.sha256(
        bundle.bootstrap_dispatcher.encode()
    ).hexdigest()
    assert bundle.runtime_launcher_sha256 == hashlib.sha256(
        bundle.runtime_launcher.encode()
    ).hexdigest()
    assert bundle.systemd_unit_sha256 == hashlib.sha256(
        bundle.systemd_unit.encode()
    ).hexdigest()
    assert bundle == render_target_host_templates(target_id="rover")


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        ({"target_id": "rover\nExecStart=/bin/sh"}, "target id"),
        ({"runtime_user": "root;id"}, "runtime user"),
        ({"robotctl_path": "/opt/rolo/../bin/robotctl"}, "normalized"),
        ({"robotctl_path": "/opt/rolo/bin/robotctl\";id"}, "POSIX path"),
        ({"agent_port": 0}, "port"),
    ],
)
def test_host_template_renderer_rejects_interpolation_inputs(
    updates: dict[str, object],
    match: str,
) -> None:
    values: dict[str, object] = {"target_id": "rover"}
    values.update(updates)
    with pytest.raises(ValueError, match=match):
        render_target_host_templates(**values)  # type: ignore[arg-type]


def test_host_template_contract_detects_content_tamper() -> None:
    bundle = render_target_host_templates(target_id="rover")
    with pytest.raises(ValidationError, match="digest mismatch"):
        TargetHostTemplateBundle.model_validate(
            {**bundle.model_dump(), "systemd_unit": bundle.systemd_unit + "# changed\n"}
        )
    changed = bundle.systemd_unit.replace("ProtectHome=true", "ProtectHome=false")
    with pytest.raises(ValidationError, match="not canonical"):
        TargetHostTemplateBundle.model_validate(
            {
                **bundle.model_dump(),
                "systemd_unit": changed,
                "systemd_unit_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            }
        )


def test_forced_dispatch_accepts_exact_status_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _status_request()

    class FakeLocalExecutor:
        def execute_bootstrap(self, value):  # type: ignore[no-untyped-def]
            assert value == request
            return TargetBootstrapExecutionResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.target_id,
                package_id=value.package_id,
                manifest_sha256=value.manifest_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                operation=value.operation,
                status=TargetExecutionStatus.SUCCEEDED,
                install_index=None,
            )

    from rolo.commands import target_executor as target_executor_commands

    monkeypatch.setattr(target_executor_commands, "LocalTargetExecutor", FakeLocalExecutor)
    result = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=request.model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor bootstrap"},
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "SUCCEEDED"


def test_forced_dispatch_accepts_verified_adapter_release_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _adapter_status_request()

    class FakeLocalExecutor:
        def status_adapter_release(self, value):  # type: ignore[no-untyped-def]
            assert value == request
            return AdapterReleaseStatusExecutionResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.desired.target_id,
                robot_id=value.desired.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code="INTEGRITY_ERROR",
            )

    from rolo.commands import target_executor as target_executor_commands

    monkeypatch.setattr(target_executor_commands, "LocalTargetExecutor", FakeLocalExecutor)
    result = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=request.model_dump_json(),
        env={
            "SSH_ORIGINAL_COMMAND": "robotctl target-executor adapter-release-status"
        },
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["error_code"] == "INTEGRITY_ERROR"


def test_forced_dispatch_rejects_mutation_and_unknown_commands_without_echo() -> None:
    public_key = b"p" * 32
    mutation = TargetBootstrapExecutionRequest(
        request_id="forced-install-0001",
        operation=TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
        target_id="rover",
        package_id="rolo-target",
        manifest_sha256="a" * 64,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(public_key).decode(),
        signing_public_key_sha256=ed25519_public_key_sha256(public_key),
        approval_id="approval-" + "b" * 32,
    )
    rejected = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=mutation.model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor bootstrap"},
    )
    assert rejected.exit_code == 2
    assert '"status": "SUCCEEDED"' not in rejected.output

    secret_command = "sh -c super-secret-token"
    unknown = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        env={"SSH_ORIGINAL_COMMAND": secret_command},
    )
    assert unknown.exit_code == 2
    assert "not permitted" in unknown.output
    assert secret_command not in unknown.output


def test_forced_dispatch_allows_only_enrollment_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    status_request = TargetEnrollmentRequest(
        request_id="forced-enrollment-status",
        operation=TargetEnrollmentOperation.STATUS,
        target_id="rover-target",
        robot_id="rover",
        challenge_nonce="c" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    class FakeLocalExecutor:
        def __init__(self, **_: object) -> None:
            pass

        def execute_enrollment(self, value):  # type: ignore[no-untyped-def]
            assert value == status_request
            return TargetEnrollmentResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                operation=value.operation,
                target_id=value.target_id,
                robot_id=value.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.SUCCEEDED,
                enrollment_status=TargetEnrollmentStatus.NOT_ENROLLED,
            )

        def detect_project_evidence(self, value):  # type: ignore[no-untyped-def]
            return TargetProjectEvidenceExecutionResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.workspace.target_id,
                robot_id=value.workspace.robot_id,
                workspace_id=value.workspace.workspace_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
            )

        def discover_source(self, value):  # type: ignore[no-untyped-def]
            return TargetSourceDiscoveryExecutionResult(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.workspace.target_id,
                robot_id=value.workspace.robot_id,
                workspace_id=value.workspace.workspace_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
            )

        def collect_evidence_v4(self, value):  # type: ignore[no-untyped-def]
            return TargetEvidenceCollectionResultV4(
                request_id=value.request_id,
                request_sha256=value.canonical_sha256(),
                target_id=value.target_id,
                robot_id=value.evidence_request.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
            )

    from rolo.commands import target_executor as target_executor_commands

    monkeypatch.setattr(target_executor_commands, "LocalTargetExecutor", FakeLocalExecutor)
    allowed = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=status_request.model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor enroll"},
    )
    assert allowed.exit_code == 0, allowed.output
    assert json.loads(allowed.output)["enrollment_status"] == "NOT_ENROLLED"

    mutation = TargetEnrollmentRequest(
        request_id="forced-enrollment-mutation",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="rover-target",
        robot_id="rover",
        challenge_nonce="d" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        configuration_sha256=CollectorConfigurationV4().canonical_sha256(),
        configuration=CollectorConfigurationV4(),
        approval_id="approval-" + "f" * 32,
    )
    rejected = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=mutation.model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor enroll"},
    )
    assert rejected.exit_code == 2
    assert '"enrollment_status": "ENROLLED"' not in rejected.output

    evidence_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=TargetEvidenceCollectionRequestV4(
            request_id="forced-runtime-evidence-0001",
            target_id="rover-target",
            evidence_request=new_request("rover"),
            approval_id="approval-" + "1" * 32,
        ).model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor evidence-v4"},
    )
    assert evidence_command.exit_code == 0, evidence_command.output
    assert json.loads(evidence_command.output)["error_code"] == "AUTHORIZATION_FAILED"

    stage_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor adapter-release-stage"},
    )
    assert stage_command.exit_code == 2
    assert "not permitted" in stage_command.output

    activation_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor adapter-release-activate"},
    )
    assert activation_command.exit_code == 2
    assert "not permitted" in activation_command.output

    describe_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor adapter-release-describe"},
    )
    assert describe_command.exit_code == 2
    assert "not permitted" in describe_command.output

    project_evidence_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=_project_evidence_request().model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor project-evidence"},
    )
    assert project_evidence_command.exit_code == 0, project_evidence_command.output
    assert json.loads(project_evidence_command.output)["error_code"] == (
        "AUTHORIZATION_FAILED"
    )

    source_discovery_command = CliRunner().invoke(
        app,
        ["target-executor", "dispatch"],
        input=_source_discovery_request().model_dump_json(),
        env={"SSH_ORIGINAL_COMMAND": "robotctl target-executor source-discovery"},
    )
    assert source_discovery_command.exit_code == 0, source_discovery_command.output
    assert json.loads(source_discovery_command.output)["error_code"] == (
        "AUTHORIZATION_FAILED"
    )
