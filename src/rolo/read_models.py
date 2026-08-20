from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import RobotCapability
from rolo.stages.contracts import PipelineAssessment, StageAssessment, StageStatus


class OverviewState(str, Enum):
    READY = "READY"
    ATTENTION = "ATTENTION"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class OverviewBlocker(BaseModel):
    schema_version: Literal["rolo-blocker-summary/v1"] = "rolo-blocker-summary/v1"
    blocker_id: str
    stage: str
    message: str
    recommended_action: str
    owner: str
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["pipeline_assessment"] = "pipeline_assessment"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"
    evidence_refs: list[str] = Field(default_factory=list)


class RobotOverview(BaseModel):
    schema_version: Literal["rolo-robot-overview/v1"] = "rolo-robot-overview/v1"
    robot_id: str
    state: OverviewState
    summary: str
    next_action: str
    blockers: list[OverviewBlocker] = Field(default_factory=list)
    pipeline: PipelineAssessment
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["computed_read_model"] = "computed_read_model"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"


def _blocker_id(robot_id: str, stage: str, message: str) -> str:
    digest = sha256(f"{robot_id}\0{stage}\0{message}".encode()).hexdigest()[:16]
    return f"blocker_{digest}"


def _overview_blockers(pipeline: PipelineAssessment) -> list[OverviewBlocker]:
    blockers: list[OverviewBlocker] = []
    for stage in pipeline.stages:
        for message in stage.blockers:
            blockers.append(
                OverviewBlocker(
                    blocker_id=_blocker_id(pipeline.robot_id, stage.stage.value, message),
                    stage=stage.stage.value,
                    message=message,
                    recommended_action=message,
                    owner=stage.agent_requirement.value,
                    observed_at=stage.observed_at,
                    evidence_refs=sorted(stage.artifacts.values()),
                )
            )
    return blockers


def _overview_state(stages: list[StageAssessment]) -> OverviewState:
    statuses = {stage.status for stage in stages}
    if StageStatus.BLOCKED in statuses:
        return OverviewState.ATTENTION
    if StageStatus.DEGRADED in statuses:
        return OverviewState.DEGRADED
    ready_statuses = {StageStatus.READY, StageStatus.COMPLETE}
    if stages and all(stage.status in ready_statuses for stage in stages):
        return OverviewState.READY
    return OverviewState.NOT_READY


def build_robot_overview(
    robot: RobotCapability,
    pipeline: PipelineAssessment,
) -> RobotOverview:
    blockers = _overview_blockers(pipeline)
    state = _overview_state(pipeline.stages)
    if blockers:
        first = blockers[0]
        summary = f"{first.stage.title()} is blocked: {first.message}"
        next_action = first.recommended_action
    elif not pipeline.stages:
        summary = "No pipeline assessments are available."
        next_action = "Run adapt discovery"
    else:
        active = next(
            (stage for stage in pipeline.stages if stage.status != StageStatus.COMPLETE),
            pipeline.stages[-1],
        )
        summary = active.summary
        next_action = active.summary

    return RobotOverview(
        robot_id=robot.robot_id,
        state=state,
        summary=summary,
        next_action=next_action,
        blockers=blockers,
        pipeline=pipeline,
        observed_at=pipeline.observed_at,
    )
