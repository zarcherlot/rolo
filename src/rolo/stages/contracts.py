from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from rolo.core.models import utc_now


class StageName(str, Enum):
    ADAPT = "adapt"
    DIAGNOSE = "diagnose"
    VERIFY = "verify"


class AgentRequirement(str, Enum):
    ADAPTER_AGENT = "adapter_agent"
    DIAGNOSIS_AGENT = "diagnosis_agent"
    VERIFICATION_AGENT = "verification_agent"


class StageStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    READY = "READY"
    COMPLETE = "COMPLETE"


class StageAssessment(BaseModel):
    schema_version: str = "robot-stage-assessment/v1"
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
    schema_version: str = "robot-three-stage-pipeline/v1"
    robot_id: str
    stages: list[StageAssessment]
    observed_at: datetime = Field(default_factory=utc_now)
