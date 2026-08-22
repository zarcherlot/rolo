"""Strict, non-authoritative output contracts for Adapt heuristic skills."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from rolo.stages.adapt.agent_contracts import AgentArtifactProvenance, AgentBudgetUsage

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_DEFINITION_ID_PATTERN = r"^[a-z][a-z0-9_.-]{0,127}$"
_ACTION_ID_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
_PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bPLACEHOLDER\b|<[^>]+>|\{\{[^}]+\}\})",
    re.IGNORECASE,
)


def _reject_placeholder(value: str) -> str:
    if _PLACEHOLDER_RE.search(value):
        raise ValueError("skill output must not contain placeholders")
    return value


def _reject_json_placeholders(value: JsonValue) -> None:
    if isinstance(value, str):
        _reject_placeholder(value)
    elif isinstance(value, list):
        for item in value:
            _reject_json_placeholders(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_placeholder(key)
            _reject_json_placeholders(item)


class DiscoveryPlanAction(BaseModel):
    """One proposed invocation of an orchestrator-owned, read-only definition."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(pattern=_ACTION_ID_PATTERN)
    kind: Literal["PROBE", "QUERY"]
    definition_id: str = Field(pattern=_DEFINITION_ID_PATTERN)
    parameters: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)
    expected_evidence_types: list[str] = Field(min_length=1, max_length=16)
    rationale: str = Field(min_length=8, max_length=1_000)
    risk: Literal["R0"] = "R0"

    @field_validator("expected_evidence_types")
    @classmethod
    def validate_evidence_types(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("expected evidence types must be unique")
        for item in value:
            if not re.fullmatch(_DEFINITION_ID_PATTERN, item):
                raise ValueError("expected evidence types must use canonical identifiers")
        return value

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        return _reject_placeholder(value)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _reject_json_placeholders(value)
        return value


class DiscoveryRemainingBudget(BaseModel):
    """Budget left for the orchestrator after accepting this proposal."""

    model_config = ConfigDict(extra="forbid")

    rounds: int = Field(ge=0, le=256)
    elapsed_ms: int = Field(ge=0)
    result_bytes: int = Field(ge=0)
    failures: int = Field(ge=0, le=256)


class AdaptDiscoveryPlan(BaseModel):
    """A bounded plan proposal; it is never authority to execute a probe."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-discovery-plan/v1"] = (
        "rolo-adapt-discovery-plan/v1"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    discovery_id: str = Field(min_length=1, max_length=128)
    target_fingerprint_sha256: str = Field(pattern=_SHA256_PATTERN)
    actions: list[DiscoveryPlanAction] = Field(default_factory=list, max_length=32)
    unknowns: list[str] = Field(default_factory=list, max_length=128)
    stop_conditions: list[str] = Field(min_length=1, max_length=16)
    remaining_budget: DiscoveryRemainingBudget
    budget_usage: AgentBudgetUsage
    provenance: AgentArtifactProvenance

    @field_validator("unknowns", "stop_conditions")
    @classmethod
    def validate_notes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("discovery plan notes must be unique")
        for item in value:
            if not item or len(item) > 1_000:
                raise ValueError("discovery plan notes must contain 1-1000 characters")
            _reject_placeholder(item)
        return value

    @model_validator(mode="after")
    def validate_action_identity(self) -> AdaptDiscoveryPlan:
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("discovery action IDs must be unique")
        if self.provenance.skill_name != "rolo-adapt-discovery":
            raise ValueError("discovery plan provenance must identify rolo-adapt-discovery")
        if not self.provenance.input_artifact_sha256:
            raise ValueError("discovery plan provenance requires input artifact hashes")
        return self
