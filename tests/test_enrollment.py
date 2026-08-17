from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from rolo.agentd import create_agentd_app
from rolo.cli import app
from rolo.core.config import get_settings, load_yaml
from rolo.enrollment import EnrollmentService, list_profiles


def test_enrolls_arbitrary_identity_from_profile(tmp_path: Path) -> None:
    service = EnrollmentService(
        config_root=tmp_path / "config", profile_root=Path("configs/profiles")
    )

    result = service.enroll(
        robot_id="warehouse_bot_17",
        profile_id="differential_drive",
        safety_profile_confirmed=True,
    )
    capability = load_yaml(result.capability_path)

    assert result.status == "ENROLLED_DEGRADED"
    assert capability["robot_id"] == "warehouse_bot_17"
    assert capability["platform"]["compute"] == "auto_discover"
    assert capability["features"]["enrollment"] == {
        "profile_id": "differential_drive",
        "safety_profile_confirmed": True,
        "bindings_verified": False,
        "calibration_verified": False,
    }
    capability_text = result.capability_path.read_text(encoding="utf-8")
    for legacy_suffix in ("a", "b"):
        assert f"robot_{legacy_suffix}" not in capability_text


def test_enrollment_is_idempotent_but_refuses_second_identity(tmp_path: Path) -> None:
    service = EnrollmentService(
        config_root=tmp_path / "config", profile_root=Path("configs/profiles")
    )
    first = service.enroll(
        robot_id="field_unit_01",
        profile_id="ackermann",
        safety_profile_confirmed=True,
    )
    repeated = service.enroll(
        robot_id="field_unit_01",
        profile_id="ackermann",
        safety_profile_confirmed=True,
    )

    assert first.status == "ENROLLED_DEGRADED"
    assert repeated.status == "ALREADY_ENROLLED"
    with pytest.raises(ValueError, match="one installed instance"):
        service.enroll(
            robot_id="field_unit_02",
            profile_id="ackermann",
            safety_profile_confirmed=True,
        )


def test_enrollment_requires_valid_identity_and_safety_confirmation(tmp_path: Path) -> None:
    service = EnrollmentService(
        config_root=tmp_path / "config", profile_root=Path("configs/profiles")
    )

    with pytest.raises(ValueError, match="robot_id must match"):
        service.enroll(
            robot_id="INVALID ID",
            profile_id="ackermann",
            safety_profile_confirmed=True,
        )
    with pytest.raises(ValueError, match="confirm-safety-profile"):
        service.enroll(
            robot_id="valid_unit",
            profile_id="ackermann",
            safety_profile_confirmed=False,
        )


def test_profile_catalog_is_data_driven() -> None:
    profiles = list_profiles(Path("configs/profiles"))

    assert {profile["profile_id"] for profile in profiles} == {
        "ackermann",
        "differential_drive",
    }


def test_new_enrollment_remains_degraded_until_binding_and_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "config"
    service = EnrollmentService(config_root=config_root, profile_root=Path("configs/profiles"))
    service.enroll(
        robot_id="new_field_unit",
        profile_id="differential_drive",
        safety_profile_confirmed=True,
    )
    monkeypatch.setenv("ROBOT_LOOP_CONFIG_DIR", str(config_root))
    get_settings.cache_clear()

    with TestClient(create_agentd_app("new_field_unit")) as client:
        health = client.get("/health")
        state = client.get("/v1/state/snapshot")

    get_settings.cache_clear()
    assert health.json()["status"] == "DEGRADED"
    assert state.json()["safety"]["watchdog"] == "DISARMED"
    assert state.json()["application"]["navigation"] == "NOT_READY"


def test_enrollment_cli_accepts_arbitrary_identity(tmp_path: Path) -> None:
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        [
            "enroll",
            "init",
            "--robot-id",
            "customer_rover_42",
            "--profile",
            "ackermann",
            "--profile-root",
            str(Path("configs/profiles").resolve()),
            "--confirm-safety-profile",
        ],
        env={"ROBOT_LOOP_CONFIG_DIR": str(tmp_path / "config")},
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert '"robot_id": "customer_rover_42"' in result.output
    assert (tmp_path / "config/robots/customer_rover_42.yaml").is_file()
