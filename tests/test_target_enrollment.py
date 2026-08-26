from __future__ import annotations

import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.commands import target as target_commands
from rolo.core.config import Settings
from rolo.targets import (
    OrchestratorPlacement,
    TargetProfile,
    TargetProfileRegistry,
    TargetTransport,
)
from rolo.targets.enrollment import (
    CollectorConfigurationDiscoveryV4,
    CollectorConfigurationV4,
    CollectorDescriptorV4,
    CollectorEnrollmentPinRegistry,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
    TargetEnrollmentStateConflict,
    TargetEnrollmentStatus,
    discover_collector_configuration_v4,
    verify_collector_rotation_transition,
    verify_enrollment_attestation,
)

NOW = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
APPROVAL_ID = "approval-" + "a" * 32
CONFIGURATION = CollectorConfigurationV4()
CONFIG_DIGEST = CONFIGURATION.canonical_sha256()


def _request(
    operation: TargetEnrollmentOperation,
    *,
    request_id: str,
    nonce: str,
    expected_collector_id: str | None = None,
    approval_id: str | None = None,
) -> TargetEnrollmentRequest:
    configuration = CONFIGURATION if operation != TargetEnrollmentOperation.STATUS else None
    return TargetEnrollmentRequest(
        request_id=request_id,
        operation=operation,
        target_id="wheeltec-target",
        robot_id="wheeltec",
        challenge_nonce=nonce,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        expected_collector_id=expected_collector_id,
        configuration_sha256=(
            configuration.canonical_sha256() if configuration is not None else None
        ),
        configuration=configuration,
        approval_id=approval_id,
    )


def _enroll_request(request_id: str = "enroll-wheeltec-0001") -> TargetEnrollmentRequest:
    return _request(
        TargetEnrollmentOperation.ENROLL,
        request_id=request_id,
        nonce="1" * 32,
        approval_id=APPROVAL_ID,
    )


def _service(root: Path, *, fingerprint: str = "c" * 64) -> TargetEnrollmentService:
    return TargetEnrollmentService(
        root,
        host_fingerprint_provider=lambda: fingerprint,
        clock=lambda: NOW,
    )


def test_enrollment_generates_target_local_key_and_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path / "enrollment")
    request = _enroll_request()

    created = service.execute(request)
    repeated = service.execute(_enroll_request(request_id="enroll-wheeltec-repeat"))

    assert created.enrollment_status == TargetEnrollmentStatus.ENROLLED
    assert repeated.enrollment_status == TargetEnrollmentStatus.ALREADY_ENROLLED
    assert created.descriptor == repeated.descriptor
    assert verify_enrollment_attestation(request, created, now=NOW) == created.descriptor
    assert (
        verify_enrollment_attestation(
            _enroll_request(request_id="enroll-wheeltec-repeat"),
            repeated,
            now=NOW,
        )
        == repeated.descriptor
    )
    assert created.descriptor is not None
    identity_root = tmp_path / "enrollment" / "identities" / created.descriptor.collector_id
    private_key = identity_root / "private-key.pem"
    assert private_key.is_file()
    assert len(list((tmp_path / "enrollment" / "identities").glob("collector-*"))) == 1
    serialized = created.model_dump_json()
    assert "PRIVATE KEY" not in serialized
    assert "private-key.pem" not in serialized
    if os.name == "posix":
        assert stat.S_IMODE(private_key.stat().st_mode) == 0o600


def test_status_returns_fresh_proof_of_possession_or_not_enrolled(tmp_path: Path) -> None:
    service = _service(tmp_path / "enrollment")
    status_request = _request(
        TargetEnrollmentOperation.STATUS,
        request_id="enrollment-status-0001",
        nonce="2" * 32,
    )
    absent = service.execute(status_request)
    assert absent.enrollment_status == TargetEnrollmentStatus.NOT_ENROLLED
    assert verify_enrollment_attestation(status_request, absent, now=NOW) is None

    service.execute(_enroll_request())
    fresh_request = _request(
        TargetEnrollmentOperation.STATUS,
        request_id="enrollment-status-0002",
        nonce="3" * 32,
    )
    present = service.execute(fresh_request)
    assert present.enrollment_status == TargetEnrollmentStatus.ENROLLED
    assert verify_enrollment_attestation(fresh_request, present, now=NOW) == (present.descriptor)


def test_attestation_rejects_tamper_replay_expiry_and_identity_mismatch(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path / "enrollment")
    request = _enroll_request()
    result = service.execute(request)
    assert result.attestation is not None
    assert result.descriptor is not None

    signature = result.attestation.signature_base64
    replacement = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = result.model_copy(
        update={
            "attestation": result.attestation.model_copy(update={"signature_base64": replacement})
        }
    )
    with pytest.raises(ValueError, match="signature mismatch"):
        verify_enrollment_attestation(request, tampered, now=NOW)

    replay = _enroll_request(request_id="different-enrollment-request")
    with pytest.raises(ValueError, match="request binding mismatch"):
        verify_enrollment_attestation(replay, result, now=NOW)

    with pytest.raises(ValueError, match="expired"):
        verify_enrollment_attestation(request, result, now=NOW + timedelta(minutes=8))

    changed_descriptor = result.descriptor.model_copy(update={"robot_id": "other"})
    changed = result.model_copy(update={"descriptor": changed_descriptor})
    with pytest.raises(ValueError, match="attestation binding mismatch"):
        verify_enrollment_attestation(request, changed, now=NOW)


def test_rotation_is_signed_by_old_identity_and_uses_compare_and_swap(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path / "enrollment")
    enrolled = service.execute(_enroll_request())
    previous = enrolled.descriptor
    assert previous is not None

    wrong = _request(
        TargetEnrollmentOperation.ROTATE,
        request_id="rotate-wheeltec-wrong",
        nonce="4" * 32,
        expected_collector_id="collector-" + "0" * 32,
        approval_id=APPROVAL_ID,
    )
    with pytest.raises(TargetEnrollmentStateConflict, match="expected rotation pin"):
        service.execute(wrong)

    rotate = _request(
        TargetEnrollmentOperation.ROTATE,
        request_id="rotate-wheeltec-0001",
        nonce="5" * 32,
        expected_collector_id=previous.collector_id,
        approval_id=APPROVAL_ID,
    )
    rotated = service.execute(rotate)

    assert rotated.enrollment_status == TargetEnrollmentStatus.ROTATED
    assert rotated.descriptor is not None
    assert rotated.descriptor.collector_id != previous.collector_id
    assert rotated.transition is not None
    verify_collector_rotation_transition(
        rotated.transition,
        previous_descriptor=previous,
        new_descriptor=rotated.descriptor,
    )
    assert verify_enrollment_attestation(rotate, rotated, now=NOW) == rotated.descriptor

    tampered_transition = rotated.transition.model_copy(update={"new_descriptor_sha256": "e" * 64})
    with pytest.raises(ValueError, match="identity binding mismatch"):
        verify_collector_rotation_transition(
            tampered_transition,
            previous_descriptor=previous,
            new_descriptor=rotated.descriptor,
        )


def test_concurrent_enrollment_creates_exactly_one_identity(tmp_path: Path) -> None:
    root = tmp_path / "enrollment"
    service = _service(root)
    requests = (
        _enroll_request("concurrent-enroll-0001"),
        _enroll_request("concurrent-enroll-0002"),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.execute, requests))

    observed = sorted(
        result.enrollment_status.value for result in results if result.enrollment_status is not None
    )
    assert observed == [
        TargetEnrollmentStatus.ALREADY_ENROLLED.value,
        TargetEnrollmentStatus.ENROLLED.value,
    ]
    assert results[0].descriptor == results[1].descriptor
    assert len(list((root / "identities").glob("collector-*"))) == 1


def test_interrupted_initial_activation_leaves_no_current_or_private_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "enrollment"
    service = _service(root)

    def fail_index(_index) -> None:  # type: ignore[no-untyped-def]
        raise OSError("simulated power interruption")

    monkeypatch.setattr(service, "_write_index", fail_index)
    with pytest.raises(OSError, match="power interruption"):
        service.execute(_enroll_request())

    assert not (root / "current.json").exists()
    assert not list((root / "identities").glob("collector-*"))


def test_active_identity_is_bound_to_target_host(tmp_path: Path) -> None:
    root = tmp_path / "enrollment"
    _service(root, fingerprint="c" * 64).execute(_enroll_request())
    moved = _service(root, fingerprint="d" * 64)
    request = _request(
        TargetEnrollmentOperation.STATUS,
        request_id="moved-host-status",
        nonce="6" * 32,
    )
    with pytest.raises(ValueError, match="different target host"):
        moved.execute(request)


def test_enrollment_contracts_fail_closed() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TargetEnrollmentRequest.model_validate(
            {
                **_enroll_request().model_dump(),
                "private_key": "must-not-be-accepted",
            }
        )
    with pytest.raises(ValidationError, match="configuration source and approval"):
        _request(
            TargetEnrollmentOperation.ENROLL,
            request_id="missing-approval",
            nonce="7" * 32,
        )


def test_target_discovers_bounded_collector_configuration_from_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    executable = workspace / "install" / "bin" / "robot-demo"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    overlay = workspace / "install" / "local_setup.bash"
    overlay.write_text("export ROS_DISTRO=test\n", encoding="utf-8")
    discovery = CollectorConfigurationDiscoveryV4(
        workspace_root=str(workspace.absolute()),
        help_executable_relative_paths=["install/bin/robot-demo"],
    )

    configuration = discover_collector_configuration_v4(
        discovery,
        environment={},
        ros_root=tmp_path / "no-system-ros",
    )

    assert len(configuration.help_executables) == 1
    assert configuration.help_executables[0].path == str(executable.resolve())
    assert configuration.help_executables[0].sha256
    assert [item.path for item in configuration.ros_setup_files] == [str(overlay.resolve())]
    with pytest.raises(ValidationError, match="must be normalized"):
        CollectorConfigurationDiscoveryV4(
            workspace_root=str(workspace.absolute()),
            help_executable_relative_paths=["install/../secret"],
        )


def test_enrollment_auto_configuration_is_discovered_and_attested(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request = TargetEnrollmentRequest(
        request_id="auto-enroll-wheeltec",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="wheeltec-target",
        robot_id="wheeltec",
        challenge_nonce="e" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        configuration_discovery=CollectorConfigurationDiscoveryV4(
            workspace_root=str(workspace.absolute()),
            ros_auto_source=False,
        ),
        approval_id=APPROVAL_ID,
    )

    result = _service(tmp_path / "enrollment").execute(request)

    assert result.enrollment_status == TargetEnrollmentStatus.ENROLLED
    assert result.configuration == CollectorConfigurationV4()
    assert result.descriptor is not None
    assert result.descriptor.configuration_sha256 == (result.configuration.canonical_sha256())
    verify_enrollment_attestation(request, result, now=NOW)


def test_descriptor_rejects_public_key_digest_mismatch() -> None:
    with pytest.raises(ValidationError, match="public key digest mismatch"):
        CollectorDescriptorV4(
            target_id="wheeltec-target",
            robot_id="wheeltec",
            collector_id="collector-" + "1" * 32,
            target_host_fingerprint="c" * 64,
            key_id="collector-key-" + "2" * 32,
            public_key_base64="A" * 43 + "=",
            public_key_sha256="f" * 64,
            configuration_sha256=CONFIG_DIGEST,
            created_at=NOW,
        )


def test_controller_pins_public_key_and_applies_old_key_rotation(tmp_path: Path) -> None:
    service = _service(tmp_path / "target")
    registry = CollectorEnrollmentPinRegistry(tmp_path / "controller")
    enroll_request = _enroll_request()
    enrolled = service.execute(enroll_request)

    initial_pin = registry.apply(enroll_request, enrolled, now=NOW)
    repeated_pin = registry.apply(enroll_request, enrolled, now=NOW)

    assert repeated_pin == initial_pin
    assert registry.get("wheeltec-target") == initial_pin
    assert initial_pin.descriptor == enrolled.descriptor
    assert "private" not in initial_pin.model_dump_json().casefold()
    assert initial_pin.transition_id is None
    assert enrolled.descriptor is not None

    rotate_request = _request(
        TargetEnrollmentOperation.ROTATE,
        request_id="controller-rotate-0001",
        nonce="8" * 32,
        expected_collector_id=enrolled.descriptor.collector_id,
        approval_id=APPROVAL_ID,
    )
    rotated = service.execute(rotate_request)
    rotated_pin = registry.apply(rotate_request, rotated, now=NOW)

    assert rotated_pin.descriptor == rotated.descriptor
    assert rotated_pin.transition_id == rotated.transition.transition_id  # type: ignore[union-attr]
    assert registry.get("wheeltec-target") == rotated_pin
    assert (tmp_path / "controller" / "transitions" / f"{rotated_pin.transition_id}.json").is_file()


def test_controller_rejects_unapproved_pin_replacement(tmp_path: Path) -> None:
    registry = CollectorEnrollmentPinRegistry(tmp_path / "controller")
    first_service = _service(tmp_path / "target-a")
    request = _enroll_request()
    first = first_service.execute(request)
    registry.apply(request, first, now=NOW)

    second_service = _service(tmp_path / "target-b")
    replacement_request = _enroll_request("replacement-enroll")
    replacement = second_service.execute(replacement_request)
    with pytest.raises(TargetEnrollmentStateConflict, match="different collector"):
        registry.apply(replacement_request, replacement, now=NOW)

    assert registry.get("wheeltec-target").descriptor == first.descriptor


def test_target_enroll_cli_routes_through_command_bus_and_pins_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, rolo_config_dir=tmp_path / "config")
    profiles = TargetProfileRegistry(settings.target_profile_dir)
    profiles.save_target(
        TargetProfile(
            target_id="local-rover",
            orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
            transport=TargetTransport.LOCAL,
            workspace_root="/opt/robot/ws",
            desired_rolo_version="0.2.0",
        )
    )
    monkeypatch.setattr(target_commands, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "c" * 64,
    )
    issued = datetime.now(timezone.utc)
    argv = [
        "target",
        "enroll",
        "--target",
        "local-rover",
        "--robot-id",
        "rover",
        "--approval-id",
        APPROVAL_ID,
        "--request-id",
        "cli-enrollment-0001",
        "--challenge-nonce",
        "a" * 32,
        "--issued-at",
        issued.isoformat(),
        "--expires-at",
        (issued + timedelta(minutes=5)).isoformat(),
    ]

    first = CliRunner().invoke(app, argv)
    repeated = CliRunner().invoke(app, argv)

    assert first.exit_code == 0, first.output
    assert repeated.exit_code == 0, repeated.output
    first_payload = json.loads(first.output)
    repeated_payload = json.loads(repeated.output)
    assert first_payload["command_sha256"] == repeated_payload["command_sha256"]
    assert first_payload["result"]["execution"]["enrollment_status"] == "ENROLLED"
    assert repeated_payload["result"]["execution"]["enrollment_status"] == ("ALREADY_ENROLLED")
    assert "robotctl target enroll" in first_payload["canonical_cli"]
    assert (settings.target_profile_dir / "enrollment-v4" / "pins" / "local-rover.json").is_file()
    assert (
        settings.target_profile_dir / "local-state" / "local-rover" / "enrollment" / "current.json"
    ).is_file()


def test_target_enroll_cli_auto_configuration_uses_registered_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, rolo_config_dir=tmp_path / "config")
    workspace = tmp_path / "workspace"
    executable = workspace / "install" / "bin" / "rover-cli"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    TargetProfileRegistry(settings.target_profile_dir).save_target(
        TargetProfile(
            target_id="local-auto",
            orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
            transport=TargetTransport.LOCAL,
            workspace_root=str(workspace.absolute()),
            desired_rolo_version="0.2.0",
        )
    )
    monkeypatch.setattr(target_commands, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "d" * 64,
    )

    result = CliRunner().invoke(
        app,
        [
            "target",
            "enroll",
            "--target",
            "local-auto",
            "--robot-id",
            "local-auto",
            "--approval-id",
            APPROVAL_ID,
            "--auto-configuration",
            "--no-ros-auto-source",
            "--help-executable-relative-path",
            "install/bin/rover-cli",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    execution = payload["result"]["execution"]
    assert execution["configuration"]["help_executables"][0]["path"] == str(executable.resolve())
    assert "--auto-configuration" in payload["canonical_cli"]
    assert "--no-ros-auto-source" in payload["canonical_cli"]
