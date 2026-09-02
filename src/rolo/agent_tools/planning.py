"""Small typed planning protocol shared by the current Agent and Rolo."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.agent_tools.native_tools import AgentNativeToolDescriptor


class ToolPlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-planning-request/v1"] = (
        "rolo-tool-planning-request/v1"
    )
    goal: str = Field(min_length=1, max_length=4_000)
    target_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    surface_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_tool_ids: list[str] = Field(min_length=1, max_length=256)
    expires_at: datetime


class ToolPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(min_length=1, max_length=128)
    arguments: dict[str, str] = Field(default_factory=dict, max_length=32)
    expected_observation: str = Field(min_length=1, max_length=1_000)
    mode: Literal["readonly", "mutating"] = "readonly"


class ToolPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-plan/v1"] = "rolo-tool-plan/v1"
    goal: str = Field(min_length=1, max_length=4_000)
    target_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    surface_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    steps: list[ToolPlanStep] = Field(min_length=1, max_length=32)
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_digest(self) -> ToolPlan:
        payload = self.model_dump(mode="json", exclude={"plan_sha256"})
        expected = hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.plan_sha256 != expected:
            raise ValueError("tool plan digest mismatch")
        return self


def build_tool_plan(
    *,
    goal: str,
    target_id: str,
    session_id: str,
    surface_digest: str,
    steps: Sequence[ToolPlanStep],
) -> ToolPlan:
    payload = {
        "schema_version": "rolo-tool-plan/v1",
        "goal": goal,
        "target_id": target_id,
        "session_id": session_id,
        "surface_digest": surface_digest,
        "steps": [step.model_dump(mode="json") for step in steps],
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ToolPlan(**payload, plan_sha256=digest)


def validate_tool_plan(
    plan: ToolPlan,
    *,
    allowed_tool_ids: Sequence[str],
    catalog: Sequence[AgentNativeToolDescriptor],
    allow_mutating: bool = False,
) -> None:
    allowed = set(allowed_tool_ids)
    descriptors = {item.tool_id: item for item in catalog}
    for step in plan.steps:
        if step.tool_id not in allowed:
            raise ValueError(f"tool plan step is outside the session allowlist: {step.tool_id}")
        descriptor = descriptors.get(step.tool_id)
        if descriptor is None:
            raise ValueError(f"tool plan references an unknown tool: {step.tool_id}")
        if step.mode == "mutating" and not allow_mutating:
            raise ValueError("mutating tool plan steps require explicit approval")
        if descriptor.access == "read" and step.mode != "readonly":
            raise ValueError(f"read-only tool cannot be planned as mutating: {step.tool_id}")


def utc_expiry(seconds: int) -> datetime:
    """Return a timezone-aware planning expiry for interactive Agent use."""
    if seconds < 1 or seconds > 86_400:
        raise ValueError("planning expiry must be between 1 second and 24 hours")
    return datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=seconds)
