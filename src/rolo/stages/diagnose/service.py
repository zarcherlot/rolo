from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.stages.adapt.conformance import validate_adapter_handoff
from rolo.stages.agent_runner import StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus
from rolo.stages.diagnose_contract import validate_structured_diagnosis_report
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


def build_diagnosis_task(
    artifact_root: Path,
    robot_id: str,
    *,
    provider: str,
    executor: str,
    model: str | None = None,
) -> StageAgentTask:
    """Build a digest-bound Diagnose task without invoking an Agent."""
    layout = ArtifactLayout(artifact_root)
    adapter_handoff = validate_adapter_handoff(artifact_root, robot_id)
    del adapter_handoff
    inputs = layout.stage_file("diagnose", robot_id, "inputs.json")
    if not inputs.is_file():
        raise FileNotFoundError(f"diagnosis inputs are missing: {inputs}")
    input_refs = {
        "diagnosis_inputs": layout.ref(inputs),
        "adapter_latest": layout.ref(layout.stage_latest_index("adapt", robot_id)),
    }
    input_sha256 = {
        name: sha256_file(resolve_artifact_ref(artifact_root, reference))
        for name, reference in input_refs.items()
    }
    task_identity = {
        "stage": "diagnose",
        "robot_id": robot_id,
        "input_refs": input_refs,
        "input_sha256": input_sha256,
        "output_contract": "robot-diagnosis-handoff/v1",
        "provider": provider,
        "executor": executor,
        "model": model,
    }
    return StageAgentTask(
        stage="diagnose",
        robot_id=robot_id,
        task=(
            "Analyze the frozen Adapt handoff and target evidence. Produce a diagnosis report "
            "and a frozen configuration; never mutate the target or claim release authority."
        ),
        input_refs=input_refs,
        input_sha256=input_sha256,
        output_contract="robot-diagnosis-handoff/v1",
        provider=provider,
        executor=executor,
        model=model,
        plan_sha256=canonical_json_sha256(task_identity),
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
            handoff = validate_diagnosis_handoff(artifact_root, robot_id)
            # Legacy v1 handoffs may omit the report pair.  They remain readable for
            # migration, but cannot make the Diagnose stage COMPLETE: the report is the
            # auditable output of baseline/observe/hypothesis reasoning.
            if not handoff.diagnosis_report_ref or not handoff.diagnosis_report_sha256:
                handoff_error = "Diagnosis handoff has no immutable diagnosis report"
            else:
                report_path = resolve_artifact_ref(artifact_root, handoff.diagnosis_report_ref)
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if not isinstance(report, dict):
                    raise ValueError("diagnosis report must be a JSON object")
                validate_structured_diagnosis_report(report, robot_id=robot_id)
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
