from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest

from rolo.capabilities import (
    CapabilityAccess,
    CapabilityDescriptor,
    InspectRequest,
    InspectResult,
    InvokeRequest,
    InvokeResult,
    ProviderCapabilitiesResult,
    ProviderCapability,
    ProviderHost,
    ProviderHostSnapshot,
    ProviderManifest,
    ProviderProbeResult,
    ProviderRegistration,
    ProviderRegistrationStatus,
    ProviderStatus,
    SemanticLayer,
    TransportDescriptor,
)


def manifest(provider_id: str = "opaque-provider") -> ProviderManifest:
    return ProviderManifest(
        provider_id=provider_id,
        provider_kind="future.unknown-kind",
        provider_version="v1",
        semantic_layers=[SemanticLayer.OS],
        capabilities=[
            ProviderCapability(
                capability_id="os.runtime.status",
                capability_version="1.0",
                route_ref=f"opaque://{provider_id}/status",
            ),
            ProviderCapability(
                capability_id="os.workload.stop",
                capability_version="1.0",
                route_ref=f"opaque://{provider_id}/stop",
            ),
        ],
        transport=TransportDescriptor(kind="future.unknown-transport"),
        evidence=[" fixture:manifest ", "fixture:manifest"],
    )


def descriptors() -> list[CapabilityDescriptor]:
    return [
        CapabilityDescriptor(
            capability_id="os.runtime.status",
            semantic_layer=SemanticLayer.OS,
            version="1.0",
            access=CapabilityAccess.READ,
            risk="R0",
        ),
        CapabilityDescriptor(
            capability_id="os.workload.stop",
            semantic_layer=SemanticLayer.OS,
            version="1.0",
            access=CapabilityAccess.WRITE,
            risk="R2",
        ),
    ]


@dataclass
class HostFakeProvider:
    provider_manifest: ProviderManifest = field(default_factory=manifest)
    capability_descriptors: list[CapabilityDescriptor] = field(default_factory=descriptors)
    probe_delay_s: float = 0
    fail_inspect: bool = False
    result_version: str = "v1"
    invoke_count: int = 0

    def probe(self) -> ProviderProbeResult:
        if self.probe_delay_s:
            time.sleep(self.probe_delay_s)
        return ProviderProbeResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.provider_manifest.provider_version,
            manifest=self.provider_manifest,
            evidence=["fixture:probe", " fixture:probe "],
        )

    def capabilities(self) -> ProviderCapabilitiesResult:
        return ProviderCapabilitiesResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.provider_manifest.provider_version,
            capabilities=self.capability_descriptors,
            evidence=["fixture:capabilities"],
        )

    def inspect(self, request: InspectRequest) -> InspectResult:
        if self.fail_inspect:
            raise RuntimeError("provider-private-secret")
        return InspectResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.result_version,
            value={"capability_id": request.capability_id},
            evidence=["fixture:inspect", "fixture:inspect"],
        )

    def invoke(self, request: InvokeRequest) -> InvokeResult:
        self.invoke_count += 1
        return InvokeResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.result_version,
            value={"route_ref": request.route_ref},
            evidence=["fixture:invoke"],
        )


class AllowWrites:
    def __init__(self) -> None:
        self.calls = 0

    def authorize(
        self,
        manifest: ProviderManifest,
        descriptor: CapabilityDescriptor,
        request: InvokeRequest,
    ) -> None:
        assert manifest.provider_id == "opaque-provider"
        assert descriptor.access == CapabilityAccess.WRITE
        assert request.authorization_ref == "policy://allow"
        self.calls += 1


class DenyWrites:
    def authorize(
        self,
        manifest: ProviderManifest,
        descriptor: CapabilityDescriptor,
        request: InvokeRequest,
    ) -> None:
        raise ValueError("denied by fixture policy")


def test_empty_host_and_registration_are_release_neutral() -> None:
    with ProviderHost() as host:
        assert host.manifests() == []
        assert host.snapshot() == ProviderHostSnapshot()

        registration = host.register(HostFakeProvider())

        assert registration.status == ProviderRegistrationStatus.REGISTERED
        assert registration.provider_id == "opaque-provider"
        assert registration.capability_count == 2
        assert registration.manifest_sha256
        assert registration.evidence == sorted(set(registration.evidence))
        assert "provider:opaque-provider" in registration.evidence
        assert host.snapshot().influences_release is False
        assert host.unregister("opaque-provider") is True
        assert host.unregister("opaque-provider") is False


def test_duplicate_provider_id_and_manifest_descriptor_drift_are_rejected() -> None:
    with ProviderHost() as host:
        assert host.register(HostFakeProvider()).status == ProviderRegistrationStatus.REGISTERED
        duplicate = host.register(HostFakeProvider())
        assert duplicate.status == ProviderRegistrationStatus.REJECTED
        assert "already registered" in (duplicate.reason or "")

    invalid_descriptor = descriptors()[0].model_copy(
        update={"capability_id": "os.undeclared.capability"}
    )
    with ProviderHost() as host:
        rejected = host.register(
            HostFakeProvider(capability_descriptors=[invalid_descriptor])
        )
        assert rejected.status == ProviderRegistrationStatus.REJECTED
        assert rejected.reason == "provider capabilities failed: ValueError"
        assert host.manifests() == []


def test_unavailable_manifest_is_not_registered() -> None:
    unavailable = manifest().model_copy(update={"status": ProviderStatus.UNAVAILABLE})
    with ProviderHost() as host:
        registration = host.register(HostFakeProvider(provider_manifest=unavailable))

        assert registration.status == ProviderRegistrationStatus.UNAVAILABLE
        assert registration.reason == "provider manifest reported unavailable"
        assert host.manifests() == []


def test_timeout_is_isolated_and_does_not_register_the_provider() -> None:
    started = time.monotonic()
    with ProviderHost(timeout_s=0.01) as host:
        registration = host.register(HostFakeProvider(probe_delay_s=0.1))
        elapsed = time.monotonic() - started

        assert registration.status == ProviderRegistrationStatus.REJECTED
        assert registration.reason == "provider probe timed out"
        assert elapsed < 0.08
        assert host.manifests() == []


def test_inspect_missing_capability_and_provider_failure_are_normal_unavailable() -> None:
    provider = HostFakeProvider(fail_inspect=True)
    with ProviderHost() as host:
        assert host.register(provider).status == ProviderRegistrationStatus.REGISTERED
        missing = host.inspect(
            "opaque-provider", InspectRequest(capability_id="os.missing")
        )
        failed = host.inspect(
            "opaque-provider", InspectRequest(capability_id="os.runtime.status")
        )

        assert missing.status == ProviderStatus.UNAVAILABLE
        assert "not declared" in (missing.reason or "")
        assert failed.status == ProviderStatus.UNAVAILABLE
        assert failed.reason == "provider inspect failed: RuntimeError"
        assert "provider-private-secret" not in failed.model_dump_json()


def test_unknown_provider_is_a_normal_unavailable_result() -> None:
    with ProviderHost() as host:
        inspected = host.inspect("future-provider", InspectRequest(capability_id="os.status"))
        invoked = host.invoke(
            "future-provider",
            InvokeRequest(capability_id="os.status", route_ref="opaque://future/status"),
        )

        assert inspected.status == ProviderStatus.UNAVAILABLE
        assert invoked.status == ProviderStatus.UNAVAILABLE
        assert inspected.provider_version == "unknown"
        assert inspected.reason == "provider is not registered"
        assert "provider:future-provider" in inspected.evidence


def test_result_version_mismatch_is_isolated() -> None:
    provider = HostFakeProvider(result_version="wrong-version")
    with ProviderHost() as host:
        host.register(provider)
        result = host.inspect(
            "opaque-provider", InspectRequest(capability_id="os.runtime.status")
        )

        assert result.status == ProviderStatus.UNAVAILABLE
        assert result.reason == "provider inspect failed: ValueError"


def test_read_invoke_runs_but_write_invoke_fails_closed_without_policy() -> None:
    provider = HostFakeProvider()
    with ProviderHost() as host:
        host.register(provider)
        read_result = host.invoke(
            "opaque-provider",
            InvokeRequest(
                capability_id="os.runtime.status",
                route_ref="opaque://opaque-provider/status",
            ),
        )
        write_result = host.invoke(
            "opaque-provider",
            InvokeRequest(
                capability_id="os.workload.stop",
                route_ref="opaque://opaque-provider/stop",
            ),
        )

        assert read_result.status == ProviderStatus.AVAILABLE
        assert write_result.status == ProviderStatus.UNAVAILABLE
        assert "Runtime policy authorization" in (write_result.reason or "")
        assert provider.invoke_count == 1


def test_write_authorizer_can_deny_or_allow_without_granting_host_authority() -> None:
    provider = HostFakeProvider()
    request = InvokeRequest(
        capability_id="os.workload.stop",
        route_ref="opaque://opaque-provider/stop",
        authorization_ref="policy://allow",
    )
    with ProviderHost() as host:
        host.register(provider)
        denied = host.invoke("opaque-provider", request, authorizer=DenyWrites())
        authorizer = AllowWrites()
        allowed = host.invoke("opaque-provider", request, authorizer=authorizer)

        assert denied.status == ProviderStatus.UNAVAILABLE
        assert denied.reason == "Runtime policy denied write capability: ValueError"
        assert allowed.status == ProviderStatus.AVAILABLE
        assert authorizer.calls == 1
        assert provider.invoke_count == 1


def test_undeclared_route_is_rejected_before_provider_invocation() -> None:
    provider = HostFakeProvider()
    with ProviderHost() as host:
        host.register(provider)
        result = host.invoke(
            "opaque-provider",
            InvokeRequest(
                capability_id="os.runtime.status",
                route_ref="opaque://attacker/route",
            ),
        )

        assert result.status == ProviderStatus.UNAVAILABLE
        assert "route_ref is not declared" in (result.reason or "")
        assert provider.invoke_count == 0


def test_registration_and_snapshot_schemas_are_strict() -> None:
    for model in (ProviderRegistration, ProviderHostSnapshot):
        schema = model.model_json_schema()
        assert schema["additionalProperties"] is False


def test_closed_host_rejects_new_calls() -> None:
    host = ProviderHost()
    host.close()

    with pytest.raises(RuntimeError, match="closed"):
        host.register(HostFakeProvider())
