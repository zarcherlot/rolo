from __future__ import annotations

from pathlib import Path

from rolo.stages.contracts import StageAssessment, StageName, StageStatus

TEST_SKILLS = ["robot-test-designer", "robot-test-runner"]


def assess_test(artifact_root: Path, robot_id: str) -> StageAssessment:
    debug_handoff = artifact_root / "debug" / robot_id / "latest" / "handoff.json"
    test_handoff = artifact_root / "test" / robot_id / "latest" / "handoff.json"
    if not debug_handoff.is_file():
        return StageAssessment(
            stage=StageName.TEST,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Optional acceptance testing requires a frozen debug handoff",
            optional=True,
            prerequisites=[str(debug_handoff)],
            blockers=["Missing debug handoff"],
            required_skills=TEST_SKILLS,
        )
    return StageAssessment(
        stage=StageName.TEST,
        robot_id=robot_id,
        status=StageStatus.COMPLETE if test_handoff.is_file() else StageStatus.NOT_STARTED,
        summary=(
            "Final regression report and evidence package are available"
            if test_handoff.is_file()
            else "Optional autonomous acceptance testing has not started"
        ),
        optional=True,
        prerequisites=[str(debug_handoff)],
        artifacts={"handoff": str(test_handoff)} if test_handoff.is_file() else {},
        blockers=[] if test_handoff.is_file() else ["Test stage was not requested or has not run"],
        required_skills=TEST_SKILLS,
    )
