"""Bounded, sanitized artifact-analysis read model for the workbench API."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from rolo.jobs import JobStore
from rolo.target_ref import TargetRef
from rolo.targets.profiles import TargetProfileStore

ARTIFACT_ANALYSIS_API_FEATURES = ("workbench.artifact-analysis-read-model/v1",)

SafeId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9._:-]{0,127}$")]
SafeText = Annotated[str, StringConstraints(min_length=1, max_length=240)]
Tone = Literal["blue", "slate", "violet", "amber", "green"]

_MAX_ITEMS = 40
_UNSAFE_TERMS = (
    "artifact://",
    "ssh://",
    "signed url",
    "download url",
    "http://",
    "https://",
    "private key",
    "known_hosts",
    "credential",
    "password",
    "secret",
    "token",
    "command",
    "shell",
    "argv",
    "base64",
    "raw_path",
    "local_path",
    "remote_path",
    "c:\\",
    "/home/",
)
_DIGEST = re.compile(r"^[0-9a-f]{8,64}(?:…[0-9a-f]{8,64})?$")


def _safe_texts(values: list[str]) -> list[str]:
    for value in values:
        if any(term in value.casefold() for term in _UNSAFE_TERMS):
            raise ValueError("artifact-analysis text contains a restricted reference")
    return values


class ArtifactAnalysisMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: SafeText
    value: float = Field(ge=0, le=1_000_000_000)
    display: SafeText
    tone: Tone


class ArtifactAnalysisOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    route: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    route_status: Literal["observed", "unresolved", "deferred"]
    checks: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        max_length=8
    )
    contract: Annotated[str, StringConstraints(min_length=1, max_length=160)]


class ArtifactAnalysisGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    state: SafeText
    tone: Tone


class ArtifactAnalysisStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    status: Literal["passed", "partial", "blocked", "pending"]
    timestamp: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    detail: SafeText


class ArtifactAnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: Tone
    title: SafeText
    body: SafeText


class ArtifactAnalysisSummary(BaseModel):
    """Producer-owned bounded summary; no bytes, locations, or executable text."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-artifact-analysis-summary/v1"] = (
        "rolo-artifact-analysis-summary/v1"
    )
    analysis_id: SafeId
    target_id: SafeId
    robot_id: SafeId
    job_id: SafeId | None = None
    run_id: SafeId | None = None
    discovery_id: SafeId
    source_kind: Literal["rolo_api"] = "rolo_api"
    source_label: SafeText
    observed_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    contains_secret_payloads: Literal[False] = False
    kind: SafeText
    run_status: SafeText
    title: SafeText
    description: SafeText
    gate_status: Literal["PASSED", "BLOCKED", "NOT_AVAILABLE"]
    gate_label: SafeText
    gate_tone: Tone
    release_status: SafeText
    release_label: SafeText
    release_tone: Tone
    run_duration: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    event_count: int = Field(ge=0, le=1_000_000)
    eligible_operation_count: int = Field(ge=0, le=1_000_000)
    route_review_flags: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    context_bars: list[ArtifactAnalysisMetric] = Field(max_length=_MAX_ITEMS)
    evidence_note: SafeText
    operations: list[ArtifactAnalysisOperation] = Field(max_length=_MAX_ITEMS)
    graph_nodes: list[ArtifactAnalysisGraphNode] = Field(max_length=_MAX_ITEMS)
    stages: list[ArtifactAnalysisStage] = Field(max_length=_MAX_ITEMS)
    findings: list[ArtifactAnalysisFinding] = Field(max_length=_MAX_ITEMS)
    hashes: list[tuple[Annotated[str, StringConstraints(min_length=1, max_length=80)], str]] = (
        Field(max_length=_MAX_ITEMS)
    )
    limitations: list[SafeText] = Field(max_length=_MAX_ITEMS)

    @field_validator("hashes")
    @classmethod
    def validate_hashes(cls, values: list[tuple[str, str]]) -> list[tuple[str, str]]:
        for label, digest in values:
            if not _DIGEST.fullmatch(digest):
                raise ValueError("artifact-analysis hashes must be redacted digests")
            if any(term in label.casefold() for term in _UNSAFE_TERMS):
                raise ValueError("artifact-analysis hash label contains a restricted reference")
        return values

    @field_validator(
        "source_label",
        "kind",
        "run_status",
        "title",
        "description",
        "gate_label",
        "release_status",
        "release_label",
        "evidence_note",
        "route_review_flags",
        "run_duration",
    )
    @classmethod
    def validate_text(cls, value: str) -> str:
        _safe_texts([value])
        return value

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _safe_texts(values)

    @model_validator(mode="after")
    def validate_payload_boundary(self) -> ArtifactAnalysisSummary:
        payload = self.model_dump(mode="json")

        def walk(value: object, key: str = "") -> None:
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    normalized = child_key.casefold()
                    if normalized != "contains_secret_payloads" and any(
                        term in normalized
                        for term in ("path", "url", "bytes", "token", "secret", "command", "argv")
                    ):
                        raise ValueError("artifact-analysis contains a restricted field")
                    walk(child_value, normalized)
            elif isinstance(value, list):
                for child in value:
                    walk(child, key)
            elif isinstance(value, str) and any(term in value.casefold() for term in _UNSAFE_TERMS):
                raise ValueError("artifact-analysis contains a restricted reference")

        walk(payload)
        return self

    @property
    def producer_revision(self) -> str:
        return hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class ArtifactAnalysisConflict(ValueError):
    """Persisted analysis is not bound to the requested producer identity."""


def _analysis_path(config_root: Path, target_id: str) -> Path:
    if not re.fullmatch(r"^[a-z][a-z0-9_-]{2,63}$", target_id):
        raise ArtifactAnalysisConflict("target identity is invalid")
    return config_root.expanduser().resolve() / "artifact-analysis" / f"{target_id}.json"


def _load_summary(config_root: Path, target_id: str) -> ArtifactAnalysisSummary | None:
    profiles = TargetProfileStore(config_root)
    try:
        profile = profiles.load(target_id)
    except FileNotFoundError:
        return None
    path = _analysis_path(config_root, target_id)
    if not path.is_file():
        return _not_available_summary(target_id, profile.updated_at)
    if path.is_symlink():
        raise ArtifactAnalysisConflict("artifact-analysis fixture must not be a symlink")
    try:
        summary = ArtifactAnalysisSummary.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactAnalysisConflict("artifact-analysis summary is invalid") from exc
    if summary.target_id != target_id or summary.robot_id != profile.robot_id:
        raise ArtifactAnalysisConflict("artifact-analysis target identity mismatch")
    if summary.source_kind != "rolo_api":
        raise ArtifactAnalysisConflict("artifact-analysis producer source is invalid")
    return summary


def _not_available_summary(target_id: str, observed_at: datetime) -> ArtifactAnalysisSummary:
    """Return an explicit non-empty projection when no analysis artifact exists."""

    return ArtifactAnalysisSummary(
        analysis_id=f"analysis-unavailable-{target_id}",
        target_id=target_id,
        robot_id=target_id,
        discovery_id=f"discovery-unavailable-{target_id}",
        source_label="Rolo producer; analysis unavailable",
        observed_at=observed_at,
        freshness="unknown",
        kind="Artifact analysis summary",
        run_status="NOT_AVAILABLE",
        title="Artifact analysis unavailable",
        description="No bounded analysis summary is currently available.",
        gate_status="NOT_AVAILABLE",
        gate_label="Analysis unavailable",
        gate_tone="slate",
        release_status="UNKNOWN",
        release_label="No release conclusion",
        release_tone="slate",
        run_duration="0s",
        event_count=0,
        eligible_operation_count=0,
        route_review_flags="0 / 0",
        context_bars=[],
        evidence_note="The producer did not find an analysis result.",
        operations=[],
        graph_nodes=[],
        stages=[
            {
                "label": "Analysis",
                "status": "pending",
                "timestamp": observed_at.isoformat(),
                "detail": "No analysis result is available.",
            }
        ],
        findings=[],
        hashes=[],
        limitations=[
            "Analysis is not available for this target.",
            "No readiness, job, physical, or release conclusion is implied.",
        ],
    )


def get_artifact_analysis(config_root: Path, target_id: str) -> ArtifactAnalysisSummary | None:
    return _load_summary(config_root, target_id)


def get_job_artifact_analysis(config_root: Path, job_id: str) -> ArtifactAnalysisSummary | None:
    if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$", job_id):
        return None
    root = config_root.expanduser().resolve() / "jobs"
    try:
        job, _, _ = JobStore(root).load(job_id)
        target = TypeAdapter(TargetRef).validate_json(job.target)
    except (OSError, ValueError, TypeError):
        return None
    target_id = None
    for profile in TargetProfileStore(config_root).list_profiles():
        if profile.target == target:
            target_id = profile.profile_id
            break
    if target_id is None:
        raise ArtifactAnalysisConflict("job target is not bound to a target profile")
    summary = _load_summary(config_root, target_id)
    if summary is None or summary.job_id != job_id:
        raise ArtifactAnalysisConflict("artifact-analysis job identity mismatch")
    return summary
