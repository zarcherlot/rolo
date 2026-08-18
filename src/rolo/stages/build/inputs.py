from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from rolo.core.models import utc_now
from rolo.stages.contracts import AgentRequirement


class BuildInputsStatus(str, Enum):
    READY_FOR_CODING = "READY_FOR_CODING"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class SemanticCandidate(BaseModel):
    field: str
    value: Any
    unit: str | None = None
    source_kind: Literal["urdf", "launch", "config", "agent", "user"]
    source_path: str
    source_key: str
    status: Literal["DECLARED_UNVERIFIED", "DISCOVERED_UNVERIFIED"]
    safety_authority: Literal["none"] = "none"


class SemanticContext(BaseModel):
    schema_version: str = "robot-semantic-context/v1"
    robot_id: str
    discovery_id: str
    unresolved_semantics: list[str] = Field(default_factory=list)
    candidates: list[SemanticCandidate] = Field(default_factory=list)
    candidates_are_verified_limits: bool = False
    motion_safety_status: Literal["UNAPPROVED", "APPROVED"] = "UNAPPROVED"
    required_validation: list[str] = Field(
        default_factory=lambda: [
            "Correlate each candidate with controller behavior and robot documentation",
            "Validate motion limits under controlled debug and test procedures",
            "Require explicit safety approval before promoting a candidate to a hard limit",
        ]
    )
    created_at: datetime = Field(default_factory=utc_now)


class StageSemanticInputs(BaseModel):
    schema_version: str = "robot-stage-semantic-inputs/v1"
    stage: Literal["debug", "test"]
    robot_id: str
    source_discovery_id: str
    semantic_context_ref: str = ""
    unresolved_semantics: list[str] = Field(default_factory=list)
    semantic_candidates: list[SemanticCandidate] = Field(default_factory=list)
    safety_instruction: str = (
        "Treat candidates as diagnostic/test inputs only; never use them as verified motion "
        "safety limits until explicit validation and approval."
    )
    created_at: datetime = Field(default_factory=utc_now)


class BuildInputs(BaseModel):
    schema_version: str = "robot-build-inputs/v1"
    stage: str = "build"
    robot_id: str
    discovery_id: str
    status: BuildInputsStatus
    capability_manifest_ref: str
    semantic_bindings_ref: str
    semantic_context_ref: str
    tool_catalog_ref: str
    software_summary_ref: str = ""
    package_inventory_ref: str = ""
    software_package_count: int = 0
    software_inventory_complete: bool = False
    probe_refs: dict[str, str]
    semantic_binding_candidates: int = 0
    semantic_value_candidates: int = 0
    tool_count: int = 0
    unresolved_dependencies: list[str] = Field(default_factory=list)
    unresolved_semantics: list[str] = Field(default_factory=list)
    agent_requirement: AgentRequirement = AgentRequirement.CODING_AGENT
    created_at: datetime = Field(default_factory=utc_now)
