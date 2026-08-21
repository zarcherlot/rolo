from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rolo.capabilities.models import (
    CapabilityDescriptor,
    InspectRequest,
    InspectResult,
    InvokeRequest,
    InvokeResult,
    ProviderCapabilitiesResult,
    ProviderManifest,
    ProviderProbeResult,
    ProviderStatus,
)


@dataclass
class FakeCapabilityProvider:
    """Reusable provider-neutral fixture; it never connects to a real platform."""

    manifest: ProviderManifest
    descriptors: list[CapabilityDescriptor]
    inspect_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    invoke_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    unavailable_capabilities: set[str] = field(default_factory=set)
    delays_s: dict[str, float] = field(default_factory=dict)
    failures: set[str] = field(default_factory=set)
    probe_count: int = 0
    capabilities_count: int = 0
    inspect_requests: list[InspectRequest] = field(default_factory=list)
    invoke_requests: list[InvokeRequest] = field(default_factory=list)

    def probe(self) -> ProviderProbeResult:
        self.probe_count += 1
        self._before("probe")
        return ProviderProbeResult(
            status=self.manifest.status,
            provider_version=self.manifest.provider_version,
            manifest=(self.manifest if self.manifest.status == ProviderStatus.AVAILABLE else None),
            evidence=["fake-provider:probe"],
            reason=(
                None
                if self.manifest.status == ProviderStatus.AVAILABLE
                else "fake provider configured unavailable"
            ),
        )

    def capabilities(self) -> ProviderCapabilitiesResult:
        self.capabilities_count += 1
        self._before("capabilities")
        return ProviderCapabilitiesResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.manifest.provider_version,
            capabilities=[item.model_copy(deep=True) for item in self.descriptors],
            evidence=["fake-provider:capabilities"],
        )

    def inspect(self, request: InspectRequest) -> InspectResult:
        self.inspect_requests.append(request.model_copy(deep=True))
        self._before("inspect")
        if request.capability_id in self.unavailable_capabilities:
            return self._inspect_unavailable(request.capability_id)
        value = self.inspect_values.get(request.capability_id)
        if value is None:
            return self._inspect_unavailable(request.capability_id)
        return InspectResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.manifest.provider_version,
            value=dict(value),
            evidence=[f"fake-provider:inspect:{request.capability_id}"],
        )

    def invoke(self, request: InvokeRequest) -> InvokeResult:
        self.invoke_requests.append(request.model_copy(deep=True))
        self._before("invoke")
        if request.capability_id in self.unavailable_capabilities:
            return self._invoke_unavailable(request.capability_id)
        value = self.invoke_values.get(request.capability_id)
        if value is None:
            return self._invoke_unavailable(request.capability_id)
        return InvokeResult(
            status=ProviderStatus.AVAILABLE,
            provider_version=self.manifest.provider_version,
            value=dict(value),
            evidence=[f"fake-provider:invoke:{request.capability_id}"],
        )

    def _before(self, phase: str) -> None:
        delay = self.delays_s.get(phase, 0)
        if delay > 0:
            time.sleep(delay)
        if phase in self.failures:
            raise RuntimeError(f"fake provider configured failure: {phase}")

    def _inspect_unavailable(self, capability_id: str) -> InspectResult:
        return InspectResult(
            status=ProviderStatus.UNAVAILABLE,
            provider_version=self.manifest.provider_version,
            evidence=[f"fake-provider:inspect:{capability_id}"],
            reason="fake provider capability is unavailable",
        )

    def _invoke_unavailable(self, capability_id: str) -> InvokeResult:
        return InvokeResult(
            status=ProviderStatus.UNAVAILABLE,
            provider_version=self.manifest.provider_version,
            evidence=[f"fake-provider:invoke:{capability_id}"],
            reason="fake provider capability is unavailable",
        )
