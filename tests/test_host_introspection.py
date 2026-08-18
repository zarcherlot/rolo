import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo import host_introspection
from rolo.cli import app


def test_host_inventory_exposes_bootstrap_control_planes() -> None:
    result = host_introspection.host_inventory()

    assert result["operation"] == "linux.host.inventory"
    assert result["status"] == "SUCCEEDED"
    assert result["data"]["host"]["system"]
    assert set(result["data"]["control_planes"]) == {
        "service_managers",
        "container_runtimes",
        "schedulers",
        "container_markers",
    }


def test_service_list_normalizes_linux_systemd_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda *args, **kwargs: {
            "status": "SUCCEEDED",
            "stdout": "robot.service loaded active running Robot controller\n",
        },
    )

    result = host_introspection.service_list()

    assert result["data"]["services"] == [
        {
            "name": "robot.service",
            "load": "loaded",
            "active": "active",
            "sub": "running",
            "description": "Robot controller",
        }
    ]


def test_cli_probe_rejects_operational_arguments(tmp_path: Path) -> None:
    executable = tmp_path / "robot-driver"
    executable.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported self-description"):
        host_introspection.cli_probe(executable, ["move", "--speed"])


def test_config_locate_searches_only_adjacent_bounded_locations(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    config_dir = binary_dir / "config"
    config_dir.mkdir(parents=True)
    binary = binary_dir / "controller"
    binary.write_text("", encoding="utf-8")
    config = config_dir / "controller.yaml"
    config.write_text("enabled: true\n", encoding="utf-8")

    result = host_introspection.config_locate(binary=binary)

    assert result["data"]["candidates"] == [
        {"path": str(config.resolve()), "source": "binary adjacency"}
    ]


def test_secret_assignment_redaction_preserves_key_but_not_value() -> None:
    redacted = host_introspection._redact(
        "--token=abc password: hunter2 --api-key third safe=value"
    )

    assert "abc" not in redacted
    assert "hunter2" not in redacted
    assert "third" not in redacted
    assert redacted == (
        "--token=<redacted> password: <redacted> --api-key <redacted> safe=value"
    )


def test_structured_redaction_hides_nested_secret_fields() -> None:
    value = {"Config": {"Env": ["SAFE=yes", "TOKEN=abc"], "ApiKey": "secret"}}

    assert host_introspection._redact_data(value) == {
        "Config": {"Env": ["SAFE=yes", "TOKEN=<redacted>"], "ApiKey": "<redacted>"}
    }


def test_cli_exposes_introspection_command_tree() -> None:
    runner = CliRunner()

    linux_help = runner.invoke(app, ["linux", "--help"])
    middleware = runner.invoke(app, ["middleware", "inspect"])
    binary = runner.invoke(app, ["linux", "binary", "describe", sys.executable])

    assert linux_help.exit_code == 0, linux_help.output
    for command in (
        "host",
        "service",
        "container",
        "schedule",
        "process",
        "binary",
        "cli",
        "config",
        "network",
    ):
        assert command in linux_help.output
    assert middleware.exit_code == 0, middleware.output
    assert json.loads(middleware.output)["operation"] == "middleware.inspect"
    assert binary.exit_code == 0, binary.output
    assert json.loads(binary.output)["operation"] == "linux.binary.describe"
