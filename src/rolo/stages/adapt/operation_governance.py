from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.stages.adapt.operation_registry import CanonicalOperationRegistry


class SemanticLayer(str, Enum):
    PRODUCT_CONTROL = "product_control"
    HARDWARE = "hardware"
    OS = "os"
    MIDDLEWARE = "middleware"
    APPLICATION = "application"


class ExecutionClass(str, Enum):
    AGENT_NATIVE = "AGENT_NATIVE"
    PRODUCT_BUILTIN = "PRODUCT_BUILTIN"
    TARGET_ADAPTER = "TARGET_ADAPTER"
    PLATFORM_SPECIFIC = "PLATFORM_SPECIFIC"


class MigrationStatus(str, Enum):
    PLANNED = "PLANNED"
    RETAINED = "RETAINED"
    DEFERRED = "DEFERRED"


class CurrentRegistryAction(str, Enum):
    KEEP = "KEEP"


_CURRENT_TO_SEMANTIC_LAYER = {
    "control": SemanticLayer.PRODUCT_CONTROL,
    "hw": SemanticLayer.HARDWARE,
    "linux": SemanticLayer.OS,
    "middleware": SemanticLayer.MIDDLEWARE,
    "ros": SemanticLayer.MIDDLEWARE,
    "app": SemanticLayer.APPLICATION,
}


class OperationDisposition(BaseModel):
    """Governance metadata kept deliberately outside the canonical registry."""

    model_config = ConfigDict(extra="forbid")

    current_operation: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    current_layer: Literal["control", "hw", "linux", "middleware", "ros", "app"]
    semantic_layer: SemanticLayer
    execution_class: ExecutionClass
    portable_semantics: bool
    future_capability: str | None = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
    )
    migration_status: MigrationStatus
    migration_reason: str = Field(min_length=12)
    current_registry_action: CurrentRegistryAction

    @model_validator(mode="after")
    def validate_layer_mapping(self) -> OperationDisposition:
        expected = _CURRENT_TO_SEMANTIC_LAYER[self.current_layer]
        if self.semantic_layer != expected:
            raise ValueError(
                f"semantic_layer for {self.current_operation} must be {expected.value}"
            )
        return self


class OperationDispositionLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-operation-disposition/v1"] = (
        "robot-operation-disposition/v1"
    )
    entries: list[OperationDisposition] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_operations(self) -> OperationDispositionLedger:
        operations = [entry.current_operation for entry in self.entries]
        duplicates = sorted(
            operation for operation in set(operations) if operations.count(operation) > 1
        )
        if duplicates:
            raise ValueError(f"operation disposition contains duplicates: {duplicates}")
        return self

    def validate_against_registry(self, registry: CanonicalOperationRegistry) -> None:
        """Require an exact, layer-preserving inventory of the supplied registry."""
        registered = {entry.operation: entry.layer for entry in registry.operations}
        governed = {entry.current_operation: entry.current_layer for entry in self.entries}
        missing = sorted(set(registered) - set(governed))
        unknown = sorted(set(governed) - set(registered))
        mismatched_layers = sorted(
            operation
            for operation in set(registered) & set(governed)
            if registered[operation] != governed[operation]
        )
        if missing or unknown or mismatched_layers:
            raise ValueError(
                "operation disposition does not match canonical registry: "
                f"missing={missing}, unknown={unknown}, "
                f"mismatched_layers={mismatched_layers}"
            )

    def by_operation(self) -> dict[str, OperationDisposition]:
        return {entry.current_operation: entry for entry in self.entries}


def operation_disposition_path() -> Path:
    return Path(__file__).with_name("operation_dispositions.yaml")


@lru_cache(maxsize=1)
def load_operation_dispositions() -> OperationDispositionLedger:
    payload = yaml.safe_load(operation_disposition_path().read_text(encoding="utf-8"))
    ledger = OperationDispositionLedger.model_validate(payload)
    # Import lazily so importing this governance module does not materialize the registry.
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    ledger.validate_against_registry(canonical_operation_registry())
    return ledger
