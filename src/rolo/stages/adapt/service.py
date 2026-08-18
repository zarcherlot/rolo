from __future__ import annotations

from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.models import DiscoveryStatus
from rolo.stages.adapt.conformance import AdapterPromotionService
from rolo.stages.adapt.dependencies import AdapterAgentDependencyManager
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.adapt.executor import CodexAdaptExecutor
from rolo.stages.adapt.inputs import AdaptInputs
from rolo.stages.adapt.models import (
    AdapterAgentConfig,
    AdapterAgentDependencyReport,
    AdapterAgentDependencyStatus,
    AdapterAgentRun,
    AdaptPlan,
    AdaptPlanStatus,
    AdaptRunSummary,
    AdaptTask,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus

ADAPT_SKILLS = ["canonical-adapter-builder", "cli-conformance", "state-graph-builder"]


def coding_agent_config(settings: Settings) -> AdapterAgentConfig:
    """Return the effective secret-free Adapter Agent configuration."""
    return AdapterAgentConfig(
        provider=settings.coding_agent_provider.strip() or "codex",
        executor=settings.coding_agent_executor.strip() or "codex",
        base_url=(settings.coding_agent_base_url or "").strip() or None,
        model=(settings.coding_agent_model or "").strip() or None,
        api_key_configured=bool(settings.coding_agent_api_key),
        auto_install=settings.coding_agent_auto_install,
        require_auth=settings.coding_agent_require_auth,
    )


class AdaptExecutionService:
    """Prepare the configured Adapter Agent and execute one evidence-backed Adapt plan."""

    def __init__(self, artifacts: ArtifactStore, settings: Settings) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.config = coding_agent_config(settings)

    def prepare(
        self, *, skip_auth: bool = False
    ) -> tuple[AdapterAgentDependencyReport, Path]:
        return AdapterAgentDependencyManager(self.artifacts).prepare(
            config=self.config,
            executable=self.settings.coding_agent_executable,
            auto_install=self.settings.coding_agent_auto_install,
            require_auth=self.settings.coding_agent_require_auth and not skip_auth,
            install_timeout_s=self.settings.coding_agent_install_timeout_s,
            install_home=self.settings.coding_agent_install_home,
            codex_home=self.settings.coding_agent_home,
        )

    @staticmethod
    def dependency_ready(
        report: AdapterAgentDependencyReport, *, allow_installed: bool = False
    ) -> bool:
        return report.status == AdapterAgentDependencyStatus.READY or (
            allow_installed and report.status == AdapterAgentDependencyStatus.INSTALLED
        )

    def execute(
        self,
        *,
        robot_id: str,
        workspace: Path,
        timeout_s: int,
        plan: AdaptPlan,
    ) -> tuple[AdapterAgentDependencyReport, AdapterAgentRun | None, Path | None]:
        if plan.status != AdaptPlanStatus.REQUIRES_CODING:
            raise ValueError(f"Adapt plan for {robot_id} is {plan.status.value}")
        dependency, _ = self.prepare()
        if not self.dependency_ready(
            dependency,
            allow_installed=not self.settings.coding_agent_require_auth,
        ):
            return dependency, None, None
        executor = CodexAdaptExecutor(
            self.artifacts,
            executable=dependency.executable or self.settings.coding_agent_executable,
            api_key=self.settings.coding_agent_api_key,
        )
        run, artifact = executor.execute(
            robot_id=robot_id,
            workspace=workspace,
            timeout_s=timeout_s,
            plan=plan,
        )
        return dependency, run, artifact


class AdaptRunService:
    """Run planning, Agent execution, output freezing, and the independent gate."""

    def __init__(self, artifacts: ArtifactStore, settings: Settings) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.layout = ArtifactLayout(artifacts.root)

    def dry_run(self, robot_id: str) -> AdaptPlan:
        return AdaptStageService(
            self.artifacts,
            coding_agent=coding_agent_config(self.settings),
        ).derive_plan(robot_id)

    def run(
        self,
        *,
        robot_id: str,
        workspace: Path,
        timeout_s: int,
    ) -> tuple[AdaptRunSummary, Path]:
        plan = self.dry_run(robot_id)
        if plan.status != AdaptPlanStatus.REQUIRES_CODING:
            raise ValueError(f"Adapt plan for {robot_id} is {plan.status.value}")
        dependency, agent_run, agent_run_path = AdaptExecutionService(
            self.artifacts, self.settings
        ).execute(
            robot_id=robot_id,
            workspace=workspace,
            timeout_s=timeout_s,
            plan=plan,
        )
        if agent_run is None or agent_run_path is None:
            raise ValueError(
                f"Adapter Agent dependency is not ready: {dependency.status.value}"
            )
        if agent_run.status != "SUCCEEDED":
            raise ValueError(
                f"Adapter Agent run {agent_run.run_id} is {agent_run.status.value}: "
                f"{agent_run.error or 'no error detail'}"
            )
        promotion = AdapterPromotionService(self.artifacts)
        snapshot, snapshot_path = promotion.snapshot(agent_run)
        handoff, handoff_path, _, gate_path = promotion.promote_run(
            agent_run, snapshot
        )
        summary = AdaptRunSummary(
            robot_id=robot_id,
            run_id=agent_run.run_id,
            agent_run_ref=self.layout.ref(agent_run_path),
            snapshot_ref=self.layout.ref(snapshot_path),
            gate_ref=self.layout.ref(gate_path),
            handoff_ref=self.layout.ref(handoff_path),
        )
        summary_path = self.artifacts.write_json(
            self.layout.relative(
                self.layout.stage_run("adapt", robot_id, agent_run.run_id)
                / "summary.json"
            ),
            summary.model_dump(mode="json"),
        )
        assert handoff.source_agent_run_id == summary.run_id
        return summary, summary_path


class AdaptStageService:
    def __init__(
        self, artifacts: ArtifactStore, coding_agent: AdapterAgentConfig | None = None
    ) -> None:
        self.artifacts = artifacts
        self.coding_agent = coding_agent or AdapterAgentConfig()

    def derive_plan(self, robot_id: str) -> AdaptPlan:
        layout = ArtifactLayout(self.artifacts.root)
        adapt_inputs = layout.stage_file("adapt", robot_id, "inputs.json")
        if not adapt_inputs.is_file():
            raise FileNotFoundError(f"No adapt inputs for {robot_id}; run adapt discovery first")
        inputs = AdaptInputs.model_validate_json(adapt_inputs.read_text(encoding="utf-8"))
        report = load_report(self.artifacts.root, robot_id, inputs.discovery_id)
        wiki_path = resolve_artifact_ref(self.artifacts.root, inputs.robot_wiki_ref)
        if not wiki_path.is_file():
            raise FileNotFoundError(f"Robot Wiki is missing for {robot_id}: {wiki_path}")
        candidates = sorted(
            tool.operation
            for tool in report.tool_catalog
            if tool.availability == "DISCOVERED_UNVERIFIED"
        )
        blocked = report.status == DiscoveryStatus.FAILED
        tasks = [
            AdaptTask(
                id="canonical-adapters",
                description="Implement canonical adapters for discovered semantic bindings",
                operations=candidates,
                required_skill="canonical-adapter-builder",
            ),
            AdaptTask(
                id="cli-conformance",
                description="Validate schemas, errors, idempotency, cancellation, and safety",
                operations=[tool.operation for tool in report.tool_catalog],
                required_skill="cli-conformance",
            ),
            AdaptTask(
                id="state-graph-baseline",
                description="Build the initial typed State Graph from verified capability evidence",
                required_skill="state-graph-builder",
            ),
            AdaptTask(
                id="semantic-resolution-context",
                description=(
                    "Preserve unresolved robot semantics and source-derived candidates for "
                    "controlled diagnosis and verification"
                ),
                required_skill="state-graph-builder",
            ),
        ]
        plan = AdaptPlan(
            robot_id=robot_id,
            source_discovery_id=report.discovery_id,
            status=(AdaptPlanStatus.BLOCKED if blocked else AdaptPlanStatus.REQUIRES_CODING),
            tasks=tasks,
            required_skills=ADAPT_SKILLS,
            adapter_agent=self.coding_agent,
            candidate_operations=candidates,
            semantic_context_ref=inputs.semantic_context_ref,
            unresolved_semantics=inputs.unresolved_semantics,
            semantic_value_candidates=inputs.semantic_value_candidates,
            active_discovery_report_ref=inputs.active_discovery_report_ref,
            robot_wiki_ref=inputs.robot_wiki_ref,
            discovery_manifest_ref=inputs.discovery_manifest_ref,
            discovery_manifest_sha256=inputs.discovery_manifest_sha256,
            handoff_ref=f"artifact://adapt/{robot_id}/latest.json",
        )
        return plan

def assess_adapt(artifact_root: Path, robot_id: str) -> StageAssessment:
    layout = ArtifactLayout(artifact_root)
    adapt_inputs = layout.stage_file("adapt", robot_id, "inputs.json")
    handoff_index = layout.stage_latest_index("adapt", robot_id)
    discovery_report = layout.discovery_latest(robot_id)
    if not adapt_inputs.is_file():
        return StageAssessment(
            stage=StageName.ADAPT,
            robot_id=robot_id,
            status=StageStatus.NOT_STARTED,
            summary="Adapt discovery has not produced probes and Agent inputs",
            prerequisites=[str(adapt_inputs)],
            blockers=["Run adapt discovery"],
            required_skills=ADAPT_SKILLS,
            agent_requirement=AgentRequirement.ADAPTER_AGENT,
        )
    report = load_latest_report(artifact_root, robot_id)
    if report.status == DiscoveryStatus.FAILED:
        return StageAssessment(
            stage=StageName.ADAPT,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Adapt discovery probes failed",
            artifacts={"inputs": str(adapt_inputs), "discovery_report": str(discovery_report)},
            blockers=["Resolve failed discovery probes"],
            required_skills=ADAPT_SKILLS,
            agent_requirement=AgentRequirement.ADAPTER_AGENT,
        )
    try:
        wiki_path = resolve_artifact_ref(artifact_root, report.review_ref)
        if not wiki_path.is_file():
            raise FileNotFoundError(wiki_path)
    except (OSError, ValueError) as exc:
        return StageAssessment(
            stage=StageName.ADAPT,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="The editable robot Wiki is unavailable",
            artifacts={"inputs": str(adapt_inputs)},
            blockers=[f"Regenerate or restore the robot Wiki: {exc}"],
            required_skills=ADAPT_SKILLS,
            agent_requirement=AgentRequirement.ADAPTER_AGENT,
        )
    handoff_valid = False
    handoff_error: str | None = None
    if handoff_index.is_file():
        try:
            from rolo.stages.adapt.conformance import validate_adapter_handoff

            validate_adapter_handoff(artifact_root, robot_id)
            handoff_valid = True
        except (OSError, ValueError) as exc:
            handoff_error = str(exc)
    if handoff_valid:
        return StageAssessment(
            stage=StageName.ADAPT,
            robot_id=robot_id,
            status=StageStatus.COMPLETE,
            summary="Verified CLI and State Graph handoff is available",
            artifacts={
                "robot_wiki": str(wiki_path),
                "handoff_index": str(handoff_index),
            },
            required_skills=ADAPT_SKILLS,
            agent_requirement=AgentRequirement.ADAPTER_AGENT,
        )
    return StageAssessment(
        stage=StageName.ADAPT,
        robot_id=robot_id,
        status=(
            StageStatus.DEGRADED
            if report.status == DiscoveryStatus.PARTIAL
            else StageStatus.NOT_STARTED
        ),
        summary="Adapter Agent must implement and verify the canonical CLI and State Graph",
        prerequisites=[str(adapt_inputs)],
        artifacts={
            "inputs": str(adapt_inputs),
            "discovery_report": str(discovery_report),
            "robot_wiki": str(wiki_path),
        },
        blockers=[
            handoff_error or "Missing verified canonical CLI and State Graph handoff"
        ],
        required_skills=ADAPT_SKILLS,
        agent_requirement=AgentRequirement.ADAPTER_AGENT,
    )
