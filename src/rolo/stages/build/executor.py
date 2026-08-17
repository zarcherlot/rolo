from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import utc_now
from rolo.stages.build.discovery import load_latest_report
from rolo.stages.build.enrollment import ROBOT_ID_PATTERN
from rolo.stages.build.models import (
    BuildPlan,
    BuildPlanStatus,
    CodingAgentConfig,
    CodingAgentResult,
    CodingAgentRun,
    CodingAgentRunStatus,
)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _decode_process_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def build_codex_command(
    *,
    executable: str,
    workspace: Path,
    schema_path: Path,
    final_message_path: Path,
    config: CodingAgentConfig,
    api_key_configured: bool,
) -> list[str]:
    """Build an argv-only Codex command; credentials are never command arguments."""
    command = [
        executable,
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_message_path),
        "-c",
        "shell_environment_policy.ignore_default_excludes=false",
    ]
    if config.model:
        command.extend(["--model", config.model])

    provider = config.provider.strip().lower()
    if provider != "codex" and not config.base_url:
        raise ValueError(
            "The Codex executor requires CODING_AGENT_BASE_URL for a non-default provider"
        )
    if config.base_url:
        parsed = urlparse(config.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("CODING_AGENT_BASE_URL must be an absolute HTTP(S) URL")
        provider_id = "rolo_configured"
        overrides = {
            "model_provider": provider_id,
            f"model_providers.{provider_id}.name": config.provider,
            f"model_providers.{provider_id}.base_url": config.base_url,
            f"model_providers.{provider_id}.wire_api": "responses",
        }
        if api_key_configured:
            overrides[f"model_providers.{provider_id}.env_key"] = "CODEX_API_KEY"
        for key, value in overrides.items():
            command.extend(["-c", f"{key}={_toml_string(value)}"])

    command.append("-")
    return command


class CodexBuildExecutor:
    """Run one explicit Stage 1 plan through the non-interactive Codex CLI."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        *,
        executable: str = "codex",
        api_key: str | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.executable = executable
        self.api_key = api_key

    def execute(
        self,
        *,
        robot_id: str,
        workspace: Path,
        timeout_s: int = 1800,
    ) -> tuple[CodingAgentRun, Path]:
        if not ROBOT_ID_PATTERN.fullmatch(robot_id):
            raise ValueError(
                "robot_id must match ^[a-z][a-z0-9_-]{2,63}$ before artifacts are resolved"
            )
        workspace = workspace.resolve()
        if not workspace.is_dir():
            raise ValueError(f"Coding Agent workspace is not a directory: {workspace}")
        if timeout_s < 1:
            raise ValueError("Coding Agent timeout must be at least one second")
        if shutil.which(self.executable) is None:
            raise FileNotFoundError(
                f"Codex CLI executable not found: {self.executable}; install it and run codex login"
            )

        plan_path = self.artifacts.root / "build" / robot_id / "latest" / "plan.json"
        if not plan_path.is_file():
            raise FileNotFoundError(f"No build plan for {robot_id}; run build plan first")
        plan = BuildPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        if plan.status == BuildPlanStatus.BLOCKED:
            raise ValueError(f"Build plan for {robot_id} is blocked by discovery failures")

        started_at = utc_now()
        run_id = f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        relative_run_root = f"build/{robot_id}/coding-agent-runs/{run_id}"
        run_root = self.artifacts.root / relative_run_root
        run_root.mkdir(parents=True, exist_ok=False)
        prompt_path = run_root / "prompt.txt"
        schema_path = run_root / "result.schema.json"
        event_log_path = run_root / "events.jsonl"
        stderr_path = run_root / "stderr.log"
        final_message_path = run_root / "final-message.json"
        result_path = run_root / "result.json"

        prompt = self._build_prompt(plan)
        prompt_path.write_text(prompt, encoding="utf-8")
        schema_path.write_text(
            json.dumps(CodingAgentResult.model_json_schema(), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        command = build_codex_command(
            executable=self.executable,
            workspace=workspace,
            schema_path=schema_path,
            final_message_path=final_message_path,
            config=plan.coding_agent,
            api_key_configured=bool(self.api_key),
        )
        environment = self._child_environment()

        stdout = ""
        stderr = ""
        exit_code: int | None = None
        status = CodingAgentRunStatus.FAILED
        error: str | None = None
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                check=False,
                cwd=workspace,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            if completed.returncode != 0:
                error = f"Codex exited with code {completed.returncode}"
            elif not final_message_path.is_file():
                error = "Codex did not write the required structured final message"
            else:
                try:
                    result = CodingAgentResult.model_validate_json(
                        final_message_path.read_text(encoding="utf-8")
                    )
                except ValueError as exc:
                    error = f"Codex final message failed schema validation: {exc}"
                else:
                    self.artifacts.write_json(
                        f"{relative_run_root}/result.json", result.model_dump(mode="json")
                    )
                    status = CodingAgentRunStatus.SUCCEEDED
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_process_output(exc.stdout)
            stderr = _decode_process_output(exc.stderr)
            status = CodingAgentRunStatus.TIMED_OUT
            error = f"Codex exceeded the {timeout_s}-second timeout"
        except OSError as exc:
            error = f"Could not start Codex: {exc}"

        event_log_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        thread_id, event_count = self._inspect_events(stdout)
        completed_at = utc_now()
        run = CodingAgentRun(
            run_id=run_id,
            robot_id=robot_id,
            source_discovery_id=plan.source_discovery_id,
            provider=plan.coding_agent.provider,
            model=plan.coding_agent.model,
            status=status,
            workspace=str(workspace),
            command=command,
            prompt_ref=f"artifact://{relative_run_root}/prompt.txt",
            event_log_ref=f"artifact://{relative_run_root}/events.jsonl",
            stderr_ref=f"artifact://{relative_run_root}/stderr.log",
            final_message_ref=f"artifact://{relative_run_root}/final-message.json",
            result_ref=(
                f"artifact://{relative_run_root}/result.json"
                if result_path.is_file()
                else None
            ),
            thread_id=thread_id,
            event_count=event_count,
            exit_code=exit_code,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
            duration_s=(completed_at - started_at).total_seconds(),
        )
        run_path = self.artifacts.write_json(
            f"{relative_run_root}/run.json", run.model_dump(mode="json")
        )
        self.artifacts.write_json(
            f"build/{robot_id}/coding-agent-runs/latest.json", run.model_dump(mode="json")
        )
        return run, run_path

    def _child_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        # Only the deliberately configured secret may reach the Codex process. The
        # shell environment policy above keeps KEY/SECRET/TOKEN values out of tools
        # launched by the model.
        for name in ("CODING_AGENT_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"):
            environment.pop(name, None)
        if self.api_key:
            environment["CODEX_API_KEY"] = self.api_key
        return environment

    def _build_prompt(self, plan: BuildPlan) -> str:
        report = load_latest_report(self.artifacts.root, plan.robot_id)
        context: dict[str, Any] = {
            "platform": report.platform,
            "capability_manifest": report.capability_manifest,
            "semantic_bindings": report.semantic_bindings,
            "tool_catalog": [tool.model_dump(mode="json") for tool in report.tool_catalog],
        }
        return (
            "You are the Stage 1 Coding Agent for rolo. Work only inside the supplied "
            "workspace and implement the approved plan below. Preserve unrelated user changes. "
            "Inspect the repository before editing, complete the plan tasks in order, and run "
            "targeted validation. Never weaken safety gates or expose credentials. Do not create "
            "or publish build/<robot>/latest/handoff.json; a separate conformance gate owns that "
            "promotion. Return only the JSON object required by the supplied output schema.\n\n"
            f"BUILD PLAN:\n{plan.model_dump_json(indent=2)}\n\n"
            f"DISCOVERY CONTEXT:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        )

    @staticmethod
    def _inspect_events(stdout: str) -> tuple[str | None, int]:
        thread_id: str | None = None
        event_count = 0
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_count += 1
            if event.get("type") == "thread.started" and isinstance(
                event.get("thread_id"), str
            ):
                thread_id = event["thread_id"]
        return thread_id, event_count
