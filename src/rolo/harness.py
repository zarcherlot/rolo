"""Model-harness adapters used by the interactive Rolo surface.

Rolo owns policy, evidence and authorization. A harness owns model transport and
streaming. Keeping this boundary small lets Codex and a future Claude Code
adapter share the same console and MCP integrations without granting either
model direct authority over target operations.
"""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

OutputCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class HarnessRequest:
    prompt: str
    workspace: Path
    timeout_s: int = 1800


class HarnessError(RuntimeError):
    """A model transport failure, never an authorization decision."""


class ModelHarness:
    """Minimal interface shared by Codex, Claude Code and future providers."""

    name = "unknown"

    def run(
        self,
        request: HarnessRequest,
        *,
        on_output: OutputCallback | None = None,
    ) -> tuple[str, str, int]:
        raise NotImplementedError


class CodexHarness(ModelHarness):
    """Invoke the installed Codex CLI with an isolated, read-only chat session."""

    name = "codex"

    def __init__(
        self,
        *,
        executable: str = "codex",
        model: str | None = None,
        provider: str = "codex",
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.executable = executable
        self.model = model
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key

    def _command(self) -> list[str]:
        command = [
            self.executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        if self.model:
            command.extend(["--model", self.model])
        # Provider/base URL are intentionally passed as Codex configuration,
        # never as prompt text or command-line secrets.
        if self.provider.strip().lower() != "codex" and not self.base_url:
            raise HarnessError("a non-default model provider requires a base URL")
        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HarnessError("model provider base URL must be an absolute HTTP(S) URL")
            provider_id = "rolo_configured"
            overrides = {
                "model_provider": provider_id,
                f"model_providers.{provider_id}.name": self.provider,
                f"model_providers.{provider_id}.base_url": self.base_url,
                f"model_providers.{provider_id}.wire_api": "responses",
            }
            if self.api_key:
                overrides[f"model_providers.{provider_id}.env_key"] = "CODEX_API_KEY"
            for key, value in overrides.items():
                escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
                command.extend(["-c", f'{key}="{escaped}"'])
        command.append("-")
        return command

    def run(
        self,
        request: HarnessRequest,
        *,
        on_output: OutputCallback | None = None,
    ) -> tuple[str, str, int]:
        if request.timeout_s < 1:
            raise ValueError("harness timeout must be at least one second")
        command = self._command()
        environment = os.environ.copy()
        if self.api_key:
            environment["CODEX_API_KEY"] = self.api_key
        # Never forward unrelated host credentials into the model process.
        for key in ("OPENAI_API_KEY", "CODING_AGENT_API_KEY"):
            if key != "CODEX_API_KEY":
                environment.pop(key, None)
        try:
            process = subprocess.Popen(
                command,
                cwd=request.workspace,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise HarnessError(f"could not start Codex: {exc}") from exc
        assert process.stdin and process.stdout and process.stderr
        process.stdin.write(request.prompt)
        process.stdin.close()
        streams: dict[str, list[str]] = {"stdout": [], "stderr": []}

        def drain(name: str, stream) -> None:
            for line in iter(stream.readline, ""):
                streams[name].append(line)
                if on_output is not None:
                    on_output(name, line.rstrip("\r\n")[:8_000])
            stream.close()

        workers = [
            threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
        ]
        for worker in workers:
            worker.start()
        try:
            process.wait(timeout=request.timeout_s)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            for worker in workers:
                worker.join(timeout=2)
            raise HarnessError(f"Codex exceeded the {request.timeout_s}-second timeout") from exc
        for worker in workers:
            worker.join(timeout=2)
        return "".join(streams["stdout"]), "".join(streams["stderr"]), process.returncode


def configured_harness(settings) -> ModelHarness:
    """Resolve the configured harness without coupling policy to a provider."""
    executor = str(settings.coding_agent_executor).strip().lower()
    if executor == "codex":
        return CodexHarness(
            executable=settings.coding_agent_executable,
            model=settings.coding_agent_model,
            provider=settings.coding_agent_provider,
            base_url=settings.coding_agent_base_url,
            api_key=settings.coding_agent_api_key,
        )
    raise HarnessError(f"unsupported model harness: {executor}")
