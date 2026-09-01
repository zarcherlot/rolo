from pathlib import Path

from rolo.builtin_runtime import invoke_builtin, supported_builtin_operations
from rolo.core.models import DiscoveryReport, DiscoveryStatus, ProbeResult
from rolo.stages.adapt.operation_registry import _BUILTIN_CLI, materialize_active_catalog


def _report() -> DiscoveryReport:
    probes = {
        layer: ProbeResult(layer=layer, status=DiscoveryStatus.SUCCEEDED)
        for layer in ("hw", "linux", "ros")
    }
    return DiscoveryReport(
        discovery_id="disc-test",
        robot_id="robot-test",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes=probes,
    )


def test_every_product_builtin_has_a_dispatcher() -> None:
    assert supported_builtin_operations() == set(_BUILTIN_CLI)


def test_materialized_catalog_verifies_dispatchable_read_builtins() -> None:
    catalog = materialize_active_catalog(_report())
    by_operation = {item.operation: item for item in catalog.tools}
    assert len(by_operation) == 294
    assert all(
        by_operation[operation].availability == "VERIFIED"
        for operation in _BUILTIN_CLI
    )
    assert all(
        by_operation[operation].adapter.startswith("builtin.")
        for operation in _BUILTIN_CLI
    )


def test_builtin_runtime_version_is_schema_ready() -> None:
    result = invoke_builtin(
        "runtime.version",
        {},
        robot_id="robot-test",
        artifact_root=Path("."),
        release_root=Path("."),
        release=None,
        catalog=None,
    )
    assert result["status"] == "SUCCEEDED"
    assert result["operation_contract_schema"] == "robot-operation-contract/v1"
