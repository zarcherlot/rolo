from __future__ import annotations

from pathlib import Path

from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus

DIAGNOSIS_SKILLS = ["robot-diagnosis", "robot-use-supervisor"]


def assess_debug(artifact_root: Path, robot_id: str) -> StageAssessment:
    build_handoff = artifact_root / "build" / robot_id / "latest" / "handoff.json"
    agent_inputs = artifact_root / "debug" / robot_id / "latest" / "inputs.json"
    debug_handoff = artifact_root / "debug" / robot_id / "latest" / "handoff.json"
    if not build_handoff.is_file():
        return StageAssessment(
            stage=StageName.DEBUG,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Debug is blocked until verified CLI and State Graph are available",
            prerequisites=[str(build_handoff)],
            artifacts={"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {},
            blockers=["Missing build handoff"],
            required_skills=DIAGNOSIS_SKILLS,
            agent_requirement=AgentRequirement.DIAGNOSIS_AGENT,
        )
    return StageAssessment(
        stage=StageName.DEBUG,
        robot_id=robot_id,
        status=StageStatus.COMPLETE if debug_handoff.is_file() else StageStatus.NOT_STARTED,
        summary=(
            "A frozen debug configuration is available"
            if debug_handoff.is_file()
            else "User constraints, closed-loop diagnosis, and tuning have not completed"
        ),
        prerequisites=[str(build_handoff)],
        artifacts={
            **({"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {}),
            **({"handoff": str(debug_handoff)} if debug_handoff.is_file() else {}),
        },
        blockers=[] if debug_handoff.is_file() else ["Missing debug handoff"],
        required_skills=DIAGNOSIS_SKILLS,
        agent_requirement=AgentRequirement.DIAGNOSIS_AGENT,
    )
