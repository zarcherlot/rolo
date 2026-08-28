from __future__ import annotations

import json
from pathlib import Path

from rolo.agent_provider import create_stage_agent_executor
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.harness import CodexHarness, available_harnesses, configured_harness, register_harness
from rolo.stages.agent_runner import StageAgentTask
from rolo.stages.codex_downstream import CodexStageAgentExecutor
from rolo.stages.handoffs import DiagnosisHandoff


def _task(stage: str) -> StageAgentTask:
    return StageAgentTask(
        stage=stage,
        robot_id="robot-1",
        task="run stage",
        input_refs={},
        output_contract=(
            "robot-diagnosis-handoff/v1"
            if stage == "diagnose"
            else "robot-verification-handoff/v1"
        ),
        provider="codex",
        executor="codex",
        model="gpt-test",
        plan_sha256="a" * 64,
    )


def test_diagnose_and_verify_default_to_codex_provider_and_executor() -> None:
    settings = Settings(_env_file=None)

    assert settings.coding_agent_provider == "codex"
    assert settings.coding_agent_executor == "codex"


class _FakeHarness:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def run(self, request, *, on_output=None):
        if on_output:
            on_output("stdout", "structured result")
        return json.dumps(self.payload), "", 0


class _CapturingHarness(_FakeHarness):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(payload)
        self.prompt = ""

    def run(self, request, *, on_output=None):
        self.prompt = request.prompt
        return super().run(request, on_output=on_output)


def test_codex_diagnose_executor_materializes_structured_result(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(_env_file=None, coding_agent_timeout_s=30)
    executor = CodexStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=settings, stage="diagnose"
    )
    monkeypatch.setattr(
        "rolo.stages.codex_downstream.configured_harness",
        lambda _settings: _FakeHarness(
            {"frozen_config": {"speed": 0.2}, "diagnosis_report": {"ok": True}}
        ),
    )
    monkeypatch.setattr(
        "rolo.stages.codex_downstream.commit_diagnosis_handoff",
        lambda *args, **kwargs: DiagnosisHandoff(
            robot_id="robot-1",
            source_adapter_handoff_ref="artifact://adapt/robot-1/handoff.json",
            source_adapter_handoff_sha256="a" * 64,
            frozen_config_ref="artifact://diagnose/robot-1/frozen.json",
            frozen_config_sha256="b" * 64,
        ),
    )
    result = executor.execute_stage(_task("diagnose"), workspace=tmp_path)
    assert result["handoff"].endswith("diagnose/robot-1/latest/handoff.json")
    assert result["frozen_config"] == "artifact://diagnose/robot-1/frozen.json"


def test_codex_downstream_materializes_artifact_inputs_for_the_harness(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"robot_id":"robot-1"}\n', encoding="utf-8")
    harness = _CapturingHarness(
        {"regression_report": {"status": "PASS"}, "evidence_package": {"artifacts": []}}
    )
    settings = Settings(_env_file=None, coding_agent_timeout_s=30)
    executor = CodexStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=settings, stage="verify"
    )
    task = _task("verify").model_copy(
        update={"input_refs": {"verification_inputs": "artifact://source.json"}}
    )
    monkeypatch.setattr(
        "rolo.stages.codex_downstream.configured_harness", lambda _settings: harness
    )
    monkeypatch.setattr(
        "rolo.stages.codex_downstream.commit_verification_handoff",
        lambda *args, **kwargs: type("Handoff", (), {
            "regression_report_ref": "artifact://verify/robot-1/report.json",
            "evidence_package_ref": "artifact://verify/robot-1/evidence.json",
        })(),
    )
    result = executor.execute_stage(task, workspace=tmp_path / "workspace")

    assert result["regression_report"] == "artifact://verify/robot-1/report.json"
    assert "verification_inputs" in harness.prompt
    assert (tmp_path / "workspace" / "rolo-stage-inputs" / "verification_inputs.json").is_file()


def test_codex_verify_executor_requires_both_result_sections(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(_env_file=None, coding_agent_timeout_s=30)
    executor = CodexStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=settings, stage="verify"
    )
    monkeypatch.setattr(
        "rolo.stages.codex_downstream.configured_harness",
        lambda _settings: _FakeHarness({"regression_report": {"passed": 1}}),
    )
    try:
        executor.execute_stage(_task("verify"), workspace=tmp_path)
    except ValueError as exc:
        assert "did not return a JSON object" in str(exc)
    else:
        raise AssertionError("incomplete Verify result must fail closed")


def test_provider_factory_exposes_builtin_codex_stage_executor(tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    executor = create_stage_agent_executor(
        "codex", artifacts=ArtifactStore(tmp_path), settings=settings, stage="diagnose"
    )
    assert isinstance(executor, CodexStageAgentExecutor)


def test_codex_harness_creates_policy_without_overwriting_user_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    CodexHarness._ensure_agents_policy(workspace)
    policy = workspace / "AGENTS.md"
    first = policy.read_text(encoding="utf-8")
    assert "Do not claim release" in first
    policy.write_text("user policy\n", encoding="utf-8")
    CodexHarness._ensure_agents_policy(workspace)
    assert policy.read_text(encoding="utf-8") == "user policy\n"


def test_harness_registry_keeps_executor_and_provider_separate() -> None:
    assert "codex" in available_harnesses()

    class FakeHarness:
        def run(self, request, *, on_output=None):
            del request, on_output
            return "", "", 0

    name = "test-harness"
    register_harness(name, lambda *, settings: FakeHarness())
    settings = Settings(_env_file=None, coding_agent_executor=name)
    assert isinstance(configured_harness(settings), FakeHarness)


def test_codex_diagnose_binds_unverified_observation_when_no_episode_exists(tmp_path: Path) -> None:
    executor = CodexStageAgentExecutor(
        artifacts=ArtifactStore(tmp_path), settings=Settings(_env_file=None), stage="diagnose"
    )
    report = {
        "schema_version": "rolo-diagnosis-report/v1",
        "robot_id": "robot-1",
        "baseline": {"speed": 0.2},
        "observations": [{"kind": "snapshot"}],
        "hypotheses": [{"kind": "nominal"}],
        "changes": [{"kind": "none"}],
        "smoke": {"status": "NOT_RUN"},
        "decision": "INCONCLUSIVE",
    }
    task = _task("diagnose").model_copy(
        update={"input_refs": {"inputs": "artifact://inputs.json"}}
    )
    enriched = executor._prepare_diagnosis_report(task, report, "codex-test")
    refs = enriched["episode_refs"]
    assert isinstance(refs, list) and refs[0].startswith("artifact://")
    assert "unverified" in enriched["limitations"][0]
    assert (tmp_path / refs[0].removeprefix("artifact://")).is_file()
