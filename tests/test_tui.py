from io import StringIO

from typer.testing import CliRunner

from rolo.job_service import JobService
from rolo.jobs import JobStore
from rolo.product_cli import app
from rolo.query_adapter import ServiceJobQueryAdapter
from rolo.tui import RoloTui
from rolo.ui_models import JobUiAdapter


def _tui(tmp_path):
    return RoloTui(JobUiAdapter(ServiceJobQueryAdapter(JobService(tmp_path))))


def test_tui_renders_empty_job_list_once(tmp_path):
    output = StringIO()
    _tui(tmp_path).run(output_stream=output, once=True)
    assert "Rolo TUI" in output.getvalue()
    assert "Jobs: 0" in output.getvalue()


def test_tui_lists_jobs_and_maps_natural_language_without_execution(tmp_path):
    store = JobStore(tmp_path)
    store.create("target.inspect", "local:C:/robot")
    output = StringIO()
    _tui(tmp_path).run(
        input_stream=StringIO("list\nask 检查目标 C:/robot\nquit\n"),
        output_stream=output,
    )
    text = output.getvalue()
    assert "target.inspect" in text
    assert "Intent: target.inspect" in text
    assert "TUI is read-only" in text
    assert "bye" in text


def test_product_cli_tui_once_is_available(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    result = CliRunner().invoke(app, ["tui", "--once"])
    assert result.exit_code == 0, result.output
    assert "Rolo TUI" in result.output
