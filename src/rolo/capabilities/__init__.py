"""Provider-neutral capability contracts for future platform adapters.

This package is intentionally disconnected from the active registry and release
pipeline. It provides contracts that platform providers can implement later.
"""

from rolo.capabilities.host import (
    CapabilityWriteAuthorizer,
    ProviderHost,
    ProviderHostSnapshot,
    ProviderRegistration,
    ProviderRegistrationStatus,
)
from rolo.capabilities.models import (
    CapabilityAccess,
    CapabilityAvailability,
    CapabilityDescriptor,
    CapabilityResolution,
    CapabilityResolutionShadow,
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
from rolo.capabilities.provider import CapabilityProvider
from rolo.capabilities.resolver import CapabilityResolver
from rolo.capabilities.semantics import LEGACY_LAYER_SEMANTICS

__all__ = [
    "LEGACY_LAYER_SEMANTICS",
    "CapabilityAccess",
    "CapabilityAvailability",
    "CapabilityDescriptor",
    "CapabilityProvider",
    "CapabilityResolution",
    "CapabilityResolutionShadow",
    "CapabilityResolver",
    "CapabilityWriteAuthorizer",
    "InspectRequest",
    "InspectResult",
    "InvokeRequest",
    "InvokeResult",
    "OperationCapabilityRequirement",
    "PlatformFact",
    "PlatformProfile",
    "ProviderCapabilitiesResult",
    "ProviderCapability",
    "ProviderManifest",
    "ProviderHost",
    "ProviderHostSnapshot",
    "ProviderProbeResult",
    "ProviderRegistration",
    "ProviderRegistrationStatus",
    "ProviderStatus",
    "ResolutionStatus",
    "SemanticLayer",
    "TransportDescriptor",
]
