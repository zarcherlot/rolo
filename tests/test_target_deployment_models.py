from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.targets import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentEvent,
    DeploymentEventType,
    DeploymentJob,
    InteractionSurface,
    OrchestratorPlacement,
    TargetConnectionProfile,
    TargetProfile,
    TargetTransport,
    TargetTrustLevel,
)

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
HEX_ID = "a" * 32


def _command(**updates: object) -> DeploymentCommand:
    values: dict[str, object] = {
        "command": DeploymentCommandKind.BOOTSTRAP_AND_ADAPT,
        "target_id": "wheeltec",
        "workspace_root": "/home/robot/wheeltec_ws",
        "requested_by": "session-agent",
        "interaction_surface": InteractionSurface.NATURAL_LANGUAGE,
        "idempotency_key": "request-20260825-0001",
    }
    values.update(updates)
    return DeploymentCommand.model_validate(values)


def test_local_and_ssh_target_profiles_are_explicit() -> None:
    local = TargetProfile(
        target_id="local-robot",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/opt/robot/ws",
        desired_rolo_version="v0.2.0",
    )
    remote = TargetProfile(
        target_id="remote-robot",
        orchestrator_placement=OrchestratorPlacement.CONTROLLER,
        transport=TargetTransport.SSH,
        connection_profile_id="conn-remote",
        workspace_root="/home/robot/ws",
        desired_rolo_version="v0.2.0-rc.1",
    )

    assert local.connection_profile_id is None
    assert remote.connection_profile_id == "conn-remote"

    with pytest.raises(ValidationError, match="requires connection_profile_id"):
        TargetProfile(
            target_id="invalid",
            orchestrator_placement=OrchestratorPlacement.CONTROLLER,
            transport=TargetTransport.SSH,
            workspace_root="/home/robot/ws",
            desired_rolo_version="v0.2.0",
        )


def test_target_workspace_rejects_relative_or_parent_traversal() -> None:
    common = {
        "target_id": "demo",
        "orchestrator_placement": OrchestratorPlacement.TARGET_LOCAL,
        "transport": TargetTransport.LOCAL,
        "desired_rolo_version": "v0.2.0",
    }
    with pytest.raises(ValidationError, match="absolute target POSIX path"):
        TargetProfile(**common, workspace_root="relative/ws")
    with pytest.raises(ValidationError, match="cannot traverse"):
        TargetProfile(**common, workspace_root="/opt/../secret")


def test_local_target_accepts_native_windows_workspace_but_ssh_does_not() -> None:
    local = TargetProfile(
        target_id="local-windows",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root=r"C:\robot\ws",
        desired_rolo_version="v0.2.0",
    )

    assert local.workspace_root == "C:/robot/ws"
    with pytest.raises(ValidationError, match="absolute POSIX path"):
        TargetProfile(
            target_id="remote-windows-path",
            orchestrator_placement=OrchestratorPlacement.CONTROLLER,
            transport=TargetTransport.SSH,
            connection_profile_id="conn-remote",
            workspace_root=r"C:\robot\ws",
            desired_rolo_version="v0.2.0",
        )


def test_release_signing_key_pin_is_atomic_and_uses_controller_absolute_path(
    tmp_path: Path,
) -> None:
    values = {
        "target_id": "demo",
        "orchestrator_placement": OrchestratorPlacement.TARGET_LOCAL,
        "transport": TargetTransport.LOCAL,
        "workspace_root": "/opt/robot/ws",
        "desired_rolo_version": "v0.2.0",
        "release_signing_key_id": "release-key-2026",
        "release_signing_public_key_path": str((tmp_path / "release.pub").resolve()),
        "release_signing_public_key_sha256": "f" * 64,
    }
    profile = TargetProfile.model_validate(values)

    assert profile.release_signing_key_id == "release-key-2026"
    with pytest.raises(ValidationError, match="configured together"):
        TargetProfile.model_validate(
            {**values, "release_signing_public_key_sha256": None}
        )
    with pytest.raises(ValidationError, match="must be absolute"):
        TargetProfile.model_validate(
            {**values, "release_signing_public_key_path": "relative/release.pub"}
        )


def test_strict_ssh_profile_requires_pin_or_ca_and_never_accepts_inline_secret(
    tmp_path: Path,
) -> None:
    values = {
        "connection_profile_id": "conn-wheeltec",
        "host": "wheeltec.local",
        "user": "rolo-evidence",
        "credential_ref": "credential://ssh/wheeltec",
        "known_hosts_path": str((tmp_path / "known_hosts").resolve()),
        "trust_level": TargetTrustLevel.STRICT,
    }
    with pytest.raises(ValidationError, match="requires a host fingerprint"):
        TargetConnectionProfile.model_validate(values)

    profile = TargetConnectionProfile.model_validate(
        {**values, "expected_host_key_sha256": "SHA256:" + "A" * 43}
    )
    assert profile.credential_ref == "credential://ssh/wheeltec"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TargetConnectionProfile.model_validate(
            {
                **values,
                "expected_host_key_sha256": "SHA256:" + "A" * 43,
                "private_key": "-----BEGIN PRIVATE KEY-----",
            }
        )


def test_deployment_command_is_deterministic_and_command_specific() -> None:
    command = _command()
    repeated = DeploymentCommand.model_validate(command.model_dump(mode="json"))

    assert command.canonical_sha256() == repeated.canonical_sha256()
    assert len(command.canonical_sha256()) == 64

    with pytest.raises(ValidationError, match="requires workspace_root"):
        _command(workspace_root=None)
    with pytest.raises(ValidationError, match="does not accept workspace_root"):
        _command(
            command=DeploymentCommandKind.COLLECT_EVIDENCE,
            workspace_root="/home/robot/wheeltec_ws",
        )
    with pytest.raises(ValidationError, match="requires target registration digest"):
        _command(
            command=DeploymentCommandKind.ASSESS_CONNECTION,
            workspace_root=None,
        )


def test_job_binds_the_exact_command_digest() -> None:
    command = _command()
    job = DeploymentJob(
        job_id=f"deployment-{HEX_ID}",
        command=command,
        command_sha256=command.canonical_sha256(),
        created_at=NOW,
        updated_at=NOW,
    )
    assert job.command.target_id == "wheeltec"

    with pytest.raises(ValidationError, match="command digest mismatch"):
        DeploymentJob(
            job_id=f"deployment-{HEX_ID}",
            command=command,
            command_sha256="0" * 64,
            created_at=NOW,
            updated_at=NOW,
        )


def test_approval_and_event_are_bounded_and_secret_closed() -> None:
    command = _command()
    approval = ApprovalRequest(
        approval_id=f"approval-{HEX_ID}",
        job_id=f"deployment-{HEX_ID}",
        target_id="wheeltec",
        command_sha256=command.canonical_sha256(),
        requester_principal="session-agent",
        approver_principal="operator@example.com",
        action=ApprovalAction.USE_SUDO,
        risk="R3",
        sanitized_summary="Install the pinned target bundle as rolo-target.",
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )
    event = DeploymentEvent(
        event_id=f"event-{HEX_ID}",
        job_id=approval.job_id,
        step_id="bootstrap-install",
        target_id="wheeltec",
        event_type=DeploymentEventType.APPROVAL_REQUIRED,
        timestamp=NOW,
        state="BOOTSTRAPPING",
        sanitized_summary="Waiting for approved installation scope.",
        approval_ref=approval.approval_id,
        artifact_refs=["artifact://deployments/wheeltec/plan.json"],
    )

    assert event.approval_ref == approval.approval_id
    for model in (
        TargetProfile,
        TargetConnectionProfile,
        DeploymentCommand,
        DeploymentJob,
        DeploymentEvent,
        ApprovalRequest,
    ):
        properties = {name.casefold() for name in model.model_json_schema()["properties"]}
        assert "password" not in properties
        assert "private_key" not in properties
        assert "token" not in properties

    with pytest.raises(ValidationError, match="artifact ref is invalid"):
        DeploymentEvent.model_validate(
            {
                **event.model_dump(mode="json"),
                "artifact_refs": ["file:///etc/shadow"],
            }
        )
