from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from rolo.capabilities import (
    CapabilityAccess,
    CapabilityAvailability,
    CapabilityDescriptor,
    CapabilityProvider,
    CapabilityResolutionShadow,
    CapabilityResolver,
    InspectRequest,
    InspectResult,
    InvokeRequest,
    InvokeResult,
    OperationCapabilityRequirement,
    PlatformFact,
    PlatformProfile,
    ProviderCapabilitiesResult,
    ProviderCapability,
    ProviderManifest,
    ProviderProbeResult,
    ProviderStatus,
    ResolutionStatus,
    SemanticLayer,
    TransportDescriptor,
)
from rolo.capabilities.semantics import semantic_layer_for_legacy

SCHEMA_MODELS = {
    "CapabilityDescriptor.schema.json": CapabilityDescriptor,
    "ProviderManifest.schema.json": ProviderManifest,
    "PlatformProfile.schema.json": PlatformProfile,
    "CapabilityResolutionShadow.schema.json": CapabilityResolutionShadow,
}


def descriptor(capability_id: str, layer: SemanticLayer) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        semantic_layer=layer,
        version="1.0",
        access=CapabilityAccess.READ,
        risk="R0",
    )


def manifest(
    provider_id: str,
    capabilities: list[str],
    *,
    layer: SemanticLayer = SemanticLayer.OS,
    provider_kind: str = "test.unknown-provider-kind",
    transport: str = "test.opaque-transport",
    priority: int = 0,
    required_features: list[str] | None = None,
) -> ProviderManifest:
    return ProviderManifest(
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_version="fixture-v1",
        semantic_layers=[layer],
        capabilities=[
            ProviderCapability(
                capability_id=capability_id,
                capability_version="1.0",
                route_ref=f"fixture://{provider_id}/{capability_id}",
                priority=priority,
                required_features=required_features or [],
            )
            for capability_id in capabilities
        ],
        transport=TransportDescriptor(kind=transport),
        evidence=[f"fixture:{provider_id}"],
    )


@pytest.fixture
def full_os_provider() -> ProviderManifest:
    return manifest(
        "full-os",
        [
            "os.runtime.status",
            "os.workload.list",
            "os.workload.inspect",
            "os.resource.snapshot",
            "os.log.query",
            "os.time.status",
            "os.service.list",
            "os.filesystem.inspect",
        ],
    )


@pytest.fixture
def rtos_like_provider() -> ProviderManifest:
    return manifest(
        "rtos-like",
        ["os.runtime.status", "os.workload.list", "os.resource.snapshot"],
        required_features=["task-workloads"],
    )


@pytest.fixture
def service_less_provider() -> ProviderManifest:
    return manifest("service-less", ["os.runtime.status", "os.workload.list"])


@pytest.fixture
def filesystem_less_provider() -> ProviderManifest:
    return manifest("filesystem-less", ["os.runtime.status", "os.log.query"])


@pytest.fixture
def graph_middleware_provider() -> ProviderManifest:
    return manifest(
        "graph-middleware",
        ["middleware.graph.snapshot", "middleware.endpoint.list"],
        layer=SemanticLayer.MIDDLEWARE,
    )


@pytest.fixture
def channel_only_middleware_provider() -> ProviderManifest:
    return manifest(
        "channel-only",
        ["middleware.channel.list", "middleware.channel.sample"],
        layer=SemanticLayer.MIDDLEWARE,
    )


def requirement(
    capability_id: str,
    *,
    operation: str = "legacy.operation",
    layer: SemanticLayer = SemanticLayer.OS,
) -> OperationCapabilityRequirement:
    return OperationCapabilityRequirement(
        operation=operation,
        capability_id=capability_id,
        capability_version="1.0",
        semantic_layer=layer,
    )


def profile(*, features: list[str] | None = None) -> PlatformProfile:
    return PlatformProfile(
        profile_id="fixture-profile",
        os=PlatformFact(family="unrecognized-os-family", features=features or []),
        middleware=[PlatformFact(family="unrecognized-middleware-family")],
        available_transports=["test.opaque-transport"],
    )


def test_legacy_layers_have_external_semantics_without_registry_mutation() -> None:
    assert semantic_layer_for_legacy("control") is None
    assert semantic_layer_for_legacy("linux") == SemanticLayer.OS
    assert semantic_layer_for_legacy("ros") == SemanticLayer.MIDDLEWARE
    assert semantic_layer_for_legacy("app") == SemanticLayer.APPLICATION


@pytest.mark.parametrize("schema_name,model", SCHEMA_MODELS.items())
def test_capability_schema_matches_model(schema_name: str, model: type) -> None:
    tracked = json.loads(Path("schemas", schema_name).read_text(encoding="utf-8"))
    assert tracked == model.model_json_schema()


def test_open_provider_platform_and_transport_strings_are_accepted(
    full_os_provider: ProviderManifest,
) -> None:
    assert full_os_provider.provider_kind == "test.unknown-provider-kind"
    assert full_os_provider.transport.kind == "test.opaque-transport"
    assert profile().os is not None
    assert profile().os.family == "unrecognized-os-family"


def test_missing_service_and_filesystem_are_normal_unavailable_results(
    service_less_provider: ProviderManifest,
    filesystem_less_provider: ProviderManifest,
) -> None:
    resolver = CapabilityResolver()

    for candidate, capability_id in [
        (service_less_provider, "os.service.list"),
        (filesystem_less_provider, "os.filesystem.inspect"),
    ]:
        result = resolver.resolve(requirement(capability_id), profile(), [candidate])
        assert result.status == ResolutionStatus.UNAVAILABLE
        assert result.provider_id is None


def test_task_workload_capability_does_not_require_process_semantics(
    rtos_like_provider: ProviderManifest,
) -> None:
    result = CapabilityResolver().resolve(
        requirement("os.workload.list"),
        profile(features=["task-workloads"]),
        [rtos_like_provider],
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.provider_id == "rtos-like"


def test_channel_capability_does_not_require_topic_semantics(
    channel_only_middleware_provider: ProviderManifest,
) -> None:
    result = CapabilityResolver().resolve(
        requirement(
            "middleware.channel.list",
            operation="ros.topic.list",
            layer=SemanticLayer.MIDDLEWARE,
        ),
        profile(),
        [channel_only_middleware_provider],
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.provider_id == "channel-only"


def test_equal_priority_matches_are_reported_as_deterministic_ambiguity() -> None:
    candidates = [
        manifest("provider-z", ["os.runtime.status"]),
        manifest("provider-a", ["os.runtime.status"]),
    ]

    result = CapabilityResolver().resolve(
        requirement("os.runtime.status"), profile(), list(reversed(candidates))
    )

    assert result.status == ResolutionStatus.AMBIGUOUS
    assert result.candidate_provider_ids == ["provider-a", "provider-z"]


def test_unique_highest_priority_provider_is_resolved() -> None:
    candidates = [
        manifest("fallback", ["os.runtime.status"]),
        manifest("preferred", ["os.runtime.status"], priority=10),
    ]

    result = CapabilityResolver().resolve(
        requirement("os.runtime.status"), profile(), candidates
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.provider_id == "preferred"


def test_profile_transport_and_features_are_deterministic_compatibility_inputs() -> None:
    candidate = manifest(
        "feature-bound",
        ["os.runtime.status"],
        required_features=["required-feature"],
    )
    wrong_transport = profile(features=["required-feature"])
    wrong_transport.available_transports = ["different-opaque-transport"]

    assert (
        CapabilityResolver()
        .resolve(requirement("os.runtime.status"), wrong_transport, [candidate])
        .status
        == ResolutionStatus.UNAVAILABLE
    )
    assert (
        CapabilityResolver()
        .resolve(requirement("os.runtime.status"), profile(), [candidate])
        .status
        == ResolutionStatus.UNAVAILABLE
    )


def test_duplicate_provider_ids_are_rejected() -> None:
    candidate = manifest("duplicate", ["os.runtime.status"])
    with pytest.raises(ValueError, match="unique provider IDs"):
        CapabilityResolver().resolve(
            requirement("os.runtime.status"), profile(), [candidate, candidate]
        )


def test_unavailable_declaration_is_not_a_candidate() -> None:
    candidate = manifest("disabled", [])
    candidate.capabilities.append(
        ProviderCapability(
            capability_id="os.runtime.status",
            capability_version="1.0",
            availability=CapabilityAvailability.UNAVAILABLE,
        )
    )

    result = CapabilityResolver().resolve(
        requirement("os.runtime.status"), profile(), [candidate]
    )
    assert result.status == ResolutionStatus.UNAVAILABLE


def test_extensions_do_not_change_core_digests(full_os_provider: ProviderManifest) -> None:
    descriptor_a = descriptor("os.runtime.status", SemanticLayer.OS)
    descriptor_b = descriptor_a.model_copy(update={"extensions": {"vendor": {"x": 1}}})
    assert descriptor_a.core_digest() == descriptor_b.core_digest()

    provider_b = full_os_provider.model_copy(deep=True)
    provider_b.extensions["provider-data"] = True
    provider_b.transport.extensions["transport-data"] = "opaque"
    provider_b.capabilities[0].extensions["route-data"] = [1, 2, 3]
    assert full_os_provider.core_digest() == provider_b.core_digest()

    profile_a = profile()
    profile_b = profile_a.model_copy(deep=True)
    profile_b.extensions["profile-data"] = True
    assert profile_b.os is not None
    profile_b.os.extensions["os-data"] = "opaque"
    assert profile_a.core_digest() == profile_b.core_digest()


def test_shadow_artifact_is_sorted_and_never_influences_release(
    full_os_provider: ProviderManifest,
) -> None:
    artifact = CapabilityResolver().shadow_artifact(
        [
            requirement("os.workload.list", operation="z.operation"),
            requirement("os.runtime.status", operation="a.operation"),
        ],
        profile(),
        [full_os_provider],
        discovery_evidence=["evidence:z", "evidence:a", "evidence:a"],
    )

    assert artifact.influences_release is False
    assert [item.operation for item in artifact.resolutions] == ["a.operation", "z.operation"]
    assert artifact.discovery_evidence == ["evidence:a", "evidence:z"]
    assert len(artifact.provider_manifest_sha256) == 1


@dataclass
class FakeProvider:
    manifest: ProviderManifest

    def probe(self) -> ProviderProbeResult:
        return ProviderProbeResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.manifest.provider_version,
            manifest=self.manifest,
            evidence=["fixture:probe"],
        )

    def capabilities(self) -> ProviderCapabilitiesResult:
        return ProviderCapabilitiesResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.manifest.provider_version,
            capabilities=[
                descriptor(item.capability_id, self.manifest.semantic_layers[0])
                for item in self.manifest.capabilities
            ],
            evidence=["fixture:capabilities"],
        )

    def inspect(self, request: InspectRequest) -> InspectResult:
        return InspectResult(
            status=ProviderStatus.UNAVAILABLE,
            provider_version=self.manifest.provider_version,
            evidence=["fixture:inspect"],
            reason=f"no fixture resource for {request.capability_id}",
        )

    def invoke(self, request: InvokeRequest) -> InvokeResult:
        return InvokeResult(
            status=ProviderStatus.UNAVAILABLE,
            provider_version=self.manifest.provider_version,
            evidence=["fixture:invoke"],
            reason=f"fixture never invokes {request.route_ref}",
        )


def test_fake_provider_conforms_to_spi_and_can_return_unavailable(
    graph_middleware_provider: ProviderManifest,
) -> None:
    provider = FakeProvider(graph_middleware_provider)

    assert isinstance(provider, CapabilityProvider)
    assert provider.probe().status == ProviderStatus.AVAILABLE
    assert provider.capabilities().status == ProviderStatus.AVAILABLE
    assert (
        provider.inspect(InspectRequest(capability_id="middleware.endpoint.inspect")).status
        == ProviderStatus.UNAVAILABLE
    )
    assert (
        provider.invoke(
            InvokeRequest(capability_id="middleware.service.call", route_ref="fixture://none")
        ).status
        == ProviderStatus.UNAVAILABLE
    )
