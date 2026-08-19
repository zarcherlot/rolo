from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from rolo.core.models import (
    DiscoveryLatestIndex,
    DiscoveryReport,
    OperationCandidate,
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    ToolDescriptor,
)
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport
from rolo.stages.adapt.inputs import AdaptInputs
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
from rolo.stages.adapt.operation_registry import CanonicalOperationRegistry
from rolo.stages.adapt.software_relevance import (
    DirectDependencyReport,
    SoftwareSummary,
)
from rolo.stages.adapt.workset import AdaptOperationWorkset
from rolo.stages.contracts import PipelineAssessment, StageAssessment
from rolo.stages.discovery_manifest import DiscoveryRunManifest
from rolo.stages.handoffs import DiagnosisHandoff, VerificationHandoff

CANONICAL_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    RobotCapability,
    RobotUseRequest,
    RobotUseSupervision,
    DiscoveryReport,
    DiscoveryLatestIndex,
    OperationCandidate,
    CanonicalOperationRegistry,
    ToolDescriptor,
    AdaptInputs,
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
    AdaptOperationWorkset,
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
