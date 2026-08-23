from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from rolo.core.models import DiscoveryReport, DiscoveryStatus, utc_now
from rolo.stages.adapt.discovery import load_latest_report, load_report
from rolo.stages.artifact_paths import ArtifactLayout

_MAX_DISCOVERY_RUNS = 200
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9._-]+")


class DiscoveryHeuristicSummary(BaseModel):
    """Sanitized advisory projection of the verified heuristic discovery fields."""

    schema_version: Literal["rolo-discovery-heuristic-summary/v1"] = (
        "rolo-discovery-heuristic-summary/v1"
    )
    mode: Literal["disabled", "shadow", "enabled"]
    status: Literal["AGENT_COMPLETED", "FALLBACK", "DISABLED"]
    inferred_operation_count: int = Field(ge=0)
    missing_evidence_count: int = Field(ge=0)
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def require_consistent_state(self) -> DiscoveryHeuristicSummary:
        if self.mode == "disabled":
            if self.status != "DISABLED":
                raise ValueError("disabled heuristic mode requires DISABLED status")
            if self.inferred_operation_count or self.missing_evidence_count:
                raise ValueError("disabled heuristic mode cannot report advisory counts")
        elif self.status == "DISABLED":
            raise ValueError("active heuristic mode cannot report DISABLED status")
        return self


class DiscoveryTargetEvidenceSummary(BaseModel):
    """Safe target-evidence metadata derived from verified discovery probes."""

    schema_version: Literal["rolo-discovery-target-evidence-summary/v1"] = (
        "rolo-discovery-target-evidence-summary/v1"
    )
    deployment_scope: Literal["LOCAL", "REMOTE"]
    freshness: Literal["FRESH", "STALE"]
    collected_at: datetime
    refresh_required: bool
    refresh_reason: str | None = None

    @model_validator(mode="after")
    def require_consistent_refresh_state(self) -> DiscoveryTargetEvidenceSummary:
        if self.freshness == "FRESH" and (self.refresh_required or self.refresh_reason is not None):
            raise ValueError("fresh target evidence cannot require refresh")
        if self.freshness == "STALE" and (not self.refresh_required or not self.refresh_reason):
            raise ValueError("stale target evidence requires a safe refresh reason")
        return self


class DiscoverySnapshotSummary(BaseModel):
    schema_version: Literal["rolo-discovery-snapshot-summary/v3"] = (
        "rolo-discovery-snapshot-summary/v3"
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
    heuristic_summary: DiscoveryHeuristicSummary
    target_evidence: DiscoveryTargetEvidenceSummary | None = None


class DiscoverySnapshotCollection(BaseModel):
    schema_version: Literal["rolo-discovery-snapshot-collection/v3"] = (
        "rolo-discovery-snapshot-collection/v3"
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
    source_kind: Literal["verified_discovery_history"] = "verified_discovery_history"
    integrity_status: Literal["verified"] = "verified"
    limitations: list[str] = Field(default_factory=list)


def _safe_mode(value: str) -> str:
    normalized = _SAFE_TOKEN.sub("_", value.strip())[:48].strip("_")
    return normalized or "unknown"


def _heuristic_summary(report: DiscoveryReport) -> DiscoveryHeuristicSummary:
    return DiscoveryHeuristicSummary(
        mode=report.heuristic_mode,
        status=report.heuristic_status,
        inferred_operation_count=report.heuristic_inferred_operation_count,
        missing_evidence_count=report.heuristic_missing_evidence_count,
        influences_release=False,
    )


def _target_evidence_summary(
    report: DiscoveryReport,
    observed_at: datetime,
) -> DiscoveryTargetEvidenceSummary | None:
    from rolo.stages.adapt.target_evidence import MAX_CLOCK_SKEW, MAX_REQUEST_LIFETIME

    layers = ("hw", "linux", "ros")
    bindings = {
        layer: report.probes[layer].data.get("target_evidence")
        for layer in layers
        if layer in report.probes
        and isinstance(report.probes[layer].data.get("target_evidence"), dict)
    }
    if not bindings:
        return None
    if set(bindings) != set(layers):
        raise ValueError("target evidence must bind every target probe")

    identity_fields = (
        "schema_version",
        "robot_id",
        "collector_id",
        "target_host_fingerprint",
        "bundle_payload_sha256",
        "access",
        "deployment_mode",
        "collected_at",
    )
    first = bindings["hw"]
    identity = tuple(first.get(field) for field in identity_fields)
    if any(
        tuple(binding.get(field) for field in identity_fields) != identity
        for binding in bindings.values()
    ):
        raise ValueError("target evidence bindings are inconsistent")
    if first.get("schema_version") != "robot-target-evidence-binding/v2":
        raise ValueError("unsupported target evidence binding")
    if first.get("robot_id") != report.robot_id or first.get("access") != "READ_ONLY":
        raise ValueError("target evidence identity or access is invalid")
    if not isinstance(first.get("collector_id"), str) or not first["collector_id"]:
        raise ValueError("target evidence collector identity is invalid")
    for digest_field in ("target_host_fingerprint", "bundle_payload_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(first.get(digest_field, ""))):
            raise ValueError("target evidence digest identity is invalid")
    mode = first.get("deployment_mode")
    if mode not in {"local", "remote"}:
        raise ValueError("target evidence deployment mode is invalid")
    try:
        collected_at = datetime.fromisoformat(str(first.get("collected_at")))
    except ValueError as exc:
        raise ValueError("target evidence collection time is invalid") from exc
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("target evidence collection time must include a timezone")
    resolved_at = observed_at
    if resolved_at.tzinfo is None or resolved_at.utcoffset() is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)
    age = resolved_at - collected_at
    if age < -MAX_CLOCK_SKEW:
        raise ValueError("target evidence collection time is beyond allowed clock skew")
    stale = age > MAX_REQUEST_LIFETIME + MAX_CLOCK_SKEW
    return DiscoveryTargetEvidenceSummary(
        deployment_scope=mode.upper(),
        freshness="STALE" if stale else "FRESH",
        collected_at=collected_at,
        refresh_required=stale,
        refresh_reason=(
            "Verified target evidence is older than the collector replay window." if stale else None
        ),
    )


def _summary(
    report: DiscoveryReport,
    latest_id: str | None,
    observed_at: datetime,
) -> DiscoverySnapshotSummary:
    statuses = [probe.status for probe in report.probes.values()]
    unavailable = {DiscoveryStatus.UNAVAILABLE, DiscoveryStatus.FAILED}
    warning_count = sum(len(probe.warnings) + len(probe.errors) for probe in report.probes.values())
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
        heuristic_summary=_heuristic_summary(report),
        target_evidence=_target_evidence_summary(report, observed_at),
    )


def build_discovery_snapshot_collection(
    artifact_root: Path,
    robot_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    observed_at: datetime | None = None,
) -> DiscoverySnapshotCollection:
    resolved_at = observed_at or utc_now()
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

    items: list[DiscoverySnapshotSummary] = []
    for report in reports:
        try:
            items.append(_summary(report, latest_id, resolved_at))
        except ValueError:
            excluded += 1
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
            f"{excluded} discovery run(s) were excluded because integrity or the safe "
            "Web projection could not be verified."
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
