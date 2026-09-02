from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from rolo.agent_tools import ToolPlanStep, build_tool_plan
from rolo.core.config import get_settings
from rolo.product_cli import app


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "ROLO_CONFIG_DIR": str(tmp_path / "config"),
        "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
    }


def test_profile_to_surface_and_plan_is_one_cli_chain(tmp_path: Path) -> None:
    runner = CliRunner()
    env = _env(tmp_path)
    get_settings.cache_clear()
    try:
        initialized = runner.invoke(
            app,
            [
                "target",
                "profile",
                "init",
                str(tmp_path),
                "--robot",
                "localbot",
            ],
            env=env,
        )
        assert initialized.exit_code == 0, initialized.output

        surface = runner.invoke(
            app, ["target", "tool-surface", "--profile", "localbot"], env=env
        )
        assert surface.exit_code == 0, surface.output
        surface_payload = json.loads(surface.output)
        assert surface_payload["status"] == "TOOL_SURFACE_READY"
        assert surface_payload["conformance"]["status"] == "PASS"
        descriptor = next(
            item
            for item in surface_payload["tools"]
            if item["tool_id"] == "native.linux.host.inspect"
        )
        session = surface_payload["session"]
        plan = build_tool_plan(
            goal="observe local host",
            target_id="localbot",
            session_id=session["session_id"],
            session_nonce=session["nonce"],
            surface_digest=session["native_catalog_sha256"],
            steps=[
                ToolPlanStep(
                    tool_id=descriptor["tool_id"],
                    arguments={"mode": "status"},
                    expected_observation="host status",
                )
            ],
        )
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        executed = runner.invoke(
            app,
            ["target", "tool-plan", "--profile", "localbot", str(plan_path)],
            env=env,
        )
        assert executed.exit_code == 0, executed.output
        result_payload = json.loads(executed.output)
        assert result_payload["status"] == "TOOL_PLAN_EXECUTED"
        assert result_payload["conformance"]["status"] == "PASS"
        assert result_payload["results"][0]["evidence_refs"]
    finally:
        get_settings.cache_clear()
