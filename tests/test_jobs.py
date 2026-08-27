from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from rolo.jobs import JobStatus, JobStore
from rolo.product_cli import app
from rolo.target_ref import parse_target_ref
from rolo.targets.approvals import BootstrapApprovalDecision, BootstrapApprovalRequest
from rolo.targets.bootstrap import BootstrapExecutionResult
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan


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


def test_product_cli_exposes_plan_bound_bootstrap_request_and_approval(tmp_path):
    plan = TargetBootstrapPlan(
        target=parse_target_ref("ssh://robot@example.test/home/robot/workspace"),
        assessment_state="READY",
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        required_approvals=["target.bootstrap.execute"],
    )
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(plan.model_dump_json(), encoding="utf-8")
    runner = CliRunner()
    requested = runner.invoke(
        app,
        ["target", "bootstrap-request", str(plan_file), "--requested-by", "agent"],
    )
    assert requested.exit_code == 0, requested.output
    request_file = tmp_path / "request.json"
    request_file.write_text(requested.output, encoding="utf-8")
    approved = runner.invoke(
        app,
        [
            "target",
            "bootstrap-approve",
            str(plan_file),
            str(request_file),
            "--approved-by",
            "operator",
        ],
    )
    assert approved.exit_code == 0, approved.output
    assert __import__("json").loads(approved.output)["status"] == "APPROVED"


def test_run_bootstrap_job_records_completion_checkpoint(tmp_path, monkeypatch):
    target = parse_target_ref("ssh://robot@example.test/home/robot/workspace")
    plan = TargetBootstrapPlan(
        target=target,
        assessment_state="READY",
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        required_approvals=["target.bootstrap.execute"],
    )
    request = BootstrapApprovalRequest(
        request_id="bar-" + "a" * 32,
        plan_sha256="b" * 64,
        scope="target.bootstrap.execute",
        requested_by="agent",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )
    decision = BootstrapApprovalDecision(
        request_id=request.request_id,
        plan_sha256=request.plan_sha256,
        scope=request.scope,
        approved_by="operator",
        approved_at=datetime.now(timezone.utc),
    )
    expected = BootstrapExecutionResult(
        status="SUCCEEDED",
        target=target,
        plan_sha256=request.plan_sha256,
        approval_request_id=request.request_id,
        package_id="rolo-target",
        package_version="1.0.0",
        package_sha256="c" * 64,
        remote_package_path="/tmp/rolo-target-c.pkg",
    )
    monkeypatch.setattr("rolo.jobs.execute_bootstrap", lambda *args, **kwargs: expected)
    from rolo.jobs import run_bootstrap_job

    job, result = run_bootstrap_job(
        JobStore(tmp_path),
        plan,
        request,
        decision,
        manifest_path=tmp_path / "manifest.json",
        package_path=tmp_path / "package.pkg",
        verification_key=b"key",
        transport=object(),
    )
    loaded, events, checkpoints = JobStore(tmp_path).load(job.job_id)
    assert result == expected
    assert loaded.status == JobStatus.SUCCEEDED
    assert events[-1].event_type == "BOOTSTRAP_COMPLETED"
    assert checkpoints[-1].state["phase"] == "completed"
    repeated_job, repeated_result = run_bootstrap_job(
        JobStore(tmp_path),
        plan,
        request,
        decision,
        manifest_path=tmp_path / "manifest.json",
        package_path=tmp_path / "package.pkg",
        verification_key=b"key",
        transport=object(),
    )
    assert repeated_job.job_id == job.job_id
    assert repeated_result == expected
