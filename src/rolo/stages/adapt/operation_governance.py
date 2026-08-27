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


class RegistryRole(str, Enum):
    """Which catalog owns an operation's public identity."""

    CANONICAL = "CANONICAL"
    AGENT_NATIVE = "AGENT_NATIVE"
    PRODUCT_CONTROL = "PRODUCT_CONTROL"
    PROVIDER = "PROVIDER"
    LEGACY = "LEGACY"


class ExecutionPath(str, Enum):
    """The bounded implementation path used after role classification."""

    ADAPTER = "ADAPTER"
    DIRECT_RUNNER = "DIRECT_RUNNER"
    ROS_CLI = "ROS_CLI"
    PROVIDER = "PROVIDER"
    INTERNAL_SERVICE = "INTERNAL_SERVICE"


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

    @property
    def registry_role(self) -> RegistryRole:
        """Derive the new catalog role without changing the v1 ledger schema."""
        if self.current_layer == "control":
            return RegistryRole.PRODUCT_CONTROL
        if self.execution_class == ExecutionClass.AGENT_NATIVE:
            return RegistryRole.AGENT_NATIVE
        if self.execution_class == ExecutionClass.PLATFORM_SPECIFIC:
            return RegistryRole.PROVIDER
        return RegistryRole.CANONICAL

    @property
    def execution_path(self) -> ExecutionPath:
        """Map the existing execution class to a bounded implementation path."""
        if self.registry_role == RegistryRole.PROVIDER:
            return ExecutionPath.PROVIDER
        if self.registry_role == RegistryRole.AGENT_NATIVE:
            return (
                ExecutionPath.ROS_CLI
                if self.current_layer == "ros"
                else ExecutionPath.DIRECT_RUNNER
            )
        if self.current_layer == "control":
            return ExecutionPath.INTERNAL_SERVICE
        if self.execution_class == ExecutionClass.PRODUCT_BUILTIN:
            return ExecutionPath.INTERNAL_SERVICE
        return ExecutionPath.ADAPTER

    @property
    def downstream_contract_required(self) -> bool:
        """Whether callers need the full product-owned Operation Contract."""
        return self.registry_role in {
            RegistryRole.CANONICAL,
            RegistryRole.PRODUCT_CONTROL,
        }

    @property
    def security_boundary_required(self) -> bool:
        """Agent-native reads remain bounded even when no Canonical contract is needed."""
        return True

    @property
    def target_binding_required(self) -> bool:
        return self.execution_class == ExecutionClass.TARGET_ADAPTER


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


class OperationRoleProjection(BaseModel):
    """Derived v2 role metadata used by shadow tooling and future Registry loaders."""

    model_config = ConfigDict(extra="forbid")

    operation: str
    current_layer: Literal["control", "hw", "linux", "middleware", "ros", "app"]
    registry_role: RegistryRole
    execution_path: ExecutionPath
    downstream_contract_required: bool
    security_boundary_required: bool
    target_binding_required: bool


def project_operation_roles(
    registry: CanonicalOperationRegistry | None = None,
    ledger: OperationDispositionLedger | None = None,
) -> list[OperationRoleProjection]:
    """Build a deterministic role view while leaving the protected v1 ledger untouched."""
    if registry is None:
        from rolo.stages.adapt.operation_registry import canonical_operation_registry

        registry = canonical_operation_registry()
    ledger = ledger or load_operation_dispositions()
    ledger.validate_against_registry(registry)
    by_operation = ledger.by_operation()
    return [
        OperationRoleProjection(
            operation=definition.operation,
            current_layer=definition.layer,
            registry_role=by_operation[definition.operation].registry_role,
            execution_path=by_operation[definition.operation].execution_path,
            downstream_contract_required=by_operation[
                definition.operation
            ].downstream_contract_required,
            security_boundary_required=by_operation[
                definition.operation
            ].security_boundary_required,
            target_binding_required=by_operation[definition.operation].target_binding_required,
        )
        for definition in registry.operations
    ]


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
