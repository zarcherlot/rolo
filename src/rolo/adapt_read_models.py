from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.artifacts import ArtifactStore
from rolo.stages.adapt.operation_governance import (
    ExecutionClass,
    MigrationStatus,
    OperationDisposition,
    SemanticLayer,
    load_operation_dispositions,
)
from rolo.stages.adapt.service import AdaptStageService
from rolo.stages.adapt.workset import TargetOperationSlice, build_target_operation_slice

ADAPT_API_FEATURES = (
    "adapt.operation-governance/v1",
    "adapt.target-operation-slice/v1",
)


class OperationGovernanceCollection(BaseModel):
    """Bounded, read-only projection of the external operation governance ledger."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-operation-governance-collection/v1"] = (
        "rolo-operation-governance-collection/v1"
    )
    items: list[OperationDisposition] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=1)
    source_kind: Literal["operation_disposition_ledger"] = "operation_disposition_ledger"
    influences_registry: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Governance metadata is external to the canonical Registry and does not alter "
            "eligibility, release, or runtime behavior."
        ]
    )


def build_operation_governance_collection(
    *,
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
    semantic_layer: SemanticLayer | None = None,
    execution_class: ExecutionClass | None = None,
    migration_status: MigrationStatus | None = None,
) -> OperationGovernanceCollection:
    ledger = load_operation_dispositions()
    needle = (query or "").strip().casefold()
    items = []
    for entry in ledger.entries:
        if semantic_layer is not None and entry.semantic_layer != semantic_layer:
            continue
        if execution_class is not None and entry.execution_class != execution_class:
            continue
        if migration_status is not None and entry.migration_status != migration_status:
            continue
        searchable = " ".join(
            value
            for value in (
                entry.current_operation,
                entry.current_layer,
                entry.semantic_layer.value,
                entry.execution_class.value,
                entry.future_capability or "",
                entry.migration_reason,
            )
            if value
        ).casefold()
        if needle and needle not in searchable:
            continue
        items.append(entry)

    items.sort(key=lambda entry: entry.current_operation)
    total = len(items)
    page = items[offset : offset + limit]
    next_offset = offset + len(page) if offset + len(page) < total else None
    return OperationGovernanceCollection(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


def build_robot_target_operation_slice(
    artifacts: ArtifactStore,
    output_root: Path,
    robot_id: str,
) -> TargetOperationSlice:
    """Rebuild the shadow slice from the pinned current Adapt plan without persisting it."""

    plan = AdaptStageService(artifacts).derive_plan(robot_id)
    ledger = load_operation_dispositions()
    classifier = {
        entry.current_operation: entry.execution_class.value for entry in ledger.entries
    }
    task_operations = [operation for task in plan.tasks for operation in task.operations]
    return build_target_operation_slice(
        artifacts.root,
        output_root,
        robot_id,
        plan.source_discovery_id,
        eligible_operations=plan.eligible_operations,
        deferred_operations=plan.deferred_operations,
        task_operations=task_operations,
        classifier=classifier,
    )
