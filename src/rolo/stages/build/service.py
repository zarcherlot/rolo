from __future__ import annotations

from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import DiscoveryStatus
from rolo.stages.build.discovery import load_latest_report
from rolo.stages.build.models import BuildPlan, BuildPlanStatus, BuildTask
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus

BUILD_SKILLS = ["canonical-adapter-builder", "cli-conformance", "state-graph-builder"]


class BuildStageService:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts

    def plan(self, robot_id: str) -> tuple[BuildPlan, Path]:
        build_inputs = self.artifacts.root / "build" / robot_id / "latest" / "inputs.json"
        if not build_inputs.is_file():
            raise FileNotFoundError(f"No build inputs for {robot_id}; run build discovery first")
        report = load_latest_report(self.artifacts.root, robot_id)
        candidates = sorted(
            tool.operation
            for tool in report.tool_catalog
            if tool.availability == "DISCOVERED_UNVERIFIED"
        )
        blocked = report.status == DiscoveryStatus.FAILED
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
        ]
        plan = BuildPlan(
            robot_id=robot_id,
            source_discovery_id=report.discovery_id,
            status=(BuildPlanStatus.BLOCKED if blocked else BuildPlanStatus.REQUIRES_CODING),
            tasks=tasks,
            required_skills=BUILD_SKILLS,
            candidate_operations=candidates,
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
    discovery_report = artifact_root / "discovery" / robot_id / "latest" / "report.json"
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
