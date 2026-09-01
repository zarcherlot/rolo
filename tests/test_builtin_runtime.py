from pathlib import Path

import rolo.builtin_runtime as builtin_runtime
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


def test_remote_catalog_only_verifies_target_evidence_projections() -> None:
    base = _report()
    probes = {
        layer: probe.model_copy(
            update={
                "data": {
                    "target_evidence": {"deployment_mode": "remote"},
                }
            }
        )
        for layer, probe in base.probes.items()
    }
    catalog = materialize_active_catalog(base.model_copy(update={"probes": probes}))
    by_operation = {item.operation: item for item in catalog.tools}

    assert by_operation["runtime.version"].availability == "VERIFIED"
    assert by_operation["ros.topic.list"].availability == "VERIFIED"
    assert by_operation["linux.host.inventory"].availability == "VERIFIED"
    assert by_operation["linux.service.list"].availability == "AVAILABLE"


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


def test_host_builtin_dispatch_preserves_operation_name(monkeypatch) -> None:
    monkeypatch.setattr(
        builtin_runtime.host_introspection,
        "host_uptime",
        lambda: {"status": "SUCCEEDED", "uptime_s": 42.0},
    )

    result = invoke_builtin(
        "linux.host.uptime",
        {},
        robot_id="robot-test",
        artifact_root=Path("."),
        release_root=Path("."),
        release=None,
        catalog=None,
    )

    assert result == {"status": "SUCCEEDED", "uptime_s": 42.0}
