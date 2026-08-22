from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from rolo.core.models import utc_now


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
            "Validate motion limits under controlled diagnosis and verification procedures",
            "Require explicit safety approval before promoting a candidate to a hard limit",
        ]
    )
    created_at: datetime = Field(default_factory=utc_now)


class StageSemanticInputs(BaseModel):
    schema_version: str = "robot-stage-semantic-inputs/v1"
    stage: Literal["diagnose", "verify"]
    robot_id: str
    source_discovery_id: str
    semantic_context_ref: str = ""
    unresolved_semantics: list[str] = Field(default_factory=list)
    semantic_candidates: list[SemanticCandidate] = Field(default_factory=list)
    safety_instruction: str = (
        "Treat candidates as diagnosis/verification inputs only; never use them as verified motion "
        "safety limits until explicit validation and approval."
    )
    created_at: datetime = Field(default_factory=utc_now)


class AdaptInputs(BaseModel):
    schema_version: Literal["robot-adapt-inputs/v1", "robot-adapt-inputs/v2"] = (
        "robot-adapt-inputs/v2"
    )
    stage: str = "adapt"
    robot_id: str
    discovery_id: str
    semantic_context_ref: str
    robot_wiki_ref: str = ""
    discovery_manifest_ref: str = ""
    discovery_manifest_sha256: str = ""
    heuristic_analysis_ref: str = ""
    created_at: datetime = Field(default_factory=utc_now)
