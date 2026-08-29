from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.stages.agent_runner import (
    StageAgentRunner,
    StageAgentTask,
    archive_expired_authorization_requests,
    cancel_stage_run,
    gc_stage_workspaces,
    heartbeat_stage_run,
    list_stage_authorization_requests,
    paginate_stage_stream,
    prune_stage_streams,
    recover_stale_stage_runs,
)


def _task() -> StageAgentTask:
    return StageAgentTask(
        stage="diagnose",
        robot_id="robot-1",
        task="diagnose",
        input_refs={"inputs": "artifact://diagnose/robot-1/latest/inputs.json"},
        output_contract="robot-diagnosis-handoff/v1",
        provider="anthropic",
        executor="claude-code",
        model="claude-sonnet",
        plan_sha256="a" * 64,
    )


class _FakeExecutor:
    def execute_stage(self, task: StageAgentTask, *, workspace: Path, on_output=None):
        assert task.stage == "diagnose"
        workspace.mkdir(parents=True, exist_ok=True)
        if on_output:
            on_output("stdout", "done")
        output = workspace.parent / "diagnose/robot-1/latest/inputs.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}\n", encoding="utf-8")
        return {"handoff": "artifact://diagnose/robot-1/latest/inputs.json"}


class _UnsafeExecutor:
    def execute_stage(self, task: StageAgentTask, *, workspace: Path, on_output=None):
        del task, workspace, on_output
        return {"handoff": "artifact://diagnose/robot-1/latest/missing.json"}


class _SecretExecutor:
    def execute_stage(self, task: StageAgentTask, *, workspace: Path, on_output=None):
        del task, workspace
        if on_output:
            on_output("stderr", "token=super-secret Bearer abc.def")
        return {"handoff": "artifact://diagnose/robot-1/latest/missing.json"}


def test_stage_runner_requires_confirmation_and_persists_request(tmp_path: Path) -> None:
    run = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor()).run(
        _task(), workspace=tmp_path / "workspace", confirmed=False
    )
    assert run.status == "WAITING_FOR_AUTH"
    assert run.request_ref is not None
    assert (tmp_path / "diagnose/robot-1/runs").is_dir()
    assert len(list((tmp_path / "diagnose/robot-1/authorization/requests").glob("*.json"))) == 1


def test_stage_runner_records_success_and_streams_output(tmp_path: Path) -> None:
    output: list[tuple[str, str]] = []
    run = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor()).run(
        _task(),
        workspace=tmp_path / "workspace",
        confirmed=True,
        on_output=lambda stream, line: output.append((stream, line)),
    )
    assert run.status == "SUCCEEDED"
    assert run.output_refs["handoff"].startswith("artifact://")
    assert run.stdout_ref == "artifact://diagnose/robot-1/runs/" + run.run_id + "/stdout.jsonl"
    assert output == [("stdout", "done")]
    assert (tmp_path / "diagnose/robot-1/runs" / run.run_id / "run.json").is_file()


def test_stage_runner_resumes_the_same_authorized_run_once(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    pending = runner.run(_task(), workspace=tmp_path / "workspace", confirmed=False)
    assert pending.request_ref is not None

    resumed = runner.run(
        _task(),
        workspace=tmp_path / "workspace",
        confirmed=True,
        authorization_ref=pending.request_ref,
    )
    assert resumed.status == "SUCCEEDED"

    assert resumed.run_id == pending.run_id
    request_path = tmp_path / pending.request_ref.removeprefix("artifact://")
    assert '"status": "APPROVED"' in request_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="not pending"):
        runner.run(
            _task(),
            workspace=tmp_path / "workspace",
            confirmed=True,
            authorization_ref=pending.request_ref,
        )


def test_stage_runner_fails_closed_when_executor_returns_missing_artifact(tmp_path: Path) -> None:
    run = StageAgentRunner(ArtifactStore(tmp_path), _UnsafeExecutor()).run(
        _task(), workspace=tmp_path / "workspace", confirmed=True
    )
    assert run.status == "FAILED"
    assert "artifact is missing" in (run.error or "")


def test_stage_runner_applies_rolo_owned_handoff_validator(tmp_path: Path) -> None:
    def reject_handoff(task: StageAgentTask) -> None:
        raise ValueError(f"invalid {task.stage} handoff")

    run = StageAgentRunner(
        ArtifactStore(tmp_path), _FakeExecutor(), handoff_validator=reject_handoff
    ).run(_task(), workspace=tmp_path / "workspace", confirmed=True)
    assert run.status == "FAILED"
    assert run.error == "invalid diagnose handoff"


def test_stage_runner_redacts_secret_like_streams(tmp_path: Path) -> None:
    output: list[str] = []
    run = StageAgentRunner(ArtifactStore(tmp_path), _SecretExecutor()).run(
        _task(),
        workspace=tmp_path / "workspace",
        confirmed=True,
        on_output=lambda _stream, line: output.append(line),
    )
    assert run.status == "FAILED"
    assert output == ["token=<redacted> Bearer <redacted>"]
    stream = (tmp_path / run.stderr_ref.removeprefix("artifact://")).read_text(encoding="utf-8")
    assert "super-secret" not in stream


def test_authorization_listing_filters_exact_robot_and_stage(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    runner.run(_task(), workspace=tmp_path / "workspace", confirmed=False)
    verify_task = _task().model_copy(update={"stage": "verify", "robot_id": "robot-2"})
    runner.run(verify_task, workspace=tmp_path / "workspace", confirmed=False)

    assert len(
        list_stage_authorization_requests(
            tmp_path, stage="diagnose", robot_id="robot-1"
        )
    ) == 1
    assert list_stage_authorization_requests(tmp_path, stage="verify", robot_id="robot-1") == []


def test_stage_runner_requires_confirmation_to_resume_authorization(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    pending = runner.run(_task(), workspace=tmp_path / "workspace", confirmed=False)
    assert pending.request_ref is not None
    with pytest.raises(ValueError, match="current-user confirmation"):
        runner.run(
            _task(),
            workspace=tmp_path / "workspace",
            confirmed=False,
            authorization_ref=pending.request_ref,
        )


def test_stage_runner_rejects_changed_hashed_input(tmp_path: Path) -> None:
    input_file = tmp_path / "input.json"
    input_file.write_text('{"version":1}\n', encoding="utf-8")
    task = _task().model_copy(
        update={
            "input_refs": {"input": "artifact://input.json"},
            "input_sha256": {"input": "0" * 64},
        }
    )
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())

    with pytest.raises(ValueError, match="input artifact hash mismatch"):
        runner.run(task, workspace=tmp_path / "workspace", confirmed=False)


def test_stage_runner_recovers_an_interrupted_running_run(tmp_path: Path) -> None:
    run_root = tmp_path / "diagnose" / "robot-1" / "runs" / "abandoned"
    run_root.mkdir(parents=True)
    started = datetime.now(timezone.utc) - timedelta(hours=2)
    run = {
        "schema_version": "rolo-stage-agent-run/v1",
        "stage": "diagnose",
        "robot_id": "robot-1",
        "run_id": "abandoned",
        "status": "RUNNING",
        "provider": "fake",
        "executor": "fake",
        "task_ref": "artifact://diagnose/robot-1/runs/abandoned/task.json",
        "started_at": started.isoformat(),
    }
    (run_root / "run.json").write_text(json.dumps(run), encoding="utf-8")

    recovered = recover_stale_stage_runs(tmp_path, "diagnose", "robot-1", stale_after_s=60)

    assert len(recovered) == 1
    assert recovered[0].status == "FAILED"
    assert "lease expired" in (recovered[0].error or "")
    persisted = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "FAILED"


def test_stage_runner_rejects_concurrent_execution_for_one_robot_stage(tmp_path: Path) -> None:
    lock_target = tmp_path / "diagnose" / "robot-1" / ".stage-execution.lock"
    lock_target.parent.mkdir(parents=True)
    from rolo.core.persistence import interprocess_lock

    with interprocess_lock(lock_target):
        run = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor()).run(
            _task(), workspace=tmp_path / "workspace", confirmed=True
        )

    assert run.status == "FAILED"
    assert "artifact lock" in (run.error or "")


def test_stage_runner_idempotency_returns_existing_run(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    first = runner.run(
        _task(), workspace=tmp_path / "workspace", confirmed=True, idempotency_key="same"
    )
    second = runner.run(
        _task(), workspace=tmp_path / "workspace", confirmed=True, idempotency_key="same"
    )
    assert first.status == "SUCCEEDED"
    assert second.run_id == first.run_id


def test_stage_runner_preserves_idempotency_key_when_authorization_resumes(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    pending = runner.run(
        _task(), workspace=tmp_path / "workspace", confirmed=False, idempotency_key="resume-me"
    )
    resumed = runner.run(
        _task(),
        workspace=tmp_path / "workspace",
        confirmed=True,
        authorization_ref=pending.request_ref,
    )
    assert resumed.idempotency_key == "resume-me"


def test_cancel_stage_run_is_persistent_and_idempotent(tmp_path: Path) -> None:
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    pending = runner.run(_task(), workspace=tmp_path / "workspace", confirmed=False)
    cancelled = cancel_stage_run(tmp_path, "diagnose", "robot-1", pending.run_id)
    assert cancelled.status == "CANCELLED"
    assert cancelled.cancel_requested is True
    assert cancel_stage_run(tmp_path, "diagnose", "robot-1", pending.run_id).status == "CANCELLED"


def test_stage_run_heartbeat_prevents_premature_recovery(tmp_path: Path) -> None:
    run_root = tmp_path / "diagnose" / "robot-1" / "runs" / "running"
    run_root.mkdir(parents=True)
    started = datetime.now(timezone.utc) - timedelta(hours=2)
    run = {
        "schema_version": "rolo-stage-agent-run/v1",
        "stage": "diagnose",
        "robot_id": "robot-1",
        "run_id": "running",
        "status": "RUNNING",
        "provider": "fake",
        "executor": "fake",
        "task_ref": "artifact://diagnose/robot-1/runs/running/task.json",
        "started_at": started.isoformat(),
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_root / "run.json").write_text(json.dumps(run), encoding="utf-8")
    assert recover_stale_stage_runs(tmp_path, "diagnose", "robot-1", stale_after_s=60) == []
    refreshed = heartbeat_stage_run(tmp_path, "diagnose", "robot-1", "running")
    assert refreshed.heartbeat_at is not None


def test_stage_workspace_gc_removes_only_old_rolo_workspaces(tmp_path: Path) -> None:
    old = tmp_path / "rolo-diagnose-old"
    fresh = tmp_path / "rolo-verify-fresh"
    unrelated = tmp_path / "keep-me"
    old.mkdir()
    fresh.mkdir()
    unrelated.mkdir()
    old_time = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    import os

    os.utime(old, (old_time, old_time))
    assert gc_stage_workspaces(tmp_path, older_than_s=60) == 1
    assert not old.exists()
    assert fresh.exists() and unrelated.exists()


def test_stage_runner_cancels_before_executor_and_expired_auth_is_archived(tmp_path: Path) -> None:
    event = Event()
    event.set()
    runner = StageAgentRunner(ArtifactStore(tmp_path), _FakeExecutor())
    run = runner.run(_task(), workspace=tmp_path / "workspace", confirmed=True, cancel_event=event)
    assert run.status == "CANCELLED"
    pending = runner.run(_task(), workspace=tmp_path / "workspace", confirmed=False)
    request_path = tmp_path / pending.request_ref.removeprefix("artifact://")
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    archived = archive_expired_authorization_requests(tmp_path)
    assert len(archived) == 1
    assert json.loads(request_path.read_text(encoding="utf-8"))["status"] == "EXPIRED"


def test_stage_stream_pagination_and_retention_keep_newest_records(tmp_path: Path) -> None:
    stream = tmp_path / "diagnose" / "robot-1" / "runs" / "run-1" / "stdout.jsonl"
    stream.parent.mkdir(parents=True)
    stream.write_text(
        "".join(json.dumps({"line": str(i)}) + "\n" for i in range(10)), encoding="utf-8"
    )
    assert paginate_stage_stream(stream, offset=2, limit=2) == [{"line": "2"}, {"line": "3"}]
    assert prune_stage_streams(tmp_path, max_bytes=40) == 1
    retained = stream.read_text(encoding="utf-8")
    assert '"line": "9"' in retained
