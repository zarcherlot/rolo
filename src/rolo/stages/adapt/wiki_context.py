"""Shared evidence classification for deterministic and Agent-authored Wiki content."""

from __future__ import annotations

from typing import Any

from rolo.core.models import DiscoveryReport, DiscoveryStatus
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport

_ROS_RUNTIME_KEYS = (
    "ros_distro",
    "rmw",
    "nodes",
    "topics",
    "services",
    "actions",
)
_ROS_DEPENDENCY_NAMES = {
    "ament_cmake",
    "catkin",
    "rclcpp",
    "rclpy",
    "roscpp",
    "rospy",
}


def _has_values(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_values(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_values(item) for item in value)
    return value not in (None, "", False)


def ros_evidence_relevant(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
) -> bool:
    """Return whether this discovery contains target or static evidence that ROS matters.

    An unavailable ROS probe is not itself ROS evidence. This keeps a non-ROS target from
    being documented as an incomplete ROS deployment while retaining ROS details whenever
    the target, source tree, executable analysis, or candidate routes actually declare them.
    """
    probe = report.probes.get("ros")
    if probe is not None:
        if probe.status in {DiscoveryStatus.SUCCEEDED, DiscoveryStatus.PARTIAL}:
            return True
        if any(_has_values(probe.data.get(key)) for key in _ROS_RUNTIME_KEYS):
            return True

    application = report.probes.get("application")
    if application is not None:
        for project in application.data.get("projects", []):
            if not isinstance(project, dict):
                continue
            if any(
                _has_values(project.get(key))
                for key in ("ros_interfaces", "launch_files")
            ):
                return True
            declarations = project.get("dependency_declarations", [])
            if any(
                isinstance(item, dict) and item.get("ecosystem") == "ros"
                for item in declarations
            ):
                return True
            dependencies = {
                str(item).casefold() for item in project.get("declared_dependencies", [])
            }
            if dependencies & _ROS_DEPENDENCY_NAMES:
                return True

    for executable in active.executables:
        if any(
            _has_values(executable.communication.ros.get(role))
            for role in (
                "publishers",
                "subscribers",
                "services",
                "clients",
                "actions",
                "nodes",
                "remappings",
            )
        ):
            return True
        if _has_values(executable.launch_analysis.nodes) or _has_values(
            executable.launch_analysis.remappings
        ):
            return True

    if _has_values(active.unattributed_source_interfaces):
        return True

    if any(
        route.kind.startswith("ros_")
        for candidate in report.operation_candidates
        for route in candidate.route_evidence
    ):
        return True

    expected_features = report.capability_manifest.get("expected_profile", {}).get(
        "features", {}
    )
    return _has_values(expected_features.get("urdf_hardware", {}).get("ros2_control"))
