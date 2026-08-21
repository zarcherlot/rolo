from __future__ import annotations

from typing import Protocol, runtime_checkable

from rolo.capabilities.models import (
    InspectRequest,
    InspectResult,
    InvokeRequest,
    InvokeResult,
    ProviderCapabilitiesResult,
    ProviderProbeResult,
)


@runtime_checkable
class CapabilityProvider(Protocol):
    """Future platform-provider SPI; current platform code need not implement it.

    Implementations own platform connectivity. Core callers must authorize write
    capabilities through runtime policy before calling ``invoke``; implementing
    this protocol never grants authority or publishes a capability by itself.
    """

    def probe(self) -> ProviderProbeResult: ...

    def capabilities(self) -> ProviderCapabilitiesResult: ...

    def inspect(self, request: InspectRequest) -> InspectResult: ...

    def invoke(self, request: InvokeRequest) -> InvokeResult: ...
