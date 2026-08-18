"""Single status policy for Adapt discovery."""

from __future__ import annotations

from collections.abc import Iterable

from rolo.core.models import DiscoveryStatus


def aggregate_probe_status(statuses: Iterable[DiscoveryStatus]) -> DiscoveryStatus:
    observed = set(statuses)
    if DiscoveryStatus.FAILED in observed:
        return DiscoveryStatus.FAILED
    if observed == {DiscoveryStatus.SUCCEEDED}:
        return DiscoveryStatus.SUCCEEDED
    return DiscoveryStatus.PARTIAL


def derive_discovery_status(
    probe_status: DiscoveryStatus,
    *,
    partial_coverage: bool = False,
    partial_dependencies: bool = False,
    has_executables: bool = True,
) -> DiscoveryStatus:
    """Apply all post-probe degradation rules without allowing promotion."""
    if probe_status == DiscoveryStatus.FAILED:
        return probe_status
    if (
        probe_status == DiscoveryStatus.PARTIAL
        or partial_coverage
        or partial_dependencies
        or not has_executables
    ):
        return DiscoveryStatus.PARTIAL
    return DiscoveryStatus.SUCCEEDED
