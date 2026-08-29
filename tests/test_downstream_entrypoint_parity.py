from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from rolo.api import app as api_app
from rolo.cli import app as cli_app
from rolo.core.config import get_settings
from rolo.mcp_server import handle
from rolo.stages.agent_runner import StageAgentRun


def _run(stage: str) -> StageAgentRun:
    now = datetime.now(timezone.utc)
    return StageAgentRun(
        stage=stage,
        robot_id="demo_diff",
        run_id=f"parity-{stage}",
        status="SUCCEEDED",
        provider="fake",
        executor="fake",
        model=None,
        task_ref=f"artifact://{stage}/demo_diff/runs/parity/task.json",
        started_at=now,
        completed_at=now,
    )


@pytest.mark.parametrize("stage", ["diagnose", "verify"])
def test_cli_mcp_http_share_the_same_fake_stage_service_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(Path("tests/fixtures")))
    monkeypatch.setenv("CODING_AGENT_PROVIDER", "fake")
    monkeypatch.setenv("CODING_AGENT_EXECUTOR", "fake")
    get_settings.cache_clear()
    calls: list[tuple[str, str, bool, str | None]] = []

    def fake_run(self, robot_id: str, *, confirmed: bool, authorization_ref=None, on_output=None):
        del on_output
        calls.append((self.stage, robot_id, confirmed, authorization_ref))
        return _run(self.stage)

    monkeypatch.setattr("rolo.stages.downstream.DownstreamStageService.run", fake_run)

    command = [stage, "run", "--robot", "demo_diff", "--confirm"]
    cli_response = CliRunner().invoke(cli_app, command)
    assert cli_response.exit_code == 0, cli_response.output
    cli_payload = json.loads(cli_response.output)

    mcp_response = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": f"rolo_{stage}_run",
                "arguments": {"robot_id": "demo_diff", "confirmed": True},
            },
        }
    )
    mcp_payload = mcp_response["result"]["structuredContent"]

    with TestClient(api_app) as client:
        http_response = client.post(
            f"/v1/robots/demo_diff/{stage}/run", json={"confirmed": True}
        )
    assert http_response.status_code == 200, http_response.text
    http_payload = http_response.json()

    for payload in (cli_payload, mcp_payload, http_payload):
        assert payload["stage"] == stage
        assert payload["robot_id"] == "demo_diff"
        assert payload["provider"] == "fake"
        assert payload["executor"] == "fake"
        assert payload["status"] == "SUCCEEDED"
    assert calls == [(stage, "demo_diff", True, None)] * 3
    get_settings.cache_clear()

