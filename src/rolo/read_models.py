from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import RobotCapability
from rolo.stages.contracts import PipelineAssessment, StageAssessment, StageStatus
from rolo.workbench_read_models import evidence_id_for_reference


class OverviewState(str, Enum):
    READY = "READY"
    ATTENTION = "ATTENTION"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class OverviewBlocker(BaseModel):
    schema_version: Literal["rolo-blocker-summary/v2"] = "rolo-blocker-summary/v2"
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
    evidence_ids: list[str] = Field(default_factory=list)


class RobotOverview(BaseModel):
    schema_version: Literal["rolo-robot-overview/v2"] = "rolo-robot-overview/v2"
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


def _reference_hint(reference: str) -> str:
    normalized = reference.replace("\\", "/").rstrip("/")
    basename = normalized.rsplit("/", 1)[-1] or "withheld"
    return f"artifact:{basename}"


def _stage_references(stage: StageAssessment) -> list[str]:
    return sorted(
        {reference for reference in [*stage.prerequisites, *stage.artifacts.values()] if reference},
        key=len,
        reverse=True,
    )


def _sanitize_stage_text(stage: StageAssessment, text: str) -> str:
    sanitized = text
    for reference in _stage_references(stage):
        escaped_reference = reference.replace("\\", "\\\\")
        for candidate in sorted({reference, escaped_reference}, key=len, reverse=True):
            sanitized = sanitized.replace(candidate, _reference_hint(reference))
    return sanitized


def _recommended_blocker_action(stage: StageAssessment, safe_message: str) -> str:
    normalized = safe_message.casefold()
    stage_name = stage.stage.value.title()
    if "missing verified" in normalized:
        return (
            f"Produce and validate the required {stage_name} evidence, then reassess "
            "the pipeline."
        )
    if "unavailable or invalid" in normalized:
        return (
            f"Restore a validated {stage_name} handoff, then reassess the pipeline."
        )
    if "denied" in normalized or "authorization" in normalized or "policy" in normalized:
        return (
            f"Review the external {stage_name} policy or authorization decision, then "
            "reassess the pipeline."
        )
    return f"Resolve the reported {stage_name} blocker, then reassess the pipeline."


def _project_pipeline(pipeline: PipelineAssessment) -> PipelineAssessment:
    stages = [
        stage.model_copy(
            update={
                "summary": _sanitize_stage_text(stage, stage.summary),
                "prerequisites": [
                    _reference_hint(reference) for reference in stage.prerequisites
                ],
                "artifacts": {
                    name: _reference_hint(reference)
                    for name, reference in stage.artifacts.items()
                },
                "blockers": [
                    _sanitize_stage_text(stage, message) for message in stage.blockers
                ],
            }
        )
        for stage in pipeline.stages
    ]
    return pipeline.model_copy(update={"stages": stages})


def _overview_blockers(pipeline: PipelineAssessment) -> list[OverviewBlocker]:
    blockers: list[OverviewBlocker] = []
    for stage in pipeline.stages:
        for message in stage.blockers:
            safe_message = _sanitize_stage_text(stage, message)
            blockers.append(
                OverviewBlocker(
                    blocker_id=_blocker_id(pipeline.robot_id, stage.stage.value, message),
                    stage=stage.stage.value,
                    message=safe_message,
                    recommended_action=_recommended_blocker_action(stage, safe_message),
                    owner=stage.agent_requirement.value,
                    observed_at=stage.observed_at,
                    evidence_ids=sorted(
                        evidence_id_for_reference(pipeline.robot_id, reference)
                        for reference in stage.artifacts.values()
                    ),
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
    projected_pipeline = _project_pipeline(pipeline)
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
            (
                stage
                for stage in projected_pipeline.stages
                if stage.status != StageStatus.COMPLETE
            ),
            projected_pipeline.stages[-1],
        )
        summary = active.summary
        next_action = active.summary

    return RobotOverview(
        robot_id=robot.robot_id,
        state=state,
        summary=summary,
        next_action=next_action,
        blockers=blockers,
        pipeline=projected_pipeline,
        observed_at=pipeline.observed_at,
    )
