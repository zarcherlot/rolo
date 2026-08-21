from __future__ import annotations

from rolo.stages.adapt.baseline import (
    PINNED_ADAPT_BASELINE,
    capture_adapt_baseline,
    validate_pinned_adapt_baseline,
)
from rolo.stages.adapt.operation_governance import load_operation_dispositions
from rolo.stages.adapt.operation_registry import canonical_operation_registry


def test_current_registry_matches_the_pinned_adapt_baseline() -> None:
    assert validate_pinned_adapt_baseline() == PINNED_ADAPT_BASELINE


def test_baseline_detects_contract_or_registry_drift() -> None:
    registry = canonical_operation_registry()
    changed_operation = registry.operations[0].model_copy(
        update={"description": registry.operations[0].description + " changed"}
    )
    changed_registry = registry.model_copy(
        update={"operations": [changed_operation, *registry.operations[1:]]}
    )

    changed = capture_adapt_baseline(changed_registry, load_operation_dispositions())

    assert changed.operation_count == PINNED_ADAPT_BASELINE.operation_count
    assert changed.registry_sha256 != PINNED_ADAPT_BASELINE.registry_sha256


def test_baseline_identity_digest_covers_operation_layer_and_contract() -> None:
    registry = canonical_operation_registry()
    changed_operation = registry.operations[0].model_copy(update={"layer": "app"})
    changed_registry = registry.model_copy(
        update={"operations": [changed_operation, *registry.operations[1:]]}
    )
    ledger = load_operation_dispositions().model_copy(deep=True)
    ledger.entries[0].current_layer = "app"
    ledger.entries[0].semantic_layer = "application"

    changed = capture_adapt_baseline(changed_registry, ledger)

    assert changed.operation_identity_sha256 != PINNED_ADAPT_BASELINE.operation_identity_sha256
