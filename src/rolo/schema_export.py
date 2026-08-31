from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from rolo.agent_tools import (
    AgentNativeToolDescriptor,
    AgentNativeToolResult,
    NativeToolCanaryGateReport,
    NativeToolExecutionParity,
    NativeToolParityReport,
    NativeToolRolloutDecision,
    NativeToolRunSummary,
    NativeToolSessionBudget,
    NativeToolSessionDescriptor,
)
from rolo.approval_gate_read_models import ApprovalGateCollection, ApprovalGateSummary
from rolo.capabilities import (
    CapabilityDescriptor,
    CapabilityResolutionShadow,
    PlatformProfile,
    ProviderConformanceReport,
    ProviderHostSnapshot,
    ProviderManifest,
    ProviderRegistration,
)
from rolo.contract_catalog import OperationContract, OperationContractCatalog
from rolo.core.models import (
    DiscoveryLatestIndex,
    DiscoveryReport,
    OperationCandidate,
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    RouteEvidence,
    ToolDescriptor,
)
from rolo.episode_observation_bundles import (
    CommittedEpisodeObservationRecord,
    EpisodeObservationBundleCollection,
    PublishedEpisodeObservationBundleProjection,
)
from rolo.episode_projection import CommittedEpisodeRecord
from rolo.episode_read_models import (
    EpisodeAssetSummary,
    EpisodeCohort,
    EpisodeCohortExclusions,
    EpisodeCohortMember,
    EpisodeCollection,
    EpisodeDetail,
    EpisodeFindingSummary,
    EpisodeRevisionCollection,
    EpisodeRevisionSummary,
    EpisodeSummary,
    EpisodeTimelineEvent,
    EpisodeTimelinePage,
)
from rolo.invocation_policy import (
    ExecutionQuiescenceLease,
    ExecutionQuiescenceRequest,
    InvocationPolicy,
    R3AuthorizationCapability,
    R3AuthorizationRequest,
)
from rolo.runtime_context import AdapterRuntimeContext
from rolo.stage_agent_read_models import StageAgentEvent, StageAgentEventPage, StageAgentRunDetail
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport
from rolo.stages.adapt.agent_contracts import (
    AgentOperationProposal,
    OperationProposalBundle,
    ToolSessionDescriptor,
)
from rolo.stages.adapt.baseline import AdaptBaselineSnapshot
from rolo.stages.adapt.hardware_provider import (
    HardwareEvidenceProviderRequest,
    HardwareEvidenceProviderResult,
)
from rolo.stages.adapt.heuristic_discovery import (
    DiscoveryPlanningContext,
    HeuristicDiscoverySummary,
)
from rolo.stages.adapt.inputs import AdaptInputs
from rolo.stages.adapt.journey import AdaptJourneyResult
from rolo.stages.adapt.models import (
    AdapterAgentDependencyReport,
    AdapterAgentResult,
    AdapterAgentRun,
    AdapterBundleManifest,
    AdapterConformanceReport,
    AdapterHandoff,
    AdapterOutputSnapshot,
    AdapterReleaseIndex,
    AdapterReleaseManifest,
    AdaptGateReport,
    AdaptLatestIndex,
    AdaptPlan,
    AdaptRunSummary,
    StateGraphBaseline,
    ToolCatalog,
)
from rolo.stages.adapt.operation_governance import (
    LegacyOperationDisposition,
    LegacyOperationDispositionLedger,
    OperationDispositionLedger,
)
from rolo.stages.adapt.operation_registry import CanonicalOperationRegistry
from rolo.stages.adapt.shadow_observation import (
    CapabilityShadowRunObservation,
    CapabilityShadowStabilityReport,
    TargetOperationSliceShadowReport,
)
from rolo.stages.adapt.skill_contracts import AdaptDiscoveryPlan
from rolo.stages.adapt.slice_activation import SliceActivationDecision
from rolo.stages.adapt.slice_observability import SliceStabilityReport
from rolo.stages.adapt.software_relevance import (
    DirectDependencyReport,
    SoftwareSummary,
)
from rolo.stages.adapt.wiki_diff import WikiDiscoveryDiff
from rolo.stages.adapt.wiki_insights import RoloWikiInsightBundle, WikiInsightBundle
from rolo.stages.adapt.workset import AdaptOperationWorkset, TargetOperationSlice
from rolo.stages.agent_runner import (
    StageActorIdentity,
    StageAgentRun,
    StageAgentTask,
    StageAuthorizationRequest,
)
from rolo.stages.contracts import PipelineAssessment, StageAssessment
from rolo.stages.diagnose.episode import DiagnosisEpisode, EpisodeObservation, TargetProvenance
from rolo.stages.diagnose_contract import DiagnosisReport
from rolo.stages.discovery_manifest import DiscoveryRunManifest
from rolo.stages.handoffs import DiagnosisHandoff, VerificationHandoff
from rolo.stages.real_target import CommandResult, TargetBinding
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationCaseResult,
    VerificationEvidencePackage,
    VerificationOracle,
    VerificationPlan,
    VerificationRegressionReport,
    VerificationReplayCase,
    VerificationReplayFixture,
    VerificationRunReport,
)
from rolo.stages.verify.readiness import (
    ReadinessCheck,
    RealVerifyReadinessReportV2,
    VerificationProviderManifestV2,
)
from rolo.target_readiness import TargetReadinessCollection, TargetReadinessSummary

CANONICAL_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    OperationContract,
    OperationContractCatalog,
    InvocationPolicy,
    ExecutionQuiescenceRequest,
    ExecutionQuiescenceLease,
    R3AuthorizationRequest,
    R3AuthorizationCapability,
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    DiscoveryReport,
    DiscoveryLatestIndex,
    RouteEvidence,
    OperationCandidate,
    AdapterRuntimeContext,
    CanonicalOperationRegistry,
    AdaptBaselineSnapshot,
    OperationDispositionLedger,
    LegacyOperationDisposition,
    LegacyOperationDispositionLedger,
    CapabilityDescriptor,
    ProviderManifest,
    ProviderRegistration,
    ProviderHostSnapshot,
    ProviderConformanceReport,
    PlatformProfile,
    CapabilityResolutionShadow,
    ToolDescriptor,
    AgentNativeToolDescriptor,
    AgentNativeToolResult,
    NativeToolSessionBudget,
    NativeToolSessionDescriptor,
    NativeToolRolloutDecision,
    NativeToolParityReport,
    NativeToolExecutionParity,
    NativeToolCanaryGateReport,
    NativeToolRunSummary,
    AdaptInputs,
    AdaptJourneyResult,
    AdaptPlan,
    AdapterAgentDependencyReport,
    AdapterAgentResult,
    AdapterAgentRun,
    AdapterBundleManifest,
    AdapterConformanceReport,
    StateGraphBaseline,
    ToolCatalog,
    AdapterHandoff,
    AdapterOutputSnapshot,
    AdapterReleaseManifest,
    AdapterReleaseIndex,
    AdaptGateReport,
    AdaptRunSummary,
    AdaptLatestIndex,
    DiscoveryRunManifest,
    DiagnosisHandoff,
    VerificationHandoff,
    StageAgentTask,
    StageAgentRun,
    StageActorIdentity,
    StageAuthorizationRequest,
    VerificationOracle,
    VerificationCase,
    VerificationPlan,
    VerificationCaseResult,
    VerificationRunReport,
    VerificationRegressionReport,
    VerificationEvidencePackage,
    VerificationReplayCase,
    VerificationReplayFixture,
    VerificationProviderManifestV2,
    ReadinessCheck,
    RealVerifyReadinessReportV2,
    DiagnosisReport,
    TargetProvenance,
    EpisodeObservation,
    DiagnosisEpisode,
    TargetBinding,
    CommandResult,
    StageAgentEvent,
    StageAgentEventPage,
    StageAgentRunDetail,
    StageAssessment,
    PipelineAssessment,
    SoftwareSummary,
    DirectDependencyReport,
    ActiveDiscoveryReport,
    AgentOperationProposal,
    OperationProposalBundle,
    ToolSessionDescriptor,
    AdaptDiscoveryPlan,
    DiscoveryPlanningContext,
    HeuristicDiscoverySummary,
    AdaptOperationWorkset,
    TargetOperationSlice,
    TargetOperationSliceShadowReport,
    CapabilityShadowRunObservation,
    CapabilityShadowStabilityReport,
    SliceActivationDecision,
    SliceStabilityReport,
    HardwareEvidenceProviderRequest,
    HardwareEvidenceProviderResult,
    WikiInsightBundle,
    RoloWikiInsightBundle,
    WikiDiscoveryDiff,
    EpisodeCollection,
    EpisodeSummary,
    EpisodeDetail,
    EpisodeTimelinePage,
    EpisodeTimelineEvent,
    EpisodeAssetSummary,
    EpisodeCohort,
    EpisodeCohortExclusions,
    EpisodeCohortMember,
    EpisodeFindingSummary,
    EpisodeRevisionCollection,
    EpisodeRevisionSummary,
    CommittedEpisodeRecord,
    CommittedEpisodeObservationRecord,
    EpisodeObservationBundleCollection,
    PublishedEpisodeObservationBundleProjection,
    TargetReadinessSummary,
    TargetReadinessCollection,
    ApprovalGateSummary,
    ApprovalGateCollection,
)

# Keep the pre-v2 filenames as compatibility exports for downstream consumers.
# They intentionally point at the current descriptor models; no legacy model is
# used by the runtime.
COMPATIBILITY_SCHEMA_ALIASES: tuple[tuple[str, type[BaseModel]], ...] = (
    ("AgentNativeTool", AgentNativeToolDescriptor),
    ("NativeToolSession", NativeToolSessionDescriptor),
)


def export_canonical_schemas(output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in CANONICAL_SCHEMA_MODELS:
        path = output / f"{model.__name__}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(path)
    for alias, model in COMPATIBILITY_SCHEMA_ALIASES:
        path = output / f"{alias}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(path)
    return written
