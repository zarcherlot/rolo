import json

import pytest
from typer.testing import CliRunner

from rolo.natural_language import NaturalLanguageOperation, parse_natural_language
from rolo.product_cli import app


def test_natural_language_maps_only_explicit_inspect_plan_and_recover_intents():
    assert parse_natural_language("检查目标 ssh://robot@example.test/home/robot/ws").operation == (
        NaturalLanguageOperation.INSPECT
    )
    assert parse_natural_language("生成 bootstrap 计划 C:/robot/ws").operation == (
        NaturalLanguageOperation.BOOTSTRAP_PLAN
    )
    assert parse_natural_language("恢复任务 job_abcdef0123456789").operation == (
        NaturalLanguageOperation.JOB_RECOVER
    )


def test_natural_language_rejects_ambiguous_or_command_like_text():
    for text in ("帮我处理一下目标", "检查目标 C:/robot && whoami"):
        with pytest.raises(ValueError):
            parse_natural_language(text)


def test_product_cli_lists_and_recovers_job_without_resuming_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    runner = CliRunner()
    created = runner.invoke(app, ["target", "inspect", str(tmp_path), "--job"])
    assert created.exit_code == 0, created.output
    job_id = json.loads(created.output)["job_id"]
    listed = runner.invoke(app, ["job", "list"])
    recovered = runner.invoke(app, ["job", "recover", job_id])
    assert listed.exit_code == 0, listed.output
    assert recovered.exit_code == 0, recovered.output
    assert json.loads(listed.output)["items"][0]["job_id"] == job_id
    recovery = json.loads(recovered.output)
    assert recovery["resumable"] is False
    assert recovery["limitations"]
