from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from rolo.core.models import utc_now
from rolo.stages.artifact_paths import ArtifactLayout

EPISODE_API_FEATURES = (
    "workbench.episode-read-model/v1",
    "workbench.episode-revision-history/v1",
    "workbench.episode-cohort-read-model/v1",
)

Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"),
]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=256)]
SummaryText = Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
LimitationText = Annotated[str, StringConstraints(min_length=1, max_length=1_000)]

_FORBIDDEN_KEYS = {
    "artifact_ref",
    "artifact_path",
    "local_path",
    "remote_path",
    "source_path",
    "signed_url",
    "collector_identity",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
    "command_payload",
    "command_output",
    "model_prompt",
    "model_response",
    "prompt",
    "payload",
    "path",
    "raw_payload",
    "hostname",
    "uri",
    "url",
}
_UNSAFE_STRING = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+.-]*://)"
    r"|(?:[A-Za-z]:[\\/])"
    r"|(?:\\\\[^\\\s]+\\[^\\\s]+)"
    r"|(?:/(?:home|Users|tmp|var|etc|opt|srv|mnt|Volumes)/)"
)
_METRIC_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


class EpisodeState(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"


class EpisodeOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class EpisodeVerification(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class EpisodeCoverage(str, Enum):
    METADATA_ONLY = "METADATA_ONLY"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class EpisodeCohortWindowDays(IntEnum):
    DAYS_7 = 7
    DAYS_30 = 30
    DAYS_90 = 90


class EpisodeTimelineLane(str, Enum):
    COMMAND = "COMMAND"
    STATE = "STATE"
    TELEMETRY = "TELEMETRY"
    OBSERVATION = "OBSERVATION"
    ALERT = "ALERT"
    AGENT = "AGENT"
    CONFIGURATION = "CONFIGURATION"
    CHECKPOINT = "CHECKPOINT"
    GATE = "GATE"
    OUTCOME = "OUTCOME"


class EpisodeAuthority(str, Enum):
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    VERIFIED = "VERIFIED"


class EpisodeSynchronization(str, Enum):
    SYNCED = "SYNCED"
    DEGRADED = "DEGRADED"
    UNSYNCED = "UNSYNCED"
    UNKNOWN = "UNKNOWN"


class EpisodeWorldKind(str, Enum):
    PHYSICAL = "PHYSICAL"
    SIMULATED = "SIMULATED"
    REPLAYED = "REPLAYED"


class EpisodeEvidenceKind(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    RENDERED = "RENDERED"
    GUI_SCREENSHOT = "GUI_SCREENSHOT"


class EpisodeFindingKind(str, Enum):
    OBSERVED_FACT = "OBSERVED_FACT"
    CANDIDATE_CAUSE = "CANDIDATE_CAUSE"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    VERIFIED_OUTCOME = "VERIFIED_OUTCOME"


class EpisodeSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EpisodeAssetAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    REDACTED = "REDACTED"


class EpisodePublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class EpisodeSummary(EpisodePublicModel):
    schema_version: Literal["rolo-episode-summary/v1"] = "rolo-episode-summary/v1"
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    task_label: ShortText
    state: EpisodeState
    outcome: EpisodeOutcome
    verification: EpisodeVerification
    coverage: EpisodeCoverage
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    execution_id: Identifier | None = None
    test_case_id: Identifier | None = None
    lifecycle_run_id: Identifier | None = None
    operation: Identifier | None = None
    event_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    source_kind: Literal["published_episode_projection"] = "published_episode_projection"
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> EpisodeSummary:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not precede started_at")
        if self.state == EpisodeState.RUNNING.value:
            if self.ended_at is not None:
                raise ValueError("RUNNING episode cannot have ended_at")
            if self.outcome != EpisodeOutcome.UNKNOWN.value:
                raise ValueError("RUNNING episode outcome must be UNKNOWN")
        elif self.ended_at is None:
            raise ValueError("terminal episode requires ended_at")
        if self.verification == EpisodeVerification.VERIFIED.value and not self.evidence_ids:
            raise ValueError("VERIFIED episode requires evidence_ids")
        return self


class EpisodeAssetSummary(EpisodePublicModel):
    schema_version: Literal["rolo-episode-asset-summary/v1"] = (
        "rolo-episode-asset-summary/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    asset_id: Identifier
    modality: Identifier
    source_label: ShortText
    captured_at: AwareDatetime
    offset_ms: int = Field(ge=0)
    world_kind: EpisodeWorldKind
    evidence_kind: EpisodeEvidenceKind
    frame: Identifier | None = None
    clock_domain: Identifier
    synchronization: EpisodeSynchronization
    media_type: Annotated[
        str,
        StringConstraints(pattern=r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$"),
    ]
    byte_count: int | None = Field(default=None, ge=0)
    digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    data_classification: Literal["PUBLIC", "INTERNAL", "SENSITIVE", "SECRET"]
    evidence_id: Identifier | None = None
    availability: EpisodeAssetAvailability
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_availability(self) -> EpisodeAssetSummary:
        if self.data_classification == "SECRET" and self.availability != "REDACTED":
            raise ValueError("SECRET asset metadata must be REDACTED")
        if self.data_classification == "SECRET" and self.digest is not None:
            raise ValueError("SECRET asset metadata must not expose a digest")
        if self.availability == "AVAILABLE" and self.digest is None:
            raise ValueError("available asset metadata requires a digest")
        return self


class EpisodeFindingSummary(EpisodePublicModel):
    schema_version: Literal["rolo-episode-finding-summary/v1"] = (
        "rolo-episode-finding-summary/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    finding_id: Identifier
    kind: EpisodeFindingKind
    authority: EpisodeAuthority
    title: ShortText
    summary: SummaryText
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(ge=0)
    supporting_evidence_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    supporting_asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    contradicting_evidence_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification: EpisodeVerification
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_finding_semantics(self) -> EpisodeFindingSummary:
        if self.end_offset_ms < self.start_offset_ms:
            raise ValueError("finding end_offset_ms must not precede start_offset_ms")
        if not self.supporting_evidence_ids and not self.supporting_asset_ids:
            raise ValueError("finding requires supporting evidence or an observation asset")
        expected_authority = {
            EpisodeFindingKind.OBSERVED_FACT.value: EpisodeAuthority.OBSERVED.value,
            EpisodeFindingKind.CANDIDATE_CAUSE.value: EpisodeAuthority.INFERRED.value,
            EpisodeFindingKind.HUMAN_CONFIRMATION.value: EpisodeAuthority.HUMAN_CONFIRMED.value,
            EpisodeFindingKind.VERIFIED_OUTCOME.value: EpisodeAuthority.VERIFIED.value,
        }[self.kind]
        if self.authority != expected_authority:
            raise ValueError(f"{self.kind} finding requires {expected_authority} authority")
        if self.kind == EpisodeFindingKind.CANDIDATE_CAUSE.value:
            if self.verification == EpisodeVerification.VERIFIED.value:
                raise ValueError("candidate cause cannot be VERIFIED")
        elif self.kind == EpisodeFindingKind.VERIFIED_OUTCOME.value:
            if self.verification != EpisodeVerification.VERIFIED.value:
                raise ValueError("verified outcome requires VERIFIED verification")
        return self


class EpisodeTimelineEvent(EpisodePublicModel):
    schema_version: Literal["rolo-episode-timeline-event/v1"] = (
        "rolo-episode-timeline-event/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    event_id: Identifier
    sequence: int = Field(ge=0)
    offset_ms: int = Field(ge=0)
    occurred_at: AwareDatetime
    duration_ms: int | None = Field(default=None, ge=0)
    clock_domain: Identifier
    synchronization: EpisodeSynchronization
    lane: EpisodeTimelineLane
    title: ShortText
    summary: SummaryText
    severity: EpisodeSeverity
    authority: EpisodeAuthority
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    related_event_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    metrics: dict[str, float] = Field(default_factory=dict, max_length=32)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, float]) -> dict[str, float]:
        for name, number in value.items():
            if not _METRIC_NAME.fullmatch(name):
                raise ValueError(f"unsafe metric name: {name!r}")
            if not math.isfinite(number):
                raise ValueError(f"metric {name!r} must be finite")
        return value

    @model_validator(mode="after")
    def validate_event_authority(self) -> EpisodeTimelineEvent:
        if self.authority != EpisodeAuthority.DECLARED.value:
            if not self.evidence_ids and not self.asset_ids:
                raise ValueError("non-declared event requires evidence or an observation asset")
        return self


class EpisodeDetail(EpisodeSummary):
    schema_version: Literal["rolo-episode-detail/v1"] = "rolo-episode-detail/v1"
    as_of: AwareDatetime
    immutable: bool
    clock_domain: Identifier
    synchronization: EpisodeSynchronization
    available_lanes: list[EpisodeTimelineLane] = Field(default_factory=list, max_length=10)
    expected_behavior: SummaryText | None = None
    observed_behavior: SummaryText | None = None
    assets: list[EpisodeAssetSummary] = Field(default_factory=list, max_length=1_000)
    findings: list[EpisodeFindingSummary] = Field(default_factory=list, max_length=1_000)

    @model_validator(mode="after")
    def validate_detail(self) -> EpisodeDetail:
        if self.state == EpisodeState.RUNNING.value and self.immutable:
            raise ValueError("RUNNING episode cannot be immutable")
        if self.immutable and self.state not in {
            EpisodeState.COMPLETED.value,
            EpisodeState.FAILED.value,
            EpisodeState.CANCELLED.value,
            EpisodeState.PARTIAL.value,
        }:
            raise ValueError("only terminal episodes may be immutable")
        if len(self.assets) != self.asset_count:
            raise ValueError("asset_count must match assets")
        if len(self.findings) != self.finding_count:
            raise ValueError("finding_count must match findings")
        for child in [*self.assets, *self.findings]:
            if (
                child.robot_id != self.robot_id
                or child.episode_id != self.episode_id
                or child.revision != self.revision
            ):
                raise ValueError("episode child identity or revision does not match detail")
        if len(set(self.available_lanes)) != len(self.available_lanes):
            raise ValueError("available_lanes must not contain duplicates")
        if self.as_of < self.started_at:
            raise ValueError("as_of must not precede started_at")
        assets_by_id = {asset.asset_id: asset for asset in self.assets}
        for finding in self.findings:
            if not set(finding.supporting_asset_ids) <= assets_by_id.keys():
                raise ValueError("finding references an unknown supporting asset_id")
            if not finding.supporting_evidence_ids and not any(
                assets_by_id[asset_id].availability == EpisodeAssetAvailability.AVAILABLE.value
                for asset_id in finding.supporting_asset_ids
            ):
                raise ValueError("finding has no available supporting evidence")
            if finding.kind != EpisodeFindingKind.VERIFIED_OUTCOME.value:
                continue
            if any(
                assets_by_id[asset_id].world_kind != EpisodeWorldKind.PHYSICAL.value
                for asset_id in finding.supporting_asset_ids
            ):
                raise ValueError("non-physical assets cannot support a VERIFIED_OUTCOME")
        return self


class EpisodeCollection(EpisodePublicModel):
    schema_version: Literal["rolo-episode-collection/v1"] = "rolo-episode-collection/v1"
    robot_id: Identifier
    items: list[EpisodeSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=1)
    as_of: AwareDatetime
    source_kind: Literal["published_episode_projection"] = "published_episode_projection"
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_collection(self) -> EpisodeCollection:
        if len(self.items) > self.total:
            raise ValueError("collection items cannot exceed total")
        if any(item.robot_id != self.robot_id for item in self.items):
            raise ValueError("collection item robot_id does not match collection")
        return self


class EpisodeRevisionSummary(EpisodePublicModel):
    schema_version: Literal["rolo-episode-revision-summary/v1"] = (
        "rolo-episode-revision-summary/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    parent_revision: int | None = Field(default=None, ge=1)
    committed_at: AwareDatetime
    state: EpisodeState
    outcome: EpisodeOutcome
    verification: EpisodeVerification
    coverage: EpisodeCoverage
    immutable: bool
    event_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    is_current: bool
    source_kind: Literal[
        "committed_episode_record", "published_episode_projection"
    ]
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_lineage(self) -> EpisodeRevisionSummary:
        if self.source_kind == "committed_episode_record":
            if self.revision == 1 and self.parent_revision is not None:
                raise ValueError("revision 1 cannot have parent_revision")
            if self.revision > 1 and self.parent_revision != self.revision - 1:
                raise ValueError("committed revision must reference its immediate parent")
        return self


class EpisodeRevisionCollection(EpisodePublicModel):
    schema_version: Literal["rolo-episode-revision-collection/v1"] = (
        "rolo-episode-revision-collection/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    current_revision: int = Field(ge=1)
    items: list[EpisodeRevisionSummary]
    total: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=1)
    as_of: AwareDatetime
    source_kind: Literal["episode_revision_history"] = "episode_revision_history"
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_collection(self) -> EpisodeRevisionCollection:
        if len(self.items) > self.total:
            raise ValueError("revision collection items cannot exceed total")
        if any(
            item.robot_id != self.robot_id or item.episode_id != self.episode_id
            for item in self.items
        ):
            raise ValueError("revision collection item identity does not match collection")
        if sum(item.is_current for item in self.items) > 1:
            raise ValueError("revision collection page cannot contain multiple current revisions")
        return self


class EpisodeCohortMember(EpisodePublicModel):
    schema_version: Literal["rolo-episode-cohort-member/v1"] = "rolo-episode-cohort-member/v1"
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    task_label: ShortText
    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_ms: int = Field(ge=0)
    state: Literal["COMPLETED", "FAILED", "CANCELLED", "PARTIAL"]
    outcome: EpisodeOutcome
    verification: EpisodeVerification
    coverage: EpisodeCoverage
    immutable: Literal[True] = True
    is_current: Literal[True] = True
    event_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    source_kind: Literal["current_episode_publication"] = "current_episode_publication"
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_member(self) -> EpisodeCohortMember:
        if self.ended_at < self.started_at:
            raise ValueError("cohort member ended_at must not precede started_at")
        expected_duration = int((self.ended_at - self.started_at).total_seconds() * 1000)
        if self.duration_ms != expected_duration:
            raise ValueError("cohort member duration_ms does not match timestamps")
        return self


class EpisodeCohortExclusions(EpisodePublicModel):
    schema_version: Literal["rolo-episode-cohort-exclusions/v1"] = (
        "rolo-episode-cohort-exclusions/v1"
    )
    running: int = Field(default=0, ge=0)
    mutable: int = Field(default=0, ge=0)


class EpisodeCohort(EpisodePublicModel):
    schema_version: Literal["rolo-episode-cohort/v1"] = "rolo-episode-cohort/v1"
    robot_id: Identifier
    reference_episode_id: Identifier
    reference_revision: int = Field(ge=1)
    operation: Identifier
    test_case_id: Identifier
    expected_behavior_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    window_days: Literal[7, 30, 90]
    window_started_at: AwareDatetime
    window_ended_at: AwareDatetime
    items: list[EpisodeCohortMember] = Field(max_length=100)
    population_count: int = Field(ge=0)
    included_count: int = Field(ge=0, le=100)
    excluded_count: int = Field(ge=0)
    truncated_count: int = Field(ge=0)
    exclusions: EpisodeCohortExclusions
    coverage: Literal["COMPLETE", "BOUNDED_PARTIAL"]
    limit: int = Field(ge=1, le=100)
    as_of: AwareDatetime
    source_kind: Literal["published_episode_cohort"] = "published_episode_cohort"
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_cohort(self) -> EpisodeCohort:
        if self.window_started_at >= self.window_ended_at:
            raise ValueError("cohort window must have positive duration")
        if self.window_ended_at - self.window_started_at != timedelta(days=self.window_days):
            raise ValueError("cohort window timestamps do not match window_days")
        if self.included_count != len(self.items):
            raise ValueError("included_count must match cohort items")
        if self.excluded_count != self.exclusions.running + self.exclusions.mutable:
            raise ValueError("excluded_count must match exclusion categories")
        if self.population_count != (
            self.included_count + self.excluded_count + self.truncated_count
        ):
            raise ValueError("population_count arithmetic does not balance")
        expected_coverage = "BOUNDED_PARTIAL" if self.truncated_count else "COMPLETE"
        if self.coverage != expected_coverage:
            raise ValueError("cohort coverage does not match truncation")
        if any(item.robot_id != self.robot_id for item in self.items):
            raise ValueError("cohort member robot_id does not match cohort")
        identities = [(item.episode_id, item.revision) for item in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError("cohort member identity must be unique")
        if any(item.episode_id == self.reference_episode_id for item in self.items):
            raise ValueError("reference Episode identity cannot be a cohort member")
        if any(
            item.started_at < self.window_started_at or item.started_at >= self.window_ended_at
            for item in self.items
        ):
            raise ValueError("cohort member is outside the derived window")
        expected_order = sorted(
            self.items,
            key=lambda item: (item.started_at, item.episode_id, item.revision),
            reverse=True,
        )
        if self.items != expected_order:
            raise ValueError("cohort members must be newest-first")
        return self


class EpisodeTimelinePage(EpisodePublicModel):
    schema_version: Literal["rolo-episode-timeline-page/v1"] = (
        "rolo-episode-timeline-page/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    items: list[EpisodeTimelineEvent]
    limit: int = Field(ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=80)
    next_cursor: str | None = Field(default=None, max_length=80)
    as_of: AwareDatetime
    immutable: bool
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_page(self) -> EpisodeTimelinePage:
        previous_sequence = -1
        for item in self.items:
            if (
                item.robot_id != self.robot_id
                or item.episode_id != self.episode_id
                or item.revision != self.revision
            ):
                raise ValueError("timeline item identity or revision does not match page")
            if item.sequence <= previous_sequence:
                raise ValueError("timeline page items must be strictly ordered by sequence")
            previous_sequence = item.sequence
        return self


class PublishedEpisodeProjection(EpisodePublicModel):
    """Validated persistence envelope; never returned directly by the API."""

    schema_version: Literal["rolo-episode-published-projection/v1"] = (
        "rolo-episode-published-projection/v1"
    )
    detail: EpisodeDetail
    timeline: list[EpisodeTimelineEvent] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def validate_projection(self) -> PublishedEpisodeProjection:
        if len(self.timeline) != self.detail.event_count:
            raise ValueError("event_count must match timeline")
        sequences: set[int] = set()
        last_offset = -1
        lanes: set[str] = set()
        asset_ids = {asset.asset_id for asset in self.detail.assets}
        event_ids = {event.event_id for event in self.timeline}
        if len(event_ids) != len(self.timeline):
            raise ValueError("event_id must be unique inside an episode revision")
        for event in sorted(self.timeline, key=lambda item: item.sequence):
            if (
                event.robot_id != self.detail.robot_id
                or event.episode_id != self.detail.episode_id
                or event.revision != self.detail.revision
            ):
                raise ValueError("timeline event identity or revision does not match detail")
            if event.sequence in sequences:
                raise ValueError("timeline sequence must be unique inside an episode revision")
            sequences.add(event.sequence)
            if event.offset_ms < last_offset:
                raise ValueError("timeline offset_ms must be monotonic by sequence")
            last_offset = event.offset_ms
            lanes.add(event.lane)
            if not set(event.asset_ids) <= asset_ids:
                raise ValueError("timeline event references an unknown asset_id")
            if not set(event.related_event_ids) <= event_ids:
                raise ValueError("timeline event references an unknown related_event_id")
        if lanes != set(self.detail.available_lanes):
            raise ValueError("available_lanes must match timeline lanes")
        return self


class EpisodeRevisionConflict(ValueError):
    pass


class EpisodeCohortConflict(ValueError):
    pass


class EpisodeCursorError(ValueError):
    pass


def _reject_unsafe_public_content(value: Any, *, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if normalized in _FORBIDDEN_KEYS:
                raise ValueError(f"unsafe public Episode field at {location}.{key}")
            _reject_unsafe_public_content(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unsafe_public_content(child, location=f"{location}[{index}]")
    elif isinstance(value, str) and _UNSAFE_STRING.search(value):
        raise ValueError(f"unsafe public Episode string at {location}")


def _validate_publication_root(artifact_root: Path, root: Path) -> None:
    try:
        root.resolve().relative_to(artifact_root.resolve())
        relative = root.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError("Episode publication root escapes the artifact root") from exc
    current = artifact_root
    if current.exists() and current.is_symlink():
        raise ValueError("Episode artifact root must not be a symbolic link")
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Episode publication root contains a symbolic link")


def _publication_paths(artifact_root: Path, robot_id: str) -> list[Path]:
    layout = ArtifactLayout(artifact_root)
    root = layout.episode_publications(robot_id)
    _validate_publication_root(artifact_root, root)
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for candidate in root.iterdir():
        if candidate.suffix != ".json":
            continue
        expected = layout.episode_publication(robot_id, candidate.stem)
        if candidate.is_symlink() or candidate.resolve() != expected.resolve():
            raise ValueError("unsafe Episode publication path")
        if candidate.is_file():
            paths.append(candidate)
    if len(paths) > 1_000:
        raise ValueError("Episode publication count exceeds the bounded read-model limit")
    return paths


def _load_projection(path: Path, robot_id: str, episode_id: str) -> PublishedEpisodeProjection:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Episode publication is unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Episode publication must be an object")
    _reject_unsafe_public_content(raw)
    projection = PublishedEpisodeProjection.model_validate(raw)
    if projection.detail.robot_id != robot_id or projection.detail.episode_id != episode_id:
        raise ValueError("Episode publication identity does not match its location")
    return projection


def _projection_for(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
) -> PublishedEpisodeProjection | None:
    layout = ArtifactLayout(artifact_root)
    root = layout.episode_publications(robot_id)
    _validate_publication_root(artifact_root, root)
    path = layout.episode_publication(robot_id, episode_id)
    if not path.is_file():
        return None
    if path.is_symlink():
        raise ValueError("unsafe Episode publication path")
    return _load_projection(path, robot_id, episode_id)


def build_episode_collection(
    artifact_root: Path,
    robot_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    state: EpisodeState | None = None,
    limit: int = 50,
    offset: int = 0,
    as_of: datetime | None = None,
) -> EpisodeCollection:
    items: list[EpisodeSummary] = []
    for path in _publication_paths(artifact_root, robot_id):
        projection = _load_projection(path, robot_id, path.stem)
        detail = projection.detail
        if since is not None and detail.started_at < since:
            continue
        if until is not None and detail.started_at > until:
            continue
        if state is not None and detail.state != state.value:
            continue
        items.append(
            EpisodeSummary.model_validate(
                detail.model_dump(
                    exclude={
                        "as_of",
                        "immutable",
                        "clock_domain",
                        "synchronization",
                        "available_lanes",
                        "expected_behavior",
                        "observed_behavior",
                        "assets",
                        "findings",
                    }
                )
                | {"schema_version": "rolo-episode-summary/v1"}
            )
        )
    items.sort(key=lambda item: (item.started_at, item.episode_id), reverse=True)
    total = len(items)
    return EpisodeCollection(
        robot_id=robot_id,
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < total else None,
        as_of=as_of or utc_now(),
        limitations=[],
    )


def get_episode_detail(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    *,
    revision: int | None = None,
) -> EpisodeDetail | None:
    projection = _projection_for_revision(
        artifact_root,
        robot_id,
        episode_id,
        revision=revision,
    )
    return projection.detail if projection is not None else None


def _normalized_expected_behavior(value: str) -> str:
    return unicodedata.normalize("NFC", " ".join(value.split()))


def build_episode_cohort(
    artifact_root: Path,
    robot_id: str,
    reference_episode_id: str,
    reference_revision: int,
    *,
    window_days: Literal[7, 30, 90] = 30,
    limit: int = 100,
    as_of: datetime | None = None,
) -> EpisodeCohort | None:
    reference = get_episode_detail(
        artifact_root,
        robot_id,
        reference_episode_id,
        revision=reference_revision,
    )
    if reference is None:
        return None
    if not reference.operation or not reference.test_case_id or not reference.expected_behavior:
        raise EpisodeCohortConflict(
            "Episode cohort reference requires operation, test_case_id, and expected_behavior"
        )

    normalized_expected = _normalized_expected_behavior(reference.expected_behavior)
    if not normalized_expected:
        raise EpisodeCohortConflict(
            "Episode cohort reference requires a non-empty normalized expected_behavior"
        )
    window_ended_at = reference.started_at
    window_started_at = window_ended_at - timedelta(days=window_days)
    eligible: list[EpisodeCohortMember] = []
    running = 0
    mutable = 0
    for path in _publication_paths(artifact_root, robot_id):
        projection = _load_projection(path, robot_id, path.stem)
        detail = projection.detail
        if detail.episode_id == reference_episode_id:
            continue
        if (
            detail.operation != reference.operation
            or detail.test_case_id != reference.test_case_id
            or detail.expected_behavior is None
            or _normalized_expected_behavior(detail.expected_behavior) != normalized_expected
        ):
            continue
        if not (window_started_at <= detail.started_at < window_ended_at):
            continue
        if detail.state == EpisodeState.RUNNING.value:
            running += 1
            continue
        if not detail.immutable:
            mutable += 1
            continue
        if detail.ended_at is None:
            raise ValueError("terminal cohort member has no ended_at")
        eligible.append(
            EpisodeCohortMember(
                robot_id=robot_id,
                episode_id=detail.episode_id,
                revision=detail.revision,
                task_label=detail.task_label,
                started_at=detail.started_at,
                ended_at=detail.ended_at,
                duration_ms=int((detail.ended_at - detail.started_at).total_seconds() * 1000),
                state=detail.state,
                outcome=detail.outcome,
                verification=detail.verification,
                coverage=detail.coverage,
                event_count=detail.event_count,
                asset_count=detail.asset_count,
                finding_count=detail.finding_count,
                evidence_count=len(detail.evidence_ids),
                limitations=list(detail.limitations),
            )
        )

    eligible.sort(
        key=lambda item: (item.started_at, item.episode_id, item.revision),
        reverse=True,
    )
    returned = eligible[:limit]
    truncated = len(eligible) - len(returned)
    excluded = running + mutable
    limitations = []
    if truncated:
        limitations.append(
            "The exact-match cohort exceeds the returned member limit; "
            "distributions are bounded partial."
        )
    return EpisodeCohort(
        robot_id=robot_id,
        reference_episode_id=reference_episode_id,
        reference_revision=reference_revision,
        operation=reference.operation,
        test_case_id=reference.test_case_id,
        expected_behavior_sha256=sha256(normalized_expected.encode("utf-8")).hexdigest(),
        window_days=window_days,
        window_started_at=window_started_at,
        window_ended_at=window_ended_at,
        items=returned,
        population_count=len(eligible) + excluded,
        included_count=len(returned),
        excluded_count=excluded,
        truncated_count=truncated,
        exclusions=EpisodeCohortExclusions(running=running, mutable=mutable),
        coverage="BOUNDED_PARTIAL" if truncated else "COMPLETE",
        limit=limit,
        as_of=as_of or utc_now(),
        limitations=limitations,
    )


def _projection_for_revision(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    *,
    revision: int | None,
) -> PublishedEpisodeProjection | None:
    current = _projection_for(artifact_root, robot_id, episode_id)
    if current is None:
        return None
    if revision is None or revision == current.detail.revision:
        return current
    if revision > current.detail.revision:
        raise EpisodeRevisionConflict("Episode revision is not available")
    try:
        from rolo.episode_projection import (
            load_committed_episode_record,
            project_episode_record,
        )

        record = load_committed_episode_record(
            artifact_root,
            robot_id,
            episode_id,
            revision,
        )
    except FileNotFoundError as exc:
        raise EpisodeRevisionConflict("Episode revision is not available") from exc
    return project_episode_record(record)


def build_episode_revision_collection(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> EpisodeRevisionCollection | None:
    current = _projection_for(artifact_root, robot_id, episode_id)
    if current is None:
        return None

    from rolo.episode_projection import (
        load_committed_episode_record,
        project_episode_record,
    )

    records_root = ArtifactLayout(artifact_root).episode_records(robot_id, episode_id)
    _validate_publication_root(artifact_root, records_root)
    revisions: list[EpisodeRevisionSummary] = []
    limitations: list[str] = []
    if not records_root.is_dir():
        detail = current.detail
        revisions.append(
            EpisodeRevisionSummary(
                robot_id=robot_id,
                episode_id=episode_id,
                revision=detail.revision,
                parent_revision=None,
                committed_at=detail.as_of,
                state=detail.state,
                outcome=detail.outcome,
                verification=detail.verification,
                coverage=detail.coverage,
                immutable=detail.immutable,
                event_count=detail.event_count,
                asset_count=detail.asset_count,
                finding_count=detail.finding_count,
                is_current=True,
                source_kind="published_episode_projection",
                limitations=[
                    "Historical committed records are unavailable; only the current "
                    "published revision is readable."
                ],
            )
        )
        limitations.append(
            "Revision history is limited to the current independently published projection."
        )
    else:
        paths = list(records_root.iterdir())
        if len(paths) > 1_000:
            raise ValueError("Episode revision count exceeds the bounded read-model limit")
        available: set[int] = set()
        for path in paths:
            match = re.fullmatch(r"revision-([1-9][0-9]*)\.json", path.name)
            if match is None or path.is_symlink() or not path.is_file():
                raise ValueError("unsafe Episode revision record path")
            available.add(int(match.group(1)))
        expected = set(range(1, current.detail.revision + 1))
        if available != expected:
            raise ValueError(
                "Episode revision history is incomplete or exceeds current publication"
            )
        for revision in sorted(available, reverse=True):
            record = load_committed_episode_record(
                artifact_root,
                robot_id,
                episode_id,
                revision,
            )
            projection = (
                current
                if revision == current.detail.revision
                else project_episode_record(record)
            )
            detail = projection.detail
            revisions.append(
                EpisodeRevisionSummary(
                    robot_id=robot_id,
                    episode_id=episode_id,
                    revision=revision,
                    parent_revision=record.parent_revision,
                    committed_at=record.committed_at,
                    state=detail.state,
                    outcome=detail.outcome,
                    verification=detail.verification,
                    coverage=detail.coverage,
                    immutable=detail.immutable,
                    event_count=detail.event_count,
                    asset_count=detail.asset_count,
                    finding_count=detail.finding_count,
                    is_current=revision == current.detail.revision,
                    source_kind="committed_episode_record",
                    limitations=list(detail.limitations),
                )
            )

    total = len(revisions)
    return EpisodeRevisionCollection(
        robot_id=robot_id,
        episode_id=episode_id,
        current_revision=current.detail.revision,
        items=revisions[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < total else None,
        as_of=current.detail.as_of,
        limitations=limitations,
    )


def _cursor_for(robot_id: str, episode_id: str, revision: int, offset: int) -> str:
    material = f"{robot_id}\0{episode_id}\0{revision}\0{offset}".encode()
    return f"epcur_{sha256(material).hexdigest()[:40]}"


def build_episode_timeline_page(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    *,
    revision: int,
    limit: int = 100,
    cursor: str | None = None,
) -> EpisodeTimelinePage | None:
    projection = _projection_for_revision(
        artifact_root,
        robot_id,
        episode_id,
        revision=revision,
    )
    if projection is None:
        return None
    events = sorted(projection.timeline, key=lambda item: item.sequence)
    start = 0
    if cursor is not None:
        for candidate in range(1, len(events) + 1):
            if cursor == _cursor_for(robot_id, episode_id, revision, candidate):
                start = candidate
                break
        else:
            raise EpisodeCursorError("Episode timeline cursor is invalid for this revision")
    end = min(start + limit, len(events))
    return EpisodeTimelinePage(
        robot_id=robot_id,
        episode_id=episode_id,
        revision=revision,
        items=events[start:end],
        limit=limit,
        cursor=cursor,
        next_cursor=(
            _cursor_for(robot_id, episode_id, revision, end) if end < len(events) else None
        ),
        as_of=projection.detail.as_of,
        immutable=projection.detail.immutable,
        limitations=list(projection.detail.limitations),
    )
