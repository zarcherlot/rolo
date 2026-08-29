"""Standalone read-only evidence checker for the Operation mapping Agent.

The provider copies this file and a frozen request into its read-only workspace.
It deliberately performs no discovery and executes no target code: every
answer is a deterministic projection of evidence already collected by Rolo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CONDITIONS = {
    "BINDING_MATCH",
    "ROUTE_OBSERVED",
    "INTERFACE_SCHEMA_KNOWN",
    "PROVIDER_IDENTIFIED",
    "RUNTIME_REVISION_KNOWN",
}


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate(
    request: dict[str, Any],
    *,
    operation: str,
    route_resource_id: str,
    condition: str,
) -> dict[str, object]:
    if condition not in CONDITIONS:
        raise ValueError(f"unsupported evidence condition: {condition}")
    evidence = request["discovery_evidence"]
    binding = evidence.get("deterministic_bindings", {}).get(operation, {})
    route = evidence.get("route_resources", {}).get(route_resource_id)
    binding_match = route_resource_id in binding.get("route_resource_ids", [])
    facts = {
        "BINDING_MATCH": binding_match,
        "ROUTE_OBSERVED": bool(
            binding_match and route and route.get("evidence_origin") == "OBSERVED_RUNTIME"
        ),
        "INTERFACE_SCHEMA_KNOWN": bool(
            binding_match and route and route.get("interface_schema_sha256")
        ),
        "PROVIDER_IDENTIFIED": bool(binding_match and route and route.get("provider_id")),
        "RUNTIME_REVISION_KNOWN": bool(binding_match and route and route.get("runtime_revision")),
    }
    result = {
        "operation": operation,
        "route_resource_id": route_resource_id,
        "condition": condition,
        "satisfied": facts[condition],
    }
    result_sha256 = _digest(result)
    receipt = {**result, "result_sha256": result_sha256}
    receipt["receipt_id"] = _digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Check frozen Rolo mapping evidence")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    args = parser.parse_args()
    request = json.loads(args.snapshot.read_text(encoding="utf-8"))
    print(
        json.dumps(
            evaluate(
                request,
                operation=args.operation,
                route_resource_id=args.route,
                condition=args.condition,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
