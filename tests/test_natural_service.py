import json

from typer.testing import CliRunner

from rolo.job_service import JobService
from rolo.jobs import JobStatus, JobStore
from rolo.product_cli import app
from rolo.query_adapter import ServiceJobQueryAdapter


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
