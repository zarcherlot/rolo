from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rolo.core.hashing import sha256_file
from rolo.target_ref import SshTargetRef, parse_target_ref
from rolo.targets.approvals import approve_bootstrap, request_bootstrap_approval
from rolo.targets.bootstrap import (
    CommandResult,
    SubprocessBootstrapTransport,
    execute_bootstrap,
)
from rolo.targets.models import (
    BootstrapAction,
    BootstrapPlanStatus,
    TargetBootstrapPlan,
    TargetBootstrapStep,
    TargetRisk,
)
from rolo.targets.signing import sign_companion_manifest


class FakeTransport:
    def __init__(self, target: SshTargetRef, *, fail_action: str | None = None) -> None:
        self.target = target
        self.fail_action = fail_action
        self.uploads: list[tuple[Path, str]] = []
        self.commands: list[tuple[str, ...]] = []

    def upload(self, local_path: Path, remote_path: str, *, timeout_s: float) -> CommandResult:
        del timeout_s
        self.uploads.append((local_path, remote_path))
        return CommandResult(
            ("scp",),
            1 if self.fail_action == "upload" else 0,
            stderr="upload denied",
        )

    def execute(self, remote_argv: list[str], *, timeout_s: float) -> CommandResult:
        del timeout_s
        command = tuple(remote_argv)
        self.commands.append(command)
        if command[:2] == ("sudo", "-n"):
            action = "install"
        elif command[:2] == ("rolo-target", "--version"):
            action = "health"
        else:
            action = "cleanup"
        return CommandResult(
            command,
            1 if self.fail_action == action else 0,
            stderr=f"{action} denied",
        )


def _target() -> SshTargetRef:
    target = parse_target_ref("ssh://robot@example.test/home/robot/workspace")
    assert isinstance(target, SshTargetRef)
    return target


def _plan() -> TargetBootstrapPlan:
    return TargetBootstrapPlan(
        target=_target(),
        assessment_state="READY",
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        steps=[
            TargetBootstrapStep(
                action=BootstrapAction.INSTALL_COMPANION,
                risk=TargetRisk.HOST_MUTATION,
                approval_required=True,
                description="install",
            )
        ],
        required_approvals=["target.bootstrap.execute"],
    )


def _package(tmp_path: Path) -> tuple[Path, Path]:
    package = tmp_path / "rolo-target.bin"
    package.write_bytes(b"signed payload")
    manifest = sign_companion_manifest(
        package_id="rolo-target",
        package_version="1.0.0",
        architecture="aarch64",
        package_file=package.name,
        package_sha256=sha256_file(package),
        publisher_id="rolo-release",
        verification_key=b"verification-key",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest_path, package


def _authority() -> tuple[TargetBootstrapPlan, object, object]:
    plan = _plan()
    now = datetime.now(timezone.utc)
    request = request_bootstrap_approval(plan, requested_by="agent", now=now)
    decision = approve_bootstrap(
        plan,
        request,
        approved_by="operator",
        now=now + timedelta(seconds=1),
    )
    return plan, request, decision


def test_bootstrap_executes_only_after_plan_approval_and_manifest_verification(
    tmp_path: Path,
) -> None:
    manifest, package = _package(tmp_path)
    plan, request, decision = _authority()
    transport = FakeTransport(_target())

    result = execute_bootstrap(
        plan,
        request,
        decision,
        manifest_path=manifest,
        package_path=package,
        verification_key=b"verification-key",
        transport=transport,
    )

    assert result.status == "SUCCEEDED"
    assert len(transport.uploads) == 1
    assert [command[:2] for command in transport.commands] == [
        ("sudo", "-n"),
        ("rolo-target", "--version"),
        ("rm", "-f"),
    ]
    assert transport.commands[0][-1] == "/usr/local/bin/rolo-target"


@pytest.mark.parametrize("failure", ["upload", "install", "health"])
def test_bootstrap_returns_failed_result_without_claiming_success(
    tmp_path: Path, failure: str
) -> None:
    manifest, package = _package(tmp_path)
    plan, request, decision = _authority()
    transport = FakeTransport(_target(), fail_action=failure)

    result = execute_bootstrap(
        plan,
        request,
        decision,
        manifest_path=manifest,
        package_path=package,
        verification_key=b"verification-key",
        transport=transport,
    )

    assert result.status == "FAILED"
    assert result.diagnostics


def test_bootstrap_health_failure_restores_previous_companion_when_backup_exists(
    tmp_path: Path,
) -> None:
    manifest, package = _package(tmp_path)
    plan, request, decision = _authority()
    transport = FakeTransport(_target(), fail_action="health")

    result = execute_bootstrap(
        plan,
        request,
        decision,
        manifest_path=manifest,
        package_path=package,
        verification_key=b"verification-key",
        transport=transport,
        rollback_on_failure=True,
    )

    assert result.status == "FAILED"
    assert any("restored the previous companion" in item for item in result.diagnostics)
    assert any(command[:3] == ("sudo", "-n", "mv") for command in transport.commands)


def test_bootstrap_rejects_changed_plan_or_bad_manifest_before_transport(tmp_path: Path) -> None:
    manifest, package = _package(tmp_path)
    plan, request, decision = _authority()
    transport = FakeTransport(_target())
    changed = plan.model_copy(update={"required_approvals": ["different.scope"]})

    with pytest.raises(ValueError, match="different plan"):
        execute_bootstrap(
            changed,
            request,
            decision,
            manifest_path=manifest,
            package_path=package,
            verification_key=b"verification-key",
            transport=transport,
        )
    with pytest.raises(ValueError, match="signature verification failed"):
        execute_bootstrap(
            plan,
            request,
            decision,
            manifest_path=manifest,
            package_path=package,
            verification_key=b"wrong-key",
            transport=transport,
        )
    assert transport.uploads == []


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: list[str], *, timeout_s: float) -> CommandResult:
        del timeout_s
        self.calls.append(tuple(argv))
        return CommandResult(tuple(argv), 0)


def test_subprocess_bootstrap_transport_builds_bounded_scp_and_ssh_argv(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("example.test ssh-ed25519 AAAATEST\n", encoding="utf-8")
    package = tmp_path / "package.bin"
    package.write_bytes(b"payload")
    runner = RecordingRunner()
    transport = SubprocessBootstrapTransport(_target(), known_hosts=known_hosts, runner=runner)

    transport.upload(package, "/tmp/rolo-target-pkg", timeout_s=5)
    transport.execute(["rolo-target", "--version"], timeout_s=5)

    scp, ssh = runner.calls
    assert scp[0] == "scp"
    assert scp.count("--") == 1
    assert scp[-1] == "robot@example.test:/tmp/rolo-target-pkg"
    assert ssh[0] == "ssh"
    assert ssh.count("--") == 1
    assert ssh[-2:] == ("rolo-target", "--version")


def test_bootstrap_rejects_expired_approval_before_transport(tmp_path: Path) -> None:
    manifest, package = _package(tmp_path)
    plan, request, decision = _authority()
    transport = FakeTransport(_target())

    with pytest.raises(ValueError, match="has expired"):
        execute_bootstrap(
            plan,
            request,
            decision,
            manifest_path=manifest,
            package_path=package,
            verification_key=b"verification-key",
            transport=transport,
            now=request.expires_at,
        )
    assert transport.uploads == []
