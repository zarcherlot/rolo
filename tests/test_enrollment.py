import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.main import get_command
from typer.testing import CliRunner

from rolo.agentd import create_agentd_app
from rolo.cli import app
from rolo.core.config import get_settings, load_yaml
from rolo.stages.adapt.enrollment import EnrollmentService, load_urdf_profile

PROFILE_ROOT = Path("tests/fixtures/profiles")


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
    assert profile.features["urdf_structure"] == {
        "links": ["base_link"],
        "joints": [],
        "truncated": False,
    }


def test_urdf_profile_preserves_bounded_link_joint_and_sensor_structure() -> None:
    profile = load_urdf_profile(urdf_profile("differential_drive"))
    structure = profile.features["urdf_structure"]

    assert structure["links"] == [
        "base_link",
        "front_camera_link",
        "front_lidar_link",
        "left_wheel_link",
        "right_wheel_link",
    ]
    left_wheel = next(joint for joint in structure["joints"] if joint["name"] == "left_wheel_joint")
    assert {
        key: left_wheel[key] for key in ("name", "type", "parent", "child", "axis", "limits")
    } == {
        "name": "left_wheel_joint",
        "type": "continuous",
        "parent": "base_link",
        "child": "left_wheel_link",
        "axis": "0 1 0",
        "limits": {"effort": 20.0, "velocity": 10.0},
    }
    assert profile.sensors["front_camera"]["urdf_link"] == "front_camera_link"


def test_urdf_profile_extracts_mobile_base_hardware_and_control_specs(tmp_path: Path) -> None:
    profile_path = tmp_path / "hardware_base.urdf"
    profile_path.write_text(
        """<robot name="hardware_base">
  <link name="base_link">
    <visual><origin xyz="0.08 0 0.04"/>
      <geometry><box size="0.23 0.11 0.05"/></geometry>
    </visual>
    <inertial><origin xyz="0.01 0 0.02"/><mass value="2.5"/>
      <inertia ixx="1" ixy="0" ixz="0" iyy="1" iyz="0" izz="1"/>
    </inertial>
  </link>
  <link name="left_wheel"><visual><geometry>
    <cylinder radius="0.0325" length="0.025"/>
  </geometry></visual></link>
  <link name="right_wheel"><visual><geometry>
    <cylinder radius="0.0325" length="0.025"/>
  </geometry></visual></link>
  <joint name="left_joint" type="continuous">
    <origin xyz="0 0.08 0.0325"/><parent link="base_link"/>
    <child link="left_wheel"/><axis xyz="0 1 0"/>
  </joint>
  <joint name="right_joint" type="continuous">
    <origin xyz="0 -0.08 0.0325"/><parent link="base_link"/>
    <child link="right_wheel"/><axis xyz="0 1 0"/>
  </joint>
  <transmission name="left_trans"><type>SimpleTransmission</type>
    <joint name="left_joint"><hardwareInterface>velocity</hardwareInterface></joint>
    <actuator name="left_motor"><mechanicalReduction>20</mechanicalReduction></actuator>
  </transmission>
  <ros2_control name="drive_board" type="system"><hardware>
    <plugin>vendor/DriveBoard</plugin><param name="port">can0</param>
  </hardware><joint name="left_joint"><command_interface name="velocity"/>
    <state_interface name="position"/></joint>
  </ros2_control>
  <gazebo reference="base_link"><sensor name="imu" type="imu">
    <update_rate>100</update_rate>
  </sensor></gazebo>
</robot>""",
        encoding="utf-8",
    )

    profile = load_urdf_profile(profile_path)
    hardware = profile.features["urdf_hardware"]

    assert profile.geometry["body_dimensions_m"] == [0.23, 0.11, 0.05]
    assert profile.geometry["wheel_count"] == 2
    assert profile.geometry["wheel_radii_m"] == [0.0325]
    assert profile.geometry["track_width_m"] == pytest.approx(0.16)
    assert profile.geometry["ground_clearance_m"] == pytest.approx(0.015)
    assert profile.geometry["declared_mass_kg"] == 2.5
    assert hardware["transmissions"][0]["actuators"][0]["name"] == "left_motor"
    assert hardware["ros2_control"][0]["plugins"] == ["vendor/DriveBoard"]
    assert hardware["gazebo"][0]["sensors"][0]["update_rate_hz"] == "100"


def test_urdf_profile_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    source = urdf_profile("differential_drive").read_bytes()
    source = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    crlf_profile = tmp_path / "differential_drive.urdf"
    crlf_profile.write_bytes(source.replace(b"\n", b"\r\n"))

    assert (
        load_urdf_profile(crlf_profile).sha256
        == load_urdf_profile(urdf_profile("differential_drive")).sha256
    )


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
    assert state.json()["safety"]["watchdog"] == "UNKNOWN"
    assert state.json()["application"]["navigation"] == "UNKNOWN"


def test_init_registers_and_runs_runtime_checks(tmp_path: Path) -> None:
    get_settings.cache_clear()
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
    assert '"engineering_tests"' not in result.output
    assert '"enrollment_status": "NOT_DISCOVERED"' in result.output
    assert '"motion_safety_status": "UNAPPROVED"' in result.output
    assert (tmp_path / "config/robots/customer_rover_42.yaml").is_file()


def test_init_help_contains_no_urdf_option() -> None:
    init_command = get_command(app).commands["init"]
    option_names = {
        option
        for parameter in init_command.params
        for option in getattr(parameter, "opts", ())
    }

    assert "--robot-id" in option_names
    assert "--profile" not in option_names
    assert "--urdf" not in option_names


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
