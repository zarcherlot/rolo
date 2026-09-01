"""Bounded real-target Diagnose/Verify provider for local or SSH Linux/ROS profiles.

The provider intentionally supports only a fixed read-only command catalog.  It is
the first production target slice for WSL2/Linux validation; actuator, power,
firmware, calibration and arbitrary shell execution are outside this boundary.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.stages.agent_runner import OutputCallback, StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.diagnose.episode import (
    DiagnosisEpisode,
    EpisodeObservation,
    EpisodePhase,
    TargetProvenance,
    publish_episode,
)
from rolo.stages.handoffs import commit_diagnosis_handoff, commit_verification_handoff
from rolo.stages.verify.acceptance import (
    VerificationPlan,
    VerificationReplayCase,
    VerificationReplayFixture,
    run_verification_replay,
)
from rolo.stages.verify.service import validate_verification_plan_operations
from rolo.target_ref import LocalTargetRef, SshTargetRef
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.profiles import TargetProfileStore

Stage = Literal["diagnose", "verify"]
_TOPIC = re.compile(r"^/[A-Za-z0-9_/~-]{1,255}$")
_MAX_OUTPUT_BYTES = 1_000_000
_SECRET_OUTPUT = re.compile(
    r"(?i)(\b(?:api[_-]?key|token|secret|password|credential)\b\s*[=:]\s*)[^\s,;]+"
)
_BEARER_OUTPUT = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def _redact_output(value: str) -> str:
    return _BEARER_OUTPUT.sub(
        "Bearer <redacted>", _SECRET_OUTPUT.sub(r"\1<redacted>", value)
    )


def _machine_id_sha256() -> str:
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        if candidate.is_file():
            value = candidate.read_bytes().strip()
            if value:
                return hashlib.sha256(value).hexdigest()
    # ``os.uname`` is unavailable on Windows development hosts.  The target
    # provider itself remains Linux/ROS-only, but its identity snapshot should
    # still be constructible in cross-platform contract tests.
    return hashlib.sha256(platform.node().encode("utf-8")).hexdigest()


def _os_uid() -> int:
    """Return the POSIX uid, with a deterministic development-host fallback."""

    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else 0


class TargetBinding(BaseModel):
    """Immutable identity snapshot reviewed by the Stage authorization request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-local-target-binding/v1"] = "rolo-local-target-binding/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace: str = Field(min_length=1, max_length=4096)
    workspace_device: int = Field(ge=0)
    workspace_inode: int = Field(ge=0)
    workspace_ctime_ns: int = Field(ge=0)
    machine_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    os_user: str = Field(min_length=1, max_length=128)
    os_uid: int = Field(ge=0)
    ros_domain_id: str | None = None
    rmw_implementation: str | None = None
    captured_at: datetime

    @classmethod
    def capture(cls, *, settings: Settings, robot_id: str) -> TargetBinding:
        profile = TargetProfileStore(settings.rolo_config_dir).load(robot_id)
        if not isinstance(profile.target, LocalTargetRef):
            if profile.host_key is None or profile.host_key.status != "APPROVED":
                raise ValueError("remote target host key is not approved")
            raise ValueError("local-target provider only supports a local Linux/ROS profile")
        workspace = profile.target.workspace.expanduser().resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"target workspace is missing: {workspace}")
        stat = workspace.stat()
        return cls(
            robot_id=robot_id,
            profile_sha256=canonical_json_sha256(profile.model_dump(mode="json")),
            workspace=str(workspace),
            workspace_device=stat.st_dev,
            workspace_inode=stat.st_ino,
            workspace_ctime_ns=stat.st_ctime_ns,
            machine_id_sha256=_machine_id_sha256(),
            os_user=getpass.getuser(),
            os_uid=_os_uid(),
            ros_domain_id=os.environ.get("ROS_DOMAIN_ID") or settings.ros_domain_id,
            rmw_implementation=os.environ.get("RMW_IMPLEMENTATION")
            or settings.ros_rmw_implementation,
            captured_at=datetime.now(timezone.utc),
        )

    def validate_current_host(self) -> None:
        workspace = Path(self.workspace).resolve()
        if not workspace.is_dir():
            raise ValueError("target workspace identity drift: workspace is missing")
        stat = workspace.stat()
        actual = (
            stat.st_dev,
            stat.st_ino,
            stat.st_ctime_ns,
            _machine_id_sha256(),
            getpass.getuser(),
            _os_uid(),
        )
        expected = (
            self.workspace_device,
            self.workspace_inode,
            self.workspace_ctime_ns,
            self.machine_id_sha256,
            self.os_user,
            self.os_uid,
        )
        if actual != expected:
            raise ValueError("target workspace identity drift")


def publish_target_binding(
    artifacts: ArtifactStore, settings: Settings, robot_id: str
) -> str:
    """Publish once and then reuse the authorization-bound local target identity."""

    layout = ArtifactLayout(artifacts.root)
    path = artifacts.root / "targets" / robot_id / "bindings" / "current.json"
    if path.is_file():
        reference = layout.ref(path)
        existing = validate_target_binding(artifacts.root, reference)
        profile = TargetProfileStore(settings.rolo_config_dir).load(robot_id)
        if existing.profile_sha256 != canonical_json_sha256(profile.model_dump(mode="json")):
            raise ValueError("target profile changed after the target binding was published")
        return reference
    profile = TargetProfileStore(settings.rolo_config_dir).load(robot_id)
    if isinstance(profile.target, SshTargetRef):
        if profile.host_key is None or profile.host_key.status != "APPROVED":
            raise ValueError("SSH target profile host key is not approved")
        if profile.known_hosts is None:
            raise ValueError("SSH target profile requires a pinned known_hosts file")
        if (
            profile.known_hosts.is_symlink()
            or not profile.known_hosts.is_file()
            or profile.known_hosts.stat().st_size == 0
        ):
            raise ValueError("SSH target profile known_hosts file is unavailable or empty")
        transport = SubprocessBootstrapTransport(profile.target, known_hosts=profile.known_hosts)
        from rolo.stages.verify.ssh_provenance import SshTargetProvenanceCollector

        _, reference, _ = SshTargetProvenanceCollector(
            profile.target, transport
        ).collect(
            artifacts,
            robot_id=robot_id,
            profile_sha256=canonical_json_sha256(profile.model_dump(mode="json")),
        )
        return reference
    binding = TargetBinding.capture(settings=settings, robot_id=robot_id)
    written = artifacts.write_json(
        f"targets/{robot_id}/bindings/current.json", binding.model_dump(mode="json")
    )
    return layout.ref(written)


def validate_target_binding(artifact_root: Path, reference: str) -> TargetBinding:
    path = resolve_artifact_ref(artifact_root, reference)
    binding = TargetBinding.model_validate_json(path.read_text(encoding="utf-8"))
    binding.validate_current_host()
    return binding


class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    status: Literal["READY", "ERROR", "TIMEOUT"]
    returncode: int | None = None
    output: str = ""
    lines: list[str] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)
    environment_limited: bool = False
    observed_at: datetime


class LocalTargetCommandRunner:
    """Execute only fixed, read-only Linux/ROS observations without a shell."""

    READ_ONLY_OPERATIONS = frozenset(
        {
            "linux.uname",
            "ros.doctor.report",
            "ros.node.list",
            "ros.topic.list",
            "ros.service.list",
            "ros.topic.echo_once",
        }
    )

    def run(
        self, operation: str, payload: Mapping[str, JsonValue], *, timeout_s: float
    ) -> dict[str, JsonValue]:
        if operation not in self.READ_ONLY_OPERATIONS:
            raise ValueError(f"operation is not in the read-only allowlist: {operation}")
        command = self._command(operation, payload)
        if timeout_s <= 0 or timeout_s > 600:
            raise ValueError("target command timeout must be in (0, 600]")
        try:
            completed = subprocess.run(
                command,
                cwd=None,
                env=os.environ.copy(),
                capture_output=True,
                text=False,
                timeout=timeout_s,
                check=False,
            )
            raw = (completed.stdout or b"") + (completed.stderr or b"")
            output = _redact_output(
                raw[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            )
            lines = [line for line in output.splitlines() if line.strip()]
            result = CommandResult(
                operation=operation,
                status="READY" if completed.returncode == 0 else "ERROR",
                returncode=completed.returncode,
                output=output,
                lines=lines[:4096],
                count=len(lines),
                environment_limited=(
                    operation == "ros.topic.echo_once" and completed.returncode != 0
                ),
                observed_at=datetime.now(timezone.utc),
            )
        except subprocess.TimeoutExpired as exc:
            raw = (exc.stdout or b"") + (exc.stderr or b"")
            if isinstance(raw, str):
                output = _redact_output(raw[:_MAX_OUTPUT_BYTES])
            else:
                output = _redact_output(
                    raw[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
                )
            result = CommandResult(
                operation=operation,
                status="TIMEOUT",
                output=output,
                environment_limited=operation == "ros.topic.echo_once",
                observed_at=datetime.now(timezone.utc),
            )
        return result.model_dump(mode="json")

    @staticmethod
    def _command(operation: str, payload: Mapping[str, JsonValue]) -> list[str]:
        if operation == "linux.uname":
            return ["uname", "-a"]
        if shutil.which("ros2") is None:
            raise ValueError("ros2 executable is unavailable in the target environment")
        if operation == "ros.doctor.report":
            return ["ros2", "doctor", "--report"]
        if operation == "ros.node.list":
            return ["ros2", "node", "list"]
        if operation == "ros.topic.list":
            return ["ros2", "topic", "list"]
        if operation == "ros.service.list":
            return ["ros2", "service", "list"]
        topic = payload.get("topic")
        if not isinstance(topic, str) or not _TOPIC.fullmatch(topic):
            raise ValueError("ros.topic.echo_once requires a safe absolute topic")
        return ["ros2", "topic", "echo", topic, "--once"]


class SshTargetCommandRunner:
    """Execute the same fixed read-only catalog through a pinned SSH transport."""

    READ_ONLY_OPERATIONS = LocalTargetCommandRunner.READ_ONLY_OPERATIONS

    def __init__(self, transport: SubprocessBootstrapTransport) -> None:
        self.transport = transport

    def run(
        self, operation: str, payload: Mapping[str, JsonValue], *, timeout_s: float
    ) -> dict[str, JsonValue]:
        if operation not in self.READ_ONLY_OPERATIONS:
            raise ValueError(f"operation is not in the read-only allowlist: {operation}")
        remote_argv = self._command(operation, payload)
        try:
            outcome = self.transport.execute(remote_argv, timeout_s=timeout_s)
            output = _redact_output(
                (outcome.stdout + outcome.stderr)[:_MAX_OUTPUT_BYTES]
            )
            lines = [line for line in output.splitlines() if line.strip()]
            return CommandResult(
                operation=operation,
                status="READY" if outcome.returncode == 0 else "ERROR",
                returncode=outcome.returncode,
                output=output,
                lines=lines[:4096],
                count=len(lines),
                environment_limited=(
                    operation == "ros.topic.echo_once" and outcome.returncode != 0
                ),
                observed_at=datetime.now(timezone.utc),
            ).model_dump(mode="json")
        except subprocess.TimeoutExpired:
            return CommandResult(
                operation=operation,
                status="TIMEOUT",
                environment_limited=operation == "ros.topic.echo_once",
                observed_at=datetime.now(timezone.utc),
            ).model_dump(mode="json")

    @staticmethod
    def _command(operation: str, payload: Mapping[str, JsonValue]) -> list[str]:
        if operation == "linux.uname":
            return ["uname", "-a"]
        if operation == "ros.doctor.report":
            return ["ros2", "doctor", "--report"]
        if operation == "ros.node.list":
            return ["ros2", "node", "list"]
        if operation == "ros.topic.list":
            return ["ros2", "topic", "list"]
        if operation == "ros.service.list":
            return ["ros2", "service", "list"]
        topic = payload.get("topic")
        if not isinstance(topic, str) or not _TOPIC.fullmatch(topic):
            raise ValueError("ros.topic.echo_once requires a safe absolute topic")
        return ["ros2", "topic", "echo", topic, "--once"]


class LocalTargetStageExecutor:
    """Real local target provider that materializes immutable Episode/evidence artifacts."""

    def __init__(
        self, *, artifacts: ArtifactStore, settings: Settings, stage: Stage
    ) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.stage = stage
        self.runner = LocalTargetCommandRunner()
        self.provenance_source = "local-target"

    def execute_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None = None,
        run_id: str | None = None,
        cancel_event: Event | None = None,
    ) -> Mapping[str, str]:
        if task.stage != self.stage:
            raise ValueError(f"local-target executor is bound to {self.stage}, got {task.stage}")
        if "target_profile" in task.input_refs:
            return self._execute_ssh_stage(
                task, workspace=workspace, on_output=on_output, run_id=run_id,
                cancel_event=cancel_event,
            )
        del workspace
        binding_ref = task.input_refs.get("target_binding")
        if not binding_ref:
            raise ValueError("local-target task is missing an authorization-bound target binding")
        binding = validate_target_binding(self.artifacts.root, binding_ref)
        if binding.robot_id != task.robot_id:
            raise ValueError("target binding robot identity mismatch")
        if on_output:
            on_output("stdout", f"local-target {self.stage}: identity verified")
        selected_run_id = run_id or f"local-target-{uuid4().hex}"
        if self._cancel_requested(task, selected_run_id, cancel_event):
            raise ValueError("local-target execution was cancelled before collection")
        return (
            self._diagnose(task, binding_ref, binding, on_output, selected_run_id)
            if self.stage == "diagnose"
            else self._verify(
                task,
                binding_ref,
                binding,
                on_output,
                selected_run_id,
                cancel_event,
            )
        )

    def _execute_ssh_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None,
        run_id: str | None,
        cancel_event: Event | None,
    ) -> Mapping[str, str]:
        del workspace
        profile_path = resolve_artifact_ref(
            self.artifacts.root, task.input_refs["target_profile"]
        )
        profile = TargetProfileStore(self.settings.rolo_config_dir).load(task.robot_id)
        snapshot = json.loads(profile_path.read_text(encoding="utf-8"))
        expected_digest = canonical_json_sha256(profile.model_dump(mode="json"))
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("profile_id") != profile.profile_id
            or snapshot.get("profile_sha256") != expected_digest
        ):
            raise ValueError("SSH target profile changed after the task was planned")
        if not isinstance(profile.target, SshTargetRef):
            raise ValueError("target_profile input is not an SSH profile")
        if profile.host_key is None or profile.host_key.status != "APPROVED":
            raise ValueError("SSH target profile host key is not approved")
        if profile.known_hosts is None:
            raise ValueError("SSH target profile requires a pinned known_hosts file")
        if (
            profile.known_hosts.is_symlink()
            or not profile.known_hosts.is_file()
            or profile.known_hosts.stat().st_size == 0
        ):
            raise ValueError("SSH target profile known_hosts file is unavailable or empty")
        transport = SubprocessBootstrapTransport(
            profile.target, known_hosts=profile.known_hosts
        )
        from rolo.stages.verify.ssh_provenance import SshTargetProvenanceCollector

        self.runner = SshTargetCommandRunner(transport)
        self.provenance_source = "ssh-target"
        selected_run_id = run_id or f"ssh-target-{uuid4().hex}"
        if self._cancel_requested(task, selected_run_id, cancel_event):
            raise ValueError("SSH target execution was cancelled before collection")
        _, binding_ref, _ = SshTargetProvenanceCollector(
            profile.target, transport
        ).collect(
            self.artifacts,
            robot_id=task.robot_id,
            profile_sha256=canonical_json_sha256(profile.model_dump(mode="json")),
            run_id=selected_run_id,
        )
        binding = TargetBinding.model_validate_json(
            resolve_artifact_ref(self.artifacts.root, binding_ref).read_text(encoding="utf-8")
        )
        if on_output:
            on_output("stdout", f"ssh-target {self.stage}: identity verified")
        return (
            self._diagnose(task, binding_ref, binding, on_output, selected_run_id)
            if self.stage == "diagnose"
            else self._verify(
                task, binding_ref, binding, on_output, selected_run_id, cancel_event
            )
        )

    def _cancel_requested(
        self, task: StageAgentTask, run_id: str, cancel_event: Event | None
    ) -> bool:
        if cancel_event is not None and cancel_event.is_set():
            return True
        run_path = (
            ArtifactLayout(self.artifacts.root).stage_run(task.stage, task.robot_id, run_id)
            / "run.json"
        )
        if not run_path.is_file():
            return False
        try:
            payload = json.loads(run_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return isinstance(payload, dict) and bool(payload.get("cancel_requested"))

    def _provenance(
        self, robot_id: str, run_id: str, binding_ref: str
    ) -> tuple[TargetProvenance, str, str]:
        provenance = TargetProvenance(
            schema_version="rolo-target-provenance/v2",
            target_id=robot_id,
            source=self.provenance_source,
            collector_version="0.1.0",
            collected_at=datetime.now(timezone.utc),
            clock_offset_ms=0,
            target_binding_ref=binding_ref,
            target_binding_sha256=sha256_file(
                resolve_artifact_ref(self.artifacts.root, binding_ref)
            ),
            collector_session_id=run_id,
            clock_source=(
                "remote-monotonic"
                if self.provenance_source == "ssh-target"
                else "local-monotonic"
            ),
            monotonic_ns=time.monotonic_ns(),
        )
        path = self.artifacts.write_json(
            f"targets/{robot_id}/provenance/{run_id}.json",
            provenance.model_dump(mode="json"),
        )
        reference = ArtifactLayout(self.artifacts.root).ref(path)
        return provenance, reference, sha256_file(path)

    def _diagnose(
        self,
        task: StageAgentTask,
        binding_ref: str,
        binding: TargetBinding,
        on_output: OutputCallback | None,
        run_id: str,
    ) -> Mapping[str, str]:
        provenance, provenance_ref, _ = self._provenance(
            task.robot_id, run_id, binding_ref
        )
        started = datetime.now(timezone.utc)
        baseline = {
            operation: self.runner.run(operation, {}, timeout_s=60)
            for operation in (
                "linux.uname",
                "ros.doctor.report",
                "ros.node.list",
                "ros.topic.list",
                "ros.service.list",
            )
        }
        observe = {
            operation: self.runner.run(operation, {}, timeout_s=30)
            for operation in ("ros.node.list", "ros.topic.list", "ros.service.list")
        }
        doctor_ready = baseline["ros.doctor.report"]["status"] == "READY"
        hypothesis = {
            "kind": "TARGET_RUNTIME_READY" if doctor_ready else "TARGET_RUNTIME_DEGRADED",
            "supported_by": ["ros.doctor.report", "ros.node.list", "ros.topic.list"],
        }
        change = {
            "kind": "NO_CHANGE",
            "applied": False,
            "reason": "local-target provider is restricted to read-only validation",
        }
        smoke = {
            "ros.doctor.report": self.runner.run("ros.doctor.report", {}, timeout_s=60),
            "ros.node.list": self.runner.run("ros.node.list", {}, timeout_s=30),
        }
        smoke_ready = smoke["ros.doctor.report"]["status"] == "READY"
        decision = "COMMIT" if doctor_ready and smoke_ready else "INCONCLUSIVE"
        payloads: list[tuple[EpisodePhase, dict[str, JsonValue]]] = [
            (EpisodePhase.BASELINE, baseline),
            (EpisodePhase.OBSERVE, observe),
            (EpisodePhase.HYPOTHESIS, hypothesis),
            (EpisodePhase.CHANGE, change),
            (EpisodePhase.SMOKE, smoke),
            (EpisodePhase.DECISION, {"decision": decision}),
        ]
        observations = [
            EpisodeObservation(
                sequence=index,
                phase=phase,
                observed_at=datetime.now(timezone.utc),
                payload=payload,
                provenance=provenance,
            )
            for index, (phase, payload) in enumerate(payloads, start=1)
        ]
        episode = DiagnosisEpisode(
            episode_id=f"episode-{uuid4().hex}",
            robot_id=task.robot_id,
            started_at=started,
            ended_at=datetime.now(timezone.utc),
            observations=observations,
            status="COMPLETE",
        )
        episode_ref = publish_episode(self.artifacts.root, episode)
        report = {
            "schema_version": "rolo-diagnosis-report/v1",
            "robot_id": task.robot_id,
            "baseline": baseline,
            "observations": [observe],
            "hypotheses": [hypothesis],
            "changes": [change],
            "smoke": smoke,
            "decision": decision,
            "episode_refs": [episode_ref],
            "limitations": ([] if doctor_ready else ["ros2 doctor did not complete successfully"]),
        }
        handoff = commit_diagnosis_handoff(
            self.artifacts.root,
            task.robot_id,
            frozen_config={
                "schema_version": "rolo-local-target-frozen-config/v1",
                "robot_id": task.robot_id,
                "target_binding_ref": binding_ref,
                "target_provenance_ref": provenance_ref,
                "workspace": binding.workspace,
                "ros_domain_id": binding.ros_domain_id,
                "rmw_implementation": binding.rmw_implementation,
                "mutation": "NONE",
            },
            diagnosis_report=report,
            run_id=run_id,
        )
        if on_output:
            on_output("stdout", f"local-target diagnose: {decision}")
        layout = ArtifactLayout(self.artifacts.root)
        return {
            "handoff": layout.ref(layout.stage_file("diagnose", task.robot_id, "handoff.json")),
            "frozen_config": handoff.frozen_config_ref,
            "diagnosis_report": handoff.diagnosis_report_ref or "",
            "episode": episode_ref,
            "target_provenance": provenance_ref,
        }

    def _verify(
        self,
        task: StageAgentTask,
        binding_ref: str,
        binding: TargetBinding,
        on_output: OutputCallback | None,
        run_id: str,
        cancel_event: Event | None,
    ) -> Mapping[str, str]:
        del binding
        plan_ref = task.input_refs.get("acceptance_plan")
        if not plan_ref:
            raise ValueError("local-target Verify requires a published acceptance plan")
        plan = VerificationPlan.model_validate_json(
            resolve_artifact_ref(self.artifacts.root, plan_ref).read_text(encoding="utf-8")
        )
        if plan.robot_id != task.robot_id:
            raise ValueError("verification plan robot identity mismatch")
        validate_verification_plan_operations(plan, self.runner.READ_ONLY_OPERATIONS)
        _, provenance_ref, provenance_sha256 = self._provenance(
            task.robot_id, run_id, binding_ref
        )
        captured: list[VerificationReplayCase] = []
        raw_results: list[dict[str, JsonValue]] = []
        for case in plan.cases:
            if self._cancel_requested(task, run_id, cancel_event):
                captured.append(
                    VerificationReplayCase(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="CANCELLED",
                        message="local target verification cancellation requested",
                        audit_ref=provenance_ref,
                    )
                )
                break
            result = self.runner.run(case.operation, case.payload, timeout_s=case.timeout_s)
            raw_results.append({"case_id": case.case_id, "result": result})
            target_status = str(result.get("status"))
            replay_status: Literal["SUCCEEDED", "TIMEOUT", "CANCELLED", "ERROR"] = (
                "SUCCEEDED"
                if target_status == "READY"
                else "TIMEOUT"
                if target_status == "TIMEOUT"
                else "ERROR"
            )
            captured.append(
                VerificationReplayCase(
                    case_id=case.case_id,
                    operation=case.operation,
                    status=replay_status,
                    result=result,
                    message=f"local target command completed with {target_status}",
                    audit_ref=provenance_ref,
                )
            )
        replay_path = self.artifacts.write_json(
            f"verify/{task.robot_id}/runs/{run_id}/target-replay.json",
            {
                "schema_version": "rolo-local-target-replay-capture/v1",
                "robot_id": task.robot_id,
                "run_id": run_id,
                "read_only": True,
                "results": raw_results,
            },
        )
        replay_ref = ArtifactLayout(self.artifacts.root).ref(replay_path)
        fixture = VerificationReplayFixture(
            fixture_id=f"fixture-{uuid4().hex}",
            robot_id=task.robot_id,
            target_provenance_ref=provenance_ref,
            target_provenance_sha256=provenance_sha256,
            target_provenance_schema_version="rolo-target-provenance/v2",
            cases=captured,
            safe_stop="NOT_REQUIRED",
            rollback="NOT_REQUIRED",
            replay_ref=replay_ref,
        )
        run = run_verification_replay(
            plan,
            fixture,
            artifacts=self.artifacts,
            run_id=run_id,
        )
        evidence_path = resolve_artifact_ref(self.artifacts.root, run.evidence_ref)
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        report = {
            "schema_version": "rolo-verification-regression-report/v1",
            "robot_id": task.robot_id,
            "run_id": run_id,
            "status": run.status,
            "case_results": [item.model_dump(mode="json") for item in run.case_results],
            "release_authority": "none",
        }
        handoff = commit_verification_handoff(
            self.artifacts.root,
            task.robot_id,
            regression_report=report,
            evidence_package=evidence,
            run_id=run_id,
        )
        if on_output:
            on_output("stdout", f"{self.provenance_source} verify: {run.status}")
        layout = ArtifactLayout(self.artifacts.root)
        return {
            "handoff": layout.ref(layout.stage_file("verify", task.robot_id, "handoff.json")),
            "regression_report": handoff.regression_report_ref,
            "evidence_package": handoff.evidence_package_ref,
            "target_provenance": provenance_ref,
            "replay": replay_ref,
        }
