"""Bounded L1 exploration plan for a running ``app.map.create`` session.

This module only creates and validates a deterministic plan.  It never talks
to a target and never emits velocity.  Execution is a separate, explicitly
confirmed target adapter so that planning cannot accidentally move a robot.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ExploreSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["forward", "rotate", "stop"]
    duration_s: float = Field(gt=0.0, le=15.0)
    linear_x_mps: float = Field(ge=-0.05, le=0.05)
    angular_z_rps: float = Field(ge=-0.20, le=0.20)


class MicroExplorePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-micro-explore-plan/v1"] = "rolo-micro-explore-plan/v1"
    plan_id: str = Field(pattern=r"^micro-explore-plan-[0-9a-f]{24}$")
    level: Literal["L1", "L2"] = "L1"
    cycles: int = Field(ge=1, le=3)
    input_topic: Literal["/controller/cmd_vel"] = "/controller/cmd_vel"
    expected_safe_output: Literal["/controller/cmd_vel_safe"] = "/controller/cmd_vel_safe"
    max_linear_mps: float = 0.05
    max_angular_rps: float = 0.20
    segments: list[ExploreSegment] = Field(min_length=4, max_length=12)
    total_duration_s: float = Field(gt=0.0, le=30.0)
    no_motion_until_explicit_execution: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def build_l1_micro_explore_plan(*, cycles: int = 1) -> MicroExplorePlan:
    """Build the fixed low-speed, short-range L1 canary plan."""
    if not 1 <= cycles <= 3:
        raise ValueError("L1 exploration cycles must be between 1 and 3")
    segments: list[ExploreSegment] = []
    for _ in range(cycles):
        segments.extend(
            [
                ExploreSegment(kind="forward", duration_s=1.0, linear_x_mps=0.05, angular_z_rps=0.0),
                ExploreSegment(kind="stop", duration_s=0.5, linear_x_mps=0.0, angular_z_rps=0.0),
                ExploreSegment(kind="rotate", duration_s=1.5, linear_x_mps=0.0, angular_z_rps=0.20),
                ExploreSegment(kind="stop", duration_s=0.5, linear_x_mps=0.0, angular_z_rps=0.0),
            ]
        )
    total = sum(segment.duration_s for segment in segments)
    seed = {
        "level": "L1",
        "cycles": cycles,
        "segments": [segment.model_dump(mode="json") for segment in segments],
    }
    return MicroExplorePlan(
        plan_id="micro-explore-plan-" + _digest(seed)[:24],
        cycles=cycles,
        segments=segments,
        total_duration_s=total,
    )


def build_l2_half_meter_plan() -> MicroExplorePlan:
    """Build one bounded 0.5 m forward plus short rotation sweep."""
    segments = [
        ExploreSegment(kind="forward", duration_s=10.0, linear_x_mps=0.05, angular_z_rps=0.0),
        ExploreSegment(kind="stop", duration_s=0.5, linear_x_mps=0.0, angular_z_rps=0.0),
        ExploreSegment(kind="rotate", duration_s=4.0, linear_x_mps=0.0, angular_z_rps=0.20),
        ExploreSegment(kind="stop", duration_s=0.5, linear_x_mps=0.0, angular_z_rps=0.0),
    ]
    seed = {"level": "L2", "segments": [segment.model_dump(mode="json") for segment in segments]}
    return MicroExplorePlan(
        plan_id="micro-explore-plan-" + _digest(seed)[:24],
        level="L2",
        cycles=1,
        segments=segments,
        total_duration_s=sum(segment.duration_s for segment in segments),
    )


__all__ = ["ExploreSegment", "MicroExplorePlan", "build_l1_micro_explore_plan", "build_l2_half_meter_plan"]
