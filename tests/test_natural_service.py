import json

import pytest
from typer.testing import CliRunner

from rolo.job_service import JobService
from rolo.jobs import JobStatus, JobStore
from rolo.product_cli import app
from rolo.query_adapter import ServiceJobQueryAdapter


def _intent(operation, **kwargs):
    from rolo.natural_language import NaturalLanguageIntent

    return NaturalLanguageIntent(operation=operation, source_text="test", **kwargs)


def _approval_plan(target: str = "ssh://robot.example/opt/rolo"):
    from rolo.target_ref import parse_target_ref
    from rolo.targets.models import (
        BootstrapPlanStatus,
        TargetBootstrapPlan,
        TargetConnectionState,
    )

    return TargetBootstrapPlan(
        target=parse_target_ref(target),
        assessment_state=TargetConnectionState.READY,
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        required_approvals=["target.bootstrap.execute"],
    )


def test_natural_service_dispatches_read_only_and_stage_operations(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from rolo.natural_language import NaturalLanguageOperation
    from rolo.natural_service import NaturalLanguageService

    jobs = SimpleNamespace(recover=lambda job_id: {"job_id": job_id})
    service = NaturalLanguageService(jobs)
    executor = SimpleNamespace(
        inspect=lambda: {"status": "READY"},
        plan_bootstrap=lambda: {"status": "PLAN"},
    )
    monkeypatch.setattr(
        "rolo.natural_service.create_target_executor", lambda *args, **kwargs: executor
    )
    assert service.execute(_intent(NaturalLanguageOperation.INSPECT, target=str(tmp_path))) == {
        "status": "READY"
    }
    assert service.execute(
        _intent(NaturalLanguageOperation.BOOTSTRAP_PLAN, target=str(tmp_path))
    ) == {"status": "PLAN"}

    class Stage:
        def __init__(self, settings, stage):
            self.stage = stage

        def build_task(self, robot_id):
            return {"stage": self.stage, "robot_id": robot_id}

        def run(self, robot_id, **kwargs):
            return {"stage": self.stage, "robot_id": robot_id, "confirmed": kwargs["confirmed"]}

    monkeypatch.setattr("rolo.natural_service.DownstreamStageService", Stage)
    monkeypatch.setattr("rolo.natural_service.get_settings", lambda: object())
    assert (
        service.execute(_intent(NaturalLanguageOperation.DIAGNOSE_PLAN, robot_id="r"))["stage"]
        == "diagnose"
    )
    assert (
        service.execute(_intent(NaturalLanguageOperation.VERIFY_PLAN, robot_id="r"))["stage"]
        == "verify"
    )
    assert service.execute(
        _intent(NaturalLanguageOperation.DIAGNOSE_RUN, robot_id="r"), confirmed=True
    )["confirmed"]
    assert (
        service.execute(
            _intent(NaturalLanguageOperation.VERIFY_RUN, robot_id="r", confirmed=False)
        )["stage"]
        == "verify"
    )
    assert (
        service.execute(_intent(NaturalLanguageOperation.JOB_RECOVER, job_id="job_abc"))["job_id"]
        == "job_abc"
    )


def test_natural_service_validates_mutating_requests_and_bootstrap_files(tmp_path, monkeypatch):
    from rolo.natural_language import NaturalLanguageOperation
    from rolo.natural_service import NaturalLanguageService
    from rolo.targets.approvals import request_bootstrap_approval

    service = NaturalLanguageService(type("Jobs", (), {"store": None})())
    adapt = _intent(NaturalLanguageOperation.ADAPT_START, target=str(tmp_path), robot_id="r")
    with pytest.raises(ValueError, match="explicit current-user confirmation"):
        service.execute(adapt)
    monkeypatch.setattr("rolo.natural_service.run_adapt_start", lambda **kwargs: kwargs)
    assert service.execute(adapt, confirmed=True)["robot_id"] == "r"
    with pytest.raises(ValueError, match="local workspaces"):
        service.execute(
            _intent(NaturalLanguageOperation.ADAPT_START, target="ssh://host/opt/r", robot_id="r"),
            confirmed=True,
        )

    plan = _approval_plan()
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(plan.model_dump_json(), encoding="utf-8")
    request = request_bootstrap_approval(plan, requested_by="alice")
    request_file = tmp_path / "request.json"
    request_file.write_text(request.model_dump_json(), encoding="utf-8")
    assert service.execute(
        _intent(NaturalLanguageOperation.BOOTSTRAP_REQUEST, plan_file=str(plan_file), actor="alice")
    )
    assert service.execute(
        _intent(
            NaturalLanguageOperation.BOOTSTRAP_APPROVE,
            plan_file=str(plan_file),
            request_file=str(request_file),
            actor="bob",
        )
    )

    with pytest.raises(ValueError, match="plan file and actor"):
        service.execute(_intent(NaturalLanguageOperation.BOOTSTRAP_REQUEST))
    with pytest.raises(ValueError, match="plan, request and actor"):
        service.execute(_intent(NaturalLanguageOperation.BOOTSTRAP_APPROVE))


def test_natural_service_bootstrap_execute_dry_run_and_input_guards(tmp_path):
    from rolo.natural_language import NaturalLanguageOperation
    from rolo.natural_service import NaturalLanguageService
    from rolo.targets.approvals import request_bootstrap_approval

    plan = _approval_plan()
    request = request_bootstrap_approval(plan, requested_by="alice")
    from rolo.targets.approvals import BootstrapApprovalDecision

    decision = BootstrapApprovalDecision(
        request_id=request.request_id,
        plan_sha256=request.plan_sha256,
        scope=request.scope,
        approved_by="bob",
        approved_at=request.created_at,
    )
    paths = {}
    for name, model in (("plan", plan), ("request", request), ("decision", decision)):
        path = tmp_path / f"{name}.json"
        path.write_text(model.model_dump_json(), encoding="utf-8")
        paths[name] = str(path)
    for key in ("manifest_file", "package_file", "verification_key_file", "known_hosts_file"):
        path = tmp_path / key
        path.write_text("placeholder", encoding="utf-8")
        paths[key] = str(path)
    intent = _intent(
        NaturalLanguageOperation.BOOTSTRAP_EXECUTE,
        plan_file=paths["plan"],
        request_file=paths["request"],
        decision_file=paths["decision"],
        manifest_file=paths["manifest_file"],
        package_file=paths["package_file"],
        verification_key_file=paths["verification_key_file"],
        known_hosts_file=paths["known_hosts_file"],
        execute=False,
    )
    result = NaturalLanguageService(type("Jobs", (), {"store": None})()).execute(intent)
    assert result["status"] == "BOOTSTRAP_EXECUTION_READY"
    assert result["mutation_started"] is False

    with pytest.raises(ValueError, match="requires all input files"):
        NaturalLanguageService(type("Jobs", (), {"store": None})()).execute(
            _intent(NaturalLanguageOperation.BOOTSTRAP_EXECUTE, execute=False)
        )


def test_natural_execute_uses_canonical_inspect_service(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    result = CliRunner().invoke(
        app,
        ["natural", f"检查目标 {tmp_path}", "--execute"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "INTENT_EXECUTED"


def test_natural_mutation_requires_explicit_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    request = f"适配 {tmp_path} robot=demo"

    result = CliRunner().invoke(app, ["natural", request, "--execute"])

    assert result.exit_code != 0
    assert "explicit current-user confirmation" in result.output


def test_query_adapter_reuses_job_service_models(tmp_path):
    store = JobStore(tmp_path)
    job = store.create("target.inspect", "local:C:/robot")
    store.append_event(job.job_id, "STARTED", JobStatus.RUNNING, expected_revision=0)
    adapter = ServiceJobQueryAdapter(JobService(tmp_path))
    assert adapter.list().items[0].job_id == job.job_id
    assert adapter.recover(job.job_id).latest_event.event_type == "STARTED"
    assert adapter.events(job.job_id).total == 1
