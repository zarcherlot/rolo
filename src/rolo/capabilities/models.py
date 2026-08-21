from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticLayer(str, Enum):
    HARDWARE = "hardware"
    OS = "os"
    MIDDLEWARE = "middleware"
    APPLICATION = "application"


class CapabilityAccess(str, Enum):
    READ = "read"
    WRITE = "write"


class CapabilityAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNAVAILABLE = "UNAVAILABLE"
    AMBIGUOUS = "AMBIGUOUS"


class CapabilityDescriptor(StrictModel):
    schema_version: Literal["robot-capability-descriptor/v1"] = (
        "robot-capability-descriptor/v1"
    )
    capability_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$")
    semantic_layer: SemanticLayer
    version: str = Field(min_length=1)
    access: CapabilityAccess
    risk: Literal["R0", "R1", "R2", "R3"]
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    def core_digest(self) -> str:
        return _digest(self.model_dump(mode="json", exclude={"extensions"}))


class ProviderCapability(StrictModel):
    capability_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$")
    capability_version: str = Field(min_length=1)
    availability: CapabilityAvailability = CapabilityAvailability.AVAILABLE
    route_ref: str | None = None
    priority: int = 0
    required_features: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_available_route(self) -> ProviderCapability:
        if self.availability == CapabilityAvailability.AVAILABLE and not self.route_ref:
            raise ValueError("available provider capability requires route_ref")
        if self.availability == CapabilityAvailability.UNAVAILABLE and self.route_ref is not None:
            raise ValueError("unavailable provider capability cannot expose route_ref")
        return self


class TransportDescriptor(StrictModel):
    kind: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class ProviderManifest(StrictModel):
    schema_version: Literal["robot-provider-manifest/v1"] = "robot-provider-manifest/v1"
    provider_id: str = Field(min_length=1)
    provider_kind: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    status: ProviderStatus = ProviderStatus.AVAILABLE
    semantic_layers: list[SemanticLayer] = Field(min_length=1)
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    transport: TransportDescriptor
    evidence: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_duplicate_capabilities(self) -> ProviderManifest:
        keys = [(item.capability_id, item.capability_version) for item in self.capabilities]
        if len(keys) != len(set(keys)):
            raise ValueError("provider manifest contains duplicate capability declarations")
        return self

    def core_digest(self) -> str:
        value = self.model_dump(mode="json", exclude={"extensions"})
        value["transport"].pop("extensions", None)
        for capability in value["capabilities"]:
            capability.pop("extensions", None)
        return _digest(value)


class PlatformFact(StrictModel):
    family: str = Field(min_length=1)
    version: str | None = None
    features: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)


class PlatformProfile(StrictModel):
    schema_version: Literal["robot-platform-profile/v1"] = "robot-platform-profile/v1"
    profile_id: str = Field(min_length=1)
    os: PlatformFact | None = None
    middleware: list[PlatformFact] = Field(default_factory=list)
    available_transports: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    def feature_set(self) -> frozenset[str]:
        facts = list(self.features)
        if self.os is not None:
            facts.extend(self.os.features)
        for middleware in self.middleware:
            facts.extend(middleware.features)
        return frozenset(facts)

    def core_digest(self) -> str:
        value = self.model_dump(mode="json", exclude={"extensions"})
        if value["os"] is not None:
            value["os"].pop("extensions", None)
        for middleware in value["middleware"]:
            middleware.pop("extensions", None)
        return _digest(value)


class OperationCapabilityRequirement(StrictModel):
    operation: str = Field(min_length=1)
    capability_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$")
    capability_version: str = Field(min_length=1)
    semantic_layer: SemanticLayer


class CapabilityResolution(StrictModel):
    status: ResolutionStatus
    operation: str
    capability_id: str
    capability_version: str
    provider_id: str | None = None
    route_ref: str | None = None
    candidate_provider_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> CapabilityResolution:
        if self.status == ResolutionStatus.RESOLVED:
            if not self.provider_id or not self.route_ref:
                raise ValueError("resolved capability requires provider_id and route_ref")
        elif self.provider_id is not None or self.route_ref is not None:
            raise ValueError("unresolved capability cannot select a provider route")
        if self.status == ResolutionStatus.AMBIGUOUS and len(self.candidate_provider_ids) < 2:
            raise ValueError("ambiguous capability requires at least two candidates")
        return self


class ProviderProbeResult(StrictModel):
    status: ProviderStatus
    provider_version: str = Field(min_length=1)
    manifest: ProviderManifest | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_manifest_presence(self) -> ProviderProbeResult:
        if self.status == ProviderStatus.AVAILABLE and self.manifest is None:
            raise ValueError("available probe result requires a manifest")
        if self.status == ProviderStatus.UNAVAILABLE and self.manifest is not None:
            raise ValueError("unavailable probe result cannot expose a manifest")
        if self.manifest is not None and self.provider_version != self.manifest.provider_version:
            raise ValueError("probe result and manifest provider versions must match")
        return self


class ProviderCapabilitiesResult(StrictModel):
    status: ProviderStatus
    provider_version: str = Field(min_length=1)
    capabilities: list[CapabilityDescriptor] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def reject_unavailable_capabilities(self) -> ProviderCapabilitiesResult:
        if self.status == ProviderStatus.UNAVAILABLE and self.capabilities:
            raise ValueError("unavailable capability result cannot contain descriptors")
        return self


class InspectRequest(StrictModel):
    capability_id: str
    resource_ref: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class InspectResult(StrictModel):
    status: ProviderStatus
    provider_version: str = Field(min_length=1)
    value: dict[str, Any] | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def reject_unavailable_value(self) -> InspectResult:
        if self.status == ProviderStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("unavailable inspect result cannot contain a value")
        return self


class InvokeRequest(StrictModel):
    capability_id: str
    route_ref: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    authorization_ref: str | None = None


class InvokeResult(StrictModel):
    status: ProviderStatus
    provider_version: str = Field(min_length=1)
    value: dict[str, Any] | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def reject_unavailable_value(self) -> InvokeResult:
        if self.status == ProviderStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("unavailable invoke result cannot contain a value")
        return self


class ShadowResolutionArtifact(StrictModel):
    schema_version: Literal["robot-capability-resolution-shadow/v1"] = (
        "robot-capability-resolution-shadow/v1"
    )
    profile_id: str
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_manifest_sha256: list[str] = Field(default_factory=list)
    resolutions: list[CapabilityResolution] = Field(default_factory=list)
    discovery_evidence: list[str] = Field(default_factory=list)
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def require_deterministic_order(self) -> ShadowResolutionArtifact:
        keys = [(item.operation, item.capability_id) for item in self.resolutions]
        if keys != sorted(keys):
            raise ValueError("shadow resolutions must use deterministic operation order")
        return self


def _digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
