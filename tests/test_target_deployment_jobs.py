from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.targets import (
    ApprovalAction,
    ApprovalRequest,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentEventType,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentRecoveryDisposition,
    DeploymentRemoteReconciliationOutcome,
    DeploymentStepStatus,
    InteractionSurface,
)

NOW = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


def _command(**updates: object) -> DeploymentCommand:
    values: dict[str, object] = {
        "command": DeploymentCommandKind.BOOTSTRAP_AND_ADAPT,
        "target_id": "wheeltec",
        "workspace_root": "/home/robot/wheeltec_ws",
        "requested_by": "session-agent",
        "interaction_surface": InteractionSurface.NATURAL_LANGUAGE,
        "idempotency_key": "deployment-request-20260825",
    }
    values.update(updates)
    return DeploymentCommand.model_validate(values)


def test_job_store_is_idempotent_hash_chained_and_secret_closed(tmp_path: Path) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    command = _command()
    created = store.create_job(
        command,
        now=NOW,
        job_id="deployment-" + "1" * 32,
    )
    repeated = store.create_job(command, now=NOW + timedelta(seconds=1))

    assert repeated.job.job_id == created.job.job_id
    assert created.last_event_sequence == 1
    assert created.last_event_record_sha256 is not None
    updated = store.append_event(
        created.job.job_id,
        event_type=DeploymentEventType.STATE_CHANGED,
        step_id="connection",
        summary=(
            "Connecting with token=super-secret and Authorization: "
            "Bearer abc.def.ghi\nnext-line"
        ),
        state=DeploymentJobState.CONNECTING,
        now=NOW + timedelta(seconds=2),
    )
    events = store.read_events(created.job.job_id)

    assert updated.last_event_sequence == 2
    assert [item.sequence for item in events] == [1, 2]
    assert events[1].previous_record_sha256 == events[0].record_sha256
    serialized = events[1].model_dump_json()
    assert "super-secret" not in serialized
    assert "abc.def.ghi" not in serialized
    assert "<redacted>" in serialized
    sse = "".join(store.iter_sse(created.job.job_id, after_sequence=1))
    assert sse.startswith("id: 2\nevent: state_changed\ndata: ")
    assert json.loads(sse.split("data: ", 1)[1].strip())["sequence"] == 2

    conflicting = _command(command=DeploymentCommandKind.ADAPT)
    with pytest.raises(DeploymentJobStateConflict, match="different command"):
        store.create_job(conflicting, now=NOW + timedelta(seconds=3))


def test_step_checkpoint_and_final_artifact_are_atomic_with_job_state(
    tmp_path: Path,
) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    record = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "2" * 32,
    )
    started = store.start_step(
        record.job.job_id,
        step_id="bootstrap",
        state=DeploymentJobState.BOOTSTRAPPING,
        remote=True,
        now=NOW + timedelta(seconds=1),
    )
    assert started.checkpoints[0].status == DeploymentStepStatus.RUNNING

    completed = store.complete_step(
        record.job.job_id,
        step_id="bootstrap",
        outcome_sha256="a" * 64,
        artifact_refs=["artifact://deployments/wheeltec/bootstrap.json"],
        now=NOW + timedelta(seconds=2),
    )
    assert completed.checkpoints[0].status == DeploymentStepStatus.COMPLETE
    assert completed.checkpoints[0].outcome_sha256 == "a" * 64

    final = store.complete_job(
        record.job.job_id,
        artifact_refs=["artifact://deployments/wheeltec/release.json"],
        now=NOW + timedelta(seconds=3),
    )
    reloaded = DeploymentJobStore(tmp_path / "jobs").load_job(record.job.job_id)
    assert final.job.state == DeploymentJobState.COMPLETE
    assert reloaded.final_artifact_refs == [
        "artifact://deployments/wheeltec/release.json"
    ]
    assert reloaded.last_event_sequence == len(store.read_events(record.job.job_id))


def test_per_target_lease_rejects_conflicting_job(tmp_path: Path) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    acquired = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with store.target_lease("wheeltec", timeout_s=1.0):
            acquired.set()
            assert release.wait(timeout=2.0)

    thread = threading.Thread(target=hold)
    thread.start()
    assert acquired.wait(timeout=1.0)
    try:
        with pytest.raises(TimeoutError, match="timed out"):
            with store.target_lease("wheeltec", timeout_s=0.05):
                raise AssertionError("conflicting target lease was acquired")
    finally:
        release.set()
        thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_cancel_unknown_remote_state_blocks_retry_until_reconciliation(
    tmp_path: Path,
) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "3" * 32,
    )
    store.start_step(
        job.job.job_id,
        step_id="remote-install",
        state=DeploymentJobState.BOOTSTRAPPING,
        remote=True,
        now=NOW + timedelta(seconds=1),
    )
    store.request_cancel(job.job.job_id, now=NOW + timedelta(seconds=2))
    blocked = store.resolve_cancel(
        job.job.job_id,
        remote_termination_confirmed=False,
        now=NOW + timedelta(seconds=3),
    )

    assert blocked.job.state == DeploymentJobState.BLOCKED
    assert (
        blocked.recovery_disposition
        == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
    )
    assert blocked.job.blockers == ["REQUIRES_REMOTE_RECONCILIATION"]
    with pytest.raises(DeploymentJobStateConflict, match="requires reconciliation"):
        store.retry_job(job.job.job_id, now=NOW + timedelta(seconds=4))


def _unknown_remote_job(store: DeploymentJobStore, *, suffix: str) -> str:
    job = store.create_job(
        _command(idempotency_key=f"unknown-remote-{suffix}"),
        now=NOW,
        job_id="deployment-" + suffix * 32,
    )
    store.start_step(
        job.job.job_id,
        step_id="provision-host",
        state=DeploymentJobState.BOOTSTRAPPING,
        remote=True,
        now=NOW + timedelta(seconds=1),
    )
    store.fail_step(
        job.job.job_id,
        step_id="provision-host",
        remote_state_known=False,
        artifact_refs=["artifact://deployment-jobs/original-result.json"],
        now=NOW + timedelta(seconds=2),
    )
    return job.job.job_id


def test_exact_remote_reconciliation_completes_original_job(tmp_path: Path) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job_id = _unknown_remote_job(store, suffix="b")

    reconciled = store.reconcile_remote_step(
        job_id,
        step_id="provision-host",
        outcome=DeploymentRemoteReconciliationOutcome.EXACT,
        outcome_sha256="c" * 64,
        artifact_refs=["artifact://deployment-jobs/observation.json"],
        now=NOW + timedelta(seconds=3),
    )

    assert reconciled.job.state == DeploymentJobState.COMPLETE
    assert reconciled.recovery_disposition == DeploymentRecoveryDisposition.NONE
    assert reconciled.checkpoints[0].status == DeploymentStepStatus.COMPLETE
    assert reconciled.checkpoints[0].remote_state.value == "CONFIRMED"
    assert reconciled.final_artifact_refs == [
        "artifact://deployment-jobs/observation.json",
        "artifact://deployment-jobs/original-result.json",
    ]


def test_not_committed_remote_reconciliation_unlocks_new_attempt(
    tmp_path: Path,
) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job_id = _unknown_remote_job(store, suffix="c")
    reconciled = store.reconcile_remote_step(
        job_id,
        step_id="provision-host",
        outcome=DeploymentRemoteReconciliationOutcome.NOT_COMMITTED,
        outcome_sha256="d" * 64,
        artifact_refs=["artifact://deployment-jobs/observation.json"],
        now=NOW + timedelta(seconds=3),
    )

    assert reconciled.job.state == DeploymentJobState.BLOCKED
    assert reconciled.recovery_disposition == DeploymentRecoveryDisposition.RESUMABLE
    assert reconciled.job.blockers == ["REMOTE_STATE_CONFIRMED_NOT_COMMITTED"]
    assert reconciled.checkpoints[0].status == DeploymentStepStatus.FAILED
    resumed = store.resume_job(job_id, now=NOW + timedelta(seconds=4))
    assert resumed.job.state == DeploymentJobState.CREATED
    assert resumed.attempt == 2


def test_diverged_remote_reconciliation_remains_fail_closed(tmp_path: Path) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job_id = _unknown_remote_job(store, suffix="d")
    reconciled = store.reconcile_remote_step(
        job_id,
        step_id="provision-host",
        outcome=DeploymentRemoteReconciliationOutcome.DIVERGED,
        outcome_sha256="e" * 64,
        artifact_refs=["artifact://deployment-jobs/observation.json"],
        now=NOW + timedelta(seconds=3),
    )

    assert reconciled.job.state == DeploymentJobState.BLOCKED
    assert (
        reconciled.recovery_disposition
        == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
    )
    assert reconciled.job.blockers == ["REMOTE_STATE_DIVERGED"]
    with pytest.raises(DeploymentJobStateConflict, match="requires reconciliation"):
        store.retry_job(job_id, now=NOW + timedelta(seconds=4))


def test_confirmed_step_failure_can_retry_with_new_attempt(tmp_path: Path) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "a" * 32,
    )
    store.start_step(
        job.job.job_id,
        step_id="preflight",
        state=DeploymentJobState.PREFLIGHT,
        now=NOW + timedelta(seconds=1),
    )
    failed = store.fail_step(
        job.job.job_id,
        step_id="preflight",
        remote_state_known=True,
        outcome_sha256="b" * 64,
        now=NOW + timedelta(seconds=2),
    )
    retried = store.retry_job(job.job.job_id, now=NOW + timedelta(seconds=3))

    assert failed.job.state == DeploymentJobState.FAILED
    assert failed.checkpoints[0].status == DeploymentStepStatus.FAILED
    assert retried.job.state == DeploymentJobState.CREATED
    assert retried.attempt == 2


def test_approval_decision_binds_principal_command_target_and_expiry(
    tmp_path: Path,
) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "4" * 32,
    )
    approval = store.request_approval(
        job.job.job_id,
        action=ApprovalAction.ACTIVATE_RELEASE,
        risk="R3",
        approver_principal="operator@example.com",
        summary="Activate signed release; password=must-not-leak",
        expires_at=NOW + timedelta(minutes=10),
        now=NOW + timedelta(seconds=1),
        approval_id="approval-" + "4" * 32,
    )
    assert "must-not-leak" not in approval.sanitized_summary

    with pytest.raises(ValueError, match="principal"):
        store.decide_approval(
            approval.approval_id,
            principal="other@example.com",
            approve=True,
            reason="wrong principal",
            now=NOW + timedelta(seconds=2),
        )
    decision = store.decide_approval(
        approval.approval_id,
        principal="operator@example.com",
        approve=True,
        reason="Release digest and Gate receipt reviewed.",
        now=NOW + timedelta(seconds=2),
        decision_id="decision-" + "4" * 32,
    )
    verified = store.verify_approval(
        approval.approval_id,
        job_id=job.job.job_id,
        target_id="wheeltec",
        command_sha256=job.job.command_sha256,
        action=ApprovalAction.ACTIVATE_RELEASE,
        now=NOW + timedelta(minutes=1),
    )
    assert verified == decision
    with pytest.raises(ValueError, match="does not authorize"):
        store.verify_approval(
            approval.approval_id,
            job_id=job.job.job_id,
            target_id="other-target",
            command_sha256=job.job.command_sha256,
            action=ApprovalAction.ACTIVATE_RELEASE,
            now=NOW + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="does not authorize"):
        store.verify_approval(
            approval.approval_id,
            job_id=job.job.job_id,
            target_id="wheeltec",
            command_sha256=job.job.command_sha256,
            action=ApprovalAction.ACTIVATE_RELEASE,
            now=NOW + timedelta(minutes=11),
        )

    with pytest.raises(ValidationError, match="cannot approve its own"):
        ApprovalRequest(
            approval_id="approval-" + "5" * 32,
            job_id=job.job.job_id,
            target_id="wheeltec",
            command_sha256=job.job.command_sha256,
            requester_principal="session-agent",
            approver_principal="session-agent",
            action=ApprovalAction.ACTIVATE_RELEASE,
            risk="R3",
            sanitized_summary="Self approval must fail.",
            requested_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )


def test_restart_recovery_distinguishes_remote_unknown_from_resumable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "jobs"
    store = DeploymentJobStore(root)
    remote = store.create_job(
        _command(idempotency_key="remote-recovery-request"),
        now=NOW,
        job_id="deployment-" + "6" * 32,
    )
    store.start_step(
        remote.job.job_id,
        step_id="remote-install",
        state=DeploymentJobState.BOOTSTRAPPING,
        remote=True,
        now=NOW + timedelta(seconds=1),
    )
    local = store.create_job(
        _command(
            target_id="local-robot",
            idempotency_key="local-recovery-request",
        ),
        now=NOW,
        job_id="deployment-" + "7" * 32,
    )
    store.start_step(
        local.job.job_id,
        step_id="connection",
        state=DeploymentJobState.CONNECTING,
        remote=False,
        now=NOW + timedelta(seconds=1),
    )

    recovered = DeploymentJobStore(root).recover_incomplete_jobs(
        now=NOW + timedelta(minutes=1)
    )
    by_job = {item.job_id: item for item in recovered}
    assert (
        by_job[remote.job.job_id].disposition
        == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
    )
    assert (
        by_job[local.job.job_id].disposition
        == DeploymentRecoveryDisposition.RESUMABLE
    )
    retried = store.retry_job(local.job.job_id, now=NOW + timedelta(minutes=2))
    assert retried.job.state == DeploymentJobState.CREATED
    assert retried.attempt == 2


def test_event_log_tamper_is_detected(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    store = DeploymentJobStore(root)
    job = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "8" * 32,
    )
    events_path = root / "jobs" / job.job.job_id / "events.jsonl"
    payload = events_path.read_text(encoding="utf-8")
    events_path.write_text(
        payload.replace("Deployment job created", "Tampered event"),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="record digest mismatch"):
        store.read_events(job.job.job_id)


def test_journal_replays_when_event_is_durable_before_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    store = DeploymentJobStore(root)
    first = store.create_job(
        _command(),
        now=NOW,
        job_id="deployment-" + "9" * 32,
    )
    second = store.append_event(
        first.job.job_id,
        event_type=DeploymentEventType.STATE_CHANGED,
        step_id="connection",
        summary="Connection established.",
        state=DeploymentJobState.CONNECTING,
        now=NOW + timedelta(seconds=1),
    )
    job_path = root / "jobs" / first.job.job_id / "job.json"
    job_path.write_text(first.model_dump_json(indent=2) + "\n", encoding="utf-8")

    recovered = DeploymentJobStore(root).load_job(first.job.job_id)

    assert recovered.job.state == DeploymentJobState.CONNECTING
    assert recovered.last_event_sequence == second.last_event_sequence == 2
    assert recovered.last_event_record_sha256 == second.last_event_record_sha256
