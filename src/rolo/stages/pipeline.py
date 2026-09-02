from __future__ import annotations

from pathlib import Path

from rolo.stages.adapt.service import assess_adapt
from rolo.stages.contracts import PipelineAssessment, StageAssessment, StageName
from rolo.stages.diagnose.service import assess_diagnose
from rolo.stages.verify.service import assess_verify


def assess_stage(stage: StageName, artifact_root: Path, robot_id: str) -> StageAssessment:
    assessors = {
        StageName.PROBE: assess_adapt,
        StageName.TRACE: assess_diagnose,
        StageName.CERTIFY: assess_verify,
    }
    return assessors[stage](artifact_root, robot_id)


def assess_pipeline(artifact_root: Path, robot_id: str) -> PipelineAssessment:
    return PipelineAssessment(
        robot_id=robot_id,
        stages=[assess_stage(stage, artifact_root, robot_id) for stage in StageName],
    )
