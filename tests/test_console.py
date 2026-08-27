from io import StringIO

from typer.testing import CliRunner

from rolo.console import RoloConsole
from rolo.job_service import JobService
from rolo.natural_service import NaturalLanguageService
from rolo.product_cli import app
from rolo.query_adapter import ServiceJobQueryAdapter
from rolo.ui_models import JobUiAdapter


def _console(tmp_path, *, input_text: str) -> RoloConsole:
    jobs = JobService(tmp_path)
    return RoloConsole(
        NaturalLanguageService(jobs),
        JobUiAdapter(ServiceJobQueryAdapter(jobs)),
        input_stream=StringIO(input_text),
        output_stream=StringIO(),
    )


def test_console_maps_adapt_request_and_requires_confirmation(tmp_path):
    console = _console(
        tmp_path,
        input_text="适配 ./robot_ws，机器人叫 wheeltec，先只做发现\nn\n",
    )
    console.run()
    output = console.output_stream.getvalue()

    assert "Intent: adapt.start" in output
    assert "uv run rolo adapt ./robot_ws --robot wheeltec --discover-only" in output
    assert "cancelled" in output


def test_console_executes_read_only_inspection(tmp_path):
    console = _console(tmp_path, input_text=f"检查目标 {tmp_path}\n/quit\n")
    console.run()
    output = console.output_stream.getvalue()

    assert '"state"' in output
    assert "bye" in output


def test_rolo_without_arguments_keeps_non_tty_invocation_safe():
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
