from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
)
from rolo.stages.adapt.models import AdapterBundleManifest
from rolo.stages.adapt.operation_registry import (
    adapter_operation_eligibility,
    canonical_operation_registry,
    materialize_active_catalog,
)


def _route(endpoint: str, *, observed: bool) -> RouteEvidence:
    return RouteEvidence(
        resource_id=f"ros_topic:{endpoint}",
        kind="ros_topic",
        endpoint=endpoint,
        interface_type="std_msgs/msg/String",
        evidence_origin="OBSERVED_RUNTIME" if observed else "DECLARED_STATIC",
        source="test",
    )


def test_mixed_discovery_promotes_observed_operation_and_defers_the_rest() -> None:
    observed = _route("/camera/image_raw", observed=True)
    report = DiscoveryReport(
        discovery_id="disc-mixed",
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={"route_evidence": [observed.model_dump(mode="json")]},
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.snapshot",
                route_evidence=[_route("/camera/image_raw", observed=False)],
            ),
            OperationCandidate(
                operation="app.navigation.start",
                route_evidence=[_route("/navigate_to_pose", observed=False)],
            ),
        ],
    )
    eligible, deferred = adapter_operation_eligibility(report)
    assert eligible == {"app.camera.snapshot"}
    assert deferred == {"app.navigation.start": "TARGET_ROUTE_NOT_OBSERVED"}

    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.snapshot"
    )
    bundle = AdapterBundleManifest(
        schema_version="robot-adapter-bundle/v1",
        bundle_id="mixed",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-mixed",
        package_file="adapter.py",
        package_sha256="a" * 64,
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_snapshot",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    by_operation = {
        item.operation: item for item in materialize_active_catalog(report, bundle=bundle).tools
    }
    assert by_operation["app.camera.snapshot"].availability == "VERIFIED"
    assert by_operation["app.navigation.start"].availability == "UNAVAILABLE"
    assert any(
        "TARGET_ROUTE_NOT_OBSERVED" in item
        for item in by_operation["app.navigation.start"].limitations
    )


def test_any_of_route_binding_promotes_when_one_route_is_observed() -> None:
    observed = _route("/scan", observed=True)
    report = DiscoveryReport(
        discovery_id="disc-any-route",
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={"route_evidence": [observed.model_dump(mode="json")]},
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.lidar.snapshot",
                route_evidence=[
                    _route("/scan", observed=False),
                    _route("/robot1/scan", observed=False),
                ],
                route_binding_mode="ANY_OF",
            )
        ],
    )

    eligible, deferred = adapter_operation_eligibility(report)

    assert eligible == {"app.lidar.snapshot"}
    assert deferred == {}


def test_semantic_agent_defer_and_reject_are_distinct_gate_outcomes() -> None:
    route = _route("/camera/image_raw", observed=True)
    for disposition, expected in (
        ("DEFER", "AGENT_SEMANTIC_MAPPING_DEFERRED"),
        ("REJECT", "AGENT_SEMANTIC_MAPPING_REJECTED"),
    ):
        report = DiscoveryReport(
            discovery_id=f"disc-agent-{disposition.casefold()}",
            robot_id="demo",
            status=DiscoveryStatus.SUCCEEDED,
            platform={},
            capability_manifest={},
            probes={
                "ros": ProbeResult(
                    layer="ros",
                    status=DiscoveryStatus.SUCCEEDED,
                    data={"route_evidence": [route.model_dump(mode="json")]},
                )
            },
            operation_candidates=[
                OperationCandidate(
                    operation="app.camera.snapshot",
                    route_evidence=[route],
                    semantic_review_required=True,
                    semantic_review_disposition=disposition,
                    route_review_dispositions={route.resource_id: disposition},
                )
            ],
        )

        eligible, deferred = adapter_operation_eligibility(report)

        assert eligible == set()
        assert deferred == {"app.camera.snapshot": expected}


def test_agent_accept_cannot_bypass_high_risk_review() -> None:
    route = _route("/navigate_to_pose", observed=True)
    report = DiscoveryReport(
        discovery_id="disc-agent-high-risk",
        robot_id="demo",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={"route_evidence": [route.model_dump(mode="json")]},
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.navigation.start",
                route_evidence=[route],
                semantic_review_required=True,
                semantic_review_disposition="ACCEPT",
                route_review_dispositions={route.resource_id: "ACCEPT"},
            )
        ],
    )

    eligible, deferred = adapter_operation_eligibility(report)

    assert eligible == set()
    assert deferred == {
        "app.navigation.start": "AGENT_ACCEPT_REQUIRES_HIGH_RISK_REVIEW"
    }


def test_legacy_cli_candidate_without_explicit_review_flag_fails_closed() -> None:
    route = RouteEvidence(
        resource_id="cli:vendor-find-cameras",
        kind="cli",
        endpoint="vendor-find-cameras",
        interface_type="application/cli",
        evidence_origin="OBSERVED_RUNTIME",
        source="target-help:test",
    )
    report = DiscoveryReport(
        discovery_id="disc-legacy-cli",
        robot_id="demo",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                semantic_bindings=["semantic://cli/app/camera/list"],
                route_evidence=[route],
            )
        ],
    )

    eligible, deferred = adapter_operation_eligibility(report)

    assert eligible == set()
    assert deferred == {"app.camera.list": "AGENT_SEMANTIC_REVIEW_REQUIRED"}
