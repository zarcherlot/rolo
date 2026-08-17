from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from rolo.core.models import utc_now
from rolo.stages.contracts import AgentRequirement


class BuildInputsStatus(StrEnum):
    READY_FOR_CODING = "READY_FOR_CODING"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class BuildInputs(BaseModel):
    schema_version: str = "robot-build-inputs/v1"
    stage: str = "build"
    robot_id: str
    discovery_id: str
    status: BuildInputsStatus
    capability_manifest_ref: str
    semantic_bindings_ref: str
    tool_catalog_ref: str
    probe_refs: dict[str, str]
    semantic_binding_candidates: int = 0
    tool_count: int = 0
    unresolved_dependencies: list[str] = Field(default_factory=list)
    agent_requirement: AgentRequirement = AgentRequirement.CODING_AGENT
    created_at: datetime = Field(default_factory=utc_now)
