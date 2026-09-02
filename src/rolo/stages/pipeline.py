from __future__ import annotations

from pathlib import Path

from rolo.stages.adapt.service import assess_adapt
from rolo.stages.contracts import (
    AgentRequirement,
    PipelineAssessment,
    StageAssessment,
    StageName,
    StageStatus,
)


def assess_stage(stage: StageName, artifact_root: Path, robot_id: str) -> StageAssessment:
    if stage is StageName.PROBE:
        return assess_adapt(artifact_root, robot_id)
    requirement = (
        AgentRequirement.TRACE_AGENT
        if stage is StageName.TRACE
        else AgentRequirement.CERTIFY_AGENT
    )
    return StageAssessment(
        stage=stage,
        robot_id=robot_id,
        status=StageStatus.NOT_STARTED,
        summary=f"{stage.value.title()} is reserved for a later v2 increment.",
        optional=True,
        agent_requirement=requirement,
    )


def assess_pipeline(artifact_root: Path, robot_id: str) -> PipelineAssessment:
    return PipelineAssessment(
        robot_id=robot_id,
        stages=[assess_stage(stage, artifact_root, robot_id) for stage in StageName],
    )
