from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from rolo.core.config import get_settings
from rolo.product_cli import app
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
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


def test_rolo_adapt_requires_local_project_root_for_ssh() -> None:
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "ssh://robot@example.test/home/robot/workspace",
            "--robot",
            "remote_robot",
            "--discover-only",
        ],
        # Rich reads COLUMNS directly and truncates UsageError text in narrow CI logs.
        # Keep this assertion about the complete actionable message deterministic.
        env={"COLUMNS": "120"},
    )

    assert result.exit_code == 2
    assert "SSH Adapt requires --project-root" in result.output


def test_rolo_adapt_uses_an_approved_ssh_deployment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "config"
    deployment_path = config_root / "target-evidence" / "remote_robot.json"
    deployment_path.parent.mkdir(parents=True)
    deployment_path.write_text("{}", encoding="utf-8")
    project = tmp_path / "robot-project"
    project.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "rolo.product_cli.load_deployment",
        lambda path: SimpleNamespace(
            mode=EvidenceDeploymentMode.REMOTE,
            ssh_target="robot@example.test",
            ssh_port=2222,
        ),
    )

    class Result:
        status = "DISCOVERY_COMPLETE"

        def model_dump(self, *, mode: str) -> dict[str, str]:
            del mode
            return {"status": self.status, "robot_id": "remote_robot"}

    def fake_run_adapt_start(**kwargs: object) -> Result:
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr("rolo.product_cli.run_adapt_start", fake_run_adapt_start)
    env = {
        "ROLO_CONFIG_DIR": str(config_root),
        "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
    }
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "ssh://robot@example.test:2222/home/robot/workspace",
            "--robot",
            "remote_robot",
            "--project-root",
            str(project),
            "--discover-only",
        ],
        env=env,
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert captured["evidence_mode"] == EvidenceDeploymentMode.REMOTE
    assert captured["project_root"] == project.resolve()
    assert captured["robot_id"] == "remote_robot"


@pytest.mark.parametrize(
    ("target", "deployment_target", "deployment_port", "message"),
    [
        (
            "ssh://robot@other.example.test:2222/home/robot/workspace",
            "robot@example.test",
            2222,
            "SSH target does not match",
        ),
        (
            "ssh://robot@example.test:2200/home/robot/workspace",
            "robot@example.test",
            2222,
            "SSH target port does not match",
        ),
    ],
)
def test_rolo_adapt_rejects_ssh_deployment_pin_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    deployment_target: str,
    deployment_port: int,
    message: str,
) -> None:
    config_root = tmp_path / "config"
    deployment_path = config_root / "target-evidence" / "remote_robot.json"
    deployment_path.parent.mkdir(parents=True)
    deployment_path.write_text("{}", encoding="utf-8")
    project = tmp_path / "robot-project"
    project.mkdir()
    called = False

    monkeypatch.setattr(
        "rolo.product_cli.load_deployment",
        lambda path: SimpleNamespace(
            mode=EvidenceDeploymentMode.REMOTE,
            ssh_target=deployment_target,
            ssh_port=deployment_port,
        ),
    )

    def fail_if_called(**kwargs: object) -> None:
        del kwargs
        nonlocal called
        called = True

    monkeypatch.setattr("rolo.product_cli.run_adapt_start", fail_if_called)
    env = {
        "ROLO_CONFIG_DIR": str(config_root),
        "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
    }
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            target,
            "--robot",
            "remote_robot",
            "--project-root",
            str(project),
            "--discover-only",
        ],
        env=env,
    )
    get_settings.cache_clear()

    assert result.exit_code == 2
    assert message in result.output
    assert called is False


def test_rolo_run_exposes_explicit_console_launcher() -> None:
    result = CliRunner().invoke(app, ["run", "--once"])

    assert result.exit_code == 0, result.output
    assert "natural-language console" in result.output
    assert "Type a request" in result.output


def test_rolo_adapt_requires_confirmation_for_noninteractive_agent_run(tmp_path: Path) -> None:
    project = tmp_path / "robot-project"
    project.mkdir()

    result = CliRunner().invoke(
        app,
        ["adapt", str(project), "--robot", "robot-1", "--active-probe", "none"],
        env={
            "ROLO_CONFIG_DIR": str(tmp_path / "config"),
            "ROLO_ARTIFACT_DIR": str(tmp_path / "artifacts"),
            "ROLO_OUTPUT_DIR": str(tmp_path / "output"),
        },
    )

    assert result.exit_code == 2
    assert json.loads(result.output)["status"] == "AUTHORIZATION_REQUIRED"
