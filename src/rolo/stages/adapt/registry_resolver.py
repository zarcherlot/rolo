from __future__ import annotations

import hashlib
import json

from rolo.stages.adapt.agent_contracts import OperationRegistryResolver
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationRegistry,
    canonical_operation_registry,
)
from rolo.stages.adapt.operation_registry_v2 import RegistryView, build_registry_projection


def _catalog_digest(registry: CanonicalOperationRegistry, operations: set[str]) -> str:
    payload = json.dumps(
        {
            definition.operation: definition.contract_sha256
            for definition in registry.operations
            if definition.operation in operations
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class BoundRegistryResolver(OperationRegistryResolver):
    """Release-bound registry identity used by proposal and session validators."""

    def __init__(
        self,
        registry: CanonicalOperationRegistry,
        *,
        registry_version: str,
        allowed_operations: set[str] | None = None,
    ) -> None:
        self._registry = registry
        self._definitions = {item.operation: item for item in registry.operations}
        self._allowed = allowed_operations or set(self._definitions)
        unknown = sorted(self._allowed - set(self._definitions))
        if unknown:
            raise ValueError(f"resolver allowlist contains unknown operations: {unknown}")
        self._registry_version = registry_version
        self._registry_sha256 = self._identity_sha256()
        self._contract_catalog_sha256 = _catalog_digest(registry, self._allowed)

    @property
    def registry_version(self) -> str:
        return self._registry_version

    @property
    def registry_sha256(self) -> str:
        return self._registry_sha256

    @property
    def contract_catalog_sha256(self) -> str:
        return self._contract_catalog_sha256

    @property
    def operation_count(self) -> int:
        return len(self._allowed)

    def contract_sha256_for(self, operation: str) -> str | None:
        if operation not in self._allowed:
            return None
        definition = self._definitions.get(operation)
        return definition.contract_sha256 if definition else None

    def _identity_sha256(self) -> str:
        payload = json.dumps(
            {
                "schema_version": "rolo-registry-identity/v1",
                "registry_version": self._registry_version,
                "operations": [
                    {
                        "operation": operation,
                        "contract_sha256": self._definitions[operation].contract_sha256,
                    }
                    for operation in sorted(self._allowed)
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def load_registry_resolver(
    version: str = "v1",
    *,
    registry: CanonicalOperationRegistry | None = None,
) -> BoundRegistryResolver:
    """Load v1 or the non-authoritative v2 shadow view by explicit version."""
    registry = registry or canonical_operation_registry()
    if version == "v1":
        return BoundRegistryResolver(registry, registry_version="v1")
    if version == "v2-shadow":
        projection = build_registry_projection(registry)
        return BoundRegistryResolver(
            registry,
            registry_version="v2-shadow",
            allowed_operations=set(projection.operations(RegistryView.CANONICAL)),
        )
    raise ValueError(f"unknown Registry version: {version}")


def resolver_for_identity(
    version: str,
    registry_sha256: str,
    *,
    registry: CanonicalOperationRegistry | None = None,
) -> BoundRegistryResolver:
    resolver = load_registry_resolver(version, registry=registry)
    if resolver.registry_sha256 != registry_sha256:
        raise ValueError("Registry identity does not match the requested version")
    return resolver
