from __future__ import annotations

import json
from typing import Any

from rolo.stages.adapt.operation_registry_v2 import RegistryView, build_registry_projection
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
    return {
        "status": "SUCCEEDED",
        "source_registry_version": projection.source_registry_version,
        "source_operation_count": projection.source_operation_count,
        "views": {name: len(operations) for name, operations in views.items()},
        "v1_registry_sha256": v1.registry_sha256,
        "v2_registry_sha256": v2.registry_sha256,
        "v2_registry_operation_count": v2.operation_count,
        # Kept as a compatibility alias for existing report consumers.
        "v2_shadow_registry_sha256": v2.registry_sha256,
        "v1_v2_identity_distinct": v1.registry_sha256 != v2.registry_sha256,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True))

