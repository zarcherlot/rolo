import json
import subprocess
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.registry import RobotRegistry
from rolo.discovery import DiscoveryService
from rolo.stages.build.executor import CodexBuildExecutor, build_codex_command
from rolo.stages.build.models import CodingAgentConfig, CodingAgentResult
from rolo.stages.build.service import BuildStageService


def prepare_plan(artifact_root: Path, source_root: Path) -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"), source_roots=[source_root]
    )
    BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")


def test_codex_executor_reuses_login_without_api_key_and_writes_audit_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_plan(artifact_root, workspace)
    captured: dict[str, object] = {}

    monkeypatch.setattr("rolo.stages.build.executor.shutil.which", lambda _: "codex")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            CodingAgentResult(
                schema_version="robot-coding-agent-result/v1",
                summary="Implemented the Stage 1 adapters",
                completed_tasks=["canonical-adapters"],
                changed_files=["src/adapter.py"],
                validation=["pytest passed"],
                blockers=[],
                handoff_ready=False,
            ).model_dump_json(),
            encoding="utf-8",
        )
        events = (
            '{"type":"thread.started","thread_id":"thread-test"}\n'
            '{"type":"turn.completed"}\n'
        )
        return subprocess.CompletedProcess(command, 0, stdout=events, stderr="")

    monkeypatch.setattr("rolo.stages.build.executor.subprocess.run", fake_run)
    run, run_path = CodexBuildExecutor(ArtifactStore(artifact_root)).execute(
        robot_id="demo_diff", workspace=workspace, timeout_s=30
    )

    assert run.status == "SUCCEEDED"
    assert run.thread_id == "thread-test"
    assert run.event_count == 2
    assert run.result_ref is not None
    assert run_path.is_file()
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:2] == ["codex", "exec"]
    assert "workspace-write" in command
    assert "--ephemeral" in command
    assert command[-1] == "-"
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert "CODEX_API_KEY" not in environment


def test_codex_executor_passes_key_only_in_child_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "never-write-this-secret"
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_plan(artifact_root, workspace)
    captured: dict[str, object] = {}
    monkeypatch.setattr("rolo.stages.build.executor.shutil.which", lambda _: "codex")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["environment"] = kwargs["env"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            CodingAgentResult(
                schema_version="robot-coding-agent-result/v1",
                summary="done",
                completed_tasks=[],
                changed_files=[],
                validation=[],
                blockers=[],
                handoff_ready=False,
            ).model_dump_json(),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("rolo.stages.build.executor.subprocess.run", fake_run)
    run, _ = CodexBuildExecutor(
        ArtifactStore(artifact_root), api_key=secret
    ).execute(robot_id="demo_diff", workspace=workspace, timeout_s=30)

    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["CODEX_API_KEY"] == secret
    assert secret not in json.dumps(run.model_dump(mode="json"))
    for path in artifact_root.rglob("*"):
        if path.is_file():
            assert secret not in path.read_text(encoding="utf-8", errors="ignore")


def test_custom_provider_is_configured_through_codex_without_key_in_argv(
    tmp_path: Path,
) -> None:
    command = build_codex_command(
        executable="codex",
        workspace=tmp_path,
        schema_path=tmp_path / "schema.json",
        final_message_path=tmp_path / "result.json",
        config=CodingAgentConfig(
            provider="another-vendor",
            base_url="https://relay.example.com/v1",
            model="vendor-code-model",
            api_key_configured=True,
        ),
        api_key_configured=True,
    )

    joined = " ".join(command)
    assert '--model vendor-code-model' in joined
    assert 'model_provider="rolo_configured"' in joined
    assert 'model_providers.rolo_configured.base_url="https://relay.example.com/v1"' in joined
    assert 'model_providers.rolo_configured.env_key="CODEX_API_KEY"' in joined
    assert "shell_environment_policy.ignore_default_excludes=false" in command
    assert "CODING_AGENT_API_KEY" not in joined


def test_non_default_provider_requires_base_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires CODING_AGENT_BASE_URL"):
        build_codex_command(
            executable="codex",
            workspace=tmp_path,
            schema_path=tmp_path / "schema.json",
            final_message_path=tmp_path / "result.json",
            config=CodingAgentConfig(provider="another-vendor"),
            api_key_configured=False,
        )
