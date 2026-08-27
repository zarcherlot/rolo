import json

import pytest
from typer.testing import CliRunner

from rolo.natural_language import (
    NaturalLanguageExecutionAdapter,
    NaturalLanguageOperation,
    intent_to_argv,
    parse_natural_language,
)
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
    request = parse_natural_language("申请 bootstrap 审批 C:/tmp/plan.json 由 agent")
    assert request.operation == NaturalLanguageOperation.BOOTSTRAP_REQUEST
    assert intent_to_argv(request)[0:2] == ["target", "bootstrap-request"]
    approval = parse_natural_language(
        "批准 bootstrap C:/tmp/plan.json C:/tmp/request.json by operator"
    )
    assert approval.operation == NaturalLanguageOperation.BOOTSTRAP_APPROVE
    assert approval.actor == "operator"
    execute = parse_natural_language(
        "执行 bootstrap plan.json request.json decision.json manifest.json "
        "package.pkg key.bin known_hosts"
    )
    assert execute.operation == NaturalLanguageOperation.BOOTSTRAP_EXECUTE
    assert execute.execute is False
    assert "--execute" not in intent_to_argv(execute)
    adapter = NaturalLanguageExecutionAdapter(
        {NaturalLanguageOperation.BOOTSTRAP_APPROVE: lambda value: value.operation.value}
    )
    assert adapter.dispatch(approval) == "target.bootstrap-approve"


def test_natural_language_maps_local_adapt_request():
    intent = parse_natural_language(
        "适配 ./robot_ws，机器人叫 wheeltec，URDF ./robot.urdf，先只做发现"
    )

    assert intent.operation == NaturalLanguageOperation.ADAPT_START
    assert intent.robot_id == "wheeltec"
    assert intent.urdf == "./robot.urdf"
    assert intent.run_agent is False
    assert intent_to_argv(intent) == [
        "adapt",
        "./robot_ws",
        "--robot",
        "wheeltec",
        "--urdf",
        "./robot.urdf",
        "--discover-only",
    ]


def test_natural_language_rejects_ambiguous_or_command_like_text():
    for text in ("帮我处理一下目标", "检查目标 C:/robot && whoami"):
        with pytest.raises(ValueError):
            parse_natural_language(text)


def test_natural_language_adapter_fails_closed_for_unregistered_or_unattributed_approval():
    inspect = parse_natural_language("检查目标 C:/robot/ws")
    with pytest.raises(ValueError, match="no handler"):
        NaturalLanguageExecutionAdapter({}).dispatch(inspect)
    approval = parse_natural_language("批准 bootstrap C:/tmp/plan.json C:/tmp/request.json")
    with pytest.raises(ValueError, match="explicit actor"):
        NaturalLanguageExecutionAdapter(
            {NaturalLanguageOperation.BOOTSTRAP_APPROVE: lambda value: value}
        ).dispatch(approval)


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


def test_product_cli_natural_returns_canonical_argv_without_execution():
    result = CliRunner().invoke(
        app, ["natural", "检查目标 ssh://robot@example.test/home/robot/ws"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "INTENT_PARSED"
    assert payload["argv"] == ["target", "inspect", "ssh://robot@example.test/home/robot/ws"]
