from pathlib import Path

import pytest

from rolo.core.config import Settings
from rolo.runtime import create_robot_use_runtime, create_runtime


def test_zero_configuration_defaults_are_private_and_unenrolled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ROLO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("ROLO_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("ROLO_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("WIKI_INSIGHTS_AGENT_ENABLED", raising=False)
    monkeypatch.delenv("ADAPT_HEURISTIC_AGENT_MODE", raising=False)
    monkeypatch.setenv("ROLO_SETTINGS_FILE", str(tmp_path / "missing.yaml"))
    settings = Settings(_env_file=None)

    assert not settings.rolo_config_dir.resolve().is_relative_to(Path.cwd().resolve())
    assert not settings.rolo_artifact_dir.resolve().is_relative_to(Path.cwd().resolve())
    assert not settings.rolo_output_dir.resolve().is_relative_to(Path.cwd().resolve())
    assert settings.rolo_scratch_dir is None
    assert settings.wiki_insights_agent_enabled is True
    assert settings.adapt_heuristic_agent_mode == "shadow"
    assert settings.adapt_heuristic_agent_provider_enabled is True
    assert settings.rolo_adapter_max_address_space_bytes == 4 * 1024 * 1024 * 1024
    assert settings.rolo_adapter_max_processes == 128
    assert settings.coding_agent_timeout_s is None


def test_user_yaml_is_loaded_below_environment_precedence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings_file = tmp_path / "config.yaml"
    settings_file.write_text(
        """schema_version: rolo-config/v1
storage:
  artifact_dir: /configured/artifacts
  output_dir: /configured/output
  scratch_dir: /configured/scratch
agent:
  executable: configured-codex
  timeout_s: 900
ros:
  auto_source: false
  setup_files:
    - /opt/ros/humble/setup.bash
  domain_id: '7'
  rmw_implementation: rmw_cyclonedds_cpp
adapter_runtime:
  max_address_space_bytes: 2147483648
  max_processes: 64
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROLO_SETTINGS_FILE", str(settings_file))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "environment-output"))

    settings = Settings(_env_file=None)

    assert settings.rolo_artifact_dir == Path("/configured/artifacts")
    assert settings.rolo_output_dir == tmp_path / "environment-output"
    assert settings.coding_agent_executable == "configured-codex"
    assert settings.coding_agent_timeout_s == 900
    assert settings.ros_auto_source is False
    assert settings.ros_setup_files == [Path("/opt/ros/humble/setup.bash")]
    assert settings.ros_domain_id == "7"
    assert settings.rolo_adapter_max_address_space_bytes == 2 * 1024 * 1024 * 1024
    assert settings.rolo_adapter_max_processes == 64


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
