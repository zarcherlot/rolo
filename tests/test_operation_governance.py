from __future__ import annotations

from copy import deepcopy

import pytest
import yaml
from pydantic import ValidationError

from rolo.stages.adapt.operation_governance import (
    CurrentRegistryAction,
    ExecutionClass,
    OperationDispositionLedger,
    SemanticLayer,
    load_operation_dispositions,
    operation_disposition_path,
)
from rolo.stages.adapt.operation_registry import canonical_operation_registry


def test_disposition_covers_the_current_registry_exactly() -> None:
    registry = canonical_operation_registry()
    ledger = load_operation_dispositions()

    assert len(registry.operations) == 294
    assert len(ledger.entries) == 294
    assert set(ledger.by_operation()) == {entry.operation for entry in registry.operations}
    ledger.validate_against_registry(registry)


def test_disposition_preserves_current_registry_and_externalizes_semantics() -> None:
    registry = canonical_operation_registry()
    ledger = load_operation_dispositions()
    semantic_layers = {
        "control": SemanticLayer.PRODUCT_CONTROL,
        "hw": SemanticLayer.HARDWARE,
        "linux": SemanticLayer.OS,
        "middleware": SemanticLayer.MIDDLEWARE,
        "ros": SemanticLayer.MIDDLEWARE,
        "app": SemanticLayer.APPLICATION,
    }

    for definition in registry.operations:
        disposition = ledger.by_operation()[definition.operation]
        assert disposition.current_layer == definition.layer
        assert disposition.semantic_layer == semantic_layers[definition.layer]
        assert disposition.current_registry_action == CurrentRegistryAction.KEEP


def test_disposition_has_all_execution_classes_and_no_platform_implementation() -> None:
    ledger = load_operation_dispositions()

    assert {entry.execution_class for entry in ledger.entries} == set(ExecutionClass)
    assert all(entry.future_capability != "os.windows" for entry in ledger.entries)
    assert all(entry.future_capability != "middleware.cyberrt" for entry in ledger.entries)


def test_disposition_schema_is_strict_and_requires_every_governance_field() -> None:
    schema = OperationDispositionLedger.model_json_schema()
    entry_schema = schema["$defs"]["OperationDisposition"]

    assert entry_schema["additionalProperties"] is False
    assert set(entry_schema["required"]) == {
        "current_operation",
        "current_layer",
        "semantic_layer",
        "execution_class",
        "portable_semantics",
        "future_capability",
        "migration_status",
        "migration_reason",
        "current_registry_action",
    }


def test_schema_rejects_unknown_fields_and_duplicate_operations() -> None:
    payload = yaml.safe_load(operation_disposition_path().read_text(encoding="utf-8"))
    with_unknown = deepcopy(payload)
    with_unknown["entries"][0]["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        OperationDispositionLedger.model_validate(with_unknown)

    with_duplicate = deepcopy(payload)
    with_duplicate["entries"].append(deepcopy(with_duplicate["entries"][0]))
    with pytest.raises(ValidationError, match="contains duplicates"):
        OperationDispositionLedger.model_validate(with_duplicate)


def test_registry_validation_reports_missing_unknown_and_layer_drift() -> None:
    registry = canonical_operation_registry()
    payload = yaml.safe_load(operation_disposition_path().read_text(encoding="utf-8"))
    payload["entries"] = payload["entries"][1:]
    payload["entries"][0]["current_operation"] = "future.unknown.operation"
    payload["entries"][1]["current_layer"] = "app"
    payload["entries"][1]["semantic_layer"] = "application"
    ledger = OperationDispositionLedger.model_validate(payload)

    with pytest.raises(
        ValueError,
        match="missing=.*unknown=.*mismatched_layers=",
    ):
        ledger.validate_against_registry(registry)
