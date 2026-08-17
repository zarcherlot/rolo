import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.registry import RobotRegistry
from rolo.discovery import DiscoveryService
from rolo.stages.build.service import BuildStageService
from rolo.stages.pipeline import assess_pipeline


def discover_demo(artifact_root: Path, source_root: Path) -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"), source_roots=[source_root]
    )


def test_discovery_writes_deployment_handoff_and_build_plan(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)

    deploy_handoff = json.loads(
        (artifact_root / "deploy/demo_diff/latest/handoff.json").read_text(encoding="utf-8")
    )
    plan, plan_path = BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")

    assert deploy_handoff["stage"] == "deploy"
    assert deploy_handoff["agent_skill_required"] is False
    assert deploy_handoff["status"] in {"READY_FOR_BUILD", "DEGRADED"}
    assert plan_path.is_file()
    assert plan.stage == "build"
    assert plan.status == "REQUIRES_CODING"
    assert plan.required_skills == [
        "canonical-adapter-builder",
        "cli-conformance",
        "state-graph-builder",
    ]


def test_pipeline_exposes_four_ordered_stages(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)
    BuildStageService(ArtifactStore(artifact_root)).plan("demo_diff")

    pipeline = assess_pipeline(artifact_root, "demo_diff")

    assert [stage.stage for stage in pipeline.stages] == ["deploy", "build", "debug", "test"]
    assert pipeline.stages[0].status in {"COMPLETE", "DEGRADED"}
    assert pipeline.stages[1].coding_agent_required is True
    assert pipeline.stages[2].status == "BLOCKED"
    assert pipeline.stages[3].optional is True


def test_stage_cli_keeps_legacy_and_nested_deploy_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ROBOT_LOOP_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    runner = CliRunner()

    nested = runner.invoke(
        app,
        ["deploy", "discover", "run", "--robot", "demo_diff", "--source-root", str(tmp_path)],
    )
    legacy = runner.invoke(app, ["discover", "show", "--robot", "demo_diff"])
    plan = runner.invoke(app, ["build", "plan", "--robot", "demo_diff"])
    pipeline = runner.invoke(app, ["pipeline-status", "--robot", "demo_diff"])

    get_settings.cache_clear()
    assert nested.exit_code == 0, nested.output
    assert legacy.exit_code == 0, legacy.output
    assert plan.exit_code == 0, plan.output
    assert '"required_skills"' in plan.output
    assert pipeline.exit_code == 0, pipeline.output
    assert '"stage": "test"' in pipeline.output
