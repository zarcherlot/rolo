from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from rolo.adapter_runtime import load_current_release
from rolo.agent_provider import create_agent_executor, dependency_adapter_for
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings, get_settings
from rolo.core.models import DiscoveryStatus
from rolo.stages.adapt.conformance import AdapterPromotionService, validate_adapter_handoff
from rolo.stages.adapt.dependencies import AdapterAgentDependencyManager
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.adapt.executor import CodexAdaptExecutor  # noqa: F401 - v1 compatibility import
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
from rolo.stages.adapt.operation_registry import (
    adapter_operation_eligibility,
    required_adapter_agent_conformance_operations,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.contracts import AgentRequirement, StageAssessment, StageName, StageStatus


class AdaptAuthorizationRequired(ValueError):
    """The journey is resumable, but a separate user capability is missing."""

    def __init__(self, report: AdapterAgentDependencyReport) -> None:
        super().__init__(f"Adapter Agent dependency is not ready: {report.status.value}")
        self.authorization_report = report.model_dump(mode="json")


@contextmanager
def _temporary_agent_workspace(*, prefix: str, parent: Path | None) -> Iterator[str]:
    """Create an ephemeral workspace without letting Windows sandbox ACLs mask the run."""
    if os.name != "nt":
        with tempfile.TemporaryDirectory(prefix=prefix, dir=parent) as workspace:
            yield workspace
        return
    workspace = tempfile.mkdtemp(prefix=prefix, dir=parent)
    try:
        yield workspace
    finally:
        # The workspace is never an authority boundary: all accepted files were
        # already reconstructed from the hashed result before this point.
        shutil.rmtree(workspace, ignore_errors=True)


def coding_agent_config(settings: Settings) -> AdapterAgentConfig:
    """Return the effective secret-free Adapter Agent configuration."""
    return AdapterAgentConfig(
        provider=settings.coding_agent_provider.strip() or "codex",
        executor=settings.coding_agent_executor.strip() or "codex",
        base_url=(settings.coding_agent_base_url or "").strip() or None,
        model=(settings.coding_agent_model or "").strip() or None,
        api_key_env=settings.coding_agent_api_key_env.strip() or "CODING_AGENT_API_KEY",
        api_key_configured=bool(settings.resolved_coding_agent_api_key),
        auto_install=settings.coding_agent_auto_install,
        require_auth=settings.coding_agent_require_auth,
    )


class AdaptExecutionService:
    """Prepare the configured Adapter Agent and execute one evidence-backed Adapt plan."""

    def __init__(self, artifacts: ArtifactStore, settings: Settings) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.config = coding_agent_config(settings)

    def prepare(self, *, skip_auth: bool = False) -> tuple[AdapterAgentDependencyReport, Path]:
        adapter = dependency_adapter_for(self.config.executor)
        return AdapterAgentDependencyManager(
            self.artifacts,
            adapter=adapter,
            use_default_adapter=adapter is None and self.config.executor.strip().lower() == "codex",
        ).prepare(
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
        timeout_s: int | None,
        plan: AdaptPlan,
        slice_canary: bool = False,
        on_output: Callable[[str, str], None] | None = None,
    ) -> tuple[AdapterAgentDependencyReport, AdapterAgentRun | None, Path | None]:
        if plan.status != AdaptPlanStatus.REQUIRES_CODING:
            raise ValueError(f"Adapt plan for {robot_id} is {plan.status.value}")
        dependency, _ = self.prepare()
        if not self.dependency_ready(
            dependency,
            allow_installed=not self.settings.coding_agent_require_auth,
        ):
            if dependency.status == AdapterAgentDependencyStatus.AUTH_REQUIRED:
                raise AdaptAuthorizationRequired(dependency)
            return dependency, None, None
        executor = create_agent_executor(
            self.config.executor,
            artifacts=self.artifacts,
            executable=dependency.executable or self.settings.coding_agent_executable,
            api_key=self.settings.resolved_coding_agent_api_key,
            api_key_env=self.config.api_key_env,
            agent_config=self.config,
            output_root=self.settings.rolo_output_dir,
            slice_activation_mode=self.settings.adapt_operation_slice_mode,
            slice_activation_robot_ids=self.settings.adapt_operation_slice_robot_ids,
            slice_activation_run_ids=self.settings.adapt_operation_slice_run_ids,
            slice_activation_max_operations=(self.settings.adapt_operation_slice_max_operations),
            native_tool_mode=self.settings.adapt_native_tool_mode,
            native_tool_robot_ids=self.settings.adapt_native_tool_robot_ids,
            native_tool_run_ids=self.settings.adapt_native_tool_run_ids,
            native_tool_max_calls=self.settings.adapt_native_tool_max_calls,
            native_tool_max_elapsed_s=self.settings.adapt_native_tool_max_elapsed_s,
            native_tool_max_result_bytes=self.settings.adapt_native_tool_max_result_bytes,
        )
        run, artifact = executor.execute(
            robot_id=robot_id,
            workspace=workspace,
            timeout_s=timeout_s or self.settings.coding_agent_timeout_s or 1800,
            plan=plan,
            slice_canary=slice_canary,
            on_output=on_output,
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
        scratch_root: Path | None,
        timeout_s: int | None,
        slice_canary: bool = False,
        on_output: Callable[[str, str], None] | None = None,
    ) -> tuple[AdaptRunSummary, Path]:
        plan = self.dry_run(robot_id)
        if plan.status != AdaptPlanStatus.REQUIRES_CODING:
            raise ValueError(f"Adapt plan for {robot_id} is {plan.status.value}")
        source_root = Path(__file__).resolve().parents[4]
        output_root = self.settings.rolo_output_dir.expanduser().resolve()
        try:
            output_root.relative_to(source_root)
        except ValueError:
            pass
        else:
            raise ValueError("ROLO_OUTPUT_DIR must be outside the rolo source tree")
        temporary_parent: Path | None = None
        if scratch_root is not None:
            temporary_parent = scratch_root.expanduser().resolve()
            temporary_parent.mkdir(parents=True, exist_ok=True)
            try:
                temporary_parent.relative_to(source_root)
            except ValueError:
                pass
            else:
                raise ValueError("Adapter Agent scratch root must be outside the rolo source tree")
        with _temporary_agent_workspace(
            prefix=f"rolo-adapt-{robot_id}-",
            parent=temporary_parent,
        ) as temporary_workspace:
            workspace = Path(temporary_workspace)
            dependency, agent_run, agent_run_path = AdaptExecutionService(
                self.artifacts, self.settings
            ).execute(
                robot_id=robot_id,
                workspace=workspace,
                timeout_s=timeout_s,
                plan=plan,
                slice_canary=slice_canary,
                on_output=on_output,
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
            promotion = AdapterPromotionService(self.artifacts, output_root)
            snapshot, snapshot_path = promotion.snapshot(agent_run)
            handoff, handoff_path, _, gate_path = promotion.promote_run(agent_run, snapshot)
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
                self.layout.stage_run("probe", robot_id, agent_run.run_id) / "summary.json"
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
        adapt_inputs = layout.stage_file("probe", robot_id, "inputs.json")
        if not adapt_inputs.is_file():
            raise FileNotFoundError(f"No adapt inputs for {robot_id}; run adapt discovery first")
        inputs = AdaptInputs.model_validate_json(adapt_inputs.read_text(encoding="utf-8"))
        report = load_report(self.artifacts.root, robot_id, inputs.discovery_id)
        wiki_path = resolve_artifact_ref(self.artifacts.root, inputs.robot_wiki_ref)
        if not wiki_path.is_file():
            raise FileNotFoundError(f"Robot Wiki is missing for {robot_id}: {wiki_path}")
        eligible, deferred = adapter_operation_eligibility(report)
        conformance_operations = sorted(required_adapter_agent_conformance_operations(report))
        blocked = report.status == DiscoveryStatus.FAILED or not eligible
        tasks = [
            AdaptTask(
                id="canonical-adapters",
                description="Implement canonical adapters for discovered semantic bindings",
                operations=sorted(eligible),
            ),
            AdaptTask(
                id="cli-conformance",
                description=(
                    "Validate generated bundle schemas, errors, idempotency, and cancellation "
                    "locally; Rolo validates builtin operations independently"
                ),
                operations=conformance_operations,
            ),
            AdaptTask(
                id="state-graph-baseline",
                description="Build the initial typed State Graph from bounded discovery evidence",
            ),
            AdaptTask(
                id="semantic-resolution-context",
                description=(
                    "Preserve unresolved robot semantics and evidence-backed candidates for "
                    "controlled diagnosis and verification"
                ),
            ),
        ]
        plan = AdaptPlan(
            robot_id=robot_id,
            source_discovery_id=report.discovery_id,
            status=(AdaptPlanStatus.BLOCKED if blocked else AdaptPlanStatus.REQUIRES_CODING),
            tasks=tasks,
            eligible_operations=sorted(eligible),
            deferred_operations=deferred,
            adapter_agent=self.coding_agent,
            semantic_context_ref=inputs.semantic_context_ref,
            robot_wiki_ref=inputs.robot_wiki_ref,
            discovery_manifest_ref=inputs.discovery_manifest_ref,
            discovery_manifest_sha256=inputs.discovery_manifest_sha256,
            heuristic_analysis_ref=inputs.heuristic_analysis_ref,
        )
        return plan


def assess_adapt(artifact_root: Path, robot_id: str) -> StageAssessment:
    layout = ArtifactLayout(artifact_root)
    adapt_inputs = layout.stage_file("probe", robot_id, "inputs.json")
    handoff_index = layout.stage_latest_index("probe", robot_id)
    discovery_report = layout.discovery_latest(robot_id)
    if not adapt_inputs.is_file():
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.NOT_STARTED,
            summary="Adapt discovery has not produced probes and Agent inputs",
            prerequisites=[str(adapt_inputs)],
            blockers=["Run adapt discovery"],
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    try:
        report = load_latest_report(artifact_root, robot_id)
    except (OSError, ValueError):
        # A broken latest marker must degrade the read model, not take down the
        # control-plane overview endpoint. The next discovery run can repair it.
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Latest Adapt discovery evidence is unavailable or invalid",
            prerequisites=[str(discovery_report)],
            artifacts={"inputs": str(adapt_inputs)},
            blockers=[
                "Latest discovery evidence failed manifest, schema, or integrity validation"
            ],
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    if report.status == DiscoveryStatus.FAILED:
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="Adapt discovery probes failed",
            artifacts={"inputs": str(adapt_inputs), "discovery_report": str(discovery_report)},
            blockers=["Resolve failed discovery probes"],
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    try:
        wiki_path = resolve_artifact_ref(artifact_root, report.review_ref)
        if not wiki_path.is_file():
            raise FileNotFoundError(wiki_path)
    except (OSError, ValueError) as exc:
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.BLOCKED,
            summary="The editable robot Wiki is unavailable",
            artifacts={"inputs": str(adapt_inputs)},
            blockers=[f"Regenerate or restore the robot Wiki: {exc}"],
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    handoff_valid = False
    handoff_error: str | None = None
    if handoff_index.is_file():
        try:
            handoff = validate_adapter_handoff(artifact_root, robot_id)
            _, release, _, _ = load_current_release(
                get_settings().rolo_output_dir,
                robot_id,
                artifact_root=artifact_root,
            )
            handoff_valid = (
                handoff.source_discovery_id == release.discovery_id
                and release.release_id == handoff.source_agent_run_id
            )
            if not handoff_valid:
                handoff_error = "The gated adapter release is stale for the latest discovery"
        except (OSError, ValueError) as exc:
            handoff_error = str(exc)
    if handoff_valid:
        return StageAssessment(
            stage=StageName.PROBE,
            robot_id=robot_id,
            status=StageStatus.COMPLETE,
            summary="Verified CLI and State Graph handoff is available",
            artifacts={
                "robot_wiki": str(wiki_path),
                "handoff_index": str(handoff_index),
            },
            agent_requirement=AgentRequirement.PROBE_AGENT,
        )
    return StageAssessment(
            stage=StageName.PROBE,
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
        blockers=[handoff_error or "Missing verified canonical CLI and State Graph handoff"],
            agent_requirement=AgentRequirement.PROBE_AGENT,
    )
