from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

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
from rolo.episode_projection import CommittedEpisodeRecord
from rolo.episode_read_models import (
    EpisodeAssetSummary,
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
from rolo.stages.adapt.operation_governance import OperationDispositionLedger
from rolo.stages.adapt.operation_registry import CanonicalOperationRegistry
from rolo.stages.adapt.shadow_observation import TargetOperationSliceShadowReport
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
from rolo.stages.contracts import PipelineAssessment, StageAssessment
from rolo.stages.discovery_manifest import DiscoveryRunManifest
from rolo.stages.handoffs import DiagnosisHandoff, VerificationHandoff

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
    CapabilityDescriptor,
    ProviderManifest,
    ProviderRegistration,
    ProviderHostSnapshot,
    ProviderConformanceReport,
    PlatformProfile,
    CapabilityResolutionShadow,
    ToolDescriptor,
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
    EpisodeFindingSummary,
    EpisodeRevisionCollection,
    EpisodeRevisionSummary,
    CommittedEpisodeRecord,
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
    return written
