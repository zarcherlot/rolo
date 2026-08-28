from __future__ import annotations

import pytest

from rolo.agent_provider import (
    available_agent_executors,
    create_agent_executor,
    create_stage_agent_executor,
    register_agent_executor,
)
from rolo.core.config import Settings
from rolo.stages.adapt.models import AdapterAgentConfig


def test_codex_is_a_registered_builtin_executor() -> None:
    assert "codex" in available_agent_executors()
    executor = create_agent_executor(" CODEX ", artifacts=object())
    assert executor.__class__.__name__ == "CodexAdaptExecutor"


def test_external_executor_can_register_without_changing_lifecycle() -> None:
    class FakeExecutor:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def execute(self, **kwargs: object) -> tuple[object, object]:
            return kwargs, object()

    name = "test.external"
    register_agent_executor(name, FakeExecutor, dependency_adapter=object())
    instance = create_agent_executor(name, marker=True)
    assert isinstance(instance, FakeExecutor)
    assert instance.kwargs == {"marker": True}


def test_stage_executor_factory_requires_downstream_spi() -> None:
    class StageExecutor:
        def execute(self, **kwargs: object) -> tuple[object, object]:
            return kwargs, object()

        def execute_stage(self, task: object, *, workspace: object, on_output=None):
            del task, workspace, on_output
            return {}

    name = "stage-test"
    register_agent_executor(name, StageExecutor)
    assert isinstance(create_stage_agent_executor(name), StageExecutor)

    with pytest.raises(ValueError, match="downstream Stage Agent SPI"):
        create_stage_agent_executor("codex", artifacts=object())


def test_agent_config_separates_provider_from_executor_and_validates_key_env() -> None:
    config = AdapterAgentConfig(
        provider="anthropic",
        executor="claude-code",
        base_url="https://gateway.example/v1",
        model="claude-sonnet",
        api_key_env="ANTHROPIC_API_KEY",
    )
    assert config.provider == "anthropic"
    assert config.executor == "claude-code"
    assert config.api_key_env == "ANTHROPIC_API_KEY"
    with pytest.raises(ValueError):
        AdapterAgentConfig(api_key_env="not-a-valid-env-name")


def test_api_key_can_be_resolved_from_the_selected_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-secret")
    settings = Settings(
        _env_file=None,
        coding_agent_api_key=None,
        coding_agent_api_key_env="ANTHROPIC_API_KEY",
    )
    assert settings.resolved_coding_agent_api_key == "test-secret"
