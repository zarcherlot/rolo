from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from rolo.core.models import utc_now
from rolo.stages.contracts import AgentRequirement


class BuildPlanStatus(StrEnum):
    BLOCKED = "BLOCKED"
    REQUIRES_CODING = "REQUIRES_CODING"
    READY_FOR_CONFORMANCE = "READY_FOR_CONFORMANCE"


class BuildTask(BaseModel):
    id: str
    description: str
    operations: list[str] = Field(default_factory=list)
    required_skill: str
    agent_requirement: AgentRequirement = AgentRequirement.CODING_AGENT


class BuildPlan(BaseModel):
    schema_version: str = "robot-build-plan/v1"
    stage: str = "build"
    robot_id: str
    source_discovery_id: str
    status: BuildPlanStatus
    tasks: list[BuildTask]
    required_skills: list[str]
    candidate_operations: list[str] = Field(default_factory=list)
    state_graph_baseline_required: bool = True
    handoff_ref: str
    created_at: datetime = Field(default_factory=utc_now)
