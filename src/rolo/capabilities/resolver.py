from __future__ import annotations

from collections.abc import Iterable, Sequence

from rolo.capabilities.models import (
    CapabilityAvailability,
    CapabilityResolution,
    OperationCapabilityRequirement,
    PlatformProfile,
    ProviderManifest,
    ProviderStatus,
    ResolutionStatus,
    ShadowResolutionArtifact,
)


class CapabilityResolver:
    """Pure, deterministic shadow resolver for provider-neutral capabilities."""

    def resolve(
        self,
        requirement: OperationCapabilityRequirement,
        profile: PlatformProfile,
        manifests: Sequence[ProviderManifest],
        *,
        discovery_evidence: Iterable[str] = (),
    ) -> CapabilityResolution:
        candidates: list[tuple[int, str, str, tuple[str, ...]]] = []
        feature_set = profile.feature_set()
        transports = frozenset(profile.available_transports)
        provider_ids = [item.provider_id for item in manifests]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("capability resolution requires unique provider IDs")

        for manifest in sorted(manifests, key=lambda item: item.provider_id):
            if manifest.status != ProviderStatus.AVAILABLE:
                continue
            if requirement.semantic_layer not in manifest.semantic_layers:
                continue
            if transports and manifest.transport.kind not in transports:
                continue
            for capability in manifest.capabilities:
                if capability.capability_id != requirement.capability_id:
                    continue
                if capability.capability_version != requirement.capability_version:
                    continue
                if capability.availability != CapabilityAvailability.AVAILABLE:
                    continue
                if not set(capability.required_features).issubset(feature_set):
                    continue
                candidates.append(
                    (
                        capability.priority,
                        manifest.provider_id,
                        capability.route_ref or "",
                        tuple(sorted({*manifest.evidence, *capability.evidence})),
                    )
                )

        base_evidence = tuple(sorted(set(discovery_evidence)))
        if not candidates:
            return CapabilityResolution(
                status=ResolutionStatus.UNAVAILABLE,
                operation=requirement.operation,
                capability_id=requirement.capability_id,
                capability_version=requirement.capability_version,
                evidence=list(base_evidence),
                reason="no compatible provider capability",
            )

        highest_priority = max(item[0] for item in candidates)
        finalists = [item for item in candidates if item[0] == highest_priority]
        if len(finalists) > 1:
            candidate_evidence = {
                evidence
                for _, _, _, provider_evidence in finalists
                for evidence in provider_evidence
            }
            return CapabilityResolution(
                status=ResolutionStatus.AMBIGUOUS,
                operation=requirement.operation,
                capability_id=requirement.capability_id,
                capability_version=requirement.capability_version,
                candidate_provider_ids=sorted(item[1] for item in finalists),
                evidence=sorted({*base_evidence, *candidate_evidence}),
                reason="multiple compatible providers have equal priority",
            )

        _, provider_id, route_ref, provider_evidence = finalists[0]
        return CapabilityResolution(
            status=ResolutionStatus.RESOLVED,
            operation=requirement.operation,
            capability_id=requirement.capability_id,
            capability_version=requirement.capability_version,
            provider_id=provider_id,
            route_ref=route_ref,
            candidate_provider_ids=[provider_id],
            evidence=sorted({*base_evidence, *provider_evidence}),
        )

    def shadow_artifact(
        self,
        requirements: Sequence[OperationCapabilityRequirement],
        profile: PlatformProfile,
        manifests: Sequence[ProviderManifest],
        *,
        discovery_evidence: Iterable[str] = (),
    ) -> ShadowResolutionArtifact:
        evidence = sorted(set(discovery_evidence))
        resolutions = [
            self.resolve(item, profile, manifests, discovery_evidence=evidence)
            for item in sorted(
                requirements,
                key=lambda value: (value.operation, value.capability_id),
            )
        ]
        return ShadowResolutionArtifact(
            profile_id=profile.profile_id,
            profile_sha256=profile.core_digest(),
            provider_manifest_sha256=sorted(item.core_digest() for item in manifests),
            resolutions=resolutions,
            discovery_evidence=evidence,
            influences_release=False,
        )
