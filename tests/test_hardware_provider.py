import json
from pathlib import Path

import pytest

from rolo.stages.adapt.discovery import HardwareProbe
from rolo.stages.adapt.hardware_provider import collect_hardware_provider_evidence


def _provider(path: Path, *, robot_expression: str = "request['robot_id']") -> Path:
    path.write_text(
        "import json,sys\n"
        "request = json.load(sys.stdin)\n"
        "print(json.dumps({\n"
        "  'schema_version': 'robot-hardware-evidence/v1',\n"
        f"  'robot_id': {robot_expression},\n"
        "  'components': [{\n"
        "    'kind': 'motor_controller', 'name': 'base_mcu',\n"
        "    'source': 'hardware_provider', 'provider_id': 'wheeltec-readonly/v1',\n"
        "    'model': 'STM32F4', 'firmware_version': '1.2.3'\n"
        "  }],\n"
        "  'devices': [{'path': '/dev/ttyUSB0', 'category': 'serial'}],\n"
        "  'warnings': []\n"
        "}))\n",
        encoding="utf-8",
    )
    return path


def test_hardware_provider_publishes_standardized_read_only_components(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider.py")
    result = collect_hardware_provider_evidence(provider, robot_id="demo_robot")
    assert result.robot_id == "demo_robot"
    assert result.components[0].kind == "motor_controller"
    assert result.components[0].model_extra == {
        "model": "STM32F4",
        "firmware_version": "1.2.3",
    }


def test_hardware_probe_merges_provider_evidence_on_non_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path / "provider.py")
    monkeypatch.setattr("rolo.stages.adapt.discovery.platform.system", lambda: "Windows")
    result = HardwareProbe().run(robot_id="demo_robot", provider_path=provider)
    component = next(item for item in result.data["components"] if item["name"] == "base_mcu")
    assert component["source"] == "hardware_provider"
    assert component["firmware_version"] == "1.2.3"
    assert component["resource_id"] == (
        "hardware_provider:wheeltec-readonly/v1:motor_controller:base_mcu"
    )
    assert result.data["hardware_provider"]["status"] == "SUCCEEDED"
    assert any(item["path"] == "/dev/ttyUSB0" for item in result.data["devices"])


def test_hardware_provider_rejects_robot_identity_mismatch(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider.py", robot_expression=json.dumps("other_robot"))
    with pytest.raises(ValueError, match="robot identity mismatch"):
        collect_hardware_provider_evidence(provider, robot_id="demo_robot")


def test_hardware_probe_records_provider_failure_as_degraded_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path / "provider.py", robot_expression=json.dumps("other_robot"))
    monkeypatch.setattr("rolo.stages.adapt.discovery.platform.system", lambda: "Windows")

    result = HardwareProbe().run(robot_id="demo_robot", provider_path=provider)

    assert result.status == "PARTIAL"
    assert result.data["hardware_provider"]["status"] == "FAILED"
    assert any("identity mismatch" in item for item in result.warnings)
