from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rolo.stages.downstream import DownstreamStageService, _stage_workspace


def _settings(tmp_path: Path, *, scratch: Path | None = None):
    return SimpleNamespace(
        rolo_artifact_dir=tmp_path / "artifacts",
        rolo_scratch_dir=scratch,
        coding_agent_provider="fake-provider",
        coding_agent_executor="fake-executor",
        coding_agent_model="fake-model",
    )


def test_stage_workspace_is_ephemeral_and_rejects_nested_roots(tmp_path: Path) -> None:
    settings = _settings(tmp_path, scratch=tmp_path / "scratch")
    with _stage_workspace(settings, "diagnose") as workspace:
        assert workspace.is_dir()
        marker = workspace / "marker"
        marker.write_text("x", encoding="utf-8")
    assert not workspace.exists()

    nested = _settings(tmp_path, scratch=tmp_path / "artifacts" / "scratch")
    with pytest.raises(ValueError, match="must not contain"):
        with _stage_workspace(nested, "verify"):
            pass


def test_build_task_selects_stage_builder_and_local_target_binding(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _settings(tmp_path)
    service = DownstreamStageService(settings, "diagnose")
    monkeypatch.setattr("rolo.stages.diagnose.service.validate_adapter_handoff", lambda *args: None)
    monkeypatch.setattr(
        "rolo.stages.downstream.build_diagnosis_task",
        lambda *args, **kwargs: {"stage": "diagnose", "args": args, "kwargs": kwargs},
    )
    task = service.build_task("robot-1")
    assert task["stage"] == "diagnose"
    assert task["kwargs"]["provider"] == "fake-provider"

    service = DownstreamStageService(settings, "verify")
    monkeypatch.setattr(
        "rolo.stages.downstream.build_verification_task",
        lambda *args, **kwargs: {"stage": "verify", "kwargs": kwargs},
    )
    assert service.build_task("robot-1")["stage"] == "verify"

    settings.coding_agent_executor = "local-target"
    monkeypatch.setattr(
        "rolo.stages.real_target.publish_target_binding", lambda *args: "artifact://binding"
    )
    monkeypatch.setattr(
        "rolo.stages.downstream.build_diagnosis_task",
        lambda *args, **kwargs: kwargs,
    )
    bound = DownstreamStageService(settings, "diagnose").build_task("robot-1")
    assert bound["additional_input_refs"] == {"target_binding": "artifact://binding"}


def test_run_wires_executor_runner_and_handoff_validator(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    service = DownstreamStageService(settings, "diagnose")
    task = SimpleNamespace(executor="fake")
    monkeypatch.setattr(service, "build_task", lambda robot_id: task)
    monkeypatch.setattr(
        "rolo.stages.downstream.create_stage_agent_executor",
        lambda *args, **kwargs: object(),
    )
    captured: dict[str, object] = {}

    class Runner:
        def __init__(self, artifacts, executor, *, handoff_validator):
            captured["validator"] = handoff_validator

        def run(self, task, *, workspace, confirmed, authorization_ref, on_output):
            captured.update(
                task=task,
                workspace=workspace,
                confirmed=confirmed,
                authorization_ref=authorization_ref,
                on_output=on_output,
            )
            return "run-result"

    monkeypatch.setattr("rolo.stages.downstream.StageAgentRunner", Runner)
    monkeypatch.setattr("rolo.stages.downstream.validate_diagnosis_handoff", lambda *args: None)
    result = service.run("robot-1", confirmed=True, authorization_ref="artifact://auth")
    assert result == "run-result"
    assert captured["task"] is task
    assert captured["confirmed"] is True
    assert captured["authorization_ref"] == "artifact://auth"
    captured["validator"](task)
