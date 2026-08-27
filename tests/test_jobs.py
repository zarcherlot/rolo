from datetime import datetime, timezone

import pytest

from rolo.jobs import JobStatus, JobStore


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
