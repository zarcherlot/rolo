from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import DiscoveryReport, DiscoveryStatus, utc_now
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.artifact_paths import ArtifactLayout

_MAX_DISCOVERY_RUNS = 200
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9._-]+")


class DiscoverySnapshotSummary(BaseModel):
    schema_version: Literal["rolo-discovery-snapshot-summary/v1"] = (
        "rolo-discovery-snapshot-summary/v1"
    )
    robot_id: str
    discovery_id: str
    status: DiscoveryStatus
    discovery_mode: str
    created_at: datetime
    is_latest: bool
    probe_total: int = Field(ge=0)
    observed_probes: int = Field(ge=0)
    partial_probes: int = Field(ge=0)
    unavailable_probes: int = Field(ge=0)
    operation_candidates: int = Field(ge=0)
    semantic_bindings: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["verified"] = "verified"
    limitations: list[str] = Field(default_factory=list)


class DiscoverySnapshotCollection(BaseModel):
    schema_version: Literal["rolo-discovery-snapshot-collection/v1"] = (
        "rolo-discovery-snapshot-collection/v1"
    )
    robot_id: str
    items: list[DiscoverySnapshotSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    excluded_unverified: int = Field(ge=0)
    observed_at: datetime
    freshness: Literal["unknown"] = "unknown"
    source_kind: Literal["verified_discovery_history"] = (
        "verified_discovery_history"
    )
    integrity_status: Literal["verified"] = "verified"
    limitations: list[str] = Field(default_factory=list)


def _safe_mode(value: str) -> str:
    normalized = _SAFE_TOKEN.sub("_", value.strip())[:48].strip("_")
    return normalized or "unknown"


def _summary(report: DiscoveryReport, latest_id: str | None) -> DiscoverySnapshotSummary:
    statuses = [probe.status for probe in report.probes.values()]
    unavailable = {DiscoveryStatus.UNAVAILABLE, DiscoveryStatus.FAILED}
    warning_count = sum(
        len(probe.warnings) + len(probe.errors) for probe in report.probes.values()
    )
    return DiscoverySnapshotSummary(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        status=report.status,
        discovery_mode=_safe_mode(report.discovery_mode),
        created_at=report.created_at,
        is_latest=report.discovery_id == latest_id,
        probe_total=len(statuses),
        observed_probes=statuses.count(DiscoveryStatus.SUCCEEDED),
        partial_probes=statuses.count(DiscoveryStatus.PARTIAL),
        unavailable_probes=sum(status in unavailable for status in statuses),
        operation_candidates=len(report.operation_candidates),
        semantic_bindings=len(report.semantic_bindings),
        warning_count=warning_count,
        confidence=1.0 if report.status is DiscoveryStatus.SUCCEEDED else 0.8,
        limitations=[
            "Discovery coverage does not prove runtime availability, task success, "
            "or physical state."
        ],
    )


def build_discovery_snapshot_collection(
    artifact_root: Path,
    robot_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> DiscoverySnapshotCollection:
    layout = ArtifactLayout(artifact_root)
    runs_root = layout.discovery_latest(robot_id).parent / "runs"
    latest_id: str | None = None
    latest_unavailable = False
    try:
        latest_id = load_latest_report(artifact_root, robot_id).discovery_id
    except (FileNotFoundError, OSError, ValueError):
        latest_unavailable = True

    candidates = []
    if runs_root.is_dir():
        candidates = [item for item in runs_root.iterdir() if item.is_dir()]
    candidates.sort(key=lambda item: item.name, reverse=True)
    truncated = len(candidates) > _MAX_DISCOVERY_RUNS
    reports: list[DiscoveryReport] = []
    excluded = 0
    for candidate in candidates[:_MAX_DISCOVERY_RUNS]:
        try:
            resolved = candidate.resolve()
            if resolved.parent != runs_root.resolve():
                raise ValueError("discovery run escapes history root")
            report = load_report(artifact_root, robot_id, candidate.name)
            if report.robot_id != robot_id or report.discovery_id != candidate.name:
                raise ValueError("discovery history identity mismatch")
            reports.append(report)
        except (FileNotFoundError, OSError, ValueError):
            excluded += 1

    items = [_summary(report, latest_id) for report in reports]
    items.sort(key=lambda item: (item.created_at, item.discovery_id), reverse=True)
    total = len(items)
    next_offset = offset + limit if offset + limit < total else None
    limitations = [
        "Only discovery reports that pass manifest verification are included.",
        "Discovery history is evidence of bounded observations, not runtime or physical outcomes.",
    ]
    if latest_unavailable:
        limitations.append(
            "The latest discovery commit marker is unavailable or invalid; "
            "no snapshot is marked current."
        )
    if excluded:
        limitations.append(
            f"{excluded} discovery run(s) were excluded because integrity could not be verified."
        )
    if truncated:
        limitations.append(
            f"History was bounded to the newest {_MAX_DISCOVERY_RUNS} run directories."
        )
    observed_at = max((item.created_at for item in items), default=utc_now())
    return DiscoverySnapshotCollection(
        robot_id=robot_id,
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        excluded_unverified=excluded,
        observed_at=observed_at,
        limitations=limitations,
    )
