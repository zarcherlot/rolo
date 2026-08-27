"""Approval dry-run records bound to an exact bootstrap plan digest."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def bootstrap_plan_digest(plan: TargetBootstrapPlan) -> str:
    payload = json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class BootstrapApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-bootstrap-approval-request/v1"] = (
        "rolo-bootstrap-approval-request/v1"
    )
    request_id: str = Field(pattern=r"^bar-[0-9a-f]{32}$")
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: Literal["target.bootstrap.execute"]
    requested_by: str = Field(min_length=1, max_length=128)
    status: Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED"] = "PENDING"
    created_at: datetime
    expires_at: datetime


class BootstrapApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-bootstrap-approval-decision/v1"] = (
        "rolo-bootstrap-approval-decision/v1"
    )
    request_id: str
    plan_sha256: str
    scope: Literal["target.bootstrap.execute"]
    status: Literal["APPROVED"] = "APPROVED"
    approved_by: str
    approved_at: datetime


def request_bootstrap_approval(
    plan: TargetBootstrapPlan,
    *,
    requested_by: str,
    ttl: timedelta = timedelta(minutes=10),
    now: datetime | None = None,
) -> BootstrapApprovalRequest:
    if plan.status != BootstrapPlanStatus.APPROVAL_REQUIRED:
        raise ValueError("bootstrap approval is only required for an approval-required plan")
    if "target.bootstrap.execute" not in plan.required_approvals:
        raise ValueError("bootstrap plan does not declare target.bootstrap.execute approval")
    if not requested_by or any(character.isspace() for character in requested_by):
        raise ValueError("approval requester must be a non-whitespace identifier")
    if ttl <= timedelta(0) or ttl > timedelta(hours=24):
        raise ValueError("bootstrap approval TTL must be between 1 second and 24 hours")
    created_at = now or _utc_now()
    return BootstrapApprovalRequest(
        request_id=f"bar-{uuid4().hex}",
        plan_sha256=bootstrap_plan_digest(plan),
        scope="target.bootstrap.execute",
        requested_by=requested_by,
        created_at=created_at,
        expires_at=created_at + ttl,
    )


def approve_bootstrap(
    plan: TargetBootstrapPlan,
    request: BootstrapApprovalRequest,
    *,
    approved_by: str,
    now: datetime | None = None,
) -> BootstrapApprovalDecision:
    approved_at = now or _utc_now()
    if request.status != "PENDING":
        raise ValueError("bootstrap approval request is not pending")
    if request.plan_sha256 != bootstrap_plan_digest(plan):
        raise ValueError("bootstrap approval request is bound to a different plan")
    if approved_at >= request.expires_at:
        raise ValueError("bootstrap approval request has expired")
    if not approved_by or any(character.isspace() for character in approved_by):
        raise ValueError("approver must be a non-whitespace identifier")
    if approved_by == request.requested_by:
        raise ValueError("bootstrap approval cannot be self-approved")
    return BootstrapApprovalDecision(
        request_id=request.request_id,
        plan_sha256=request.plan_sha256,
        scope=request.scope,
        approved_by=approved_by,
        approved_at=approved_at,
    )
