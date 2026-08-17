import hashlib
import json
import zipfile
from pathlib import Path

import yaml

from robot_loop.bundle import build_compatible_bundle


def test_builds_one_arm64_bundle_with_two_selectable_profiles(tmp_path: Path) -> None:
    wheel = tmp_path / "robot_loop-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"test wheel payload")

    result = build_compatible_bundle(
        robot_ids=["robot_a", "robot_b"], wheel=wheel, output_dir=tmp_path / "out"
    )

    assert result.target_arch == "arm64"
    assert result.robot_ids == ("robot_a", "robot_b")
    assert result.sha256 == hashlib.sha256(result.bundle.read_bytes()).hexdigest()
    with zipfile.ZipFile(result.bundle) as archive:
        root = "robot-loop-0.1.0-arm64/"
        names = set(archive.namelist())
        assert root + "profiles/robot_a/capability.yaml" in names
        assert root + "profiles/robot_b/capability.yaml" in names
        assert root + "config/platforms/arm64.yaml" in names
        manifest = json.loads(archive.read(root + "manifest.json"))
        install_script = archive.read(root + "install.sh").decode()
        capabilities = [
            yaml.safe_load(archive.read(root + f"profiles/{robot_id}/capability.yaml"))
            for robot_id in manifest["robot_profiles"]
        ]
        for relative, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(root + relative)).hexdigest() == expected

    assert manifest["robot_profiles"] == ["robot_a", "robot_b"]
    assert manifest["target_arch"] == "arm64"
    assert manifest["platform_baseline"] == {
        "os": "ubuntu",
        "os_version": "22.04",
        "ros_distribution": "humble",
    }
    assert manifest["supported_compute"] == [
        "nvidia_jetson_orin",
        "rockchip_rk3588",
        "raspberry_pi",
    ]
    assert "sudo bash install.sh <robot_a|robot_b>" in install_script
    assert "/opt/ros/humble/setup.bash" in install_script
    assert all(capability["platform"]["architecture"] == "arm64" for capability in capabilities)
    assert all(
        capability["features"]["robot_use"]["local_visual_detection"] is False
        for capability in capabilities
    )


def test_rejects_mixed_architecture_profiles(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "configs/robots").mkdir(parents=True)
    (project / "configs/deployment").mkdir(parents=True)
    (project / "configs/platforms").mkdir(parents=True)
    (project / "schemas").mkdir(parents=True)
    common_deployment = """source_revision: test-revision
platform_baseline:
  os: ubuntu
  os_version: '22.04'
  ros_distribution: humble
hardware_profile:
  compute: auto_discover
install_root: /opt/robot-loop
config_root: /etc/robot-loop
artifact_root: /var/lib/robot-loop/artifacts
service_user: robot-loop
"""
    for robot_id, architecture in (("robot_x", "arm64"), ("robot_y", "amd64")):
        (project / f"configs/robots/{robot_id}.yaml").write_text(
            f"robot_id: {robot_id}\nplatform:\n  architecture: {architecture}\n",
            encoding="utf-8",
        )
        (project / f"configs/deployment/{robot_id}.yaml").write_text(
            f"robot_id: {robot_id}\ntarget_arch: {architecture}\n{common_deployment}",
            encoding="utf-8",
        )
    (project / "configs/robot_use.yaml").write_text("backend: mock\n", encoding="utf-8")
    (project / "configs/discovery.yaml").write_text(
        "schema_version: robot-discovery-policy/v1\n", encoding="utf-8"
    )
    (project / "configs/platforms/arm64.yaml").write_text(
        """architecture: arm64
supported_compute:
  - id: test_compute
    name: Test Compute
""",
        encoding="utf-8",
    )
    wheel = tmp_path / "robot_loop.whl"
    wheel.write_bytes(b"wheel")

    try:
        build_compatible_bundle(
            robot_ids=["robot_x", "robot_y"], wheel=wheel, project_root=project
        )
    except ValueError as exc:
        assert "target_arch" in str(exc)
    else:
        raise AssertionError("mixed architecture profiles should be rejected")
