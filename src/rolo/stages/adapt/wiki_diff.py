"""Small, stable deltas between engineer-facing discovery snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport

WikiChangeCategory = Literal[
    "PLATFORM", "ROS", "APPLICATION", "HARDWARE", "OPERATION", "UNKNOWN"
]


class WikiDiscoveryChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: WikiChangeCategory
    added: list[str] = Field(default_factory=list, max_length=40)
    removed: list[str] = Field(default_factory=list, max_length=40)
    changed: list[str] = Field(default_factory=list, max_length=20)


class WikiDiscoveryDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-wiki-discovery-diff/v1"] = "robot-wiki-discovery-diff/v1"
    robot_id: str
    discovery_id: str
    baseline_discovery_id: str | None = None
    status: Literal["NO_BASELINE", "UNCHANGED", "CHANGED"]
    changes: list[WikiDiscoveryChange] = Field(default_factory=list, max_length=12)


def _strings(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values if value not in (None, "")}


def _named(values: Iterable[Any]) -> set[str]:
    result: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("name") or value.get("path") or value.get("endpoint")
        if value not in (None, ""):
            result.add(str(value))
    return result


def _device_keys(report: DiscoveryReport) -> set[str]:
    probe = report.probes.get("hw")
    devices = probe.data.get("devices", []) if probe else []
    keys: set[str] = set()
    for item in devices:
        if not isinstance(item, dict):
            continue
        stable = [
            item.get("serial"),
            item.get("id_path") or item.get("bus_path") or item.get("physical_path"),
            item.get("vendor_id"),
            item.get("product_id"),
        ]
        identity = ":".join(str(value) for value in stable if value not in (None, ""))
        keys.add(identity or str(item.get("path") or item.get("name") or "unidentified"))
    return keys


def _ros_values(report: DiscoveryReport) -> set[str]:
    probe = report.probes.get("ros")
    data = probe.data if probe else {}
    values = {
        f"distro={data.get('ros_distro') or 'unknown'}",
        f"rmw={data.get('rmw') or 'unknown'}",
        f"domain={data.get('domain_id') or 'unknown'}",
    }
    values.update(f"node={item}" for item in data.get("nodes", []))
    values.update(f"topic={item}" for item in data.get("topics", []))
    return values


def _platform_values(report: DiscoveryReport) -> set[str]:
    hw = report.probes.get("hw")
    linux = report.probes.get("linux")
    hw_data = hw.data if hw else {}
    host = linux.data.get("host", {}) if linux else {}
    return {
        f"status={report.status.value}",
        f"compute={hw_data.get('compute_platform') or 'unknown'}",
        f"architecture={hw_data.get('architecture') or host.get('architecture') or 'unknown'}",
        f"os={host.get('system') or 'unknown'} {host.get('release') or ''}".rstrip(),
    }


def _append_set_change(
    changes: list[WikiDiscoveryChange],
    category: WikiChangeCategory,
    current: set[str],
    previous: set[str],
) -> None:
    added = sorted(current - previous)[:40]
    removed = sorted(previous - current)[:40]
    if added or removed:
        changes.append(WikiDiscoveryChange(category=category, added=added, removed=removed))


def build_wiki_discovery_diff(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
    previous_report: DiscoveryReport | None,
    previous_active: ActiveDiscoveryReport | None,
) -> WikiDiscoveryDiff:
    """Compare bounded engineer-relevant sets; never diff exhaustive raw payloads."""
    if previous_report is None or previous_active is None:
        return WikiDiscoveryDiff(
            robot_id=report.robot_id,
            discovery_id=report.discovery_id,
            status="NO_BASELINE",
        )
    if previous_report.robot_id != report.robot_id:
        raise ValueError("Wiki diff baseline robot_id does not match")

    changes: list[WikiDiscoveryChange] = []
    _append_set_change(
        changes,
        "PLATFORM",
        _platform_values(report),
        _platform_values(previous_report),
    )
    _append_set_change(changes, "ROS", _ros_values(report), _ros_values(previous_report))
    _append_set_change(
        changes,
        "APPLICATION",
        _strings(item.name for item in active.executables),
        _strings(item.name for item in previous_active.executables),
    )
    _append_set_change(changes, "HARDWARE", _device_keys(report), _device_keys(previous_report))
    _append_set_change(
        changes,
        "OPERATION",
        _strings(item.operation for item in report.operation_candidates),
        _strings(item.operation for item in previous_report.operation_candidates),
    )
    _append_set_change(
        changes,
        "UNKNOWN",
        _strings(active.unknowns),
        _strings(previous_active.unknowns),
    )
    return WikiDiscoveryDiff(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        baseline_discovery_id=previous_report.discovery_id,
        status="CHANGED" if changes else "UNCHANGED",
        changes=changes,
    )
