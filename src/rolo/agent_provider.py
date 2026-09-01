"""Provider-neutral Agent executor SPI.

Rolo does not require a particular coding-agent product.  An executor is a local
transport adapter (Codex, Claude Code, an enterprise gateway, or a user plugin),
while ``provider`` identifies the model endpoint selected by that executor.
Codex Adapt and downstream adapters ship in-tree today; registering another
provider/product does not change lifecycle, evidence, approval, or release code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class AgentExecutor(Protocol):
    """Common execution contract consumed by Adapt."""

    def execute(self, **kwargs: Any) -> tuple[Any, Any]: ...


AgentExecutorFactory = Callable[..., AgentExecutor]
_EXECUTORS: dict[str, AgentExecutorFactory] = {}
_DEPENDENCY_ADAPTERS: dict[str, Any] = {}


def register_agent_executor(
    name: str,
    factory: AgentExecutorFactory,
    *,
    dependency_adapter: Any | None = None,
) -> None:
    key = name.strip().lower()
    if not key or any(char.isspace() for char in key):
        raise ValueError("agent executor name must be a non-empty token")
    if key in _EXECUTORS:
        raise ValueError(f"agent executor is already registered: {key}")
    _EXECUTORS[key] = factory
    if dependency_adapter is not None:
        _DEPENDENCY_ADAPTERS[key] = dependency_adapter


def available_agent_executors() -> tuple[str, ...]:
    _ensure_builtins()
    return tuple(sorted(_EXECUTORS))


def create_agent_executor(name: str, **kwargs: Any) -> AgentExecutor:
    _ensure_builtins()
    key = name.strip().lower()
    factory = _EXECUTORS.get(key)
    if factory is None:
        supported = ", ".join(available_agent_executors()) or "none"
        raise ValueError(f"unsupported agent executor {name!r}; registered executors: {supported}")
    return factory(**kwargs)


def create_stage_agent_executor(name: str, **kwargs: Any) -> Any:
    """Create an executor implementing the Diagnose/Verify stage SPI."""
    key = name.strip().lower()
    if key == "codex" and {"artifacts", "settings", "stage"} <= set(kwargs):
        from rolo.stages.codex_downstream import CodexStageAgentExecutor

        return CodexStageAgentExecutor(
            artifacts=kwargs["artifacts"], settings=kwargs["settings"], stage=kwargs["stage"]
        )
    if key == "fake" and {"artifacts", "settings", "stage"} <= set(kwargs):
        from rolo.stages.fake_downstream import FakeStageAgentExecutor

        return FakeStageAgentExecutor(
            artifacts=kwargs["artifacts"], settings=kwargs["settings"], stage=kwargs["stage"]
        )
    if key in {"local-target", "ssh-target"} and {"artifacts", "settings", "stage"} <= set(kwargs):
        from rolo.stages.real_target import LocalTargetStageExecutor

        return LocalTargetStageExecutor(
            artifacts=kwargs["artifacts"], settings=kwargs["settings"], stage=kwargs["stage"]
        )
    try:
        executor = create_agent_executor(name, **kwargs)
    except TypeError as exc:
        raise ValueError(
            f"agent executor {name!r} does not implement the downstream Stage Agent SPI"
        ) from exc
    if not callable(getattr(executor, "execute_stage", None)):
        raise ValueError(
            f"agent executor {name!r} does not implement the downstream Stage Agent SPI"
        )
    declared_stage = getattr(executor, "stage", None)
    if declared_stage is not None and declared_stage != kwargs["stage"]:
        raise ValueError(
            f"agent executor {name!r} is bound to stage {declared_stage!r}, "
            f"not {kwargs['stage']!r}"
        )
    return executor


def dependency_adapter_for(name: str) -> Any | None:
    """Return an optional plugin-owned install/auth adapter for an executor."""
    _ensure_builtins()
    return _DEPENDENCY_ADAPTERS.get(name.strip().lower())


def _ensure_builtins() -> None:
    if "codex" not in _EXECUTORS:
        from rolo.stages.adapt.dependencies import CodexDependencyAdapter
        from rolo.stages.adapt.executor import CodexAdaptExecutor

        _EXECUTORS["codex"] = CodexAdaptExecutor
        _DEPENDENCY_ADAPTERS["codex"] = CodexDependencyAdapter()
    # Open-source installations can add providers without changing Rolo.  A
    # broken optional plugin is ignored here and reported only when selected.
    from rolo.stages.plugin_manifest import discover_entrypoint_plugins

    for manifest, item in discover_entrypoint_plugins():
        if not manifest.executor_entrypoint:
            continue
        key = item.name.strip().lower()
        if key and key not in _EXECUTORS:
            try:
                factory = item.load()
            except Exception:
                continue
            if callable(factory):
                _EXECUTORS[key] = factory
