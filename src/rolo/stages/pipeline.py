"""Probe-only lifecycle read model for Rolo v2."""

from __future__ import annotations

from pathlib import Path

from rolo.stages.contracts import (
    AgentRequirement,
    PipelineAssessment,
    StageAssessment,
    StageName,
    StageStatus,
)


def _evidence_path(artifact_root: Path, robot_id: str) -> Path:
    return artifact_root.parent / "config" / "target-evidence" / f"{robot_id}-bundle.json"


def assess_stage(stage: StageName, artifact_root: Path, robot_id: str) -> StageAssessment:
    if stage is not StageName.PROBE:
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
    path = _evidence_path(artifact_root, robot_id)
    if not path.is_file():
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.NOT_STARTED,
            summary="Target evidence has not been collected",
            prerequisites=[str(path)],
            blockers=["Run `rolo probe` or `robotctl probe start`"],
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    return StageAssessment(
        stage=StageName.PROBE,
        robot_id=robot_id,
        status=StageStatus.READY,
        summary="Target evidence is available; Agent may request the Tool Surface",
        artifacts={"target_evidence": str(path)},
        agent_requirement=AgentRequirement.PROBE_AGENT,
    )


def assess_pipeline(artifact_root: Path, robot_id: str) -> PipelineAssessment:
    return PipelineAssessment(
        robot_id=robot_id,
        stages=[assess_stage(stage, artifact_root, robot_id) for stage in StageName],
    )
