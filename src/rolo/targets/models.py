"""Versioned read models for target connection and bootstrap decisions."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from rolo.target_ref import TargetRef


class TargetConnectionState(str, Enum):
    READY = "READY"
    HOST_KEY_REQUIRED = "HOST_KEY_REQUIRED"
    UNREACHABLE = "UNREACHABLE"
    WORKSPACE_MISSING = "WORKSPACE_MISSING"
    UNSUPPORTED = "UNSUPPORTED"


class CompanionStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class TargetConnectionAssessment(BaseModel):
    schema_version: Literal["rolo-target-connection-assessment/v1"] = (
        "rolo-target-connection-assessment/v1"
    )
    target: TargetRef
    state: TargetConnectionState
    reachable: bool
    host_key_pinned: bool | None = None
    platform: str | None = None
    architecture: str | None = None
    workspace_accessible: bool = False
    companion: CompanionStatus = CompanionStatus.UNKNOWN
    blockers: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class TargetRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    HOST_MUTATION = "HOST_MUTATION"


class BootstrapAction(str, Enum):
    VERIFY_PLATFORM = "VERIFY_PLATFORM"
    VERIFY_WORKSPACE = "VERIFY_WORKSPACE"
    INSTALL_COMPANION = "INSTALL_COMPANION"
    HEALTH_CHECK = "HEALTH_CHECK"


class TargetBootstrapStep(BaseModel):
    action: BootstrapAction
    risk: TargetRisk
    approval_required: bool = False
    description: str


class BootstrapPlanStatus(str, Enum):
    READY = "READY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"


class TargetBootstrapPlan(BaseModel):
    schema_version: Literal["rolo-target-bootstrap-plan/v1"] = "rolo-target-bootstrap-plan/v1"
    target: TargetRef
    assessment_state: TargetConnectionState
    status: BootstrapPlanStatus
    steps: list[TargetBootstrapStep] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
