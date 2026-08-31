from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.approval_gate_read_models import (
    ApprovalGateSummary,
    build_approval_gate_collection,
    build_approval_gate_summary,
    get_approval_gate_summary,
)
from rolo.jobs import JobEvent, JobStatus, JobStore
from rolo.target_ref import LocalTargetRef
from rolo.targets.profiles import CredentialReference, TargetProfileStore


def _credential() -> CredentialReference:
    return CredentialReference(kind="ssh-agent", reference="ssh-agent:default")


def _job(tmp_path: Path, *, status: JobStatus = JobStatus.CREATED):
    config = tmp_path / "config"
    target = tmp_path / "workspace"
    target.mkdir()
    profile_store = TargetProfileStore(config)
    profile_store.create(
        robot_id="demo_target",
        target=LocalTargetRef(workspace=target),
        credential=_credential(),
    )
    store = JobStore(config / "jobs")
    job = store.create(
        "target.bootstrap.execute",
        LocalTargetRef(workspace=target).model_dump_json(),
    )
    if status is not JobStatus.CREATED:
        store.append_event(
            job.job_id,
            "JOB_STARTED",
            JobStatus.RUNNING,
            expected_revision=0,
            payload={"approval_status": "APPROVED"},
        )
        if status is not JobStatus.RUNNING:
            store.append_event(
                job.job_id,
                "BOOTSTRAP_COMPLETED" if status is JobStatus.SUCCEEDED else "BOOTSTRAP_FAILED",
                status,
                expected_revision=1,
            )
        job, events, checkpoints = store.load(job.job_id)
    else:
        job, events, checkpoints = store.load(job.job_id)
    return config, job, events, checkpoints


def test_pending_projection_is_sanitized_and_bound(tmp_path: Path) -> None:
    config, job, events, checkpoints = _job(tmp_path)
    summary = build_approval_gate_summary(config, job, events, checkpoints)
    payload = summary.model_dump_json()
    assert summary.schema_version == "rolo-approval-gate-summary/v1"
    assert summary.job_id == job.job_id
    assert summary.target_id == "demo_target"
    assert summary.plan_status == "APPROVAL_REQUIRED"
    assert summary.approval_status == "PENDING"
    assert summary.gate_status == "PENDING"
    assert summary.recovery_state == "AVAILABLE"
    assert len(summary.steps) == 4
    assert str(tmp_path).casefold() not in payload.casefold()
    assert "ssh://" not in payload.casefold()
    assert "credential" not in payload.casefold()
    assert summary.contains_secret_payloads is False


@pytest.mark.parametrize(
    ("status", "approval_status", "gate_status", "recovery_state"),
    [
        (JobStatus.RUNNING, "APPROVED", "PENDING", "AVAILABLE"),
        (JobStatus.SUCCEEDED, "APPROVED", "PASSED", "NOT_REQUIRED"),
        (JobStatus.FAILED, "APPROVED", "FAILED", "BLOCKED"),
        (JobStatus.BLOCKED, "APPROVED", "BLOCKED", "BLOCKED"),
    ],
)
def test_job_statuses_keep_dimensions_independent(
    tmp_path: Path,
    status: JobStatus,
    approval_status: str,
    gate_status: str,
    recovery_state: str,
) -> None:
    config, job, events, checkpoints = _job(tmp_path, status=status)
    summary = build_approval_gate_summary(config, job, events, checkpoints)
    assert summary.approval_status == approval_status
    assert summary.gate_status == gate_status
    assert summary.recovery_state == recovery_state


def test_collection_and_detail_are_paginated_and_stable(tmp_path: Path) -> None:
    config, job, events, checkpoints = _job(tmp_path)
    page = build_approval_gate_collection(config, limit=1)
    assert page.total == 1
    assert page.next_offset is None
    assert get_approval_gate_summary(config, job.job_id).job_id == job.job_id
    assert get_approval_gate_summary(config, "job_missing") is None


def test_stale_projection_keeps_observed_time(tmp_path: Path) -> None:
    config, job, events, checkpoints = _job(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    stale = build_approval_gate_summary(config, job, events, checkpoints, observed_at=old)
    assert stale.freshness == "stale"
    assert stale.observed_at == old


@pytest.mark.parametrize("approval_status", ["REJECTED", "EXPIRED"])
def test_rejected_and_expired_approval_states_are_preserved(
    tmp_path: Path, approval_status: str
) -> None:
    config, job, _events, checkpoints = _job(tmp_path)
    event = JobEvent(
        job_id=job.job_id,
        sequence=1,
        event_type="APPROVAL_STATUS",
        status=JobStatus.CREATED,
        occurred_at=job.updated_at,
        payload={"approval_status": approval_status},
    )
    summary = build_approval_gate_summary(config, job, [event], checkpoints)
    assert summary.approval_status == approval_status
    assert f"APPROVAL_{approval_status}" in summary.blockers


def test_revision_drift_fails_closed(tmp_path: Path) -> None:
    config, job, events, checkpoints = _job(tmp_path)
    drifted = job.model_copy(update={"revision": 9})
    with pytest.raises(ValueError, match="latest event"):
        # Persisted-record validation is the boundary that rejects this drift.
        from rolo.approval_gate_read_models import _load_job_records

        store = JobStore(config / "jobs")
        store._write(
            job.job_id,
            {
                "job": drifted.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in events],
                "checkpoints": [checkpoint.model_dump(mode="json") for checkpoint in checkpoints],
            },
        )
        _load_job_records(config)


def test_summary_rejects_empty_or_repeated_identities() -> None:
    with pytest.raises(ValidationError):
        ApprovalGateSummary(
            job_id="job_demo",
            target_id="target_demo",
            producer_revision="a" * 64,
            plan_status="APPROVAL_REQUIRED",
            steps=[],
            approval_status="PENDING",
            gate_status="PENDING",
            gate_checks=["CHECK"],
            recovery_state="UNKNOWN",
            observed_at=datetime.now(timezone.utc),
            freshness="fresh",
        )
