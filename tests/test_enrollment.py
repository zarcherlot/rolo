import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from rolo.agentd import create_agentd_app
from rolo.cli import app
from rolo.core.config import get_settings, load_yaml
from rolo.enrollment import EnrollmentService, list_profiles, load_urdf_profile

PROFILE_ROOT = Path("configs/profiles")


def urdf_profile(name: str) -> Path:
    return PROFILE_ROOT / f"{name}.urdf"


def test_registers_arbitrary_identity_without_reading_urdf(tmp_path: Path) -> None:
    service = EnrollmentService(config_root=tmp_path / "config")

    result = service.enroll(robot_id="warehouse_bot_17")
    capability = load_yaml(result.capability_path)

    assert result.status == "IDENTITY_REGISTERED"
    assert capability["robot_id"] == "warehouse_bot_17"
    assert capability["platform"]["compute"] == "auto_discover"
    assert capability["platform"]["os"] == "auto_discover"
    assert capability["platform"]["ros_distro"] == "auto_discover"
    assert capability["platform"]["drive_model"] == "unresolved"
    assert capability["geometry"] == {}
    enrollment = capability["features"]["enrollment"]
    assert enrollment["identity_status"] == "REGISTERED"
    assert enrollment["urdf_status"] == "NOT_DISCOVERED"
    assert enrollment["semantic_status"] == "UNRESOLVED"
    assert enrollment["motion_safety_status"] == "UNAPPROVED"
    assert enrollment["bindings_verified"] is False
    assert enrollment["calibration_verified"] is False
    assert not {"profile_id", "profile_path", "profile_sha256"} & set(enrollment)


def test_enrollment_is_idempotent_but_refuses_second_identity(tmp_path: Path) -> None:
    service = EnrollmentService(config_root=tmp_path / "config")
    first = service.enroll(robot_id="field_unit_01")
    repeated = service.enroll(robot_id="field_unit_01")

    assert first.status == "IDENTITY_REGISTERED"
    assert repeated.status == "ALREADY_REGISTERED"
    with pytest.raises(ValueError, match="one installed instance"):
        service.enroll(robot_id="field_unit_02")


def test_enrollment_requires_valid_identity(tmp_path: Path) -> None:
    service = EnrollmentService(config_root=tmp_path / "config")
    with pytest.raises(ValueError, match="robot_id must match"):
        service.enroll(robot_id="INVALID ID")


def test_urdf_profile_records_missing_semantics_for_discovery(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "structural_only.urdf"
    profile_path.write_text(
        '<robot name="structural_only"><link name="base_link"/></robot>', encoding="utf-8"
    )

    profile = load_urdf_profile(profile_path)
    assert profile.platform["drive_model"] == "unresolved"
    assert set(profile.unresolved_semantics) == {
        "geometry.footprint_m",
        "geometry.hard_max_linear_velocity_mps",
        "geometry.hard_max_angular_velocity_radps",
        "platform.drive_model",
    }



def test_urdf_profile_catalog_is_data_driven() -> None:
    profiles = list_profiles(PROFILE_ROOT)

    assert {profile["profile_id"] for profile in profiles} == {
        "ackermann",
        "differential_drive",
    }
    assert {profile["format"] for profile in profiles} == {"urdf"}
    assert all(str(profile["path"]).endswith(".urdf") for profile in profiles)


def test_urdf_profile_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    source = urdf_profile("differential_drive").read_bytes()
    crlf_profile = tmp_path / "differential_drive.urdf"
    crlf_profile.write_bytes(source.replace(b"\n", b"\r\n"))

    assert load_urdf_profile(crlf_profile).sha256 == load_urdf_profile(
        urdf_profile("differential_drive")
    ).sha256


def test_new_enrollment_remains_degraded_until_binding_and_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "config"
    service = EnrollmentService(config_root=config_root)
    service.enroll(robot_id="new_field_unit")
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(config_root))
    get_settings.cache_clear()

    with TestClient(create_agentd_app("new_field_unit")) as client:
        health = client.get("/health")
        state = client.get("/v1/state/snapshot")

    get_settings.cache_clear()
    assert health.json()["status"] == "DEGRADED"
    assert state.json()["safety"]["watchdog"] == "DISARMED"
    assert state.json()["application"]["navigation"] == "NOT_READY"


def test_init_registers_and_runs_all_install_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        "rolo.cli._run_engineering_tests",
        lambda _workspace: {"status": "PASSED", "exit_code": 0, "summary": "48 passed"},
    )
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--robot-id",
            "customer_rover_42",
        ],
        env={"ROLO_CONFIG_DIR": str(tmp_path / "config")},
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert '"robot_id": "customer_rover_42"' in result.output
    assert '"profile_path"' not in result.output
    assert '"status": "READY_FOR_DISCOVERY"' in result.output
    assert '"engineering_tests"' in result.output
    assert '"enrollment_status": "NOT_DISCOVERED"' in result.output
    assert '"motion_safety_status": "UNAPPROVED"' in result.output
    assert (tmp_path / "config/robots/customer_rover_42.yaml").is_file()


def test_init_help_contains_no_urdf_option() -> None:
    result = CliRunner().invoke(app, ["init", "--help"])

    assert result.exit_code == 0, result.output
    assert "--robot-id" in result.output
    assert "--profile" not in result.output
    assert "--urdf" not in result.output


def test_doctor_treats_fresh_unenrolled_checkout_as_ready(tmp_path: Path) -> None:
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        ["doctor"],
        env={
            "ROLO_CONFIG_DIR": str(tmp_path / "config"),
            "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        },
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "READY"
    assert payload["enrollment_status"] == "NOT_ENROLLED"
    assert payload["robots"] == 0
    assert any("No robot is registered" in warning for warning in payload["warnings"])


def test_doctor_still_rejects_invalid_robot_manifest(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    robots_root = config_root / "robots"
    robots_root.mkdir(parents=True)
    (robots_root / "broken.yaml").write_text("robot_id: [\n", encoding="utf-8")

    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        ["doctor"],
        env={
            "ROLO_CONFIG_DIR": str(config_root),
            "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        },
    )
    get_settings.cache_clear()

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "NOT_READY"
    assert payload["enrollment_status"] == "INVALID"
    assert payload["errors"]
