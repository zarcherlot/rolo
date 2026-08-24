from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from rolo.cli import app

runner = CliRunner()


def test_config_init_writes_editable_v1_without_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"

    first = runner.invoke(app, ["config", "init", "--output", str(destination)])
    second = runner.invoke(app, ["config", "init", "--output", str(destination)])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 2
    payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "rolo-config/v1"
    assert payload["ros"]["auto_source"] is True


def test_config_validate_prepares_external_directories(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROLO_SETTINGS_FILE", str(tmp_path / "missing.yaml"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("ROLO_SCRATCH_DIR", str(tmp_path / "scratch"))

    result = runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0, result.output
    for name in ("state", "artifacts", "output", "scratch"):
        assert (tmp_path / name).is_dir()
