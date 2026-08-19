from copy import deepcopy

import pytest

from rolo.contract_catalog import (
    ContractLifecycle,
    OperationContract,
    compatibility_issues,
    load_operation_contracts,
    render_canonical_cli,
    render_contract_catalog,
)
from rolo.stages.adapt.operation_registry import canonical_operation_registry


def test_authored_contracts_compile_into_the_complete_product_vocabulary() -> None:
    catalog = load_operation_contracts()
    registry = canonical_operation_registry()

    assert len(catalog.contracts) == 28
    assert len(registry.operations) == 297
    assert sum(item.lifecycle == ContractLifecycle.RELEASED for item in catalog.contracts) == 21
    assert sum(item.lifecycle == ContractLifecycle.GATEABLE for item in catalog.contracts) == 7
    draft_count = sum(
        item.contract_lifecycle == ContractLifecycle.DRAFT for item in registry.operations
    )
    assert draft_count == 269
    assert registry.contract_catalog_sha256 == catalog.sha256
    assert len(catalog.sha256) == 64


def test_contract_hash_and_cli_rendering_are_deterministic() -> None:
    contract = load_operation_contracts().by_operation()["app.camera.snapshot"]

    assert contract.sha256 == OperationContract.model_validate(
        contract.model_dump(mode="json")
    ).sha256
    assert render_canonical_cli(
        contract, robot_id="robot-1", payload={"camera": "front"}
    )[-1] == '{"camera":"front"}'


def test_breaking_contract_change_requires_a_new_major_version() -> None:
    previous = load_operation_contracts().by_operation()["app.camera.snapshot"]
    changed = deepcopy(previous.model_dump(mode="json"))
    changed["input_schema"]["properties"]["quality"] = {"type": "integer"}
    changed["input_schema"].setdefault("required", []).append("quality")
    current = OperationContract.model_validate(changed)

    assert "new required input properties: ['quality']" in compatibility_issues(
        previous, current
    )
    assert "breaking changes require a new major version" in compatibility_issues(
        previous, current
    )


def test_contract_schema_rejects_unknown_keywords() -> None:
    payload = deepcopy(
        load_operation_contracts().by_operation()["app.camera.snapshot"].model_dump(
            mode="json"
        )
    )
    payload["input_schema"]["unevaluatedProperties"] = False

    with pytest.raises(ValueError, match="unsupported schema keywords"):
        OperationContract.model_validate(payload)


def test_rendered_contract_catalog_contains_every_authored_contract() -> None:
    catalog = load_operation_contracts()
    rendered = render_contract_catalog(catalog)

    assert rendered.count("\n| `") == len(catalog.contracts)
    assert "app.teleop.velocity" in rendered
