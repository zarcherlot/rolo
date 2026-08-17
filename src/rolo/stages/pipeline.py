from __future__ import annotations

from pathlib import Path

from rolo.stages.build.service import assess_build
from rolo.stages.contracts import PipelineAssessment, StageAssessment, StageName
from rolo.stages.debug.service import assess_debug
from rolo.stages.deploy.service import assess_deploy
from rolo.stages.test.service import assess_test


def assess_stage(stage: StageName, artifact_root: Path, robot_id: str) -> StageAssessment:
    assessors = {
        StageName.DEPLOY: assess_deploy,
        StageName.BUILD: assess_build,
        StageName.DEBUG: assess_debug,
        StageName.TEST: assess_test,
    }
    return assessors[stage](artifact_root, robot_id)


def assess_pipeline(artifact_root: Path, robot_id: str) -> PipelineAssessment:
    return PipelineAssessment(
        robot_id=robot_id,
        stages=[assess_stage(stage, artifact_root, robot_id) for stage in StageName],
    )
