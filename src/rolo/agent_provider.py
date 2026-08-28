"""Provider-neutral Agent executor SPI.

Rolo does not require a particular coding-agent product.  An executor is a local
transport adapter (Codex, Claude Code, an enterprise gateway, or a user plugin),
while ``provider`` identifies the model endpoint selected by that executor.
Only the Codex adapter ships in-tree today; registering another adapter does not
change lifecycle, evidence, approval, or release code.
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


def register_agent_executor(name: str, factory: AgentExecutorFactory) -> None:
    key = name.strip().lower()
    if not key or any(char.isspace() for char in key):
        raise ValueError("agent executor name must be a non-empty token")
    if key in _EXECUTORS:
        raise ValueError(f"agent executor is already registered: {key}")
    _EXECUTORS[key] = factory


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


def _ensure_builtins() -> None:
    if "codex" not in _EXECUTORS:
        from rolo.stages.adapt.executor import CodexAdaptExecutor

        _EXECUTORS["codex"] = CodexAdaptExecutor
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
