from __future__ import annotations

import pytest

from rolo.capabilities import (
    CapabilityAccess,
    CapabilityDescriptor,
    CapabilityResolver,
    FakeCapabilityProvider,
    InspectRequest,
    OperationCapabilityRequirement,
    PlatformFact,
    PlatformProfile,
    ProviderCapability,
    ProviderConformanceReport,
    ProviderConformanceStatus,
    ProviderHost,
    ProviderManifest,
    ProviderRegistrationStatus,
    ProviderStatus,
    ResolutionStatus,
    SemanticLayer,
    TransportDescriptor,
    run_provider_conformance,
)


def fake_provider(
    provider_id: str,
    capabilities: list[tuple[str, CapabilityAccess]],
    *,
    layer: SemanticLayer = SemanticLayer.OS,
) -> FakeCapabilityProvider:
    provider_manifest = ProviderManifest(
        provider_id=provider_id,
        provider_kind="conformance.unknown-provider-kind",
        provider_version="conformance-v1",
        semantic_layers=[layer],
        capabilities=[
            ProviderCapability(
                capability_id=capability_id,
                capability_version="1.0",
                route_ref=f"conformance://{provider_id}/{capability_id}",
            )
            for capability_id, _ in capabilities
        ],
        transport=TransportDescriptor(kind="conformance.opaque-transport"),
        evidence=[f"conformance:{provider_id}"],
    )
    descriptors = [
        CapabilityDescriptor(
            capability_id=capability_id,
            semantic_layer=layer,
            version="1.0",
            access=access,
            risk="R2" if access == CapabilityAccess.WRITE else "R0",
        )
        for capability_id, access in capabilities
    ]
    return FakeCapabilityProvider(manifest=provider_manifest, descriptors=descriptors)


@pytest.mark.parametrize(
    ("provider_id", "layer", "capabilities", "missing_capability"),
    [
        (
            "service-less",
            SemanticLayer.OS,
            ["os.runtime.status", "os.workload.list"],
            "os.service.list",
        ),
        (
            "filesystem-less",
            SemanticLayer.OS,
            ["os.runtime.status", "os.log.query"],
            "os.filesystem.inspect",
        ),
        (
            "rtos-like",
            SemanticLayer.OS,
            ["os.runtime.status", "os.workload.list", "os.resource.snapshot"],
            "os.process.inspect",
        ),
        (
            "channel-only",
            SemanticLayer.MIDDLEWARE,
            ["middleware.channel.list", "middleware.channel.sample"],
            "middleware.service.list",
        ),
    ],
)
def test_provider_neutral_scenario_matrix_conforms_and_preserves_absence(
    provider_id: str,
    layer: SemanticLayer,
    capabilities: list[str],
    missing_capability: str,
) -> None:
    provider = fake_provider(
        provider_id,
        [(item, CapabilityAccess.READ) for item in capabilities],
        layer=layer,
    )

    report = run_provider_conformance(provider)
    resolution = CapabilityResolver().resolve(
        OperationCapabilityRequirement(
            operation="legacy.missing.operation",
            capability_id=missing_capability,
            capability_version="1.0",
            semantic_layer=layer,
        ),
        PlatformProfile(
            profile_id="conformance-profile",
            os=PlatformFact(family="opaque-os"),
            available_transports=["conformance.opaque-transport"],
        ),
        [provider.manifest],
    )

    assert report.conforms is True
    assert report.influences_release is False
    assert resolution.status == ResolutionStatus.UNAVAILABLE


def test_empty_provider_is_a_valid_conformance_subject() -> None:
    provider = fake_provider("empty-provider", [])

    report = run_provider_conformance(provider)

    assert report.conforms is True
    assert report.registration is not None
    assert report.registration.capability_count == 0


def test_conformance_write_check_never_invokes_the_provider() -> None:
    provider = fake_provider(
        "write-provider",
        [("os.workload.stop", CapabilityAccess.WRITE)],
    )

    report = run_provider_conformance(provider)
    write_check = next(item for item in report.checks if item.name == "write_policy")

    assert report.conforms is True
    assert write_check.status == ProviderConformanceStatus.PASSED
    assert write_check.evidence == ["write-capability-count:1"]
    assert provider.invoke_requests == []


def test_unknown_extensions_are_accepted_without_changing_core_digests() -> None:
    provider = fake_provider(
        "extension-provider",
        [("os.runtime.status", CapabilityAccess.READ)],
    )
    provider.manifest.extensions["future-provider-extension"] = {"opaque": True}
    provider.manifest.transport.extensions["future-transport-extension"] = [1, 2]
    provider.descriptors[0].extensions["future-capability-extension"] = "opaque"

    report = run_provider_conformance(provider)

    assert report.conforms is True
    extension_check = next(item for item in report.checks if item.name == "extension_digest")
    assert extension_check.status == ProviderConformanceStatus.PASSED


def test_timeout_and_descriptor_drift_return_failed_reports_instead_of_raising() -> None:
    timeout_provider = fake_provider("timeout-provider", [])
    timeout_provider.delays_s["probe"] = 0.1
    timeout_report = run_provider_conformance(timeout_provider, timeout_s=0.01)

    invalid_provider = fake_provider(
        "invalid-provider",
        [("os.runtime.status", CapabilityAccess.READ)],
    )
    invalid_provider.descriptors[0] = invalid_provider.descriptors[0].model_copy(
        update={"capability_id": "os.undeclared"}
    )
    invalid_report = run_provider_conformance(invalid_provider)

    assert timeout_report.conforms is False
    assert invalid_report.conforms is False
    assert timeout_report.registration is not None
    assert timeout_report.registration.status == ProviderRegistrationStatus.REJECTED
    assert all(
        item.status == ProviderConformanceStatus.FAILED
        for item in timeout_report.checks
        if item.name == "registration"
    )


def test_fake_provider_returns_unavailable_for_missing_capability() -> None:
    provider = fake_provider(
        "fake-template",
        [("os.runtime.status", CapabilityAccess.READ)],
    )

    result = provider.inspect(InspectRequest(capability_id="os.missing"))

    assert result.status == ProviderStatus.UNAVAILABLE
    assert result.reason == "fake provider capability is unavailable"


def test_conformance_detects_non_spi_objects() -> None:
    report = run_provider_conformance(object())

    assert report.provider_id == "unidentified"
    assert report.conforms is False
    assert report.checks[0].name == "spi"


def test_host_descriptor_view_is_sorted_and_defensive() -> None:
    provider = fake_provider(
        "descriptor-provider",
        [
            ("os.zeta", CapabilityAccess.READ),
            ("os.alpha", CapabilityAccess.READ),
        ],
    )
    with ProviderHost() as host:
        host.register(provider)
        first = host.descriptors("descriptor-provider")
        first[0].extensions["mutated"] = True
        second = host.descriptors("descriptor-provider")

        assert [item.capability_id for item in second] == ["os.alpha", "os.zeta"]
        assert second[0].extensions == {}
        assert host.descriptors("missing-provider") == []


def test_conformance_report_schema_is_strict_and_summary_is_consistent() -> None:
    schema = ProviderConformanceReport.model_json_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "provider_id",
        "checks",
        "conforms",
    }
