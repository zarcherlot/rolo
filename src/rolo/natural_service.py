"""Formal natural-language service entrypoint backed by canonical target services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rolo.commands.lifecycle import run_adapt_start
from rolo.job_service import JobService
from rolo.jobs import run_bootstrap_job
from rolo.natural_language import NaturalLanguageIntent, NaturalLanguageOperation
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.target_ref import LocalTargetRef, SshTargetRef, parse_target_ref
from rolo.targets.approvals import (
    BootstrapApprovalDecision,
    BootstrapApprovalRequest,
    approve_bootstrap,
    request_bootstrap_approval,
)
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.executor import create_target_executor
from rolo.targets.models import TargetBootstrapPlan
from rolo.targets.security import validate_bootstrap_security


class NaturalLanguageService:
    def __init__(self, jobs: JobService) -> None:
        self.jobs = jobs

    def execute(
        self,
        intent: NaturalLanguageIntent,
        *,
        known_hosts: Path | None = None,
        timeout_s: float = 10.0,
    ) -> Any:
        if intent.operation == NaturalLanguageOperation.ADAPT_START:
            if not intent.target or not intent.robot_id:
                raise ValueError("Adapt request requires target and robot id")
            target = parse_target_ref(intent.target)
            if not isinstance(target, LocalTargetRef):
                raise ValueError(
                    "natural-language Adapt currently supports local workspaces only"
                )
            return run_adapt_start(
                robot_id=intent.robot_id,
                project_root=target.workspace,
                urdf=Path(intent.urdf) if intent.urdf else None,
                active_probe=ActiveProbeMode.RUNTIME_READONLY,
                run_agent=intent.run_agent,
                scratch_root=None,
                timeout=None,
                evidence_mode=EvidenceDeploymentMode.LOCAL,
                allow_executable=None,
                collector_descriptor=None,
                verification_secret=None,
                ssh_target=None,
                known_hosts=None,
                collector_config=".rolo/config/target-evidence-collector.json",
                evidence_timeout=45.0,
            )
        if intent.operation == NaturalLanguageOperation.INSPECT:
            target = self._target(intent.target)
            return create_target_executor(
                target, known_hosts=known_hosts, timeout_s=timeout_s
            ).inspect()
        if intent.operation == NaturalLanguageOperation.BOOTSTRAP_PLAN:
            target = self._target(intent.target)
            return create_target_executor(
                target, known_hosts=known_hosts, timeout_s=timeout_s
            ).plan_bootstrap()
        if intent.operation == NaturalLanguageOperation.BOOTSTRAP_REQUEST:
            if not intent.plan_file or not intent.actor:
                raise ValueError("bootstrap request requires plan file and actor")
            plan = TargetBootstrapPlan.model_validate_json(
                Path(intent.plan_file).read_text(encoding="utf-8")
            )
            return request_bootstrap_approval(plan, requested_by=intent.actor)
        if intent.operation == NaturalLanguageOperation.BOOTSTRAP_APPROVE:
            if not intent.plan_file or not intent.request_file or not intent.actor:
                raise ValueError("bootstrap approval requires plan, request and actor")
            plan = TargetBootstrapPlan.model_validate_json(
                Path(intent.plan_file).read_text(encoding="utf-8")
            )
            request = BootstrapApprovalRequest.model_validate_json(
                Path(intent.request_file).read_text(encoding="utf-8")
            )
            return approve_bootstrap(plan, request, approved_by=intent.actor)
        if intent.operation == NaturalLanguageOperation.BOOTSTRAP_EXECUTE:
            required = (
                intent.plan_file,
                intent.request_file,
                intent.decision_file,
                intent.manifest_file,
                intent.package_file,
                intent.verification_key_file,
                intent.known_hosts_file,
            )
            if any(value is None for value in required):
                raise ValueError("bootstrap execute requires all input files")
            plan = TargetBootstrapPlan.model_validate_json(
                Path(intent.plan_file).read_text(encoding="utf-8")
            )
            request = BootstrapApprovalRequest.model_validate_json(
                Path(intent.request_file).read_text(encoding="utf-8")
            )
            decision = BootstrapApprovalDecision.model_validate_json(
                Path(intent.decision_file).read_text(encoding="utf-8")
            )
            if not isinstance(plan.target, SshTargetRef):
                raise ValueError("bootstrap execution requires an SSH target")
            if not intent.execute:
                return {
                    "status": "BOOTSTRAP_EXECUTION_READY",
                    "plan_sha256": request.plan_sha256,
                    "approval_request_id": request.request_id,
                    "target": plan.target.model_dump(mode="json"),
                    "mutation_started": False,
                }
            known_hosts, verification_key_path = validate_bootstrap_security(
                Path(intent.known_hosts_file), Path(intent.verification_key_file)
            )
            verification_key = verification_key_path.read_bytes()
            transport = SubprocessBootstrapTransport(
                plan.target, known_hosts=known_hosts
            )
            job, result = run_bootstrap_job(
                self.jobs.store,
                plan,
                request,
                decision,
                manifest_path=Path(intent.manifest_file),
                package_path=Path(intent.package_file),
                verification_key=verification_key,
                transport=transport,
                timeout_s=timeout_s,
                rollback_on_failure=True,
            )
            return {"job": job, "result": result}
        if intent.operation == NaturalLanguageOperation.JOB_RECOVER:
            if not intent.job_id:
                raise ValueError("job recovery requires job id")
            return self.jobs.recover(intent.job_id)
        raise ValueError(f"unsupported natural-language operation: {intent.operation.value}")

    @staticmethod
    def _target(value: str | None):
        if not value:
            raise ValueError("natural-language target is required")
        return parse_target_ref(value)
