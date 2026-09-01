"""Read-only Local/SSH target executors and typed bootstrap planning."""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol

from rolo.target_ref import LocalTargetRef, SshTargetRef, TargetRef
from rolo.targets.models import (
    BootstrapAction,
    BootstrapPlanStatus,
    CompanionStatus,
    TargetBootstrapPlan,
    TargetBootstrapStep,
    TargetConnectionAssessment,
    TargetConnectionState,
    TargetRisk,
)

MAX_DIAGNOSTIC_CHARS = 1000


def quote_remote_arg(value: str) -> str:
    """Quote one argument for the remote POSIX shell used by OpenSSH."""
    if "\x00" in value:
        raise ValueError("remote command arguments must not contain NUL bytes")
    return shlex.quote(value)


def quote_remote_argv(remote_argv: list[str]) -> list[str]:
    """Encode an argv vector before OpenSSH joins it for the remote shell."""
    return [quote_remote_arg(value) for value in remote_argv]


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def run(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        cancel_event: Event | None = None,
    ) -> CommandResult: ...


class SubprocessCommandRunner:
    """Run fixed executor argv without a shell or interactive input."""

    def run(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        cancel_event: Event | None = None,
    ) -> CommandResult:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        started = time.monotonic()
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                process.kill()
                stdout, stderr = process.communicate()
                return CommandResult(
                    argv=tuple(argv),
                    returncode=130,
                    stdout=(stdout or "")[:MAX_DIAGNOSTIC_CHARS],
                    stderr=(stderr or "")[:MAX_DIAGNOSTIC_CHARS] or "cancelled",
                )
            if time.monotonic() - started >= timeout_s:
                process.kill()
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    argv,
                    timeout_s,
                    output=stdout,
                    stderr=stderr,
                )
            time.sleep(0.02)
        stdout, stderr = process.communicate()
        return CommandResult(
            argv=tuple(argv),
            returncode=process.returncode,
            stdout=(stdout or "")[:MAX_DIAGNOSTIC_CHARS],
            stderr=(stderr or "")[:MAX_DIAGNOSTIC_CHARS],
        )


class TargetExecutor(Protocol):
    target: TargetRef

    def inspect(self) -> TargetConnectionAssessment: ...

    def plan_bootstrap(
        self, assessment: TargetConnectionAssessment | None = None
    ) -> TargetBootstrapPlan: ...


def _blocked_plan(
    assessment: TargetConnectionAssessment,
) -> TargetBootstrapPlan:
    return TargetBootstrapPlan(
        target=assessment.target,
        assessment_state=assessment.state,
        status=BootstrapPlanStatus.BLOCKED,
        blockers=assessment.blockers,
    )


class LocalTargetExecutor:
    def __init__(self, target: LocalTargetRef) -> None:
        self.target = target

    def inspect(self) -> TargetConnectionAssessment:
        workspace_accessible = self.target.workspace.is_dir() and os.access(
            self.target.workspace, os.R_OK
        )
        state = (
            TargetConnectionState.READY
            if workspace_accessible
            else TargetConnectionState.WORKSPACE_MISSING
        )
        blockers = [] if workspace_accessible else ["local workspace is unavailable or unreadable"]
        return TargetConnectionAssessment(
            target=self.target,
            state=state,
            reachable=True,
            platform=platform.system(),
            architecture=platform.machine(),
            workspace_accessible=workspace_accessible,
            companion=CompanionStatus.NOT_REQUIRED,
            blockers=blockers,
        )

    def plan_bootstrap(
        self, assessment: TargetConnectionAssessment | None = None
    ) -> TargetBootstrapPlan:
        assessment = assessment or self.inspect()
        if assessment.state != TargetConnectionState.READY:
            return _blocked_plan(assessment)
        return TargetBootstrapPlan(
            target=self.target,
            assessment_state=assessment.state,
            status=BootstrapPlanStatus.READY,
            steps=[
                TargetBootstrapStep(
                    action=BootstrapAction.VERIFY_WORKSPACE,
                    risk=TargetRisk.READ_ONLY,
                    description="Use the existing local Rolo runtime and verified workspace.",
                )
            ],
        )


class SshTargetExecutor:
    def __init__(
        self,
        target: SshTargetRef,
        *,
        known_hosts: Path | None,
        timeout_s: float = 10.0,
        runner: CommandRunner | None = None,
    ) -> None:
        if not 1.0 <= timeout_s <= 300.0:
            raise ValueError("SSH target timeout must be between 1 and 300 seconds")
        self.target = target
        self.known_hosts = known_hosts.expanduser().resolve() if known_hosts else None
        self.timeout_s = timeout_s
        self.runner = runner or SubprocessCommandRunner()

    def _ssh_argv(self, remote_argv: list[str]) -> list[str]:
        if self.known_hosts is None:
            raise ValueError("SSH inspection requires a pinned known_hosts file")
        destination = (
            f"{self.target.user}@{self.target.host}"
            if self.target.user
            else self.target.host
        )
        argv = [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={self.known_hosts}",
            "-o",
            "GlobalKnownHostsFile=none",
            "-o",
            "ClearAllForwardings=yes",
            "-o",
            "ForwardAgent=no",
            "-o",
            "ForwardX11=no",
            "-o",
            "PermitLocalCommand=no",
            "-o",
            f"ConnectTimeout={max(1, min(int(self.timeout_s), 300))}",
        ]
        if self.target.port is not None:
            argv.extend(["-p", str(self.target.port)])
        return [*argv, "--", destination, *quote_remote_argv(remote_argv)]

    def _run(self, remote_argv: list[str]) -> CommandResult:
        return self.runner.run(self._ssh_argv(remote_argv), timeout_s=self.timeout_s)

    @staticmethod
    def _failure_detail(result: CommandResult) -> str:
        return result.stderr.strip() or result.stdout.strip() or f"SSH exited {result.returncode}"

    def inspect(self) -> TargetConnectionAssessment:
        if self.known_hosts is None:
            return TargetConnectionAssessment(
                target=self.target,
                state=TargetConnectionState.HOST_KEY_REQUIRED,
                reachable=False,
                host_key_pinned=False,
                blockers=["SSH host key must be pinned before connection inspection"],
            )
        try:
            known_hosts_available = (
                self.known_hosts.is_file() and self.known_hosts.stat().st_size > 0
            )
        except OSError:
            known_hosts_available = False
        if not known_hosts_available:
            return TargetConnectionAssessment(
                target=self.target,
                state=TargetConnectionState.HOST_KEY_REQUIRED,
                reachable=False,
                host_key_pinned=False,
                blockers=["pinned SSH known_hosts file is unavailable or empty"],
            )
        try:
            system = self._run(["uname", "-s"])
            if system.returncode != 0:
                return TargetConnectionAssessment(
                    target=self.target,
                    state=TargetConnectionState.UNREACHABLE,
                    reachable=False,
                    host_key_pinned=True,
                    blockers=["SSH target connection inspection failed"],
                    diagnostics=[self._failure_detail(system)],
                )
            platform_name = system.stdout.strip()
            architecture = self._run(["uname", "-m"])
            if architecture.returncode != 0:
                return TargetConnectionAssessment(
                    target=self.target,
                    state=TargetConnectionState.UNREACHABLE,
                    reachable=True,
                    host_key_pinned=True,
                    platform=platform_name,
                    blockers=["SSH target architecture inspection failed"],
                    diagnostics=[self._failure_detail(architecture)],
                )
            if platform_name.casefold() != "linux":
                return TargetConnectionAssessment(
                    target=self.target,
                    state=TargetConnectionState.UNSUPPORTED,
                    reachable=True,
                    host_key_pinned=True,
                    platform=platform_name,
                    architecture=architecture.stdout.strip(),
                    blockers=["the first remote Target Executor supports Linux only"],
                )
            workspace = self._run(["test", "-d", str(self.target.workspace)])
            companion = self._run(["command", "-v", "rolo-target"])
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            return TargetConnectionAssessment(
                target=self.target,
                state=TargetConnectionState.UNREACHABLE,
                reachable=False,
                host_key_pinned=True,
                blockers=["SSH target connection inspection could not complete"],
                diagnostics=[str(exc)[:MAX_DIAGNOSTIC_CHARS]],
            )
        workspace_accessible = workspace.returncode == 0
        state = (
            TargetConnectionState.READY
            if workspace_accessible
            else TargetConnectionState.WORKSPACE_MISSING
        )
        return TargetConnectionAssessment(
            target=self.target,
            state=state,
            reachable=True,
            host_key_pinned=True,
            platform=platform_name,
            architecture=architecture.stdout.strip(),
            workspace_accessible=workspace_accessible,
            companion=(
                CompanionStatus.AVAILABLE
                if companion.returncode == 0
                else CompanionStatus.MISSING
            ),
            blockers=([] if workspace_accessible else ["remote workspace is unavailable"]),
        )

    def plan_bootstrap(
        self, assessment: TargetConnectionAssessment | None = None
    ) -> TargetBootstrapPlan:
        assessment = assessment or self.inspect()
        if assessment.state != TargetConnectionState.READY:
            return _blocked_plan(assessment)
        steps = [
            TargetBootstrapStep(
                action=BootstrapAction.VERIFY_PLATFORM,
                risk=TargetRisk.READ_ONLY,
                description="Verify the pinned Linux target platform and architecture.",
            ),
            TargetBootstrapStep(
                action=BootstrapAction.VERIFY_WORKSPACE,
                risk=TargetRisk.READ_ONLY,
                description="Verify that the remote workspace is readable.",
            ),
        ]
        if assessment.companion == CompanionStatus.MISSING:
            steps.extend(
                [
                    TargetBootstrapStep(
                        action=BootstrapAction.INSTALL_COMPANION,
                        risk=TargetRisk.HOST_MUTATION,
                        approval_required=True,
                        description="Install the signed minimal rolo-target companion.",
                    ),
                    TargetBootstrapStep(
                        action=BootstrapAction.HEALTH_CHECK,
                        risk=TargetRisk.READ_ONLY,
                        description="Verify the installed companion before enrollment.",
                    ),
                ]
            )
            return TargetBootstrapPlan(
                target=self.target,
                assessment_state=assessment.state,
                status=BootstrapPlanStatus.APPROVAL_REQUIRED,
                steps=steps,
                required_approvals=["target.bootstrap.execute"],
            )
        steps.append(
            TargetBootstrapStep(
                action=BootstrapAction.HEALTH_CHECK,
                risk=TargetRisk.READ_ONLY,
                description="Verify the existing rolo-target companion before enrollment.",
            )
        )
        return TargetBootstrapPlan(
            target=self.target,
            assessment_state=assessment.state,
            status=BootstrapPlanStatus.READY,
            steps=steps,
        )


def create_target_executor(
    target: TargetRef,
    *,
    known_hosts: Path | None = None,
    timeout_s: float = 10.0,
    runner: CommandRunner | None = None,
) -> TargetExecutor:
    if isinstance(target, LocalTargetRef):
        if known_hosts is not None:
            raise ValueError("local target inspection does not accept --known-hosts")
        return LocalTargetExecutor(target)
    return SshTargetExecutor(
        target,
        known_hosts=known_hosts,
        timeout_s=timeout_s,
        runner=runner,
    )
