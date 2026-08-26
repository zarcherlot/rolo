from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from rolo.targets.models import DeploymentCommand, DeploymentCommandKind


class CanonicalCommandParameters(Protocol):
    def canonical_sha256(self) -> str: ...


@dataclass(frozen=True)
class CommandEnvelope:
    command: DeploymentCommand
    parameters: CanonicalCommandParameters | None = None

    def validate(self) -> None:
        expected = self.command.parameters_sha256
        if self.parameters is None:
            if expected is not None:
                raise ValueError("command parameters are missing")
            return
        if expected is None:
            raise ValueError("command does not bind supplied parameters")
        if self.parameters.canonical_sha256() != expected:
            raise ValueError("command parameter digest mismatch")


@dataclass(frozen=True)
class CommandExecution:
    command: DeploymentCommand
    command_sha256: str
    canonical_cli: str
    result: Any


CommandHandler = Callable[[CommandEnvelope], Any]
CommandRenderer = Callable[[CommandEnvelope], list[str]]


def _base_cli_argv(command: DeploymentCommand) -> list[str]:
    if command.command == DeploymentCommandKind.ADAPT:
        argv = [
            "robotctl",
            "adapt",
            "start",
            "--robot-id",
            command.target_id,
            "--project-root",
            command.workspace_root or "",
            "--active-probe",
            command.active_probe,
        ]
        if not command.run_adapter_agent:
            argv.append("--discover-only")
        return argv
    return [
        "robotctl",
        "deployment",
        command.command.value.casefold().replace("_", "-"),
        "--target",
        command.target_id,
    ]


class ApplicationCommandBus:
    def __init__(self) -> None:
        self._handlers: dict[DeploymentCommandKind, CommandHandler] = {}
        self._renderers: dict[DeploymentCommandKind, CommandRenderer] = {}

    def register(
        self,
        command: DeploymentCommandKind,
        handler: CommandHandler,
        *,
        renderer: CommandRenderer | None = None,
    ) -> None:
        if command in self._handlers:
            raise ValueError(f"command handler already registered: {command.value}")
        self._handlers[command] = handler
        if renderer is not None:
            self._renderers[command] = renderer

    def canonical_cli_argv(self, envelope: CommandEnvelope) -> list[str]:
        envelope.validate()
        renderer = self._renderers.get(envelope.command.command)
        return renderer(envelope) if renderer is not None else _base_cli_argv(envelope.command)

    def canonical_cli(self, envelope: CommandEnvelope) -> str:
        return shlex.join(self.canonical_cli_argv(envelope))

    def dispatch(self, envelope: CommandEnvelope) -> CommandExecution:
        envelope.validate()
        try:
            handler = self._handlers[envelope.command.command]
        except KeyError as exc:
            raise ValueError(
                f"no command handler registered: {envelope.command.command.value}"
            ) from exc
        return CommandExecution(
            command=envelope.command,
            command_sha256=envelope.command.canonical_sha256(),
            canonical_cli=self.canonical_cli(envelope),
            result=handler(envelope),
        )
