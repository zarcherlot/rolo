from __future__ import annotations

import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport
from rolo.stages.adapt.discovery import load_latest_report
from rolo.stages.adapt.wiki import WikiGenerationMetadata
from rolo.stages.adapt.wiki_diff import WikiDiscoveryDiff
from rolo.stages.adapt.wiki_insights import (
    RoloWikiInsightBundle,
    WikiInsightBundle,
    parse_wiki_insight_bundle_json,
)
from rolo.stages.artifact_paths import ArtifactLayout

_MAX_WIKI_BYTES = 128_000
_MAX_SECTIONS = 24
_MAX_LINES_PER_SECTION = 30
_MAX_LINE_CHARS = 400

_HTML = re.compile(r"<[^>]*>")
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_ARTIFACT_REF = re.compile(r"\bartifact://\S+", re.IGNORECASE)
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s|,;]+")
_PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9_])/(?:home|root|etc|var|tmp|workspace|mnt|Users)/[^\s|,;]+",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|password|secret|credential)\b"
    r"\s*[:=]\s*[^\s|,;]+"
)


class WikiLayerSummary(BaseModel):
    schema_version: Literal["rolo-wiki-layer-summary/v1"] = (
        "rolo-wiki-layer-summary/v1"
    )
    layer: Literal[
        "Hardware", "Linux", "Middleware", "Application", "Dependencies"
    ]
    status: Literal["OBSERVED", "PARTIAL", "UNAVAILABLE", "UNKNOWN"]
    summary: str
    facts: dict[str, str | int | float | bool] = Field(default_factory=dict)


class WikiSection(BaseModel):
    schema_version: Literal["rolo-wiki-section/v1"] = "rolo-wiki-section/v1"
    heading: str
    lines: list[str] = Field(default_factory=list, max_length=_MAX_LINES_PER_SECTION)


class WikiInsightSummary(BaseModel):
    schema_version: Literal["rolo-wiki-insight-summary/v1"] = (
        "rolo-wiki-insight-summary/v1"
    )
    category: Literal[
        "SAFETY", "ARCHITECTURE", "HARDWARE", "OPERATIONS", "MAINTENANCE"
    ]
    statement: str
    confidence: Literal["LOW", "MEDIUM"]
    verification: str
    source: Literal["DETERMINISTIC_RULE", "ADAPT_AGENT_SKILL"]
    evidence_id: str


class WikiChangeSummary(BaseModel):
    schema_version: Literal["rolo-wiki-change-summary/v1"] = (
        "rolo-wiki-change-summary/v1"
    )
    category: Literal[
        "PLATFORM", "ROS", "APPLICATION", "HARDWARE", "OPERATION", "UNKNOWN"
    ]
    added: list[str] = Field(default_factory=list, max_length=40)
    removed: list[str] = Field(default_factory=list, max_length=40)
    changed: list[str] = Field(default_factory=list, max_length=20)
    evidence_id: str


class RobotWikiSnapshot(BaseModel):
    schema_version: Literal["rolo-robot-wiki/v1"] = "rolo-robot-wiki/v1"
    robot_id: str
    discovery_id: str
    discovery_status: str
    created_at: datetime
    content_origin: Literal["GENERATED_MATCH", "HUMAN_EDITED", "MISSING"]
    content_integrity: Literal["validated", "unverified", "unavailable"]
    sections: list[WikiSection] = Field(default_factory=list, max_length=_MAX_SECTIONS)
    layers: list[WikiLayerSummary]
    insights: list[WikiInsightSummary] = Field(default_factory=list, max_length=40)
    diff_status: Literal["NO_BASELINE", "UNCHANGED", "CHANGED"]
    baseline_discovery_id: str | None = None
    changes: list[WikiChangeSummary] = Field(default_factory=list, max_length=12)
    observed_at: datetime
    freshness: Literal["unknown"] = "unknown"
    source_kind: Literal["verified_discovery_snapshot"] = "verified_discovery_snapshot"
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["verified"] = "verified"
    limitations: list[str] = Field(default_factory=list)


class WikiEvidenceSpec(BaseModel):
    evidence_id: str
    title: str
    summary: str
    source_kind: Literal["wiki_insight", "wiki_diff"]
    reference: str
    observed_at: datetime
    limitations: list[str] = Field(default_factory=list)


def _evidence_id(robot_id: str, reference: str) -> str:
    digest = sha256(f"{robot_id}\0{reference}".encode()).hexdigest()
    return f"ev_{digest[:18]}"


def _safe_text(value: object) -> str:
    text = str(value).replace("\x00", " ")
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _HTML.sub("", text)
    text = _ARTIFACT_REF.sub("[redacted reference]", text)
    text = _WINDOWS_PATH.sub("[redacted path]", text)
    text = _PRIVATE_PATH.sub("[redacted path]", text)
    text = _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = text.replace("`", "").replace("**", "")
    return " ".join(text.split())[:_MAX_LINE_CHARS]


def _read_sections(path: Path) -> tuple[list[WikiSection], bool]:
    if not path.is_file():
        return [], False
    payload = path.read_bytes()
    truncated = len(payload) > _MAX_WIKI_BYTES
    text = payload[:_MAX_WIKI_BYTES].decode("utf-8", errors="replace")
    sections: list[WikiSection] = []
    heading = "Overview"
    lines: list[str] = []
    in_code = False

    def flush() -> None:
        nonlocal lines
        if lines and len(sections) < _MAX_SECTIONS:
            sections.append(WikiSection(heading=_safe_text(heading), lines=lines))
        lines = []

    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        if match := re.match(r"^#{1,4}\s+(.+)$", stripped):
            flush()
            heading = match.group(1)
            continue
        if re.fullmatch(r"\|?\s*:?-{3,}.*", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            stripped = " · ".join(
                cell.strip() for cell in stripped.strip("|").split("|") if cell.strip()
            )
        stripped = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+|>\s*)", "", stripped)
        safe = _safe_text(stripped)
        if safe and len(lines) < _MAX_LINES_PER_SECTION:
            lines.append(safe)
    flush()
    return sections, truncated


def _status(value: object) -> Literal["OBSERVED", "PARTIAL", "UNAVAILABLE", "UNKNOWN"]:
    normalized = str(getattr(value, "value", value)).upper()
    if normalized in {"SUCCEEDED", "OBSERVED"}:
        return "OBSERVED"
    if normalized == "PARTIAL":
        return "PARTIAL"
    if normalized in {"UNAVAILABLE", "FAILED"}:
        return "UNAVAILABLE"
    return "UNKNOWN"


def _layer_summaries(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
) -> list[WikiLayerSummary]:
    hardware = report.probes.get("hw")
    linux = report.probes.get("linux")
    ros = report.probes.get("ros")
    hardware_data = hardware.data if hardware else {}
    linux_data = linux.data if linux else {}
    host = linux_data.get("host", {}) if isinstance(linux_data.get("host"), dict) else {}
    ros_data = ros.data if ros else {}
    dependency = active.dependency_summary
    missing = dependency.get("missing", []) if isinstance(dependency, dict) else []
    conflicting = dependency.get("conflicting", []) if isinstance(dependency, dict) else []
    return [
        WikiLayerSummary(
            layer="Hardware",
            status=_status(hardware.status if hardware else "UNKNOWN"),
            summary="Bounded hardware observations from the latest discovery.",
            facts={
                "devices": len(hardware_data.get("devices", [])),
                "compute": _safe_text(hardware_data.get("compute_platform", "unknown")),
                "architecture": _safe_text(hardware_data.get("architecture", "unknown")),
            },
        ),
        WikiLayerSummary(
            layer="Linux",
            status=_status(linux.status if linux else "UNKNOWN"),
            summary="Host and software facts without configuration payloads.",
            facts={
                "system": _safe_text(host.get("system", "unknown")),
                "release": _safe_text(host.get("release", "unknown")),
                "tools": len(linux_data.get("software", {})),
            },
        ),
        WikiLayerSummary(
            layer="Middleware",
            status=_status(ros.status if ros else "UNKNOWN"),
            summary="Observed ROS environment and graph coverage.",
            facts={
                "ros_distro": _safe_text(ros_data.get("ros_distro", "unknown")),
                "rmw": _safe_text(ros_data.get("rmw", "unknown")),
                "nodes": len(ros_data.get("nodes", [])),
                "topics": len(ros_data.get("topics", [])),
            },
        ),
        WikiLayerSummary(
            layer="Application",
            status=_status(active.technical_status),
            summary="Engineer-relevant executables and canonical operation candidates.",
            facts={
                "applications": len(active.executables),
                "operation_candidates": len(report.operation_candidates),
                "unattributed_interfaces": len(active.unattributed_source_interfaces),
            },
        ),
        WikiLayerSummary(
            layer="Dependencies",
            status="PARTIAL" if missing or conflicting or active.unknowns else "OBSERVED",
            summary="Known dependency gaps and unresolved discovery questions.",
            facts={
                "missing": len(missing),
                "conflicting": len(conflicting),
                "unknowns": len(active.unknowns),
                "warnings": len(active.warnings),
            },
        ),
    ]


def _load_snapshot_models(
    artifact_root: Path,
    robot_id: str,
) -> tuple[
    DiscoveryReport,
    ActiveDiscoveryReport,
    WikiInsightBundle | RoloWikiInsightBundle,
    WikiDiscoveryDiff,
    WikiGenerationMetadata,
    Path,
]:
    report = load_latest_report(artifact_root, robot_id)
    run_root = ArtifactLayout(artifact_root).discovery_run(robot_id, report.discovery_id)
    active = ActiveDiscoveryReport.model_validate_json(
        (run_root / "active_discovery_report.json").read_text(encoding="utf-8")
    )
    insights = parse_wiki_insight_bundle_json(
        (run_root / "wiki_insights.json").read_text(encoding="utf-8")
    )
    diff = WikiDiscoveryDiff.model_validate_json(
        (run_root / "wiki_diff.json").read_text(encoding="utf-8")
    )
    generation = WikiGenerationMetadata.model_validate_json(
        (run_root / "wiki_generation.json").read_text(encoding="utf-8")
    )
    identities = {
        (active.robot_id, active.discovery_id),
        (insights.robot_id, insights.discovery_id),
        (diff.robot_id, diff.discovery_id),
    }
    if identities != {(robot_id, report.discovery_id)}:
        raise ValueError("Wiki machine evidence identity mismatch")
    return report, active, insights, diff, generation, run_root / "robot_wiki.md"


def wiki_evidence_specs(
    artifact_root: Path,
    robot_id: str,
) -> dict[str, WikiEvidenceSpec]:
    try:
        report, _, insights, diff, _, _ = _load_snapshot_models(artifact_root, robot_id)
    except (FileNotFoundError, OSError, ValueError):
        return {}
    specs: dict[str, WikiEvidenceSpec] = {}
    for index, finding in enumerate(insights.findings):
        reference = f"discovery:{report.discovery_id}:wiki-insight:{index}"
        evidence_id = _evidence_id(robot_id, reference)
        specs[evidence_id] = WikiEvidenceSpec(
            evidence_id=evidence_id,
            title=f"Wiki insight: {finding.category.title()}",
            summary=_safe_text(finding.statement),
            source_kind="wiki_insight",
            reference=reference,
            observed_at=report.created_at,
            limitations=[
                "This is an advisory inference and must not be promoted to a verified "
                "physical fact."
            ],
        )
    for index, change in enumerate(diff.changes):
        reference = f"discovery:{report.discovery_id}:wiki-diff:{index}"
        evidence_id = _evidence_id(robot_id, reference)
        specs[evidence_id] = WikiEvidenceSpec(
            evidence_id=evidence_id,
            title=f"Discovery change: {change.category.title()}",
            summary="A bounded domain-level change was computed against the previous discovery.",
            source_kind="wiki_diff",
            reference=reference,
            observed_at=report.created_at,
            limitations=["The change describes discovery evidence, not a physical outcome."],
        )
    return specs


def build_robot_wiki(artifact_root: Path, robot_id: str) -> RobotWikiSnapshot:
    report, active, insights, diff, generation, wiki_path = _load_snapshot_models(
        artifact_root, robot_id
    )
    sections, truncated = _read_sections(wiki_path)
    if not wiki_path.is_file():
        content_origin: Literal["GENERATED_MATCH", "HUMAN_EDITED", "MISSING"] = "MISSING"
        content_integrity: Literal["validated", "unverified", "unavailable"] = "unavailable"
    else:
        current_digest = sha256(wiki_path.read_text(encoding="utf-8").encode()).hexdigest()
        generated_match = current_digest == generation.generated_sha256
        content_origin = "GENERATED_MATCH" if generated_match else "HUMAN_EDITED"
        content_integrity = "validated" if generated_match else "unverified"
    specs = wiki_evidence_specs(artifact_root, robot_id)
    insight_items: list[WikiInsightSummary] = []
    for index, finding in enumerate(insights.findings):
        reference = f"discovery:{report.discovery_id}:wiki-insight:{index}"
        insight_items.append(
            WikiInsightSummary(
                category=finding.category,
                statement=_safe_text(finding.statement),
                confidence=finding.confidence,
                verification=_safe_text(finding.verification),
                source=finding.source,
                evidence_id=_evidence_id(robot_id, reference),
            )
        )
    change_items: list[WikiChangeSummary] = []
    for index, change in enumerate(diff.changes):
        reference = f"discovery:{report.discovery_id}:wiki-diff:{index}"
        change_items.append(
            WikiChangeSummary(
                category=change.category,
                added=[_safe_text(item) for item in change.added],
                removed=[_safe_text(item) for item in change.removed],
                changed=[_safe_text(item) for item in change.changed],
                evidence_id=_evidence_id(robot_id, reference),
            )
        )
    limitations = [
        "Machine insights and discovery changes are manifest-verified; they remain "
        "observations or advisory inferences."
    ]
    if content_origin == "HUMAN_EDITED":
        limitations.append(
            "The human-maintained Wiki differs from the generated snapshot and is "
            "displayed as unverified text."
        )
    if truncated:
        limitations.append("Wiki text was truncated to the bounded Web read-model limit.")
    if not specs and (insights.findings or diff.changes):
        raise ValueError("Wiki evidence index could not be constructed")
    return RobotWikiSnapshot(
        robot_id=robot_id,
        discovery_id=report.discovery_id,
        discovery_status=report.status.value,
        created_at=report.created_at,
        content_origin=content_origin,
        content_integrity=content_integrity,
        sections=sections,
        layers=_layer_summaries(report, active),
        insights=insight_items,
        diff_status=diff.status,
        baseline_discovery_id=diff.baseline_discovery_id,
        changes=change_items,
        observed_at=report.created_at,
        confidence=1.0 if report.status.value == "SUCCEEDED" else 0.8,
        limitations=limitations,
    )
