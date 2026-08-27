from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from rolo.stages.adapt.conformance import validate_adapter_handoff
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus
from rolo.stages.downstream_tools import (
    DownstreamToolConsumer,
    DownstreamToolGateway,
    create_downstream_tool_consumer,
)
from rolo.stages.handoffs import validate_diagnosis_handoff


def create_diagnosis_tool_consumer(
    *,
    artifact_root: Path,
    robot_id: str,
    gateway: DownstreamToolGateway,
    clock: Callable[[], datetime] | None = None,
) -> DownstreamToolConsumer:
    """Bind a Diagnose Agent to its frozen, read-only Tool Session handoff."""

    return create_downstream_tool_consumer(
        artifact_root=artifact_root,
        robot_id=robot_id,
        stage="diagnose",
        gateway=gateway,
        clock=clock,
    )


def assess_diagnose(artifact_root: Path, robot_id: str) -> StageAssessment:
    layout = ArtifactLayout(artifact_root)
    adapt_handoff = layout.stage_latest_index("adapt", robot_id)
    agent_inputs = layout.stage_file("diagnose", robot_id, "inputs.json")
    diagnosis_handoff = layout.stage_file("diagnose", robot_id, "handoff.json")
    try:
        validate_adapter_handoff(artifact_root, robot_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        return StageAssessment(
            stage=StageName.DIAGNOSE,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Diagnosis is blocked until verified CLI and State Graph are available",
            prerequisites=[str(adapt_handoff)],
            artifacts={"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {},
            blockers=[f"Adapter handoff is unavailable or invalid: {exc}"],
            agent_requirement=AgentRequirement.DIAGNOSIS_AGENT,
        )
    handoff_valid = False
    handoff_error: str | None = None
    if diagnosis_handoff.is_file():
        try:
            validate_diagnosis_handoff(artifact_root, robot_id)
            handoff_valid = True
        except (OSError, ValueError) as exc:
            handoff_error = str(exc)
    return StageAssessment(
        stage=StageName.DIAGNOSE,
        robot_id=robot_id,
        status=StageStatus.COMPLETE if handoff_valid else StageStatus.NOT_STARTED,
        summary=(
            "A frozen diagnosis configuration is available"
            if handoff_valid
            else "User constraints, closed-loop diagnosis, and tuning have not completed"
        ),
        prerequisites=[str(adapt_handoff)],
        artifacts={
            **({"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {}),
            **({"handoff": str(diagnosis_handoff)} if diagnosis_handoff.is_file() else {}),
        },
        blockers=[] if handoff_valid else [handoff_error or "Missing diagnosis handoff"],
        agent_requirement=AgentRequirement.DIAGNOSIS_AGENT,
    )
