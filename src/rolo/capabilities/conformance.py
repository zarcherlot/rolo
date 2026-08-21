from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.capabilities.host import (
    ProviderHost,
    ProviderRegistration,
    ProviderRegistrationStatus,
)
from rolo.capabilities.models import (
    CapabilityAccess,
    CapabilityDescriptor,
    InspectRequest,
    InvokeRequest,
    ProviderManifest,
    ProviderStatus,
)
from rolo.capabilities.provider import CapabilityProvider


class ProviderConformanceStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class ProviderConformanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    status: ProviderConformanceStatus
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None


class ProviderConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-provider-conformance-report/v1"] = (
        "robot-provider-conformance-report/v1"
    )
    provider_id: str = Field(min_length=1)
    provider_version: str | None = None
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    registration: ProviderRegistration | None = None
    checks: list[ProviderConformanceCheck] = Field(min_length=1)
    conforms: bool
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def require_deterministic_consistent_checks(self) -> ProviderConformanceReport:
        names = [item.name for item in self.checks]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("provider conformance checks must use unique sorted names")
        expected = all(item.status == ProviderConformanceStatus.PASSED for item in self.checks)
        if self.conforms != expected:
            raise ValueError("provider conformance summary does not match check results")
        return self


def run_provider_conformance(
    provider: object,
    *,
    timeout_s: float = 5.0,
) -> ProviderConformanceReport:
    """Run safe structural checks; never authorize or execute a provider write."""
    checks: list[ProviderConformanceCheck] = []
    if not isinstance(provider, CapabilityProvider):
        checks.append(_failed("spi", "object does not implement CapabilityProvider"))
        return _report("unidentified", None, None, None, checks)
    checks.append(_passed("spi", ["CapabilityProvider"]))

    with ProviderHost(timeout_s=timeout_s) as host:
        registration = host.register(provider)
        if registration.status != ProviderRegistrationStatus.REGISTERED:
            checks.append(
                _failed(
                    "registration",
                    registration.reason or "provider registration failed",
                    registration.evidence,
                )
            )
            return _report(
                registration.provider_id,
                registration.provider_version,
                registration.manifest_sha256,
                registration,
                checks,
            )
        checks.append(_passed("registration", registration.evidence))
        manifest = host.manifests()[0]
        descriptors = host.descriptors(manifest.provider_id)
        checks.extend(
            [
                _descriptor_check(manifest, descriptors),
                _evidence_check(registration),
                _extension_digest_check(manifest, descriptors),
                _missing_capability_check(host, manifest),
                _snapshot_check(host, manifest),
                _write_policy_check(host, manifest, descriptors),
            ]
        )
        return _report(
            manifest.provider_id,
            manifest.provider_version,
            manifest.core_digest(),
            registration,
            checks,
        )


def _descriptor_check(
    manifest: ProviderManifest,
    descriptors: list[CapabilityDescriptor],
) -> ProviderConformanceCheck:
    declared = {
        (item.capability_id, item.capability_version) for item in manifest.capabilities
    }
    actual = {(item.capability_id, item.version) for item in descriptors}
    if not actual.issubset(declared):
        return _failed("descriptor_contracts", "descriptor is absent from manifest")
    return _passed(
        "descriptor_contracts",
        [f"descriptor-count:{len(descriptors)}"],
    )


def _evidence_check(registration: ProviderRegistration) -> ProviderConformanceCheck:
    evidence = registration.evidence
    if evidence != sorted(set(evidence)) or any(
        not item or item != item.strip() or len(item) > 512 for item in evidence
    ):
        return _failed("evidence_normalization", "registration evidence is not normalized")
    return _passed("evidence_normalization", evidence)


def _extension_digest_check(
    manifest: ProviderManifest,
    descriptors: list[CapabilityDescriptor],
) -> ProviderConformanceCheck:
    extended_manifest = manifest.model_copy(deep=True)
    extended_manifest.extensions["conformance-unknown-extension"] = {"accepted": True}
    manifest_stable = extended_manifest.core_digest() == manifest.core_digest()
    descriptors_stable = all(
        descriptor.model_copy(
            update={"extensions": {"conformance-unknown-extension": True}}
        ).core_digest()
        == descriptor.core_digest()
        for descriptor in descriptors
    )
    if not manifest_stable or not descriptors_stable:
        return _failed("extension_digest", "unknown extensions changed a core digest")
    return _passed("extension_digest", ["unknown-extensions:ignored-by-core-digest"])


def _missing_capability_check(
    host: ProviderHost,
    manifest: ProviderManifest,
) -> ProviderConformanceCheck:
    result = host.inspect(
        manifest.provider_id,
        InspectRequest(capability_id="conformance.missing-capability"),
    )
    if result.status != ProviderStatus.UNAVAILABLE:
        return _failed("missing_capability", "missing capability was not UNAVAILABLE")
    return _passed("missing_capability", result.evidence)


def _snapshot_check(
    host: ProviderHost,
    manifest: ProviderManifest,
) -> ProviderConformanceCheck:
    snapshot = host.snapshot()
    if snapshot.influences_release or [
        item.provider_id for item in snapshot.registrations
    ] != [manifest.provider_id]:
        return _failed("release_neutrality", "provider snapshot affected release authority")
    return _passed("release_neutrality", ["influences-release:false"])


def _write_policy_check(
    host: ProviderHost,
    manifest: ProviderManifest,
    descriptors: list[CapabilityDescriptor],
) -> ProviderConformanceCheck:
    writes = [item for item in descriptors if item.access == CapabilityAccess.WRITE]
    for descriptor in writes:
        route = next(
            (
                item.route_ref
                for item in manifest.capabilities
                if item.capability_id == descriptor.capability_id
                and item.capability_version == descriptor.version
            ),
            None,
        )
        if route is None:
            return _failed("write_policy", "write capability has no declared route")
        result = host.invoke(
            manifest.provider_id,
            InvokeRequest(capability_id=descriptor.capability_id, route_ref=route),
        )
        if result.status != ProviderStatus.UNAVAILABLE or "Runtime policy" not in (
            result.reason or ""
        ):
            return _failed("write_policy", "write capability did not fail closed")
    return _passed("write_policy", [f"write-capability-count:{len(writes)}"])


def _report(
    provider_id: str,
    provider_version: str | None,
    manifest_sha256: str | None,
    registration: ProviderRegistration | None,
    checks: list[ProviderConformanceCheck],
) -> ProviderConformanceReport:
    ordered = sorted(checks, key=lambda item: item.name)
    return ProviderConformanceReport(
        provider_id=provider_id,
        provider_version=provider_version,
        manifest_sha256=manifest_sha256,
        registration=registration,
        checks=ordered,
        conforms=all(item.status == ProviderConformanceStatus.PASSED for item in ordered),
        influences_release=False,
    )


def _passed(name: str, evidence: list[str]) -> ProviderConformanceCheck:
    return ProviderConformanceCheck(
        name=name,
        status=ProviderConformanceStatus.PASSED,
        evidence=sorted(set(evidence)),
    )


def _failed(
    name: str,
    reason: str,
    evidence: list[str] | None = None,
) -> ProviderConformanceCheck:
    return ProviderConformanceCheck(
        name=name,
        status=ProviderConformanceStatus.FAILED,
        evidence=sorted(set(evidence or [])),
        reason=reason,
    )
