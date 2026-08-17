import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.models import utc_now
from rolo.core.registry import RobotRegistry
from rolo.discovery import DiscoveryService
from rolo.stages.build.models import (
    CodingAgentConfig,
    CodingAgentDependencyReport,
    CodingAgentRun,
)
from rolo.stages.build.service import BuildStageService
from rolo.stages.pipeline import assess_pipeline


def discover_demo(artifact_root: Path, source_root: Path) -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"), source_roots=[source_root]
    )


def test_discovery_writes_build_inputs_with_probes_and_build_plan(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)

    build_inputs = json.loads(
        (artifact_root / "build/demo_diff/latest/inputs.json").read_text(encoding="utf-8")
    )
    plan, plan_path = BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")

    assert build_inputs["stage"] == "build"
    assert build_inputs["agent_requirement"] == "coding_agent"
    assert build_inputs["status"] in {"READY_FOR_CODING", "DEGRADED"}
    assert set(build_inputs["probe_refs"]) == {"hw", "linux", "ros", "application"}
    assert plan_path.is_file()
    assert plan.stage == "build"
    assert plan.status == "REQUIRES_CODING"
    assert plan.coding_agent.provider == "codex"
    assert plan.coding_agent.model is None
    assert plan.coding_agent.api_key_configured is False
    assert plan.required_skills == [
        "canonical-adapter-builder",
        "cli-conformance",
        "state-graph-builder",
    ]


def test_pipeline_exposes_three_ordered_stages(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)
    BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")

    pipeline = assess_pipeline(artifact_root, "demo_diff")

    assert [stage.stage for stage in pipeline.stages] == ["build", "debug", "test"]
    assert pipeline.stages[0].agent_requirement == "coding_agent"
    assert pipeline.stages[1].agent_requirement == "diagnosis_agent"
    assert pipeline.stages[1].status == "BLOCKED"
    assert pipeline.stages[2].optional is True


def test_stage_cli_keeps_legacy_and_nested_build_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    runner = CliRunner()

    nested = runner.invoke(
        app,
        ["build", "discover", "run", "--robot", "demo_diff", "--source-root", str(tmp_path)],
    )
    legacy = runner.invoke(app, ["discover", "show", "--robot", "demo_diff"])
    plan = runner.invoke(app, ["build", "plan", "--robot", "demo_diff"])
    pipeline = runner.invoke(app, ["pipeline-status", "--robot", "demo_diff"])
    removed_deploy_stage = runner.invoke(app, ["deploy", "--help"])

    get_settings.cache_clear()
    assert nested.exit_code == 0, nested.output
    assert legacy.exit_code == 0, legacy.output
    assert plan.exit_code == 0, plan.output
    assert '"required_skills"' in plan.output
    assert pipeline.exit_code == 0, pipeline.output
    assert '"stage": "test"' in pipeline.output
    assert removed_deploy_stage.exit_code != 0


def test_build_plan_accepts_vendor_model_and_never_persists_api_key(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)
    config = CodingAgentConfig(
        provider="another-vendor",
        base_url="https://relay.example.com/v1",
        model="vendor-code-model",
        api_key_configured=True,
    )

    plan, plan_path = BuildStageService(
        ArtifactStore(artifact_root), coding_agent=config
    ).plan("demo_diff")
    persisted = plan_path.read_text(encoding="utf-8")
    persisted_config = json.loads(persisted)["coding_agent"]

    assert plan.coding_agent == config
    assert plan.coding_agent.api_key_env == "CODING_AGENT_API_KEY"
    assert set(persisted_config) == {
        "provider",
        "executor",
        "base_url",
        "model",
        "api_key_env",
        "api_key_configured",
        "auto_install",
        "require_auth",
    }


def test_build_agent_config_reads_environment_without_printing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "do-not-print-this-key"
    monkeypatch.setenv("CODING_AGENT_PROVIDER", "another-vendor")
    monkeypatch.setenv("CODING_AGENT_BASE_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("CODING_AGENT_API_KEY", secret)
    monkeypatch.setenv("CODING_AGENT_MODEL", "vendor-code-model")
    get_settings.cache_clear()

    result = CliRunner().invoke(app, ["build", "agent-config"])

    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {
        "provider": "another-vendor",
        "executor": "codex",
        "base_url": "https://relay.example.com/v1",
        "model": "vendor-code-model",
        "api_key_env": "CODING_AGENT_API_KEY",
        "api_key_configured": True,
        "auto_install": True,
        "require_auth": True,
    }
    assert secret not in result.output


def test_build_execute_prepares_dependency_before_starting_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    discover_demo(artifact_root, workspace)
    BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    calls: list[str] = []

    def fake_prepare(self: object, **kwargs: object) -> tuple[object, Path]:
        del self, kwargs
        calls.append("prepare")
        report = CodingAgentDependencyReport(
            executor="codex",
            provider="codex",
            status="READY",
            platform="Linux",
            architecture="aarch64",
            executable="/usr/local/bin/codex",
            version="codex-cli test",
            installed=True,
            authentication="AUTHENTICATED",
        )
        return report, artifact_root / "coding-agent/dependency/latest.json"

    def fake_execute(self: object, **kwargs: object) -> tuple[object, Path]:
        del self, kwargs
        assert calls == ["prepare"]
        calls.append("execute")
        now = utc_now()
        run = CodingAgentRun(
            run_id="run-test",
            robot_id="demo_diff",
            source_discovery_id="discovery-test",
            provider="codex",
            status="SUCCEEDED",
            workspace=str(workspace),
            command=["codex", "exec"],
            prompt_ref="artifact://prompt",
            event_log_ref="artifact://events",
            stderr_ref="artifact://stderr",
            final_message_ref="artifact://final",
            started_at=now,
            completed_at=now,
            duration_s=0,
        )
        return run, artifact_root / "run.json"

    monkeypatch.setattr(
        "rolo.cli.CodingAgentDependencyManager.prepare", fake_prepare
    )
    monkeypatch.setattr("rolo.cli.CodexBuildExecutor.execute", fake_execute)

    result = CliRunner().invoke(
        app,
        [
            "build",
            "execute",
            "--robot",
            "demo_diff",
            "--workspace",
            str(workspace),
        ],
    )

    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert calls == ["prepare", "execute"]
