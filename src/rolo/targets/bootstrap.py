"""Approved, signed and fixed-argv bootstrap execution for target companions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from rolo.target_ref import LocalTargetRef, SshTargetRef, TargetRef
from rolo.targets.approvals import (
    BootstrapApprovalDecision,
    BootstrapApprovalRequest,
    bootstrap_plan_digest,
)
from rolo.targets.executor import (
    MAX_DIAGNOSTIC_CHARS,
    CommandResult,
    SubprocessCommandRunner,
    quote_remote_arg,
    quote_remote_argv,
)
from rolo.targets.models import BootstrapAction, BootstrapPlanStatus, TargetBootstrapPlan
from rolo.targets.signing import CompanionManifest, verify_companion_manifest


class BootstrapTransport(Protocol):
    target: TargetRef

    def upload(self, local_path: Path, remote_path: str, *, timeout_s: float) -> CommandResult: ...

    def execute(self, remote_argv: list[str], *, timeout_s: float) -> CommandResult: ...


class SubprocessBootstrapTransport:
    """Execute only fixed SSH/SCP argv; remote shells receive fixed command names and paths."""

    def __init__(
        self,
        target: SshTargetRef,
        *,
        known_hosts: Path,
        runner: SubprocessCommandRunner | None = None,
    ) -> None:
        self.target = target
        self.known_hosts = known_hosts.expanduser().resolve()
        try:
            available = self.known_hosts.is_file() and self.known_hosts.stat().st_size > 0
        except OSError:
            available = False
        if not available:
            raise ValueError("bootstrap transport requires a non-empty pinned known_hosts file")
        self.runner = runner or SubprocessCommandRunner()

    def _options(self, command: str) -> list[str]:
        destination = (
            f"{self.target.user}@{self.target.host}"
            if self.target.user
            else self.target.host
        )
        options = [
            command,
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
        ]
        if self.target.port is not None:
            options.extend(["-P" if command == "scp" else "-p", str(self.target.port)])
        return [*options, "--", destination]

    def upload(self, local_path: Path, remote_path: str, *, timeout_s: float) -> CommandResult:
        options = self._options("scp")
        destination = options[-1]
        remote_spec = f"{destination}:{quote_remote_arg(remote_path)}"
        argv = [*options[:-2], "--", str(local_path), remote_spec]
        return self.runner.run(argv, timeout_s=timeout_s)

    def execute(self, remote_argv: list[str], *, timeout_s: float) -> CommandResult:
        argv = [*self._options("ssh"), *quote_remote_argv(remote_argv)]
        return self.runner.run(argv, timeout_s=timeout_s)


class LocalBootstrapTransport:
    """Explicit no-op transport: a local Rolo installation needs no target companion."""

    def __init__(self, target: LocalTargetRef) -> None:
        self.target = target

    def upload(self, local_path: Path, remote_path: str, *, timeout_s: float) -> CommandResult:
        del local_path, remote_path, timeout_s
        raise ValueError("local target bootstrap is not required")

    def execute(self, remote_argv: list[str], *, timeout_s: float) -> CommandResult:
        del remote_argv, timeout_s
        raise ValueError("local target bootstrap is not required")


class BootstrapExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-result/v1"] = (
        "rolo-target-bootstrap-result/v1"
    )
    status: Literal["SUCCEEDED", "FAILED"]
    target: TargetRef
    plan_sha256: str
    approval_request_id: str
    package_id: str
    package_version: str
    package_sha256: str
    remote_package_path: str
    diagnostics: list[str] = []


def _transport_failure(result: CommandResult, action: str) -> str:
    detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
    return f"{action} failed: {detail[:MAX_DIAGNOSTIC_CHARS]}"


def _validate_execution_authority(
    plan: TargetBootstrapPlan,
    request: BootstrapApprovalRequest,
    decision: BootstrapApprovalDecision,
) -> str:
    plan_digest = bootstrap_plan_digest(plan)
    if plan.status != BootstrapPlanStatus.APPROVAL_REQUIRED:
        raise ValueError("bootstrap execution requires an approval-required plan")
    if request.status != "PENDING":
        raise ValueError("bootstrap approval request is not pending")
    if request.plan_sha256 != plan_digest or decision.plan_sha256 != plan_digest:
        raise ValueError("bootstrap approval is bound to a different plan")
    if decision.request_id != request.request_id:
        raise ValueError("bootstrap approval decision does not match its request")
    if request.scope != "target.bootstrap.execute" or decision.scope != request.scope:
        raise ValueError("bootstrap approval scope is invalid")
    if decision.status != "APPROVED":
        raise ValueError("bootstrap approval decision is not approved")
    if decision.approved_by == request.requested_by:
        raise ValueError("bootstrap approval cannot be self-approved")
    if decision.approved_at >= request.expires_at:
        raise ValueError("bootstrap approval request has expired")
    install_steps = [
        step for step in plan.steps if step.action == BootstrapAction.INSTALL_COMPANION
    ]
    if len(install_steps) != 1 or not install_steps[0].approval_required:
        raise ValueError("bootstrap plan does not contain exactly one approved companion install")
    if install_steps[0].risk.value != "HOST_MUTATION":
        raise ValueError("companion install must be classified as a host mutation")
    return plan_digest


def execute_bootstrap(
    plan: TargetBootstrapPlan,
    request: BootstrapApprovalRequest,
    decision: BootstrapApprovalDecision,
    *,
    manifest_path: Path,
    package_path: Path,
    verification_key: bytes,
    transport: BootstrapTransport,
    timeout_s: float = 60.0,
    rollback_on_failure: bool = False,
    now: datetime | None = None,
) -> BootstrapExecutionResult:
    """Upload/install a signed companion only after all authority checks pass."""
    if not 1.0 <= timeout_s <= 600.0:
        raise ValueError("bootstrap execution timeout must be between 1 and 600 seconds")
    plan_digest = _validate_execution_authority(plan, request, decision)
    if not isinstance(transport.target, SshTargetRef):
        raise ValueError("companion bootstrap execution requires an SSH target")
    if plan.target != transport.target:
        raise ValueError("bootstrap transport target does not match the approved plan")
    if (now or datetime.now(timezone.utc)) >= request.expires_at:
        raise ValueError("bootstrap approval request has expired")
    verified = verify_companion_manifest(
        manifest_path,
        package_path,
        verification_key=verification_key,
    )
    manifest = CompanionManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    remote_package_path = f"/tmp/rolo-target-{manifest.package_sha256}.pkg"
    rollback_path = f"/tmp/rolo-target-previous-{manifest.package_sha256}"
    diagnostics: list[str] = []
    rollback_available = False
    if rollback_on_failure:
        backup = transport.execute(
            [
                "sudo",
                "-n",
                "cp",
                "-p",
                "--",
                "/usr/local/bin/rolo-target",
                rollback_path,
            ],
            timeout_s=timeout_s,
        )
        rollback_available = backup.returncode == 0
    uploaded = transport.upload(package_path.resolve(), remote_package_path, timeout_s=timeout_s)
    if uploaded.returncode != 0:
        return BootstrapExecutionResult(
            status="FAILED",
            target=transport.target,
            plan_sha256=plan_digest,
            approval_request_id=request.request_id,
            package_id=verified.package_id,
            package_version=verified.package_version,
            package_sha256=verified.package_sha256,
            remote_package_path=remote_package_path,
            diagnostics=[_transport_failure(uploaded, "companion upload")],
        )
    installed = transport.execute(
        [
            "sudo",
            "-n",
            "install",
            "-o",
            "root",
            "-g",
            "root",
            "-m",
            "0755",
            remote_package_path,
            "/usr/local/bin/rolo-target",
        ],
        timeout_s=timeout_s,
    )
    if installed.returncode != 0:
        cleanup = transport.execute(["rm", "-f", "--", remote_package_path], timeout_s=timeout_s)
        diagnostics = [_transport_failure(installed, "companion install")]
        if cleanup.returncode != 0:
            diagnostics.append(_transport_failure(cleanup, "temporary package cleanup"))
        return BootstrapExecutionResult(
            status="FAILED",
            target=transport.target,
            plan_sha256=plan_digest,
            approval_request_id=request.request_id,
            package_id=verified.package_id,
            package_version=verified.package_version,
            package_sha256=verified.package_sha256,
            remote_package_path=remote_package_path,
            diagnostics=diagnostics,
        )
    health = transport.execute(["rolo-target", "--version"], timeout_s=timeout_s)
    expected_health = f"{manifest.package_id} {manifest.package_version}"
    health_output = health.stdout.strip()
    if health.returncode != 0 or health_output != expected_health:
        diagnostics = (
            [_transport_failure(health, "companion health check")]
            if health.returncode != 0
            else [
                "companion health version mismatch: "
                f"expected {expected_health!r}, observed {health_output!r}"
            ]
        )
        if rollback_available:
            rollback = transport.execute(
                ["sudo", "-n", "mv", "-f", "--", rollback_path, "/usr/local/bin/rolo-target"],
                timeout_s=timeout_s,
            )
            if rollback.returncode == 0:
                diagnostics.append("rollback restored the previous companion")
            else:
                diagnostics.append(_transport_failure(rollback, "companion rollback"))
        else:
            diagnostics.append("rollback unavailable: no previous companion backup")
        cleanup = transport.execute(["rm", "-f", "--", remote_package_path], timeout_s=timeout_s)
        if cleanup.returncode != 0:
            diagnostics.append(_transport_failure(cleanup, "temporary package cleanup"))
        return BootstrapExecutionResult(
            status="FAILED",
            target=transport.target,
            plan_sha256=plan_digest,
            approval_request_id=request.request_id,
            package_id=verified.package_id,
            package_version=verified.package_version,
            package_sha256=verified.package_sha256,
            remote_package_path=remote_package_path,
            diagnostics=diagnostics,
        )
    if rollback_available:
        cleanup_backup = transport.execute(["rm", "-f", "--", rollback_path], timeout_s=timeout_s)
        if cleanup_backup.returncode != 0:
            diagnostics.append(
                _transport_failure(cleanup_backup, "previous companion backup cleanup")
            )
    cleanup = transport.execute(["rm", "-f", "--", remote_package_path], timeout_s=timeout_s)
    if cleanup.returncode != 0:
        diagnostics.append(_transport_failure(cleanup, "temporary package cleanup"))
    return BootstrapExecutionResult(
        status="SUCCEEDED",
        target=transport.target,
        plan_sha256=plan_digest,
        approval_request_id=request.request_id,
        package_id=verified.package_id,
        package_version=verified.package_version,
        package_sha256=verified.package_sha256,
        remote_package_path=remote_package_path,
        diagnostics=diagnostics,
    )
