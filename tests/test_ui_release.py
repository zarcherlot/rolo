from typer.testing import CliRunner

from rolo.job_service import JobService
from rolo.jobs import JobStatus, JobStore
from rolo.product_cli import app
from rolo.query_adapter import ServiceJobQueryAdapter
from rolo.release_check import run_release_check
from rolo.ui_models import JobUiAdapter


def test_ui_adapter_produces_stable_list_and_detail_views(tmp_path):
    store = JobStore(tmp_path)
    job = store.create("target.inspect", "local:C:/robot")
    store.append_event(job.job_id, "STARTED", JobStatus.RUNNING, expected_revision=0)
    ui = JobUiAdapter(ServiceJobQueryAdapter(JobService(tmp_path)))
    assert ui.list_view().rows[0].job_id == job.job_id
    detail = ui.detail_view(job.job_id)
    assert detail.job.status == "RUNNING"
    assert detail.latest_event["event_type"] == "STARTED"
    missing = ui.safe_detail_view("job_missing")
    assert missing.status == "ERROR"
    assert missing.error.code == "JOB_NOT_FOUND"


def test_release_check_and_cli_smoke_pass():
    result = run_release_check()
    assert result.status == "PASS", result.failures
    assert "api-route:/v1/jobs" in result.checks
    assert "import:rolo.vis" in result.checks
    cli = CliRunner().invoke(app, ["release-check"])
    assert cli.exit_code == 0, cli.output
    tui = CliRunner().invoke(app, ["tui", "--once"])
    assert tui.exit_code == 0, tui.output
