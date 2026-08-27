"""Formal natural-language service entrypoint backed by canonical target services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rolo.job_service import JobService
from rolo.natural_language import NaturalLanguageIntent, NaturalLanguageOperation
from rolo.target_ref import parse_target_ref
from rolo.targets.approvals import (
    BootstrapApprovalRequest,
    approve_bootstrap,
    request_bootstrap_approval,
)
from rolo.targets.executor import create_target_executor
from rolo.targets.models import TargetBootstrapPlan


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
