from pathlib import Path

import pytest

from rolo.core.config import Settings
from rolo.runtime import create_robot_use_runtime, create_runtime


def test_zero_configuration_defaults_are_private_and_unenrolled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROLO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("ROLO_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("ROLO_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("WIKI_INSIGHTS_AGENT_ENABLED", raising=False)
    settings = Settings(_env_file=None)

    assert settings.rolo_config_dir == Path(".rolo/config")
    assert settings.rolo_artifact_dir == Path(".rolo/artifacts")
    assert not settings.rolo_output_dir.resolve().is_relative_to(Path.cwd().resolve())
    assert settings.wiki_insights_agent_enabled is True


def test_base_runtime_does_not_require_optional_robot_use_backend() -> None:
    settings = Settings(
        _env_file=None,
        rolo_config_dir=Path("tests/fixtures"),
        robot_use_backend="unsupported",
    )

    runtime = create_runtime(settings)

    assert len(runtime.registry) == 2
    with pytest.raises(ValueError, match="Unsupported ROBOT_USE_BACKEND"):
        create_robot_use_runtime(settings)
