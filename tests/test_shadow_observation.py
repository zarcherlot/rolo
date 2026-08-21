from __future__ import annotations

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.shadow_observation import (
    build_capability_requirements,
    build_capability_shadow,
    build_platform_profile,
    build_slice_shadow_report,
    resolution_status_counts,
)
from rolo.stages.adapt.workset import TargetOperationSlice


def report() -> DiscoveryReport:
    return DiscoveryReport(
        discovery_id="discovery-1",
        robot_id="robot-1",
        status="SUCCEEDED",
        platform={
            "os": "opaque-os",
            "middleware": [{"family": "opaque-mw", "version": "1"}],
            "transports": ["opaque-transport"],
        },
        capability_manifest={
            "expected_profile": {"features": {"workloads": True, "unused": False}}
        },
        probes={},
    )


def target_slice() -> TargetOperationSlice:
    return TargetOperationSlice(
        robot_id="robot-1",
        discovery_id="discovery-1",
        registry_sha256="1" * 64,
        slice_sha256="2" * 64,
        primary_operations=["linux.process.list", "tool.catalog"],
        target_adapter_operations=["linux.process.list"],
        builtin_operations=["tool.catalog"],
    )


def test_platform_profile_uses_only_provider_neutral_facts() -> None:
    profile = build_platform_profile(report())

    assert profile.os is not None
    assert profile.os.family == "opaque-os"
    assert [item.family for item in profile.middleware] == ["opaque-mw"]
    assert profile.available_transports == ["opaque-transport"]
    assert profile.features == ["workloads"]
    assert profile.extensions["source_discovery_id"] == "discovery-1"


def test_capability_shadow_allows_an_empty_provider_set() -> None:
    requirements = build_capability_requirements(target_slice())
    profile, shadow = build_capability_shadow(report(), target_slice())

    assert [item.operation for item in requirements] == ["linux.process.list"]
    assert shadow.profile_id == profile.profile_id
    assert shadow.provider_manifest_sha256 == []
    assert shadow.influences_release is False
    assert resolution_status_counts(shadow) == {
        "RESOLVED": 0,
        "UNAVAILABLE": 1,
        "AMBIGUOUS": 0,
    }


def test_slice_shadow_reports_differences_without_changing_authority() -> None:
    shadow = build_slice_shadow_report(
        target_slice(), ["linux.process.list", "app.teleop.velocity"]
    )

    assert shadow.eligible_not_in_shadow == ["app.teleop.velocity"]
    assert shadow.shadow_not_in_eligible == []
    assert shadow.influences_release is False
