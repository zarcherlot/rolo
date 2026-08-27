from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.stages.adapt.operation_governance import (
    OperationRoleProjection,
    RegistryRole,
    project_operation_roles,
)
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationDefinition,
    CanonicalOperationRegistry,
    canonical_operation_registry,
)


class RegistryView(str, Enum):
    CANONICAL = "CANONICAL"
    AGENT_NATIVE = "AGENT_NATIVE"
    PRODUCT_CONTROL = "PRODUCT_CONTROL"
    PROVIDER = "PROVIDER"


class RegistryProjection(BaseModel):
    """A deterministic, non-authoritative v2 view of the protected v1 Registry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-registry-projection/v1"] = "rolo-registry-projection/v1"
    source_registry_version: str = "v1"
    source_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_operation_count: int = Field(ge=1)
    canonical_operations: list[str]
    agent_native_operations: list[str]
    product_control_operations: list[str]
    provider_operations: list[str]

    def operations(self, view: RegistryView) -> list[str]:
        return {
            RegistryView.CANONICAL: self.canonical_operations,
            RegistryView.AGENT_NATIVE: self.agent_native_operations,
            RegistryView.PRODUCT_CONTROL: self.product_control_operations,
            RegistryView.PROVIDER: self.provider_operations,
        }[view]


V2_REGISTRY_VERSION = "v2"


def _registry_sha256(registry: CanonicalOperationRegistry) -> str:
    payload = json.dumps(
        registry.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_registry_projection(
    registry: CanonicalOperationRegistry | None = None,
) -> RegistryProjection:
    """Project v1 into future ownership views without changing v1 authority."""
    registry = registry or canonical_operation_registry()
    roles = project_operation_roles(registry)
    by_role: dict[RegistryRole, list[str]] = {role: [] for role in RegistryRole}
    for item in roles:
        if item.registry_role == RegistryRole.LEGACY:
            continue
        by_role[item.registry_role].append(item.operation)
    return RegistryProjection(
        source_registry_sha256=_registry_sha256(registry),
        source_operation_count=len(registry.operations),
        canonical_operations=sorted(by_role[RegistryRole.CANONICAL]),
        agent_native_operations=sorted(by_role[RegistryRole.AGENT_NATIVE]),
        product_control_operations=sorted(by_role[RegistryRole.PRODUCT_CONTROL]),
        provider_operations=sorted(by_role[RegistryRole.PROVIDER]),
    )


def project_definitions(
    view: RegistryView,
    registry: CanonicalOperationRegistry | None = None,
) -> list[CanonicalOperationDefinition]:
    """Return v1 definitions for a view, useful for shadow checks and future v2 loaders."""
    registry = registry or canonical_operation_registry()
    projection = build_registry_projection(registry)
    allowed = set(projection.operations(view))
    return [item for item in registry.operations if item.operation in allowed]


def _subset_catalog_sha256(
    definitions: list[CanonicalOperationDefinition],
) -> str:
    """Digest only the contracts that remain in the v2 Canonical Registry."""

    payload = json.dumps(
        {
            definition.operation: definition.contract_sha256
            for definition in definitions
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_operation_registry_v2(
    registry: CanonicalOperationRegistry | None = None,
) -> CanonicalOperationRegistry:
    """Materialize the reduced v2 Canonical Registry.

    The v1 Registry remains the source of truth for compatibility and audit.  This
    function creates an independent, deterministic v2 artifact containing only
    product-semantic Canonical Operations; Linux/ROS/HW probe operations are
    intentionally absent and must be served by the Agent-native catalog.
    """

    registry = registry or canonical_operation_registry()
    definitions = project_definitions(RegistryView.CANONICAL, registry)
    if not definitions:
        raise ValueError("v2 Canonical Registry cannot be empty")
    native_ids = set(build_registry_projection(registry).agent_native_operations)
    if native_ids & {definition.operation for definition in definitions}:
        raise ValueError("v2 Canonical Registry contains an Agent-native operation")
    return CanonicalOperationRegistry(
        schema_version="robot-canonical-operation-registry/v2",
        contract_catalog_sha256=_subset_catalog_sha256(definitions),
        operations=definitions,
    )


def role_projection_by_operation(
    registry: CanonicalOperationRegistry | None = None,
) -> dict[str, OperationRoleProjection]:
    return {item.operation: item for item in project_operation_roles(registry)}

