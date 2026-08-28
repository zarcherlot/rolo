"""Provider-neutral Agent executor SPI.

Rolo does not require a particular coding-agent product.  An executor is a local
transport adapter (Codex, Claude Code, an enterprise gateway, or a user plugin),
while ``provider`` identifies the model endpoint selected by that executor.
Codex Adapt and downstream adapters ship in-tree today; registering another
provider/product does not change lifecycle, evidence, approval, or release code.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
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
    if name.strip().lower() == "codex" and {"artifacts", "settings", "stage"} <= set(kwargs):
        from rolo.stages.codex_downstream import CodexStageAgentExecutor

        return CodexStageAgentExecutor(
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
    try:
        discovered = entry_points(group="rolo.agent_executors")
    except TypeError:  # pragma: no cover - Python 3.10 compatibility
        discovered = entry_points().select(group="rolo.agent_executors")
    for item in discovered:
        key = item.name.strip().lower()
        if key and key not in _EXECUTORS:
            try:
                factory = item.load()
            except Exception:
                continue
            if callable(factory):
                _EXECUTORS[key] = factory
