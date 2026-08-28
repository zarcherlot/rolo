from __future__ import annotations

import json
from typing import Any

from rolo.agent_tools import (
    build_native_operation_parity_report,
    native_catalog_sha256,
    native_operation_family_map,
    reduced_agent_native_catalog,
)
from rolo.stages.adapt.operation_governance import (
    LegacyOperationDisposition,
    LegacyOperationDispositionLedger,
)
from rolo.stages.adapt.operation_registry_v2 import (
    RegistryView,
    build_registry_projection,
    canonical_operation_registry_v2,
)
from rolo.stages.adapt.registry_resolver import load_registry_resolver


def build_report() -> dict[str, Any]:
    projection = build_registry_projection()
    views = {view.value: projection.operations(view) for view in RegistryView}
    all_operations = [operation for operations in views.values() for operation in operations]
    if len(all_operations) != len(set(all_operations)):
        raise ValueError("Registry projection contains overlapping views")
    if len(all_operations) != projection.source_operation_count:
        raise ValueError("Registry projection does not cover the v1 Registry exactly")
    v1 = load_registry_resolver("v1")
    v2 = load_registry_resolver("v2")
    native_catalog = reduced_agent_native_catalog()
    native_operation_map = native_operation_family_map(projection.agent_native_operations)
    canonical_ids = {item.operation for item in canonical_operation_registry_v2().operations}
    native_ids = {item.tool_id for item in native_catalog}
    if canonical_ids & native_ids:
        raise ValueError("v2 Canonical and family native catalogs overlap")
    if not set(native_operation_map.values()).issubset(native_ids):
        raise ValueError("native operation migration map references an unknown family tool")
    native_parity = build_native_operation_parity_report(
        projection.agent_native_operations,
        native_operation_map,
        native_ids,
    )
    legacy_ledger = LegacyOperationDispositionLedger(
        entries=[
            LegacyOperationDisposition(
                operation=operation,
                replacement_tool=family,
                migration_status="SHADOW",
                reason="Command-shaped probe is represented by a bounded family tool",
            )
            for operation, family in sorted(native_operation_map.items())
        ]
    )
    return {
        "status": "SUCCEEDED",
        "source_registry_version": projection.source_registry_version,
        "source_operation_count": projection.source_operation_count,
        "views": {name: len(operations) for name, operations in views.items()},
        "v1_registry_sha256": v1.registry_sha256,
        "v2_registry_sha256": v2.registry_sha256,
        "v2_registry_operation_count": v2.operation_count,
        "native_family_tool_count": len(native_catalog),
        "native_family_catalog_sha256": native_catalog_sha256(native_catalog),
        "native_family_tool_ids": sorted(native_ids),
        "native_operation_mapping_count": len(native_operation_map),
        "native_operation_parity": native_parity.model_dump(mode="json"),
        "legacy_operation_ledger": legacy_ledger.model_dump(mode="json"),
        "native_operation_family_counts": {
            family: sum(value == family for value in native_operation_map.values())
            for family in sorted(native_ids)
        },
        # Kept as a compatibility alias for existing report consumers.
        "v2_shadow_registry_sha256": v2.registry_sha256,
        "v1_v2_identity_distinct": v1.registry_sha256 != v2.registry_sha256,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True))
