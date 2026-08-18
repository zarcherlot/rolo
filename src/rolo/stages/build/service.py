from __future__ import annotations

from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import DiscoveryStatus
from rolo.stages.build.active_discovery import (
    ConfirmationStatus,
    DiscoveryConfirmation,
    confirmation_matches_report,
)
from rolo.stages.build.discovery import load_latest_report, load_report
from rolo.stages.build.inputs import BuildInputs
from rolo.stages.build.models import BuildPlan, BuildPlanStatus, BuildTask, CodingAgentConfig
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus

BUILD_SKILLS = ["canonical-adapter-builder", "cli-conformance", "state-graph-builder"]


def _confirmation_state(
    artifact_root: Path, robot_id: str, discovery_id: str
) -> tuple[bool, str, str | None]:
    report_path = (
        artifact_root
        / "discovery"
        / robot_id
        / "runs"
        / discovery_id
        / "active_discovery_report.json"
    )
    confirmation_path = report_path.with_name("confirmation.json")
    if not report_path.is_file() or not confirmation_path.is_file():
        return False, ConfirmationStatus.AWAITING_USER_CONFIRMATION.value, None
    try:
        confirmation = DiscoveryConfirmation.model_validate_json(
            confirmation_path.read_text(encoding="utf-8")
        )
    except ValueError:
        return False, ConfirmationStatus.AWAITING_USER_CONFIRMATION.value, str(confirmation_path)
    matches = confirmation_matches_report(confirmation, report_path)
    status = confirmation.confirmation_status.value
    if not matches and confirmation.confirmation_status == ConfirmationStatus.ACCEPTED:
        status = "INVALID_OR_STALE"
    return matches, status, str(confirmation_path)


class BuildStageService:
    def __init__(
        self, artifacts: ArtifactStore, coding_agent: CodingAgentConfig | None = None
    ) -> None:
        self.artifacts = artifacts
        self.coding_agent = coding_agent or CodingAgentConfig()

    def plan(self, robot_id: str) -> tuple[BuildPlan, Path]:
        build_inputs = self.artifacts.root / "build" / robot_id / "latest" / "inputs.json"
        if not build_inputs.is_file():
            raise FileNotFoundError(f"No build inputs for {robot_id}; run build discovery first")
        inputs = BuildInputs.model_validate_json(build_inputs.read_text(encoding="utf-8"))
        report = load_report(self.artifacts.root, robot_id, inputs.discovery_id)
        candidates = sorted(
            tool.operation
            for tool in report.tool_catalog
            if tool.availability == "DISCOVERED_UNVERIFIED"
        )
        blocked = report.status == DiscoveryStatus.FAILED
        confirmed, confirmation_status, confirmation_path = _confirmation_state(
            self.artifacts.root,
            robot_id,
            inputs.discovery_id,
        )
        tasks = [
            BuildTask(
                id="canonical-adapters",
                description="Implement canonical adapters for discovered semantic bindings",
                operations=candidates,
                required_skill="canonical-adapter-builder",
            ),
            BuildTask(
                id="cli-conformance",
                description="Validate schemas, errors, idempotency, cancellation, and safety",
                operations=[tool.operation for tool in report.tool_catalog],
                required_skill="cli-conformance",
            ),
            BuildTask(
                id="state-graph-baseline",
                description="Build the initial typed State Graph from verified capability evidence",
                required_skill="state-graph-builder",
            ),
            BuildTask(
                id="semantic-resolution-context",
                description=(
                    "Preserve unresolved robot semantics and source-derived candidates for "
                    "controlled Debug and Test validation"
                ),
                required_skill="state-graph-builder",
            ),
        ]
        plan = BuildPlan(
            robot_id=robot_id,
            source_discovery_id=report.discovery_id,
            status=(
                BuildPlanStatus.BLOCKED
                if blocked
                else BuildPlanStatus.REQUIRES_CODING
                if confirmed
                else BuildPlanStatus.AWAITING_CONFIRMATION
            ),
            tasks=tasks,
            required_skills=BUILD_SKILLS,
            coding_agent=self.coding_agent,
            candidate_operations=candidates,
            semantic_context_ref=inputs.semantic_context_ref,
            unresolved_semantics=inputs.unresolved_semantics,
            semantic_value_candidates=inputs.semantic_value_candidates,
            active_discovery_report_ref=inputs.active_discovery_report_ref,
            confirmation_status=confirmation_status,
            confirmation_ref=(
                f"artifact://discovery/{robot_id}/runs/{inputs.discovery_id}/confirmation.json"
                if confirmation_path
                else None
            ),
            handoff_ref=f"artifact://build/{robot_id}/latest/handoff.json",
        )
        path = self.artifacts.write_json(
            f"build/{robot_id}/latest/plan.json", plan.model_dump(mode="json")
        )
        self.artifacts.write_json(
            f"build/{robot_id}/plans/{report.discovery_id}.json", plan.model_dump(mode="json")
        )
        return plan, path


def assess_build(artifact_root: Path, robot_id: str) -> StageAssessment:
    build_inputs = artifact_root / "build" / robot_id / "latest" / "inputs.json"
    plan = artifact_root / "build" / robot_id / "latest" / "plan.json"
    handoff = artifact_root / "build" / robot_id / "latest" / "handoff.json"
    discovery_report = artifact_root / "discovery" / robot_id / "latest.json"
    if not build_inputs.is_file():
        return StageAssessment(
            stage=StageName.BUILD,
            robot_id=robot_id,
            status=StageStatus.NOT_STARTED,
            summary="Build has not produced discovery probes and coding inputs",
            prerequisites=[str(build_inputs)],
            blockers=["Run build discovery"],
            required_skills=BUILD_SKILLS,
            agent_requirement=AgentRequirement.CODING_AGENT,
        )
    report = load_latest_report(artifact_root, robot_id)
    if report.status == DiscoveryStatus.FAILED:
        return StageAssessment(
            stage=StageName.BUILD,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Build discovery probes failed",
            artifacts={"inputs": str(build_inputs), "discovery_report": str(discovery_report)},
            blockers=["Resolve failed discovery probes"],
            required_skills=BUILD_SKILLS,
            agent_requirement=AgentRequirement.CODING_AGENT,
        )
    confirmed, confirmation_status, confirmation_path = _confirmation_state(
        artifact_root,
        robot_id,
        report.discovery_id,
    )
    if not confirmed:
        return StageAssessment(
            stage=StageName.BUILD,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Build discovery report requires user confirmation",
            prerequisites=[report.active_discovery_report_ref],
            artifacts={
                "inputs": str(build_inputs),
                "discovery_report": str(discovery_report),
                **({"confirmation": confirmation_path} if confirmation_path else {}),
            },
            blockers=[f"Discovery confirmation is {confirmation_status}"],
            required_skills=BUILD_SKILLS,
            agent_requirement=AgentRequirement.CODING_AGENT,
        )
    if handoff.is_file():
        return StageAssessment(
            stage=StageName.BUILD,
            robot_id=robot_id,
            status=StageStatus.COMPLETE,
            summary="Verified CLI and State Graph handoff is available",
            artifacts={"handoff": str(handoff)},
            required_skills=BUILD_SKILLS,
            agent_requirement=AgentRequirement.CODING_AGENT,
        )
    return StageAssessment(
        stage=StageName.BUILD,
        robot_id=robot_id,
        status=(
            StageStatus.DEGRADED
            if report.status == DiscoveryStatus.PARTIAL
            else StageStatus.NOT_STARTED
        ),
        summary="Coding Agent must build and verify the canonical CLI and State Graph",
        prerequisites=[str(build_inputs)],
        artifacts={
            "inputs": str(build_inputs),
            "discovery_report": str(discovery_report),
            **({"plan": str(plan)} if plan.is_file() else {}),
        },
        blockers=["Missing verified canonical CLI and State Graph handoff"],
        required_skills=BUILD_SKILLS,
        agent_requirement=AgentRequirement.CODING_AGENT,
    )
