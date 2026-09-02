from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import utc_now


class StageName(str, Enum):
    PROBE = "probe"
    TRACE = "trace"
    CERTIFY = "certify"


class AgentRequirement(str, Enum):
    PROBE_AGENT = "probe_agent"
    TRACE_AGENT = "trace_agent"
    CERTIFY_AGENT = "certify_agent"


class StageStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    READY = "READY"
    COMPLETE = "COMPLETE"


class StageAssessment(BaseModel):
    schema_version: Literal["robot-stage-assessment/v1"] = "robot-stage-assessment/v1"
    stage: StageName
    robot_id: str
    status: StageStatus
    summary: str
    optional: bool = False
    prerequisites: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    agent_requirement: AgentRequirement
    observed_at: datetime = Field(default_factory=utc_now)


class PipelineAssessment(BaseModel):
    schema_version: Literal["rolo-probe-trace-certify-pipeline/v1"] = (
        "rolo-probe-trace-certify-pipeline/v1"
    )
    robot_id: str
    stages: list[StageAssessment]
    observed_at: datetime = Field(default_factory=utc_now)
