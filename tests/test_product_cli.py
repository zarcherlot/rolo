from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest
from typer.testing import CliRunner

from rolo.core.config import get_settings
from rolo.product_cli import app
from rolo.target_ref import LocalTargetRef, SshTargetRef, parse_target_ref


def test_target_ref_normalizes_a_relative_local_workspace(tmp_path: Path) -> None:
    target = parse_target_ref("robot-project", cwd=tmp_path)

    assert target == LocalTargetRef(workspace=(tmp_path / "robot-project").resolve())


def test_target_ref_parses_a_credential_free_ssh_uri() -> None:
    target = parse_target_ref("ssh://robot@example.test:2222/home/robot/wheeltec_ws")

    assert target == SshTargetRef(
        host="example.test",
        user="robot",
        port=2222,
        workspace=PurePosixPath("/home/robot/wheeltec_ws"),
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("ssh://robot:secret@example.test/workspace", "must not contain a password"),
        ("ssh://example.test", "absolute workspace path"),
        ("ssh:///workspace", "must include a host"),
        ("ssh://example.test/workspace?identity=x", "query parameters"),
    ],
)
def test_target_ref_rejects_unsafe_or_incomplete_ssh_uris(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_target_ref(value)


def test_rolo_adapt_runs_the_existing_local_journey(tmp_path: Path) -> None:
    project = tmp_path / "robot-project"
    project.mkdir()
    (project / "README.md").write_text("# Robot\n", encoding="utf-8")
    env = {
        "ROLO_CONFIG_DIR": str(tmp_path / "config"),
        "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
        "WIKI_INSIGHTS_AGENT_ENABLED": "false",
        "WIKI_POLISH_ENABLED": "false",
    }
    get_settings.cache_clear()

    result = CliRunner().invoke(
        app,
        [
            "adapt",
            str(project),
            "--robot",
            "product_robot",
            "--active-probe",
            "none",
            "--discover-only",
        ],
        env=env,
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "robot-adapt-journey/v2"
    assert payload["status"] == "DISCOVERY_COMPLETE"
    assert payload["robot_id"] == "product_robot"
    assert payload["evidence"]["project_root"] == str(project.resolve())


def test_rolo_adapt_fails_closed_for_ssh_until_bootstrap_is_implemented() -> None:
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "ssh://robot@example.test/home/robot/workspace",
            "--robot",
            "remote_robot",
            "--discover-only",
        ],
    )

    assert result.exit_code == 2
    assert "SSH target bootstrap is not available yet" in result.output
