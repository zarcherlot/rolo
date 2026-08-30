import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rolo.stages.agent_runner import (
    StageAgentRun,
    maintain_stage_runtime,
    recover_all_stale_stage_runs,
    remove_stale_stage_markers,
)


def _run_payload(
    run_id: str, *, started_at: datetime, status: str = "RUNNING"
) -> dict[str, object]:
    return {
        "schema_version": "rolo-stage-agent-run/v1",
        "stage": "diagnose",
        "robot_id": "robot-1",
        "run_id": run_id,
        "status": status,
        "provider": "fake",
        "executor": "fake",
        "task_ref": f"artifact://diagnose/robot-1/runs/{run_id}/task.json",
        "started_at": started_at.isoformat(),
    }


def test_recover_all_stale_runs_scans_both_stage_roots_and_is_idempotent(tmp_path: Path) -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    run_root = tmp_path / "diagnose" / "robot-1" / "runs" / "interrupted"
    run_root.mkdir(parents=True)
    (run_root / "run.json").write_text(
        json.dumps(_run_payload("interrupted", started_at=old)), encoding="utf-8"
    )

    recovered = recover_all_stale_stage_runs(tmp_path, stale_after_s=60)
    assert [run.run_id for run in recovered] == ["interrupted"]
    assert StageAgentRun.model_validate_json(
        (run_root / "run.json").read_text(encoding="utf-8")
    ).status == "FAILED"
    assert recover_all_stale_stage_runs(tmp_path, stale_after_s=60) == []


def test_remove_stale_marker_preserves_live_run_and_removes_orphan(tmp_path: Path) -> None:
    robot_root = tmp_path / "diagnose" / "robot-1"
    robot_root.mkdir(parents=True)
    stale = datetime.now(timezone.utc) - timedelta(hours=2)
    marker = robot_root / "active-run.json"
    marker.write_text(
        json.dumps(
            {
                "schema_version": "rolo-stage-active-run/v1",
                "stage": "diagnose",
                "robot_id": "robot-1",
                "run_id": "missing",
                "claimed_at": stale.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    assert remove_stale_stage_markers(tmp_path, stale_after_s=60) == [str(marker)]
    assert not marker.exists()

    live_root = robot_root / "runs" / "live"
    live_root.mkdir(parents=True)
    (live_root / "run.json").write_text(
        json.dumps(_run_payload("live", started_at=stale)), encoding="utf-8"
    )
    marker.write_text(
        json.dumps(
            {
                "schema_version": "rolo-stage-active-run/v1",
                "stage": "diagnose",
                "robot_id": "robot-1",
                "run_id": "live",
                "claimed_at": stale.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    assert remove_stale_stage_markers(tmp_path, stale_after_s=60) == []
    assert marker.exists()


def test_maintenance_report_records_recovery_and_does_not_replay(tmp_path: Path) -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    run_root = tmp_path / "verify" / "robot-2" / "runs" / "crashed"
    run_root.mkdir(parents=True)
    payload = _run_payload("crashed", started_at=old)
    payload.update({"stage": "verify", "robot_id": "robot-2"})
    (run_root / "run.json").write_text(json.dumps(payload), encoding="utf-8")

    report = maintain_stage_runtime(tmp_path, stale_after_s=60)
    assert report.schema_version == "rolo-stage-maintenance-report/v1"
    assert report.recovered_run_ids == ["crashed"]
    assert report.removed_stale_marker_paths == []
    assert maintain_stage_runtime(tmp_path, stale_after_s=60).recovered_run_ids == []
