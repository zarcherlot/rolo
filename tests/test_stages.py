import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.models import utc_now
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.discovery import DiscoveryService, load_report
from rolo.stages.adapt.models import (
    AdapterAgentConfig,
    AdapterAgentDependencyReport,
    AdapterAgentResult,
    AdapterAgentRun,
)
from rolo.stages.adapt.service import AdaptStageService
from rolo.stages.pipeline import assess_pipeline


def discover_demo(artifact_root: Path, source_root: Path) -> str:
    (source_root / "pyproject.toml").write_text(
        '[project]\nname = "stage-demo"\n\n[project.scripts]\nstage-demo = "demo:main"\n',
        encoding="utf-8",
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        source_roots=[source_root],
    )
    return report.discovery_id


def test_discovery_writes_adapt_inputs_and_derives_runtime_plan(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)

    build_inputs = json.loads(
        (artifact_root / "adapt/demo_diff/latest/inputs.json").read_text(encoding="utf-8")
    )
    plan = AdaptStageService(ArtifactStore(artifact_root)).derive_plan("demo_diff")

    assert build_inputs["stage"] == "adapt"
    assert build_inputs["agent_requirement"] == "adapter_agent"
    assert build_inputs["status"] in {"READY_FOR_CODING", "DEGRADED"}
    assert set(build_inputs["probe_refs"]) == {"hw", "linux", "ros", "application"}
    assert build_inputs["semantic_context_ref"].endswith("/semantic_context.json")
    assert not (artifact_root / "adapt/demo_diff/latest/plan.json").exists()
    assert plan.stage == "adapt"
    assert plan.status == "REQUIRES_CODING"
    assert plan.adapter_agent.provider == "codex"
    assert plan.adapter_agent.model is None
    assert plan.adapter_agent.api_key_configured is False
    assert plan.semantic_context_ref == build_inputs["semantic_context_ref"]
    assert plan.robot_wiki_ref.endswith("/robot_wiki.md")
    assert plan.required_skills == [
        "canonical-adapter-builder",
        "cli-conformance",
        "state-graph-builder",
    ]
    assert (artifact_root / "diagnose/demo_diff/latest/inputs.json").is_file()
    assert (artifact_root / "verify/demo_diff/latest/inputs.json").is_file()


def test_pipeline_exposes_three_ordered_stages(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)
    AdaptStageService(ArtifactStore(artifact_root)).derive_plan("demo_diff")

    pipeline = assess_pipeline(artifact_root, "demo_diff")

    assert [stage.stage for stage in pipeline.stages] == ["adapt", "diagnose", "verify"]
    assert pipeline.stages[0].agent_requirement == "adapter_agent"
    assert pipeline.stages[1].agent_requirement == "diagnosis_agent"
    assert pipeline.stages[1].status == "BLOCKED"
    assert "agent_inputs" in pipeline.stages[1].artifacts
    assert pipeline.stages[2].optional is True
    assert "agent_inputs" in pipeline.stages[2].artifacts


def test_adapt_plan_rejects_machine_evidence_after_manifest_changes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discovery_id = discover_demo(artifact_root, tmp_path)
    report_path = (
        artifact_root
        / "discovery/demo_diff/runs"
        / discovery_id
        / "active_discovery_report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["warnings"].append("machine evidence changed after publication")
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest hash mismatch"):
        AdaptStageService(ArtifactStore(artifact_root)).derive_plan("demo_diff")


def test_stage_cli_exposes_only_canonical_lifecycle_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "cli-demo"\n', encoding="utf-8"
    )
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    runner = CliRunner()

    nested = runner.invoke(
        app,
        [
            "adapt",
            "discover",
            "run",
            "--robot",
            "demo_diff",
            "--urdf",
            str(Path("tests/fixtures/profiles/differential_drive.urdf").resolve()),
            "--source-root",
            str(tmp_path),
        ],
    )
    removed_legacy = runner.invoke(app, ["discover", "show", "--robot", "demo_diff"])
    review = runner.invoke(app, ["adapt", "discover", "review", "--robot", "demo_diff"])
    removed_confirm = runner.invoke(app, ["adapt", "discover", "confirm", "--help"])
    plan = runner.invoke(app, ["adapt", "run", "--robot", "demo_diff", "--dry-run"])
    pipeline = runner.invoke(app, ["pipeline-status", "--robot", "demo_diff"])
    enrollment = runner.invoke(app, ["adapt", "enroll", "show"])
    removed_deploy_stage = runner.invoke(app, ["deploy", "--help"])
    removed_robots = runner.invoke(app, ["robots"])
    removed_profiles = runner.invoke(app, ["adapt", "enroll", "profiles"])
    removed_steps = [
        runner.invoke(app, ["adapt", name, "--help"])
        for name in ("plan", "agent-prepare", "execute", "promote")
    ]

    get_settings.cache_clear()
    assert nested.exit_code == 0, nested.output
    assert removed_legacy.exit_code != 0
    assert review.exit_code == 0, review.output
    assert "# 机器人 Wiki：demo_diff" in review.output
    assert removed_confirm.exit_code != 0
    assert plan.exit_code == 0, plan.output
    assert '"required_skills"' in plan.output
    assert pipeline.exit_code == 0, pipeline.output
    assert '"stage": "verify"' in pipeline.output
    assert enrollment.exit_code == 0, enrollment.output
    assert '"robot_id": "demo_diff"' in enrollment.output
    assert removed_deploy_stage.exit_code != 0
    assert removed_robots.exit_code != 0
    assert removed_profiles.exit_code != 0
    assert all(result.exit_code != 0 for result in removed_steps)


def test_cli_exposes_only_current_stage_names() -> None:
    runner = CliRunner()
    for name in ("adapt", "diagnose", "verify"):
        result = runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0, result.output
    for name in ("build", "debug", "test"):
        assert runner.invoke(app, [name, "--help"]).exit_code != 0


def test_runtime_plan_accepts_vendor_model_and_never_persists_api_key(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    discover_demo(artifact_root, tmp_path)
    config = AdapterAgentConfig(
        provider="another-vendor",
        base_url="https://relay.example.com/v1",
        model="vendor-code-model",
        api_key_configured=True,
    )

    plan = AdaptStageService(
        ArtifactStore(artifact_root), coding_agent=config
    ).derive_plan("demo_diff")
    persisted_config = plan.model_dump(mode="json")["adapter_agent"]

    assert plan.adapter_agent == config
    assert plan.adapter_agent.api_key_env == "CODING_AGENT_API_KEY"
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
    assert not (artifact_root / "adapt/demo_diff/latest/plan.json").exists()


def test_build_agent_config_reads_environment_without_printing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "do-not-print-this-key"
    monkeypatch.setenv("CODING_AGENT_PROVIDER", "another-vendor")
    monkeypatch.setenv("CODING_AGENT_BASE_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("CODING_AGENT_API_KEY", secret)
    monkeypatch.setenv("CODING_AGENT_MODEL", "vendor-code-model")
    get_settings.cache_clear()

    result = CliRunner().invoke(app, ["adapt", "agent-config"])

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


def test_adapt_run_executes_snapshots_gates_and_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    discovery_id = discover_demo(artifact_root, workspace)
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    calls: list[str] = []

    def fake_prepare(self: object, **kwargs: object) -> tuple[object, Path]:
        del self, kwargs
        calls.append("prepare")
        report = AdapterAgentDependencyReport(
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
        del self
        plan = kwargs["plan"]
        assert calls == ["prepare"]
        calls.append("execute")
        report = load_report(artifact_root, "demo_diff", discovery_id)
        tools = [tool.model_dump(mode="json") for tool in report.tool_catalog]
        for tool in tools:
            tool["availability"] = "VERIFIED"
        (workspace / "tool_catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": "robot-tool-catalog/v1",
                    "robot_id": "demo_diff",
                    "discovery_id": discovery_id,
                    "tools": tools,
                }
            ),
            encoding="utf-8",
        )
        (workspace / "state_graph.json").write_text(
            json.dumps(
                {
                    "schema_version": "robot-state-graph/v1",
                    "robot_id": "demo_diff",
                    "discovery_id": discovery_id,
                    "nodes": [],
                    "edges": [],
                }
            ),
            encoding="utf-8",
        )
        operations = []
        for tool in report.tool_catalog:
            physical = tool.risk == "R3" or tool.access == "write"
            operations.append(
                {
                    "operation": tool.operation,
                    "schema_valid": True,
                    "errors_valid": True,
                    "idempotency_valid": True,
                    "cancellation_valid": True,
                    "safety_valid": True,
                    "physical_result_valid": True if physical else None,
                    "evidence": ["artifact://evidence/result.json"] if physical else [],
                }
            )
        (workspace / "conformance.json").write_text(
            json.dumps(
                {
                    "schema_version": "robot-adapter-conformance/v1",
                    "robot_id": "demo_diff",
                    "discovery_id": discovery_id,
                    "operations": operations,
                }
            ),
            encoding="utf-8",
        )
        agent_result = AdapterAgentResult(
            schema_version="robot-adapter-agent-result/v1",
            summary="adapter outputs prepared",
            completed_tasks=[],
            changed_files=[],
            validation=[],
            blockers=[],
            handoff_ready=True,
            outputs={
                "tool_catalog": "tool_catalog.json",
                "state_graph": "state_graph.json",
                "conformance_report": "conformance.json",
            },
        )
        store = ArtifactStore(artifact_root)
        result_path = store.write_json(
            "adapt/demo_diff/runs/run-test/result.json",
            agent_result.model_dump(mode="json"),
        )
        now = utc_now()
        run = AdapterAgentRun(
            run_id="run-test",
            robot_id="demo_diff",
            source_discovery_id=plan.source_discovery_id,
            provider="codex",
            status="SUCCEEDED",
            workspace=str(workspace),
            command=["codex", "exec"],
            prompt_ref="artifact://prompt",
            event_log_ref="artifact://events",
            stderr_ref="artifact://stderr",
            final_message_ref="artifact://final",
            result_ref=f"artifact://{result_path.relative_to(artifact_root).as_posix()}",
            started_at=now,
            completed_at=now,
            duration_s=0,
        )
        run_path = store.write_json(
            "adapt/demo_diff/runs/run-test/run.json",
            run.model_dump(mode="json"),
        )
        return run, run_path

    monkeypatch.setattr(
        "rolo.stages.adapt.service.AdapterAgentDependencyManager.prepare", fake_prepare
    )
    monkeypatch.setattr("rolo.stages.adapt.service.CodexAdaptExecutor.execute", fake_execute)

    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "run",
            "--robot",
            "demo_diff",
            "--workspace",
            str(workspace),
        ],
    )

    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert calls == ["prepare", "execute"]
    payload = json.loads(result.output)
    assert payload["run"]["status"] == "COMPLETE"
    run_root = artifact_root / "adapt/demo_diff/runs/run-test"
    assert (run_root / "output-snapshot/snapshot.json").is_file()
    assert (run_root / "gate.json").is_file()
    assert (run_root / "handoff.json").is_file()
    assert (artifact_root / "adapt/demo_diff/latest.json").is_file()


def test_adapt_run_prepares_dependency_without_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    discover_demo(artifact_root, workspace)
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    calls: list[str] = []

    def unavailable_prepare(self: object, **kwargs: object) -> tuple[object, Path]:
        del self, kwargs
        calls.append("prepare")
        report = AdapterAgentDependencyReport(
            executor="codex",
            provider="codex",
            status="AUTH_REQUIRED",
            platform="Linux",
            architecture="aarch64",
            installed=True,
            authentication="AUTH_REQUIRED",
        )
        return report, artifact_root / "coding-agent/dependency/latest.json"

    monkeypatch.setattr(
        "rolo.stages.adapt.service.AdapterAgentDependencyManager.prepare", unavailable_prepare
    )

    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "run",
            "--robot",
            "demo_diff",
            "--workspace",
            str(workspace),
        ],
    )

    get_settings.cache_clear()
    assert result.exit_code == 2
    assert "dependency is not ready: AUTH_REQUIRED" in result.output
    assert calls == ["prepare"]
