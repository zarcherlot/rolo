from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.stages.adapt.operation_governance import (
    OperationDispositionLedger,
    load_operation_dispositions,
)
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationRegistry,
    canonical_operation_registry,
)


class AdaptBaselineSnapshot(BaseModel):
    """Release-neutral fingerprint for the protected Adapt operation baseline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-baseline-snapshot/v1"] = (
        "robot-adapt-baseline-snapshot/v1"
    )
    operation_count: int = Field(ge=1)
    disposition_count: int = Field(ge=1)
    contract_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


PINNED_ADAPT_BASELINE = AdaptBaselineSnapshot(
    operation_count=294,
    disposition_count=294,
    contract_catalog_sha256="6558a0d8869f0980e76456887883b5c0a3dc8447aeff75c26ffccf7b93d68f52",
    registry_sha256="67cc62e48ddbf257f49b7fd5df6bddbf3743e4cad0c5a727d41cfbf4e059b1d5",
    operation_identity_sha256="d1c55a61ced730b0f597cc1349bf6ca24964030c671a8e47feb1d7ea85a2379f",
)


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def capture_adapt_baseline(
    registry: CanonicalOperationRegistry | None = None,
    ledger: OperationDispositionLedger | None = None,
) -> AdaptBaselineSnapshot:
    registry = registry or canonical_operation_registry()
    ledger = ledger or load_operation_dispositions()
    ledger.validate_against_registry(registry)
    identities = [
        {
            "operation": item.operation,
            "layer": item.layer,
            "contract_version": item.contract_version,
            "contract_sha256": item.contract_sha256,
        }
        for item in registry.operations
    ]
    return AdaptBaselineSnapshot(
        operation_count=len(registry.operations),
        disposition_count=len(ledger.entries),
        contract_catalog_sha256=registry.contract_catalog_sha256,
        registry_sha256=_digest(registry.model_dump(mode="json")),
        operation_identity_sha256=_digest(identities),
    )


def validate_pinned_adapt_baseline() -> AdaptBaselineSnapshot:
    """Fail closed when the protected v1 Registry or governance inventory drifts."""
    current = capture_adapt_baseline()
    if current != PINNED_ADAPT_BASELINE:
        changed = [
            name
            for name in AdaptBaselineSnapshot.model_fields
            if getattr(current, name) != getattr(PINNED_ADAPT_BASELINE, name)
        ]
        raise ValueError(f"protected Adapt baseline drifted: {', '.join(changed)}")
    return current
