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
    settings = Settings(_env_file=None)

    assert settings.rolo_config_dir == Path(".rolo/config")
    assert settings.rolo_artifact_dir == Path(".rolo/artifacts")
    assert not settings.rolo_output_dir.resolve().is_relative_to(Path.cwd().resolve())


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


def test_slice_activation_defaults_off_and_accepts_explicit_canary_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ADAPT_OPERATION_SLICE_MODE",
        "ADAPT_OPERATION_SLICE_ROBOT_IDS",
        "ADAPT_OPERATION_SLICE_RUN_IDS",
        "ADAPT_OPERATION_SLICE_MAX_OPERATIONS",
    ):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    canary = Settings(
        _env_file=None,
        adapt_operation_slice_mode="canary",
        adapt_operation_slice_robot_ids="robot-b,robot-a",
        adapt_operation_slice_run_ids="run-1",
        adapt_operation_slice_max_operations=12,
    )

    assert defaults.adapt_operation_slice_mode == "shadow"
    assert defaults.adapt_operation_slice_robot_ids == ""
    assert defaults.adapt_operation_slice_run_ids == ""
    assert defaults.adapt_operation_slice_max_operations == 20
    assert canary.adapt_operation_slice_mode == "canary"
    assert canary.adapt_operation_slice_max_operations == 12
