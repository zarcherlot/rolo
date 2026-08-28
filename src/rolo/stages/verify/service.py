from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.stages.agent_runner import StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus
from rolo.stages.downstream_tools import (
    DownstreamToolConsumer,
    DownstreamToolGateway,
    create_downstream_tool_consumer,
)
from rolo.stages.handoffs import validate_diagnosis_handoff, validate_verification_handoff
from rolo.stages.verify.acceptance import VerificationPlan


def create_verification_tool_consumer(
    *,
    artifact_root: Path,
    robot_id: str,
    gateway: DownstreamToolGateway,
    clock: Callable[[], datetime] | None = None,
) -> DownstreamToolConsumer:
    """Bind a Verify Agent to its frozen, read-only Tool Session handoff."""

    return create_downstream_tool_consumer(
        artifact_root=artifact_root,
        robot_id=robot_id,
        stage="verify",
        gateway=gateway,
        clock=clock,
    )


def build_verification_task(
    artifact_root: Path,
    robot_id: str,
    *,
    provider: str,
    executor: str,
    model: str | None = None,
) -> StageAgentTask:
    """Build a digest-bound Verify task without executing regression actions."""
    layout = ArtifactLayout(artifact_root)

    validate_diagnosis_handoff(artifact_root, robot_id)
    inputs = layout.stage_file("verify", robot_id, "inputs.json")
    if not inputs.is_file():
        raise FileNotFoundError(f"verification inputs are missing: {inputs}")
    input_refs = {
        "verification_inputs": layout.ref(inputs),
        "diagnosis_handoff": layout.ref(layout.stage_file("diagnose", robot_id, "handoff.json")),
    }
    acceptance_plan_path = layout.stage_file("verify", robot_id, "acceptance_plan.json")
    if acceptance_plan_path.is_file():
        acceptance_plan = VerificationPlan.model_validate_json(
            acceptance_plan_path.read_text(encoding="utf-8")
        )
        if acceptance_plan.robot_id != robot_id:
            raise ValueError("verification acceptance plan robot identity mismatch")
        input_refs["acceptance_plan"] = layout.ref(acceptance_plan_path)
    input_sha256 = {
        name: sha256_file(resolve_artifact_ref(artifact_root, reference))
        for name, reference in input_refs.items()
    }
    task_identity = {
        "stage": "verify",
        "robot_id": robot_id,
        "input_refs": input_refs,
        "input_sha256": input_sha256,
        "output_contract": "robot-verification-handoff/v1",
        "provider": provider,
        "executor": executor,
        "model": model,
    }
    return StageAgentTask(
        stage="verify",
        robot_id=robot_id,
        task=(
            "Run the declared regression and acceptance checks against the frozen diagnosis "
            "configuration. Produce an evidence package; do not change release authority."
        ),
        input_refs=input_refs,
        input_sha256=input_sha256,
        output_contract="robot-verification-handoff/v1",
        provider=provider,
        executor=executor,
        model=model,
        plan_sha256=canonical_json_sha256(task_identity),
    )


def publish_verification_plan(
    artifact_root: Path, robot_id: str, plan: VerificationPlan
) -> str:
    """Persist a validated acceptance plan in the stage's mutable latest index."""

    if plan.robot_id != robot_id:
        raise ValueError("verification acceptance plan robot identity mismatch")
    validate_diagnosis_handoff(artifact_root, robot_id)
    layout = ArtifactLayout(artifact_root)
    path = ArtifactStore(artifact_root).write_json(
        layout.relative(layout.stage_file("verify", robot_id, "acceptance_plan.json")),
        plan.model_dump(mode="json"),
    )
    return layout.ref(path)


def _verification_status(artifact_root: Path, handoff) -> StageStatus:
    """Map a validated report outcome to a lifecycle status without trusting prose."""

    report_path = resolve_artifact_ref(artifact_root, handoff.regression_report_ref)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("regression report must be a JSON object")
    declared = str(payload.get("status", "")).upper()
    case_results = payload.get("case_results")
    if isinstance(case_results, list) and any(
        isinstance(item, dict) and item.get("status") != "PASS" for item in case_results
    ):
        return StageStatus.DEGRADED
    if declared in {"FAIL", "CANCELLED", "ERROR", "TIMEOUT"}:
        return StageStatus.DEGRADED
    return StageStatus.COMPLETE


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
    handoff_status = StageStatus.NOT_STARTED
    if verification_handoff.is_file():
        try:
            handoff = validate_verification_handoff(artifact_root, robot_id)
            handoff_valid = True
            handoff_status = _verification_status(artifact_root, handoff)
        except (OSError, ValueError) as exc:
            handoff_error = str(exc)
    return StageAssessment(
        stage=StageName.VERIFY,
        robot_id=robot_id,
        status=handoff_status if handoff_valid else StageStatus.NOT_STARTED,
        summary=(
            "Optional autonomous acceptance testing has not started"
            if not handoff_valid
            else "Final regression report and evidence package are available"
            if handoff_status == StageStatus.COMPLETE
            else "Verification completed with failed, timed-out, or cancelled cases"
        ),
        optional=True,
        prerequisites=[str(diagnosis_handoff)],
        artifacts={
            **({"agent_inputs": str(agent_inputs)} if agent_inputs.is_file() else {}),
            **({"handoff": str(verification_handoff)} if verification_handoff.is_file() else {}),
        },
        blockers=(
            []
            if handoff_valid and handoff_status == StageStatus.COMPLETE
            else ["One or more verification cases did not pass"]
            if handoff_valid
            else [handoff_error or "Verification was not requested or has not run"]
        ),
        agent_requirement=AgentRequirement.VERIFICATION_AGENT,
    )
