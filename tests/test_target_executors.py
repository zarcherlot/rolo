from __future__ import annotations

import json
import shlex
import sys
import time
from pathlib import Path
from threading import Event, Thread

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.product_cli import app
from rolo.target_ref import LocalTargetRef, SshTargetRef, parse_target_ref
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.executor import (
    CommandResult,
    LocalTargetExecutor,
    SshTargetExecutor,
    SubprocessCommandRunner,
    quote_remote_argv,
)
from rolo.targets.models import (
    BootstrapPlanStatus,
    CompanionStatus,
    TargetConnectionState,
    TargetRisk,
)


class FakeSshRunner:
    def __init__(self, *, companion_installed: bool = False) -> None:
        self.companion_installed = companion_installed
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: list[str], *, timeout_s: float) -> CommandResult:
        del timeout_s
        call = tuple(argv)
        self.calls.append(call)
        if call[-2:] == ("uname", "-s"):
            return CommandResult(call, 0, "Linux\n", "")
        if call[-2:] == ("uname", "-m"):
            return CommandResult(call, 0, "aarch64\n", "")
        if call[-3:-1] == ("test", "-d"):
            return CommandResult(call, 0, "", "")
        if call[-3:] == ("command", "-v", "rolo-target"):
            return CommandResult(call, 0 if self.companion_installed else 1, "", "")
        raise AssertionError(f"unexpected SSH probe: {call}")


def _ssh_target() -> SshTargetRef:
    target = parse_target_ref("ssh://robot@example.test:2222/home/robot/wheeltec_ws")
    assert isinstance(target, SshTargetRef)
    return target


def test_local_executor_conformance_is_ready_without_bootstrap_mutation(tmp_path: Path) -> None:
    target = LocalTargetRef(workspace=tmp_path)
    executor = LocalTargetExecutor(target)

    assessment = executor.inspect()
    plan = executor.plan_bootstrap(assessment)

    assert assessment.state == TargetConnectionState.READY
    assert assessment.companion == CompanionStatus.NOT_REQUIRED
    assert plan.status == BootstrapPlanStatus.READY
    assert all(step.risk == TargetRisk.READ_ONLY for step in plan.steps)
    assert plan.required_approvals == []


def test_ssh_executor_does_not_connect_without_a_pinned_host_key() -> None:
    runner = FakeSshRunner()
    executor = SshTargetExecutor(_ssh_target(), known_hosts=None, runner=runner)

    assessment = executor.inspect()
    plan = executor.plan_bootstrap(assessment)

    assert assessment.state == TargetConnectionState.HOST_KEY_REQUIRED
    assert assessment.host_key_pinned is False
    assert plan.status == BootstrapPlanStatus.BLOCKED
    assert runner.calls == []


def test_ssh_executor_uses_only_fixed_read_only_probes_and_types_mutation_plan(
    tmp_path: Path,
) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("example.test ssh-ed25519 AAAATEST\n", encoding="utf-8")
    runner = FakeSshRunner()
    executor = SshTargetExecutor(
        _ssh_target(),
        known_hosts=known_hosts,
        runner=runner,
    )

    assessment = executor.inspect()
    plan = executor.plan_bootstrap(assessment)

    assert assessment.state == TargetConnectionState.READY
    assert assessment.platform == "Linux"
    assert assessment.architecture == "aarch64"
    assert assessment.companion == CompanionStatus.MISSING
    assert plan.status == BootstrapPlanStatus.APPROVAL_REQUIRED
    assert plan.required_approvals == ["target.bootstrap.execute"]
    assert [step.risk for step in plan.steps].count(TargetRisk.HOST_MUTATION) == 1
    dumped = plan.model_dump(mode="json")
    assert "command" not in json.dumps(dumped)
    for call in runner.calls:
        assert "BatchMode=yes" in call
        assert "StrictHostKeyChecking=yes" in call
        assert f"UserKnownHostsFile={known_hosts.resolve()}" in call
        assert "GlobalKnownHostsFile=none" in call
        assert "ClearAllForwardings=yes" in call
        assert "ForwardAgent=no" in call
        assert "sudo" not in call
        assert "sh" not in call
        assert "bash" not in call


def test_ssh_executor_needs_no_mutation_when_companion_exists(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("example.test ssh-ed25519 AAAATEST\n", encoding="utf-8")
    executor = SshTargetExecutor(
        _ssh_target(),
        known_hosts=known_hosts,
        runner=FakeSshRunner(companion_installed=True),
    )

    plan = executor.plan_bootstrap()

    assert plan.status == BootstrapPlanStatus.READY
    assert plan.required_approvals == []
    assert all(step.risk == TargetRisk.READ_ONLY for step in plan.steps)


def test_ssh_transport_uses_pinned_identity_file(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("example.test ssh-ed25519 AAAATEST\n", encoding="utf-8")
    identity = tmp_path / "id_ed25519"
    identity.write_text("private-key-placeholder\n", encoding="utf-8")

    class CaptureRunner:
        def __init__(self) -> None:
            self.argv: list[str] = []

        def run(self, argv: list[str], *, timeout_s: float) -> CommandResult:
            del timeout_s
            self.argv = argv
            return CommandResult(tuple(argv), 0)

    runner = CaptureRunner()
    transport = SubprocessBootstrapTransport(
        _ssh_target(), known_hosts=known_hosts, identity_file=identity, runner=runner
    )
    transport.execute(["uname", "-a"], timeout_s=1)
    assert "IdentitiesOnly=yes" in runner.argv
    assert "-i" in runner.argv
    assert str(identity.resolve()) in runner.argv


def test_product_cli_exposes_local_target_inspection_and_plan(tmp_path: Path) -> None:
    runner = CliRunner()

    inspected = runner.invoke(app, ["target", "inspect", str(tmp_path)])
    planned = runner.invoke(app, ["target", "bootstrap-plan", str(tmp_path)])

    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.output)["state"] == "READY"
    assert planned.exit_code == 0, planned.output
    assert json.loads(planned.output)["status"] == "READY"


def test_ssh_target_workspace_rejects_shell_metacharacters_and_traversal() -> None:
    for value in (
        "ssh://robot@example.test/home/robot/work;touch-x",
        "ssh://robot@example.test/home/robot/../etc",
        "ssh://robot@example.test/home/robot/work%20space",
    ):
        try:
            parse_target_ref(value)
        except ValueError as exc:
            assert "workspace path" in str(exc)
        else:
            raise AssertionError(f"unsafe SSH workspace was accepted: {value}")


def test_target_ref_rejects_non_ssh_remote_uri() -> None:
    with pytest.raises(ValueError, match="must use an ssh:// URI"):
        parse_target_ref("https://example.test/home/robot/workspace")


def test_ssh_target_model_rejects_directly_constructed_unsafe_identity() -> None:
    with pytest.raises(ValidationError, match="SSH user contains unsupported characters"):
        SshTargetRef(
            host="example.test",
            user="robot;touch-x",
            workspace="/home/robot/workspace",
        )


@pytest.mark.parametrize(
    "remote_argv",
    [
        ["stat", "-c", "%d %i %Z", "/home/robot/wheeltec_ws"],
        ["printf", "space value", "quote'and\"double", "glob*;$(touch SHOULD_NOT_RUN)"],
        ["", "leading-dash-is-an-argument", "$(printf injected)"],
    ],
)
def test_remote_argv_is_shell_safe_and_round_trips(remote_argv: list[str]) -> None:
    encoded = quote_remote_argv(remote_argv)

    assert shlex.split(" ".join(encoded), comments=False, posix=True) == remote_argv
    for value, encoded_value in zip(remote_argv, encoded, strict=True):
        if any(character in value for character in " '\";$*()") or not value:
            assert encoded_value != value


def test_remote_argv_rejects_nul() -> None:
    with pytest.raises(ValueError, match="NUL"):
        quote_remote_argv(["printf", "bad\x00value"])


def test_subprocess_command_runner_cancels_inflight_process() -> None:
    cancel = Event()
    result: list[CommandResult] = []

    def run() -> None:
        result.append(
            SubprocessCommandRunner().run(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout_s=60,
                cancel_event=cancel,
            )
        )

    thread = Thread(target=run)
    thread.start()
    time.sleep(0.1)
    cancel.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert result and result[0].returncode == 130
