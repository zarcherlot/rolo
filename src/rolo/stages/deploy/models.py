from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from rolo.core.models import utc_now


class DeploymentHandoffStatus(StrEnum):
    READY_FOR_BUILD = "READY_FOR_BUILD"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class DeploymentHandoff(BaseModel):
    schema_version: str = "robot-deployment-handoff/v1"
    stage: str = "deploy"
    robot_id: str
    discovery_id: str
    status: DeploymentHandoffStatus
    capability_manifest_ref: str
    semantic_bindings_ref: str
    tool_catalog_ref: str
    semantic_binding_candidates: int = 0
    tool_count: int = 0
    unresolved_dependencies: list[str] = Field(default_factory=list)
    dependency_handler: str = "deterministic_scripts"
    agent_skill_required: bool = False
    optional_agent_skills: list[str] = Field(default_factory=lambda: ["rolo-deploy-assistant"])
    created_at: datetime = Field(default_factory=utc_now)
