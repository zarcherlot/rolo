from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.config import get_settings
from rolo.stages.adapt.journey import detect_project_evidence
from rolo.stages.adapt.models import AdaptPlanStatus, AdaptRunSummary


def _project(root: Path) -> Path:
    project = root / "robot-project"
    (project / "build").mkdir(parents=True)
    (project / "install").mkdir()
    (project / "docs").mkdir()
    (project / "src/navigation/launch").mkdir(parents=True)
    (project / "README.md").write_text("# Robot\n", encoding="utf-8")
    (project / "docs/operator.md").write_text("# Operator\n", encoding="utf-8")
    (project / "src/navigation/launch/navigation.launch.py").write_text(
        "from launch import LaunchDescription\n",
        encoding="utf-8",
    )
    return project


def test_project_evidence_detects_primary_roots_without_guessing_urdf(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "src/navigation/urdf").mkdir(parents=True)
    (project / "src/navigation/urdf/robot.urdf").write_text(
        '<robot name="test_robot"><link name="base_link"/></robot>',
        encoding="utf-8",
    )

    evidence = detect_project_evidence(project)

    assert evidence.project_root == project.resolve()
    assert evidence.source_roots == [project.resolve()]
    assert evidence.build_roots == [(project / "build").resolve()]
    assert evidence.install_roots == [(project / "install").resolve()]
    assert (project / "docs").resolve() in evidence.document_roots
    assert evidence.launch_roots == [(project / "src/navigation/launch").resolve()]
    assert not hasattr(evidence, "urdf")
    assert evidence.truncated is False


def test_adapt_start_collapses_enrollment_discovery_and_wiki_into_one_command(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    config_root = tmp_path / "config"
    artifact_root = tmp_path / "artifacts"
    output_root = tmp_path / "output"
    urdf = Path("tests/fixtures/profiles/differential_drive.urdf").resolve()
    get_settings.cache_clear()

    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "start",
            "--robot-id",
            "journey_robot",
            "--project-root",
            str(project),
            "--urdf",
            str(urdf),
            "--active-probe",
            "none",
            "--discover-only",
        ],
        env={
            "ROLO_CONFIG_DIR": str(config_root),
            "ROLO_ARTIFACT_DIR": str(artifact_root),
            "ROLO_OUTPUT_DIR": str(output_root),
            "WIKI_INSIGHTS_AGENT_ENABLED": "false",
            "WIKI_POLISH_ENABLED": "false",
        },
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "robot-adapt-journey/v1"
    assert payload["status"] == "DISCOVERY_COMPLETE"
    assert payload["robot_id"] == "journey_robot"
    assert payload["enrollment"] == "IDENTITY_REGISTERED"
    assert payload["doctor_status"] == "READY"
    assert payload["discovery_id"].startswith("disc-")
    assert payload["wiki"].endswith("robot_wiki.md")
    assert Path(payload["wiki"]).is_file()
    assert (config_root / "robots/journey_robot.yaml").is_file()
    assert payload["next_steps"][0] == "robotctl adapt run --robot journey_robot"


def test_adapt_start_reuses_the_registered_identity(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = {
        "ROLO_CONFIG_DIR": str(tmp_path / "config"),
        "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
        "WIKI_INSIGHTS_AGENT_ENABLED": "false",
        "WIKI_POLISH_ENABLED": "false",
    }
    command = [
        "adapt",
        "start",
        "--robot",
        "journey_robot",
        "--project-root",
        str(project),
        "--active-probe",
        "none",
        "--discover-only",
    ]
    runner = CliRunner()
    get_settings.cache_clear()
    first = runner.invoke(app, command, env=env)
    get_settings.cache_clear()
    second = runner.invoke(app, command, env=env)
    get_settings.cache_clear()

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["enrollment"] == "ALREADY_REGISTERED"


def test_adapt_start_returns_an_actionable_blocker_without_runtime_routes(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "start",
            "--robot",
            "blocked_robot",
            "--project-root",
            str(project),
            "--active-probe",
            "none",
        ],
        env={
            "ROLO_CONFIG_DIR": str(tmp_path / "config"),
            "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
            "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
            "WIKI_INSIGHTS_AGENT_ENABLED": "false",
            "WIKI_POLISH_ENABLED": "false",
        },
    )
    get_settings.cache_clear()

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["status"] == "BLOCKED"
    assert payload["wiki"].endswith("robot_wiki.md")
    assert "target-observed" in payload["blockers"][0]
    assert payload["next_steps"][0] == "robotctl adapt status --robot blocked_robot"


def test_adapt_start_reports_the_gate_handoff_and_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)

    class Plan:
        status = AdaptPlanStatus.REQUIRES_CODING

    monkeypatch.setattr(
        "rolo.stages.adapt.journey.AdaptRunService.dry_run",
        lambda self, robot_id: Plan(),
    )

    def completed_run(self: object, **kwargs: object) -> tuple[AdaptRunSummary, Path]:
        del self, kwargs
        artifact = tmp_path / "artifacts/adapt/release_robot/runs/run-short/summary.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("{}", encoding="utf-8")
        return (
            AdaptRunSummary(
                robot_id="release_robot",
                run_id="run-short",
                agent_run_ref="artifact://agent-run.json",
                snapshot_ref="artifact://snapshot.json",
                gate_ref="artifact://gate.json",
                handoff_ref="artifact://handoff.json",
            ),
            artifact,
        )

    monkeypatch.setattr(
        "rolo.stages.adapt.journey.AdaptRunService.run",
        completed_run,
    )
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "start",
            "--robot",
            "release_robot",
            "--project-root",
            str(project),
            "--active-probe",
            "none",
        ],
        env={
            "ROLO_CONFIG_DIR": str(tmp_path / "config"),
            "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
            "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
            "WIKI_INSIGHTS_AGENT_ENABLED": "false",
            "WIKI_POLISH_ENABLED": "false",
        },
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "COMPLETE"
    assert payload["release_id"] == "run-short"
    assert payload["gate"] == "artifact://gate.json"
    assert payload["handoff"] == "artifact://handoff.json"
