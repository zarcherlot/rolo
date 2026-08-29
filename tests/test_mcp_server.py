from __future__ import annotations

import json
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.mcp_server import handle
from rolo.stages.agent_runner import StageAgentRunner, StageAgentTask


def test_mcp_lists_downstream_tools_and_pending_requests(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    request_path = (
        artifact_root / "diagnose" / "robot-1" / "authorization" / "requests" / "auth.json"
    )
    request_path.parent.mkdir(parents=True)
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "rolo-authorization-request/v1",
                "request_id": "auth-1",
                "status": "PENDING",
                "stage": "diagnose",
                "robot_id": "robot-1",
                "plan_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()

    listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "rolo_stage_auth_requests" in names

    result = handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "rolo_stage_auth_requests", "arguments": {}},
        }
    )
    payload = result["result"]["structuredContent"]
    assert payload["requests"][0]["request_id"] == "auth-1"
    get_settings.cache_clear()


def test_mcp_stage_cancel_persists_cancelled_status(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()

    class Executor:
        def execute_stage(self, task, *, workspace, on_output=None):
            del task, workspace, on_output
            return {}

    task = StageAgentTask(
        stage="diagnose",
        robot_id="robot-1",
        task="diagnose",
        output_contract="robot-diagnosis-handoff/v1",
        provider="fake",
        executor="fake",
        plan_sha256="a" * 64,
    )
    pending = StageAgentRunner(ArtifactStore(artifact_root), Executor()).run(
        task, workspace=tmp_path / "workspace", confirmed=False
    )
    result = handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "rolo_stage_cancel",
                "arguments": {
                    "stage": "diagnose",
                    "robot_id": "robot-1",
                    "run_id": pending.run_id,
                },
            },
        }
    )
    assert result["result"]["structuredContent"]["status"] == "CANCELLED"
    get_settings.cache_clear()
