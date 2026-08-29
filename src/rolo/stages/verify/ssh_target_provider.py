"""Bounded SSH Verify provider backed by the main v2 evidence contract."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.core.persistence import interprocess_lock
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.diagnose.episode import TargetProvenance
from rolo.stages.handoffs import VerificationHandoff, commit_verification_handoff
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationCaseResult,
    VerificationOracle,
    VerificationPlan,
    VerificationRegressionReport,
    VerificationRunReport,
    validate_structured_verification_evidence,
)
from rolo.stages.verify.legacy_adapter import adapt_legacy_provider_evidence
from rolo.stages.verify.ssh_provenance import SshTargetProvenanceCollector
from rolo.target_ref import SshTargetRef
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.executor import CommandRunner


class SshTargetHealthProvider:
    """Run fixed Linux/workspace/companion checks and materialize v2 evidence."""

    platform_operation = "target.platform.read"
    workspace_operation = "target.workspace.readiness"
    companion_operation = "target.companion.health"

    def __init__(
        self,
        target: SshTargetRef,
        *,
        known_hosts: Path,
        profile_sha256: str,
        package_id: str,
        package_version: str,
        runner: CommandRunner | None = None,
    ) -> None:
        self.target = target
        self.profile_sha256 = profile_sha256
        self.expected_health = f"{package_id} {package_version}"
        self.transport = SubprocessBootstrapTransport(
            target,
            known_hosts=known_hosts,
            runner=runner,
        )

    def plan(self, robot_id: str) -> VerificationPlan:
        return VerificationPlan(
            robot_id=robot_id,
            cases=[
                VerificationCase(
                    case_id="target-platform",
                    operation=self.platform_operation,
                    payload={"mode": "system"},
                    timeout_s=30.0,
                    oracle=VerificationOracle(
                        kind="FIELD_EQUALS", path="platform", expected="Linux"
                    ),
                ),
                VerificationCase(
                    case_id="workspace-readiness",
                    operation=self.workspace_operation,
                    payload={"mode": "directory"},
                    timeout_s=30.0,
                    oracle=VerificationOracle(
                        kind="FIELD_EQUALS", path="accessible", expected=True
                    ),
                ),
                VerificationCase(
                    case_id="companion-health",
                    operation=self.companion_operation,
                    payload={"mode": "version"},
                    timeout_s=60.0,
                    oracle=VerificationOracle(
                        kind="FIELD_EQUALS", path="health", expected=self.expected_health
                    ),
                ),
            ],
        )

    def run(
        self,
        artifact_root: Path,
        *,
        robot_id: str,
        run_id: str | None = None,
        cancel_event: threading.Event | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> VerificationRunReport:
        lock_target = artifact_root / "verify" / robot_id / "ssh-target-provider.active"
        try:
            with interprocess_lock(lock_target, timeout_s=0.05, stale_after_s=600.0):
                return self._run_once(
                    artifact_root,
                    robot_id=robot_id,
                    run_id=run_id,
                    cancel_event=cancel_event,
                    clock=clock,
                )
        except TimeoutError as exc:
            raise ValueError(f"SSH target provider is already active for {robot_id}") from exc

    def _run_once(
        self,
        artifact_root: Path,
        *,
        robot_id: str,
        run_id: str | None,
        cancel_event: threading.Event | None,
        clock: Callable[[], datetime] | None,
    ) -> VerificationRunReport:
        now = clock or (lambda: datetime.now(timezone.utc))
        started = now().astimezone(timezone.utc)
        selected_run = run_id or f"verify-ssh-{uuid4().hex}"
        if cancel_event is not None and cancel_event.is_set():
            raise ValueError("SSH target verification was cancelled before collection")
        artifacts = ArtifactStore(artifact_root)
        binding, binding_ref, binding_sha256 = SshTargetProvenanceCollector(
            self.target, self.transport
        ).collect(
            artifacts,
            robot_id=robot_id,
            profile_sha256=self.profile_sha256,
            run_id=selected_run,
            clock=now,
        )
        provenance = TargetProvenance(
            schema_version="rolo-target-provenance/v2",
            target_id=robot_id,
            source="ssh-target",
            collector_version="0.1.0",
            collected_at=binding.captured_at,
            clock_offset_ms=0,
            target_binding_ref=binding_ref,
            target_binding_sha256=binding_sha256,
            collector_session_id=selected_run,
            clock_source="remote-monotonic",
            monotonic_ns=time.monotonic_ns(),
        )
        provenance_path = artifacts.write_json(
            f"targets/{robot_id}/provenance/{selected_run}.json",
            provenance.model_dump(mode="json"),
        )
        provenance_ref = ArtifactLayout(artifact_root).ref(provenance_path)
        provenance_sha256 = sha256_file(provenance_path)
        plan = self.plan(robot_id)
        commands = {
            self.platform_operation: ["uname", "-s"],
            self.workspace_operation: ["test", "-d", str(self.target.workspace)],
            self.companion_operation: ["rolo-target", "--version"],
        }
        results: list[VerificationCaseResult] = []
        for case in plan.cases:
            if cancel_event is not None and cancel_event.is_set():
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="CANCELLED",
                        message="SSH target verification cancelled before invocation",
                        provenance_ref=provenance_ref,
                    )
                )
                break
            try:
                outcome = self.transport.execute(commands[case.operation], timeout_s=case.timeout_s)
                if case.operation == self.platform_operation:
                    observation = {
                        "returncode": outcome.returncode,
                        "platform": outcome.stdout.strip(),
                    }
                elif case.operation == self.workspace_operation:
                    observation = {
                        "returncode": outcome.returncode,
                        "accessible": outcome.returncode == 0,
                        "workspace": str(self.target.workspace),
                    }
                else:
                    observation = {
                        "returncode": outcome.returncode,
                        "health": outcome.stdout.strip(),
                        "expected": self.expected_health,
                    }
                passed = outcome.returncode == 0 and (
                    (
                        case.operation == self.platform_operation
                        and observation["platform"] == "Linux"
                    )
                    or (
                        case.operation == self.workspace_operation
                        and observation["accessible"] is True
                    )
                    or (
                        case.operation == self.companion_operation
                        and observation["health"] == self.expected_health
                    )
                )
                observation_path = artifacts.write_json(
                    f"verify/{robot_id}/runs/{selected_run}/{case.case_id}_observation.json",
                    {
                        "schema_version": "rolo-target-read-only-observation/v1",
                        "case_id": case.case_id,
                        "operation": case.operation,
                        "stderr_excerpt": outcome.stderr.strip()[:1_000] or None,
                        **observation,
                    },
                )
                status: Literal["PASS", "FAIL", "ERROR"] = (
                    "ERROR" if outcome.returncode != 0 else "PASS" if passed else "FAIL"
                )
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status=status,
                        message=(
                            "target read-only case passed"
                            if passed
                            else "target read-only case failed"
                        ),
                        audit_ref=ArtifactLayout(artifact_root).ref(observation_path),
                        provenance_ref=provenance_ref,
                    )
                )
            except (TimeoutError, subprocess.TimeoutExpired):
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="TIMEOUT",
                        message="target read-only command timed out",
                        provenance_ref=provenance_ref,
                    )
                )
            except Exception as exc:
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="ERROR",
                        message=f"target provider failed: {type(exc).__name__}",
                        provenance_ref=provenance_ref,
                    )
                )
        status: Literal["PASS", "FAIL", "CANCELLED"] = (
            "CANCELLED"
            if any(item.status == "CANCELLED" for item in results)
            else "PASS"
            if results and all(item.status == "PASS" for item in results)
            else "FAIL"
        )
        replay_path = artifacts.write_json(
            f"verify/{robot_id}/runs/{selected_run}/target-replay.json",
            {
                "schema_version": "rolo-ssh-target-replay-capture/v1",
                "robot_id": robot_id,
                "run_id": selected_run,
                "read_only": True,
                "provenance_ref": provenance_ref,
                "results": [item.model_dump(mode="json") for item in results],
            },
        )
        replay_ref = ArtifactLayout(artifact_root).ref(replay_path)
        legacy_payload = {
            "schema_version": "rolo-verification-evidence/v1",
            "run_id": selected_run,
            "robot_id": robot_id,
            "status": status,
            "plan": plan.model_dump(mode="json"),
            "plan_sha256": canonical_json_sha256(plan.model_dump(mode="json")),
            "case_results": [item.model_dump(mode="json") for item in results],
            "target_provenance": {
                "transport": "ssh",
                "host": self.target.host,
                "workspace": str(self.target.workspace),
            },
            "started_at": started.isoformat(),
            "completed_at": now().astimezone(timezone.utc).isoformat(),
        }
        artifacts.write_json(
            f"verify/{robot_id}/runs/{selected_run}/legacy-provider-evidence.json", legacy_payload
        )
        _, evidence_ref = adapt_legacy_provider_evidence(
            legacy_payload,
            artifacts=artifacts,
            expected_robot_id=robot_id,
            expected_plan_sha256=canonical_json_sha256(plan.model_dump(mode="json")),
            target_provenance_ref=provenance_ref,
            target_provenance_sha256=provenance_sha256,
            target_provenance_schema_version="rolo-target-provenance/v2",
            safe_stop="NOT_REQUIRED",
            rollback="NOT_REQUIRED",
            replay_ref=replay_ref,
        )
        completed = now().astimezone(timezone.utc)
        return VerificationRunReport(
            run_id=selected_run,
            robot_id=robot_id,
            status=status,
            case_results=results,
            evidence_ref=evidence_ref,
            started_at=started,
            completed_at=completed,
        )

    def materialize_handoff(
        self,
        artifact_root: Path,
        report: VerificationRunReport,
    ) -> VerificationHandoff:
        """Commit provider output through the canonical Verify handoff validator."""

        evidence_path = ArtifactLayout(artifact_root).root / Path(
            report.evidence_ref.removeprefix("artifact://")
        )
        if not evidence_path.is_file():
            raise ValueError("SSH provider evidence artifact is missing")
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("SSH provider evidence artifact is not valid JSON") from exc
        if not isinstance(evidence, dict):
            raise ValueError("SSH provider evidence artifact must be a JSON object")
        validate_structured_verification_evidence(
            evidence, robot_id=report.robot_id, artifact_root=artifact_root
        )
        regression = VerificationRegressionReport(
            robot_id=report.robot_id,
            run_id=report.run_id,
            status=report.status,
            case_results=report.case_results,
            release_authority="none",
        )
        return commit_verification_handoff(
            artifact_root,
            report.robot_id,
            regression_report=regression.model_dump(mode="json"),
            evidence_package=evidence,
            run_id=report.run_id,
        )


__all__ = ["SshTargetHealthProvider"]
