from __future__ import annotations

from pathlib import Path

from rolo.agent_provider import create_stage_agent_executor
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.stages.agent_runner import StageAgentTask
from rolo.stages.fake_downstream import FakeStageAgentExecutor


def _task(stage: str) -> StageAgentTask:
    return StageAgentTask(
        stage=stage,
        robot_id="robot-1",
        task="exercise local stage contract",
        input_refs={"inputs": "artifact://inputs.json"},
        output_contract=(
            "robot-diagnosis-handoff/v1"
            if stage == "diagnose"
            else "robot-verification-handoff/v1"
        ),
        provider="fake",
        executor="fake",
        plan_sha256="a" * 64,
    )


def test_fake_stage_executor_is_explicit_and_does_not_change_codex_default(tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    assert settings.coding_agent_provider == "codex"
    assert settings.coding_agent_executor == "codex"
    executor = create_stage_agent_executor(
        "fake", artifacts=ArtifactStore(tmp_path), settings=settings, stage="diagnose"
    )
    assert isinstance(executor, FakeStageAgentExecutor)


def test_fake_diagnose_materializes_strict_contract_without_target_execution(
    tmp_path: Path, monkeypatch
) -> None:
    adapter = tmp_path / "adapt" / "robot-1" / "runs" / "adapt-1" / "handoff.json"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.latest_adapter_handoff_path",
        lambda root, robot_id: adapter,
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.validate_adapter_handoff", lambda *args: None
    )
    monkeypatch.setattr(
        "rolo.stages.handoffs.validate_diagnosis_handoff", lambda *args, **kwargs: None
    )
    executor = FakeStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=Settings(_env_file=None), stage="diagnose"
    )
    result = executor.execute_stage(_task("diagnose"), workspace=tmp_path / "workspace")

    assert result["handoff"].endswith("diagnose/robot-1/latest/handoff.json")
    assert result["diagnosis_report"].startswith("artifact://")
    report_path = tmp_path / result["diagnosis_report"].removeprefix("artifact://")
    report = report_path.read_text(encoding="utf-8")
    assert '"decision": "INCONCLUSIVE"' in report
    assert "NOT_EXECUTED" in report


def test_fake_verify_materializes_non_release_degraded_result(tmp_path: Path, monkeypatch) -> None:
    diagnosis = tmp_path / "diagnose" / "robot-1" / "latest" / "handoff.json"
    diagnosis.parent.mkdir(parents=True)
    diagnosis.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        "rolo.stages.handoffs.validate_diagnosis_handoff", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "rolo.stages.handoffs.validate_verification_handoff", lambda *args, **kwargs: None
    )
    executor = FakeStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=Settings(_env_file=None), stage="verify"
    )
    result = executor.execute_stage(_task("verify"), workspace=tmp_path / "workspace")

    assert result["handoff"].endswith("verify/robot-1/latest/handoff.json")
    report_path = tmp_path / result["regression_report"].removeprefix("artifact://")
    evidence_path = tmp_path / result["evidence_package"].removeprefix("artifact://")
    assert '"status": "ERROR"' in report_path.read_text(encoding="utf-8")
    assert "FAKE_UNEXECUTED" in evidence_path.read_text(encoding="utf-8")
