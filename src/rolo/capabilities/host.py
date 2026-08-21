from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.capabilities.models import (
    CapabilityAccess,
    CapabilityAvailability,
    CapabilityDescriptor,
    InspectRequest,
    InspectResult,
    InvokeRequest,
    InvokeResult,
    ProviderCapabilitiesResult,
    ProviderManifest,
    ProviderStatus,
)
from rolo.capabilities.provider import CapabilityProvider


class ProviderRegistrationStatus(str, Enum):
    REGISTERED = "REGISTERED"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED = "REJECTED"


class ProviderRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-provider-registration/v1"] = (
        "robot-provider-registration/v1"
    )
    provider_id: str = Field(min_length=1)
    provider_version: str | None = None
    status: ProviderRegistrationStatus
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    capability_count: int = Field(default=0, ge=0)
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None


class ProviderHostSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-provider-host-snapshot/v1"] = (
        "robot-provider-host-snapshot/v1"
    )
    registrations: list[ProviderRegistration] = Field(default_factory=list)
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def require_deterministic_active_registrations(self) -> ProviderHostSnapshot:
        provider_ids = [item.provider_id for item in self.registrations]
        if provider_ids != sorted(provider_ids) or len(provider_ids) != len(set(provider_ids)):
            raise ValueError("provider host registrations must use unique sorted provider IDs")
        if any(
            item.status != ProviderRegistrationStatus.REGISTERED
            for item in self.registrations
        ):
            raise ValueError("provider host snapshot can contain only active registrations")
        return self


class CapabilityWriteAuthorizer(Protocol):
    """Bridge to Runtime policy; absence must deny every write capability."""

    def authorize(
        self,
        manifest: ProviderManifest,
        descriptor: CapabilityDescriptor,
        request: InvokeRequest,
    ) -> None: ...


@dataclass(frozen=True)
class _RegisteredProvider:
    provider: CapabilityProvider
    manifest: ProviderManifest
    descriptors: dict[str, CapabilityDescriptor]
    registration: ProviderRegistration


T = TypeVar("T")


class ProviderHost:
    """Provider-neutral extension host disconnected from the active release path."""

    def __init__(self, *, timeout_s: float = 5.0, max_workers: int = 4) -> None:
        if timeout_s <= 0:
            raise ValueError("provider timeout must be positive")
        if max_workers < 1:
            raise ValueError("provider host requires at least one worker")
        self.timeout_s = timeout_s
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="rolo-capability-provider",
        )
        self._providers: dict[str, _RegisteredProvider] = {}
        self._pending: set[Future[Any]] = set()
        self._closed = False
        self._lock = RLock()

    def __enter__(self) -> ProviderHost:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            pending = list(self._pending)
        for future in pending:
            future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def register(self, provider: CapabilityProvider) -> ProviderRegistration:
        self._require_open()
        try:
            probe = self._call(provider.probe, phase="probe")
        except Exception as exc:
            return self._failed_registration("unidentified", exc, phase="probe")
        if probe.status != ProviderStatus.AVAILABLE or probe.manifest is None:
            return ProviderRegistration(
                provider_id="unidentified",
                provider_version=probe.provider_version,
                status=ProviderRegistrationStatus.UNAVAILABLE,
                evidence=_evidence("unidentified", "probe", probe.evidence),
                reason=probe.reason or "provider probe reported unavailable",
            )
        manifest = probe.manifest
        if manifest.status != ProviderStatus.AVAILABLE:
            return ProviderRegistration(
                provider_id=manifest.provider_id,
                provider_version=manifest.provider_version,
                status=ProviderRegistrationStatus.UNAVAILABLE,
                evidence=_evidence(manifest.provider_id, "probe", probe.evidence),
                reason="provider manifest reported unavailable",
            )
        with self._lock:
            if manifest.provider_id in self._providers:
                return ProviderRegistration(
                    provider_id=manifest.provider_id,
                    provider_version=manifest.provider_version,
                    status=ProviderRegistrationStatus.REJECTED,
                    evidence=_evidence(manifest.provider_id, "registration", probe.evidence),
                    reason="provider_id is already registered",
                )
        try:
            capabilities = self._call(provider.capabilities, phase="capabilities")
            descriptors = _validate_capabilities(manifest, capabilities)
        except Exception as exc:
            return self._failed_registration(
                manifest.provider_id,
                exc,
                phase="capabilities",
                provider_version=manifest.provider_version,
            )
        registration = ProviderRegistration(
            provider_id=manifest.provider_id,
            provider_version=manifest.provider_version,
            status=ProviderRegistrationStatus.REGISTERED,
            manifest_sha256=manifest.core_digest(),
            capability_count=len(descriptors),
            evidence=_evidence(
                manifest.provider_id,
                "registration",
                [*probe.evidence, *manifest.evidence, *capabilities.evidence],
            ),
        )
        with self._lock:
            if manifest.provider_id in self._providers:
                return registration.model_copy(
                    update={
                        "status": ProviderRegistrationStatus.REJECTED,
                        "reason": "provider_id was registered concurrently",
                    }
                )
            self._providers[manifest.provider_id] = _RegisteredProvider(
                provider=provider,
                manifest=manifest,
                descriptors=descriptors,
                registration=registration,
            )
        return registration

    def unregister(self, provider_id: str) -> bool:
        with self._lock:
            return self._providers.pop(provider_id, None) is not None

    def manifests(self) -> list[ProviderManifest]:
        with self._lock:
            return [self._providers[key].manifest for key in sorted(self._providers)]

    def descriptors(self, provider_id: str) -> list[CapabilityDescriptor]:
        """Return a deterministic copy of the registered provider contract surface."""
        registered = self._registered(provider_id)
        if registered is None:
            return []
        return [
            registered.descriptors[key].model_copy(deep=True)
            for key in sorted(registered.descriptors)
        ]

    def snapshot(self) -> ProviderHostSnapshot:
        with self._lock:
            registrations = [
                self._providers[key].registration for key in sorted(self._providers)
            ]
        return ProviderHostSnapshot(registrations=registrations, influences_release=False)

    def inspect(self, provider_id: str, request: InspectRequest) -> InspectResult:
        registered = self._registered(provider_id)
        if registered is None:
            return InspectResult(
                status=ProviderStatus.UNAVAILABLE,
                provider_version="unknown",
                evidence=_evidence(provider_id, "inspect", []),
                reason="provider is not registered",
            )
        descriptor = registered.descriptors.get(request.capability_id)
        if descriptor is None:
            return _inspect_unavailable(
                registered.manifest,
                "capability is not declared by the registered provider",
                phase="inspect",
            )
        try:
            result = self._call(
                lambda: registered.provider.inspect(request),
                phase="inspect",
            )
            _validate_result_version(registered.manifest, result.provider_version)
        except Exception as exc:
            return _inspect_unavailable(
                registered.manifest,
                _failure_reason(exc, "inspect"),
                phase="inspect",
            )
        return result.model_copy(
            update={
                "evidence": _evidence(provider_id, "inspect", result.evidence),
            }
        )

    def invoke(
        self,
        provider_id: str,
        request: InvokeRequest,
        *,
        authorizer: CapabilityWriteAuthorizer | None = None,
    ) -> InvokeResult:
        registered = self._registered(provider_id)
        if registered is None:
            return InvokeResult(
                status=ProviderStatus.UNAVAILABLE,
                provider_version="unknown",
                evidence=_evidence(provider_id, "invoke", []),
                reason="provider is not registered",
            )
        descriptor = registered.descriptors.get(request.capability_id)
        if descriptor is None:
            return _invoke_unavailable(
                registered.manifest,
                "capability is not declared by the registered provider",
                phase="invoke",
            )
        route = next(
            (
                item
                for item in registered.manifest.capabilities
                if item.capability_id == request.capability_id
                and item.capability_version == descriptor.version
                and item.route_ref == request.route_ref
            ),
            None,
        )
        if route is None:
            return _invoke_unavailable(
                registered.manifest,
                "route_ref is not declared by the registered provider",
                phase="invoke",
            )
        if descriptor.access == CapabilityAccess.WRITE:
            if authorizer is None:
                return _invoke_unavailable(
                    registered.manifest,
                    "write capability requires Runtime policy authorization",
                    phase="policy",
                )
            try:
                authorizer.authorize(registered.manifest, descriptor, request)
            except Exception as exc:
                return _invoke_unavailable(
                    registered.manifest,
                    f"Runtime policy denied write capability: {type(exc).__name__}",
                    phase="policy",
                )
        try:
            result = self._call(
                lambda: registered.provider.invoke(request),
                phase="invoke",
            )
            _validate_result_version(registered.manifest, result.provider_version)
        except Exception as exc:
            return _invoke_unavailable(
                registered.manifest,
                _failure_reason(exc, "invoke"),
                phase="invoke",
            )
        return result.model_copy(
            update={
                "evidence": _evidence(provider_id, "invoke", result.evidence),
            }
        )

    def _registered(self, provider_id: str) -> _RegisteredProvider | None:
        self._require_open()
        with self._lock:
            return self._providers.get(provider_id)

    def _call(self, operation: Any, *, phase: str) -> T:
        self._require_open()
        future = self._executor.submit(operation)
        with self._lock:
            self._pending.add(future)
        try:
            return future.result(timeout=self.timeout_s)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"provider {phase} timed out") from None
        finally:
            with self._lock:
                self._pending.discard(future)

    def _require_open(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("provider host is closed")

    @staticmethod
    def _failed_registration(
        provider_id: str,
        exc: Exception,
        *,
        phase: str,
        provider_version: str | None = None,
    ) -> ProviderRegistration:
        return ProviderRegistration(
            provider_id=provider_id,
            provider_version=provider_version,
            status=ProviderRegistrationStatus.REJECTED,
            evidence=_evidence(provider_id, phase, []),
            reason=_failure_reason(exc, phase),
        )


def _validate_capabilities(
    manifest: ProviderManifest,
    result: ProviderCapabilitiesResult,
) -> dict[str, CapabilityDescriptor]:
    _validate_result_version(manifest, result.provider_version)
    if result.status != ProviderStatus.AVAILABLE:
        raise ValueError("provider capabilities reported unavailable")
    descriptors = {item.capability_id: item for item in result.capabilities}
    if len(descriptors) != len(result.capabilities):
        raise ValueError("provider returned duplicate capability descriptors")
    declared = {
        (item.capability_id, item.capability_version)
        for item in manifest.capabilities
        if item.availability == CapabilityAvailability.AVAILABLE
    }
    for descriptor in result.capabilities:
        if (descriptor.capability_id, descriptor.version) not in declared:
            raise ValueError("capability descriptor is not declared by provider manifest")
        if descriptor.semantic_layer not in manifest.semantic_layers:
            raise ValueError("capability descriptor semantic layer is outside provider manifest")
    return descriptors


def _validate_result_version(manifest: ProviderManifest, provider_version: str) -> None:
    if provider_version != manifest.provider_version:
        raise ValueError("provider result version does not match registered manifest")


def _evidence(provider_id: str, phase: str, values: list[str]) -> list[str]:
    normalized = {
        value.strip()[:512]
        for value in values
        if isinstance(value, str) and value.strip()
    }
    normalized.update({f"provider:{provider_id}", f"provider-phase:{phase}"})
    return sorted(normalized)[:64]


def _failure_reason(exc: Exception, phase: str) -> str:
    if isinstance(exc, TimeoutError):
        return f"provider {phase} timed out"
    return f"provider {phase} failed: {type(exc).__name__}"


def _inspect_unavailable(
    manifest: ProviderManifest,
    reason: str,
    *,
    phase: str,
) -> InspectResult:
    return InspectResult(
        status=ProviderStatus.UNAVAILABLE,
        provider_version=manifest.provider_version,
        evidence=_evidence(manifest.provider_id, phase, []),
        reason=reason,
    )


def _invoke_unavailable(
    manifest: ProviderManifest,
    reason: str,
    *,
    phase: str,
) -> InvokeResult:
    return InvokeResult(
        status=ProviderStatus.UNAVAILABLE,
        provider_version=manifest.provider_version,
        evidence=_evidence(manifest.provider_id, phase, []),
        reason=reason,
    )
