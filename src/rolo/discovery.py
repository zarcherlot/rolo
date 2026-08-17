"""Compatibility imports for Stage 1 discovery APIs."""

from rolo.stages.deploy.discovery import (
    ApplicationProbe,
    DiscoveryService,
    HardwareProbe,
    LinuxProbe,
    RosProbe,
    detect_compute_platform,
    load_latest_report,
)

__all__ = [
    "ApplicationProbe",
    "DiscoveryService",
    "HardwareProbe",
    "LinuxProbe",
    "RosProbe",
    "detect_compute_platform",
    "load_latest_report",
]
