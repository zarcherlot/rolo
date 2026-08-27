from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from rolo.jobs import JobStatus, JobStore
from rolo.product_cli import app


def test_job_store_appends_events_and_checkpoints_with_revision(tmp_path):
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    store = JobStore(tmp_path)
    job = store.create("target.inspect", "local:C:/robot", now=now)
    event = store.append_event(
        job.job_id, "JOB_STARTED", JobStatus.RUNNING, expected_revision=0, now=now
    )
    checkpoint = store.save_checkpoint(
        job.job_id, {"phase": "inspect"}, expected_revision=1, now=now
    )

    loaded, events, checkpoints = store.load(job.job_id)
    assert loaded.status == JobStatus.RUNNING
    assert loaded.revision == 1
    assert event.sequence == checkpoint.sequence == 1
    assert events[0].event_type == "JOB_STARTED"
    assert checkpoints[0].state == {"phase": "inspect"}


def test_job_store_rejects_stale_revision_and_unsafe_ids(tmp_path):
    store = JobStore(tmp_path)
    job = store.create("target.inspect", "local:C:/robot")
    store.append_event(job.job_id, "JOB_STARTED", JobStatus.RUNNING, expected_revision=0)
    with pytest.raises(ValueError, match="revision conflict"):
        store.append_event(job.job_id, "JOB_FAILED", JobStatus.FAILED, expected_revision=0)
    with pytest.raises(ValueError, match="unsafe job id"):
        store.load("../escape")


def test_product_cli_can_persist_target_inspection_as_a_job(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    result = CliRunner().invoke(app, ["target", "inspect", str(tmp_path), "--job"])
    assert result.exit_code == 0, result.output
    payload = __import__("json").loads(result.output)
    assert payload["status"] == "JOB_COMPLETED"
    job = JobStore(tmp_path / "config" / "jobs")
    loaded, events, checkpoints = job.load(payload["job_id"])
    assert loaded.status == JobStatus.SUCCEEDED
    assert [event.event_type for event in events] == ["JOB_STARTED", "TARGET_INSPECTED"]
    assert checkpoints[0].state["assessment"]["state"] == "READY"

    planned = CliRunner().invoke(app, ["target", "bootstrap-plan", str(tmp_path), "--job"])
    assert planned.exit_code == 0, planned.output
    planned_payload = __import__("json").loads(planned.output)
    loaded_plan, plan_events, plan_checkpoints = job.load(planned_payload["job_id"])
    assert loaded_plan.status == JobStatus.SUCCEEDED
    assert plan_events[-1].event_type == "BOOTSTRAP_PLAN_CREATED"
    assert plan_checkpoints[0].state["plan"]["status"] == "READY"
