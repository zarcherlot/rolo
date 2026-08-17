import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from rolo.bundle import build_compatible_bundle
from rolo.stages.build.bundle import _coding_agent_config


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
        assert root + "systemd/rolo-bootstrap-agentd.service" in names
        assert not any("config/robots" in name for name in names)
        manifest = json.loads(archive.read(root + "manifest.json"))
        install_script = archive.read(root + "install.sh").decode()
        environment = archive.read(root + "config/rolo.env.example").decode()
        bootstrap_unit = archive.read(
            root + "systemd/rolo-bootstrap-agentd.service"
        ).decode()
        discovery_unit = archive.read(root + "systemd/rolo-discovery.service").decode()
        agentd_unit = archive.read(root + "systemd/rolo-agentd.service").decode()
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
    assert "Ubuntu 20.04, 22.04, or 24.04 is required" in install_script
    assert "Python 3.10 or newer is required" in install_script
    assert "The Python venv module is required" in install_script
    assert "CODING_AGENT_PROVIDER=codex" in environment
    assert "CODING_AGENT_EXECUTOR=codex" in environment
    assert "CODING_AGENT_BASE_URL=" in environment
    assert "CODING_AGENT_API_KEY=" in environment
    assert "CODING_AGENT_MODEL=" in environment
    assert "CODING_AGENT_EXECUTABLE=codex" in environment
    assert "CODING_AGENT_TIMEOUT_S=1800" in environment
    assert "CODING_AGENT_AUTO_INSTALL=true" in environment
    assert "CODING_AGENT_REQUIRE_AUTH=true" in environment
    assert "CODING_AGENT_INSTALL_TIMEOUT_S=300" in environment
    assert "CODING_AGENT_INSTALL_HOME=/var/lib/rolo" in environment
    assert "CODING_AGENT_HOME=/var/lib/rolo/codex" in environment
    assert "robotctl\" build agent-prepare --skip-auth" in install_script
    assert "runuser -u \"$SERVICE_USER\"" in install_script
    assert manifest["platform_baseline"]["os_versions"] == ["20.04", "22.04", "24.04"]
    assert manifest["platform_baseline"]["ros_distributions"] == ["foxy", "humble", "jazzy"]
    assert "robotctl bootstrap-agentd" in bootstrap_unit
    assert "Requires=rolo-bootstrap-agentd.service" in discovery_unit
    assert "After=network-online.target rolo-bootstrap-agentd.service" in discovery_unit
    assert "robotctl bootstrap-wait --robot ${ROBOT_ID}" in discovery_unit
    assert "Requires=rolo-discovery.service" in agentd_unit
    assert "After=network-online.target rolo-discovery.service" in agentd_unit
    assert "systemctl start rolo-agentd.service" in install_script


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


def test_bundle_rejects_unregistered_or_unsafe_coding_agent_installers() -> None:
    valid = {
        "coding_agent": {
            "executor": "codex",
            "provider": "codex",
            "auto_install": True,
            "require_auth": True,
            "executable": "codex",
            "install_home": "/var/lib/rolo",
            "home": "/var/lib/rolo/codex",
            "install_timeout_s": 300,
        }
    }

    assert _coding_agent_config(valid)["executor"] == "codex"
    valid["coding_agent"]["executor"] = "arbitrary-shell"
    with pytest.raises(ValueError, match="unsupported"):
        _coding_agent_config(valid)

    valid["coding_agent"]["executor"] = "codex"
    valid["coding_agent"]["executable"] = "codex; unsafe-command"
    with pytest.raises(ValueError, match="unsafe path"):
        _coding_agent_config(valid)
