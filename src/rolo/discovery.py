"""Compatibility imports for Stage 1 discovery APIs."""

from rolo.stages.build.discovery import (
    ApplicationProbe,
    DiscoveryService,
    HardwareProbe,
    LinuxProbe,
    RosProbe,
    detect_compute_platform,
    load_latest_report,
    load_report,
)
from rolo.stages.build.software_inventory import (
    CollectorStatus,
    DpkgPackageCollector,
    PackageCollectorState,
    PackageInventoryIndex,
    PackageRecord,
    SoftwareInventoryPolicy,
    SoftwareSummary,
)

__all__ = [
    "ApplicationProbe",
    "DiscoveryService",
    "HardwareProbe",
    "LinuxProbe",
    "RosProbe",
    "detect_compute_platform",
    "load_latest_report",
    "load_report",
    "CollectorStatus",
    "DpkgPackageCollector",
    "PackageCollectorState",
    "PackageInventoryIndex",
    "PackageRecord",
    "SoftwareInventoryPolicy",
    "SoftwareSummary",
]
