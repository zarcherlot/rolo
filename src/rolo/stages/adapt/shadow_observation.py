from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.capabilities import (
    CapabilityResolutionShadow,
    CapabilityResolver,
    OperationCapabilityRequirement,
    PlatformFact,
    PlatformProfile,
    ProviderManifest,
    ResolutionStatus,
)
from rolo.capabilities import SemanticLayer as CapabilitySemanticLayer
from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.operation_governance import (
    SemanticLayer as GovernanceSemanticLayer,
)
from rolo.stages.adapt.operation_governance import load_operation_dispositions
from rolo.stages.adapt.workset import TargetOperationSlice
from rolo.stages.artifact_paths import ArtifactLayout


class TargetOperationSliceShadowReport(BaseModel):
    """Comparison only: it must never replace current eligibility or release inputs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-operation-slice-shadow/v1"] = (
        "robot-target-operation-slice-shadow/v1"
    )
    robot_id: str
    discovery_id: str
    slice_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_eligible_operations: list[str] = Field(default_factory=list)
    shadow_target_adapter_operations: list[str] = Field(default_factory=list)
    eligible_not_in_shadow: list[str] = Field(default_factory=list)
    shadow_not_in_eligible: list[str] = Field(default_factory=list)
    influences_release: Literal[False] = False


class CapabilityShadowRunObservation(BaseModel):
    """One immutable capability-resolution shadow artifact summarized for review."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    artifact_ref: str
    profile_id: str
    resolution_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)


class CapabilityShadowStabilityReport(BaseModel):
    """Release-neutral aggregate for P2 capability resolver shadow runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-capability-resolution-stability/v1"] = (
        "robot-capability-resolution-stability/v1"
    )
    robot_id: str
    max_runs: int = Field(gt=0)
    observation_count: int = Field(ge=0)
    resolution_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    ambiguous_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    recommendation: Literal["INSUFFICIENT_DATA", "HOLD", "READY_FOR_REVIEW"]
    recommendation_reasons: list[str] = Field(default_factory=list)
    observations: list[CapabilityShadowRunObservation] = Field(default_factory=list)
    influences_release: Literal[False] = False


def build_platform_profile(report: DiscoveryReport) -> PlatformProfile:
    """Derive bounded, provider-neutral facts without platform-specific probing."""
    platform = report.platform if isinstance(report.platform, dict) else {}
    os_value = platform.get("os")
    os_fact = PlatformFact(family=str(os_value)) if os_value not in (None, "") else None
    middleware = _platform_facts(platform.get("middleware"))
    transports = _strings(platform.get("transports"))
    expected = report.capability_manifest.get("expected_profile", {})
    if isinstance(expected, dict):
        transports.extend(_strings(expected.get("transports")))
        features_value = expected.get("features", {})
    else:
        features_value = {}
    if isinstance(features_value, dict):
        features = sorted(str(key) for key, value in features_value.items() if value)
    else:
        features = sorted(_strings(features_value))
    return PlatformProfile(
        profile_id=f"{report.robot_id}:{report.discovery_id}",
        os=os_fact,
        middleware=middleware,
        available_transports=sorted(set(transports)),
        features=features,
        extensions={
            "source_discovery_id": report.discovery_id,
            "source_platform_keys": sorted(str(key) for key in platform),
        },
    )


def build_capability_requirements(
    target_slice: TargetOperationSlice,
) -> list[OperationCapabilityRequirement]:
    ledger = load_operation_dispositions().by_operation()
    operations = sorted(
        set(target_slice.primary_operations) | set(target_slice.dependency_operations)
    )
    requirements: list[OperationCapabilityRequirement] = []
    for operation in operations:
        disposition = ledger[operation]
        if (
            not disposition.future_capability
            or disposition.semantic_layer == GovernanceSemanticLayer.PRODUCT_CONTROL
        ):
            continue
        requirements.append(
            OperationCapabilityRequirement(
                operation=operation,
                capability_id=disposition.future_capability,
                capability_version="1.0",
                semantic_layer=CapabilitySemanticLayer(disposition.semantic_layer.value),
            )
        )
    return requirements


def build_slice_shadow_report(
    target_slice: TargetOperationSlice,
    authoritative_eligible_operations: Sequence[str],
) -> TargetOperationSliceShadowReport:
    eligible = set(authoritative_eligible_operations)
    shadow = set(target_slice.target_adapter_operations)
    return TargetOperationSliceShadowReport(
        robot_id=target_slice.robot_id,
        discovery_id=target_slice.discovery_id,
        slice_sha256=target_slice.slice_sha256,
        authoritative_eligible_operations=sorted(eligible),
        shadow_target_adapter_operations=sorted(shadow),
        eligible_not_in_shadow=sorted(eligible - shadow),
        shadow_not_in_eligible=sorted(shadow - eligible),
        influences_release=False,
    )


def build_capability_shadow(
    report: DiscoveryReport,
    target_slice: TargetOperationSlice,
    manifests: Sequence[ProviderManifest] = (),
) -> tuple[PlatformProfile, CapabilityResolutionShadow]:
    profile = build_platform_profile(report)
    evidence = [f"discovery:{report.discovery_id}"]
    shadow = CapabilityResolver().shadow_artifact(
        build_capability_requirements(target_slice),
        profile,
        manifests,
        discovery_evidence=evidence,
    )
    return profile, shadow


def resolution_status_counts(shadow: CapabilityResolutionShadow) -> dict[str, int]:
    return {
        status.value: sum(item.status == status for item in shadow.resolutions)
        for status in ResolutionStatus
    }


def build_capability_shadow_stability_report(
    artifact_root: Path,
    robot_id: str,
    *,
    max_runs: int = 50,
) -> CapabilityShadowStabilityReport:
    """Aggregate existing Adapt capability-shadow artifacts without changing authority."""

    if max_runs < 1:
        raise ValueError("max_runs must be positive")
    layout = ArtifactLayout(artifact_root)
    runs_root = layout.stage_latest("adapt", robot_id).parent / "runs"
    run_paths = (
        sorted(
            (path for path in runs_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        if runs_root.is_dir()
        else []
    )
    observations: list[CapabilityShadowRunObservation] = []
    for run_path in run_paths:
        shadow_path = run_path / "capability-resolution-shadow.json"
        if not shadow_path.is_file():
            continue
        shadow = CapabilityResolutionShadow.model_validate_json(
            shadow_path.read_text(encoding="utf-8")
        )
        if not shadow.profile_id.startswith(f"{robot_id}:"):
            raise ValueError(f"capability shadow robot mismatch in run {run_path.name}")
        counts = resolution_status_counts(shadow)
        observations.append(
            CapabilityShadowRunObservation(
                run_id=run_path.name,
                artifact_ref=layout.ref(shadow_path),
                profile_id=shadow.profile_id,
                resolution_count=len(shadow.resolutions),
                resolved_count=counts[ResolutionStatus.RESOLVED.value],
                unavailable_count=counts[ResolutionStatus.UNAVAILABLE.value],
                ambiguous_count=counts[ResolutionStatus.AMBIGUOUS.value],
            )
        )
        if len(observations) >= max_runs:
            break
    status_counts = Counter(
        status
        for item in observations
        for status in (
            ResolutionStatus.RESOLVED.value,
            ResolutionStatus.UNAVAILABLE.value,
            ResolutionStatus.AMBIGUOUS.value,
        )
        for _ in range(getattr(item, f"{status.lower()}_count"))
    )
    normalized_counts = {
        status.value: status_counts.get(status.value, 0) for status in ResolutionStatus
    }
    ambiguous = normalized_counts[ResolutionStatus.AMBIGUOUS.value]
    reasons: list[str] = []
    if not observations:
        recommendation: Literal["INSUFFICIENT_DATA", "HOLD", "READY_FOR_REVIEW"] = (
            "INSUFFICIENT_DATA"
        )
        reasons.append("NO_CAPABILITY_SHADOW_RUNS")
    elif ambiguous:
        recommendation = "HOLD"
        reasons.append("AMBIGUOUS_CAPABILITY_RESOLUTION_OBSERVED")
    else:
        recommendation = "READY_FOR_REVIEW"
        reasons.append("MANUAL_REVIEW_REQUIRED")
    return CapabilityShadowStabilityReport(
        robot_id=robot_id,
        max_runs=max_runs,
        observation_count=len(observations),
        resolution_count=sum(item.resolution_count for item in observations),
        status_counts=normalized_counts,
        ambiguous_count=ambiguous,
        unavailable_count=normalized_counts[ResolutionStatus.UNAVAILABLE.value],
        resolved_count=normalized_counts[ResolutionStatus.RESOLVED.value],
        recommendation=recommendation,
        recommendation_reasons=reasons,
        observations=observations,
    )


def _strings(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    return []


def _platform_facts(value: Any) -> list[PlatformFact]:
    values = value if isinstance(value, list) else ([value] if value not in (None, "") else [])
    facts: list[PlatformFact] = []
    for item in values:
        if isinstance(item, str) and item.strip():
            facts.append(PlatformFact(family=item.strip()))
        elif isinstance(item, dict) and item.get("family"):
            facts.append(
                PlatformFact(
                    family=str(item["family"]),
                    version=str(item["version"]) if item.get("version") is not None else None,
                    features=sorted(_strings(item.get("features"))),
                )
            )
    return sorted(facts, key=lambda item: (item.family, item.version or ""))
