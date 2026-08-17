import hashlib
import json
import zipfile
from pathlib import Path

from rolo.bundle import build_compatible_bundle


def test_builds_identity_free_arm64_bundle_with_dynamic_profiles(tmp_path: Path) -> None:
    wheel = tmp_path / "rolo-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"test wheel payload")

    result = build_compatible_bundle(wheel=wheel, output_dir=tmp_path / "out")

    assert result.target_arch == "arm64"
    assert result.profile_ids == ("ackermann", "differential_drive")
    assert result.sha256 == hashlib.sha256(result.bundle.read_bytes()).hexdigest()
    with zipfile.ZipFile(result.bundle) as archive:
        root = "rolo-0.1.0-arm64/"
        names = set(archive.namelist())
        assert root + "profiles/ackermann.yaml" in names
        assert root + "profiles/differential_drive.yaml" in names
        assert root + "config/deployment.yaml" in names
        assert root + "config/platforms/arm64.yaml" in names
        assert root + "systemd/robot-loop-bootstrap-agentd.service" in names
        assert not any("config/robots" in name for name in names)
        manifest = json.loads(archive.read(root + "manifest.json"))
        install_script = archive.read(root + "install.sh").decode()
        bootstrap_unit = archive.read(
            root + "systemd/robot-loop-bootstrap-agentd.service"
        ).decode()
        discovery_unit = archive.read(root + "systemd/robot-loop-discovery.service").decode()
        agentd_unit = archive.read(root + "systemd/robot-loop-agentd.service").decode()
        for relative, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(root + relative)).hexdigest() == expected

    assert manifest["identity_mode"] == "dynamic_enrollment"
    assert manifest["included_robot_ids"] == []
    assert manifest["profile_ids"] == ["ackermann", "differential_drive"]
    assert manifest["supported_compute"] == [
        "nvidia_jetson_orin",
        "rockchip_rk3588",
        "raspberry_pi",
    ]
    assert manifest["startup_order"] == ["bootstrap-agentd", "discovery", "agentd"]
    assert "<robot_id>" in install_script
    assert "robotctl\" enroll init" in install_script
    assert "--confirm-safety-profile" in install_script
    assert "continuing with bootstrap discovery in DEGRADED mode" in install_script
    assert "robotctl bootstrap-agentd" in bootstrap_unit
    assert "Requires=robot-loop-bootstrap-agentd.service" in discovery_unit
    assert "After=network-online.target robot-loop-bootstrap-agentd.service" in discovery_unit
    assert "robotctl bootstrap-wait --robot ${ROBOT_ID}" in discovery_unit
    assert "Requires=robot-loop-discovery.service" in agentd_unit
    assert "After=network-online.target robot-loop-discovery.service" in agentd_unit
    assert "systemctl start robot-loop-agentd.service" in install_script


def test_bundle_contains_no_demo_robot_identity(tmp_path: Path) -> None:
    wheel = tmp_path / "rolo-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"test wheel payload")
    result = build_compatible_bundle(wheel=wheel, output_dir=tmp_path / "out")

    with zipfile.ZipFile(result.bundle) as archive:
        text_payload = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if not name.endswith(".whl")
        )

    for legacy_suffix in ("a", "b"):
        assert f"robot_{legacy_suffix}" not in text_payload
