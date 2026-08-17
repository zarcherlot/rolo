from pathlib import Path

import pytest

from rolo.core.config import Settings


def test_zero_configuration_defaults_are_private_and_unenrolled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROLO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("ROLO_ARTIFACT_DIR", raising=False)
    settings = Settings(_env_file=None)

    assert settings.rolo_config_dir == Path(".rolo/config")
    assert settings.rolo_artifact_dir == Path(".rolo/artifacts")
