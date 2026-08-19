from __future__ import annotations

from pathlib import Path

from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus
from rolo.stages.handoffs import validate_diagnosis_handoff, validate_verification_handoff


def assess_verify(artifact_root: Path, robot_id: str) -> StageAssessment:
    layout = ArtifactLayout(artifact_root)
    diagnosis_handoff = layout.stage_file("diagnose", robot_id, "handoff.json")
    agent_inputs = layout.stage_file("verify", robot_id, "inputs.json")
    verification_handoff = layout.stage_file("verify", robot_id, "handoff.json")
    try:
        validate_diagnosis_handoff(artifact_root, robot_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        return StageAssessment(
            stage=StageName.VERIFY,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Optional verification requires a frozen diagnosis handoff",
            optional=True,
            prerequisites=[str(diagnosis_handoff)],
            artifacts={"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {},
            blockers=[f"Diagnosis handoff is unavailable or invalid: {exc}"],
            agent_requirement=AgentRequirement.VERIFICATION_AGENT,
        )
    handoff_valid = False
    handoff_error: str | None = None
    if verification_handoff.is_file():
        try:
            validate_verification_handoff(artifact_root, robot_id)
            handoff_valid = True
        except (OSError, ValueError) as exc:
            handoff_error = str(exc)
    return StageAssessment(
        stage=StageName.VERIFY,
        robot_id=robot_id,
        status=StageStatus.COMPLETE if handoff_valid else StageStatus.NOT_STARTED,
        summary=(
            "Final regression report and evidence package are available"
            if handoff_valid
            else "Optional autonomous acceptance testing has not started"
        ),
        optional=True,
        prerequisites=[str(diagnosis_handoff)],
        artifacts={
            **({"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {}),
            **({"handoff": str(verification_handoff)} if verification_handoff.is_file() else {}),
        },
        blockers=[]
        if handoff_valid
        else [handoff_error or "Verification was not requested or has not run"],
        agent_requirement=AgentRequirement.VERIFICATION_AGENT,
    )
