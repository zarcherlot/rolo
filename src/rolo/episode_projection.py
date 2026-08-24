from __future__ import annotations

import json
from datetime import datetime
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

from rolo.core.persistence import atomic_write_text
from rolo.episode_read_models import (
    EpisodeAssetAvailability,
    EpisodeAssetSummary,
    EpisodeAuthority,
    EpisodeCoverage,
    EpisodeDetail,
    EpisodeEvidenceKind,
    EpisodeFindingKind,
    EpisodeFindingSummary,
    EpisodeOutcome,
    EpisodeSeverity,
    EpisodeState,
    EpisodeSynchronization,
    EpisodeTimelineEvent,
    EpisodeTimelineLane,
    EpisodeVerification,
    EpisodeWorldKind,
    Identifier,
    LimitationText,
    PublishedEpisodeProjection,
    ShortText,
    SummaryText,
    _load_projection,
    _publication_paths,
    _reject_unsafe_public_content,
)
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.workbench_read_models import evidence_id_for_reference

EvidenceReference = Annotated[str, StringConstraints(min_length=1, max_length=1_024)]


class EpisodeProducerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class EpisodeProducerEvent(EpisodeProducerModel):
    schema_version: Literal["rolo-episode-producer-event/v1"] = (
        "rolo-episode-producer-event/v1"
    )
    event_id: Identifier
    sequence: int = Field(ge=0)
    offset_ms: int = Field(ge=0)
    occurred_at: AwareDatetime
    duration_ms: int | None = Field(default=None, ge=0)
    clock_domain: Identifier
    synchronization: EpisodeSynchronization
    lane: EpisodeTimelineLane
    public_title: ShortText
    public_summary: SummaryText
    severity: EpisodeSeverity
    authority: EpisodeAuthority
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=256)
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    related_event_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    metrics: dict[str, float] = Field(default_factory=dict, max_length=32)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @field_validator("raw_payload")
    @classmethod
    def bound_raw_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 64 * 1_024:
            raise ValueError("raw event payload exceeds the 65536-byte limit")
        return value


class EpisodeProducerAsset(EpisodeProducerModel):
    schema_version: Literal["rolo-episode-producer-asset/v1"] = (
        "rolo-episode-producer-asset/v1"
    )
    asset_id: Identifier
    modality: Identifier
    public_source_label: ShortText
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
    availability: EpisodeAssetAvailability
    artifact_ref: EvidenceReference | None = None
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_asset_source(self) -> EpisodeProducerAsset:
        if self.availability == EpisodeAssetAvailability.AVAILABLE.value:
            if self.artifact_ref is None or self.digest is None:
                raise ValueError("available producer asset requires artifact_ref and digest")
        elif self.artifact_ref is not None:
            raise ValueError("unavailable producer asset cannot publish artifact_ref")
        return self


class EpisodeProducerFinding(EpisodeProducerModel):
    schema_version: Literal["rolo-episode-producer-finding/v1"] = (
        "rolo-episode-producer-finding/v1"
    )
    finding_id: Identifier
    kind: EpisodeFindingKind
    public_title: ShortText
    public_summary: SummaryText
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(ge=0)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=256)
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    contradicting_evidence_refs: list[EvidenceReference] = Field(
        default_factory=list,
        max_length=256,
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification: EpisodeVerification
    raw_analysis: dict[str, Any] = Field(default_factory=dict)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @field_validator("raw_analysis")
    @classmethod
    def bound_raw_analysis(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 64 * 1_024:
            raise ValueError("raw finding analysis exceeds the 65536-byte limit")
        return value

    @model_validator(mode="after")
    def validate_interval_and_verification(self) -> EpisodeProducerFinding:
        if self.end_offset_ms < self.start_offset_ms:
            raise ValueError("finding interval is reversed")
        if (
            self.kind == EpisodeFindingKind.CANDIDATE_CAUSE.value
            and self.verification == EpisodeVerification.VERIFIED.value
        ):
            raise ValueError("candidate cause cannot be VERIFIED")
        if (
            self.kind == EpisodeFindingKind.VERIFIED_OUTCOME.value
            and self.verification != EpisodeVerification.VERIFIED.value
        ):
            raise ValueError("verified outcome requires VERIFIED verification")
        return self


class EpisodeRecordContent(EpisodeProducerModel):
    schema_version: Literal["rolo-episode-producer-record/v1"] = (
        "rolo-episode-producer-record/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    revision: int = Field(ge=1)
    parent_revision: int | None = Field(default=None, ge=1)
    commit_id: Identifier
    committed: Literal[True]
    committed_at: AwareDatetime
    producer: Identifier
    task_label: ShortText
    state: EpisodeState
    outcome: EpisodeOutcome
    verification: EpisodeVerification
    coverage: EpisodeCoverage
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    immutable: bool
    execution_id: Identifier | None = None
    test_case_id: Identifier | None = None
    lifecycle_run_id: Identifier | None = None
    operation: Identifier | None = None
    clock_domain: Identifier
    synchronization: EpisodeSynchronization
    expected_behavior: SummaryText | None = None
    observed_behavior: SummaryText | None = None
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=256)
    events: list[EpisodeProducerEvent] = Field(default_factory=list, max_length=10_000)
    assets: list[EpisodeProducerAsset] = Field(default_factory=list, max_length=1_000)
    findings: list[EpisodeProducerFinding] = Field(default_factory=list, max_length=1_000)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_record(self) -> EpisodeRecordContent:
        if self.revision == 1 and self.parent_revision is not None:
            raise ValueError("revision 1 cannot have parent_revision")
        if self.revision > 1 and self.parent_revision != self.revision - 1:
            raise ValueError("revision must reference its immediate parent")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not precede started_at")
        if self.state == EpisodeState.RUNNING.value:
            if self.immutable or self.ended_at is not None:
                raise ValueError("RUNNING producer record must remain mutable and open")
            if self.outcome != EpisodeOutcome.UNKNOWN.value:
                raise ValueError("RUNNING producer record outcome must be UNKNOWN")
        else:
            if self.ended_at is None:
                raise ValueError("terminal producer record requires ended_at")
            if not self.immutable:
                raise ValueError("terminal committed producer record must be immutable")
        if self.committed_at < self.started_at:
            raise ValueError("committed_at must not precede started_at")

        event_ids = {item.event_id for item in self.events}
        asset_ids = {item.asset_id for item in self.assets}
        finding_ids = {item.finding_id for item in self.findings}
        if len(event_ids) != len(self.events):
            raise ValueError("producer event_id must be unique")
        if len(asset_ids) != len(self.assets):
            raise ValueError("producer asset_id must be unique")
        if len(finding_ids) != len(self.findings):
            raise ValueError("producer finding_id must be unique")
        sequences: set[int] = set()
        last_offset = -1
        for event in sorted(self.events, key=lambda item: item.sequence):
            if event.sequence in sequences:
                raise ValueError("producer event sequence must be unique")
            sequences.add(event.sequence)
            if event.offset_ms < last_offset:
                raise ValueError("producer event offsets must be monotonic by sequence")
            last_offset = event.offset_ms
            if not set(event.asset_ids) <= asset_ids:
                raise ValueError("producer event references unknown asset_id")
            if not set(event.related_event_ids) <= event_ids:
                raise ValueError("producer event references unknown related_event_id")
        for finding in self.findings:
            if not set(finding.asset_ids) <= asset_ids:
                raise ValueError("producer finding references unknown asset_id")
        return self


def episode_record_content_sha256(value: dict[str, Any] | EpisodeRecordContent) -> str:
    if isinstance(value, EpisodeRecordContent):
        content = value.model_dump(mode="json", exclude={"content_sha256"})
    else:
        raw = dict(value)
        raw.pop("content_sha256", None)
        content = EpisodeRecordContent.model_validate(raw).model_dump(mode="json")
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class CommittedEpisodeRecord(EpisodeRecordContent):
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_digest(self) -> CommittedEpisodeRecord:
        expected = episode_record_content_sha256(self)
        if self.content_sha256 != expected:
            raise ValueError("Episode producer record content digest mismatch")
        return self


class EpisodeEvidenceSpec(EpisodeProducerModel):
    evidence_id: Identifier
    reference: EvidenceReference
    title: ShortText
    summary: SummaryText
    authority: Literal["OBSERVED", "GATED"]
    source_kind: Literal[
        "episode_record",
        "episode_event",
        "episode_asset",
        "episode_finding",
    ]
    integrity_status: Literal["validated", "verified"]
    observed_at: AwareDatetime
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)


def _unique_limitations(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))[:32]


def _evidence_ids(robot_id: str, references: list[str]) -> list[str]:
    return list(dict.fromkeys(evidence_id_for_reference(robot_id, value) for value in references))


def _require_artifact_path(artifact_root: Path, path: Path) -> None:
    if artifact_root.exists() and artifact_root.is_symlink():
        raise ValueError("Episode artifact root must not be a symbolic link")
    try:
        path.resolve().relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise ValueError("Episode path escapes the artifact root") from exc
    current = artifact_root
    try:
        relative = path.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError("Episode path is not rooted in the artifact store") from exc
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Episode path contains a symbolic link")


def _worst_synchronization(record: EpisodeRecordContent) -> str:
    rank = {
        EpisodeSynchronization.SYNCED.value: 0,
        EpisodeSynchronization.UNKNOWN.value: 1,
        EpisodeSynchronization.DEGRADED.value: 2,
        EpisodeSynchronization.UNSYNCED.value: 3,
    }
    values = [record.synchronization]
    values.extend(event.synchronization for event in record.events)
    values.extend(asset.synchronization for asset in record.assets)
    return max(values, key=rank.__getitem__)


def project_episode_record(record: CommittedEpisodeRecord) -> PublishedEpisodeProjection:
    limitations = list(record.limitations)
    public_assets: list[EpisodeAssetSummary] = []
    available_asset_ids: set[str] = set()
    for asset in record.assets:
        asset_limitations = list(asset.limitations)
        availability = asset.availability
        digest = asset.digest
        evidence_id = (
            evidence_id_for_reference(record.robot_id, asset.artifact_ref)
            if asset.artifact_ref is not None
            else None
        )
        if asset.data_classification == "SECRET":
            availability = EpisodeAssetAvailability.REDACTED.value
            digest = None
            evidence_id = None
            asset_limitations.append(
                "SECRET observation metadata is redacted by the control plane."
            )
        elif availability == EpisodeAssetAvailability.AVAILABLE.value:
            available_asset_ids.add(asset.asset_id)
        else:
            asset_limitations.append("Observation asset evidence is unavailable.")
            limitations.append(f"Asset {asset.asset_id} has no available observation evidence.")
        public_assets.append(
            EpisodeAssetSummary(
                robot_id=record.robot_id,
                episode_id=record.episode_id,
                revision=record.revision,
                asset_id=asset.asset_id,
                modality=asset.modality,
                source_label=asset.public_source_label,
                captured_at=asset.captured_at,
                offset_ms=asset.offset_ms,
                world_kind=asset.world_kind,
                evidence_kind=asset.evidence_kind,
                frame=asset.frame,
                clock_domain=asset.clock_domain,
                synchronization=asset.synchronization,
                media_type=asset.media_type,
                byte_count=asset.byte_count,
                digest=digest,
                data_classification=asset.data_classification,
                evidence_id=evidence_id,
                availability=availability,
                limitations=_unique_limitations(asset_limitations),
            )
        )

    public_events: list[EpisodeTimelineEvent] = []
    for event in sorted(record.events, key=lambda item: item.sequence):
        event_limitations = list(event.limitations)
        evidence_ids = _evidence_ids(record.robot_id, event.evidence_refs)
        usable_asset_ids = set(event.asset_ids) & available_asset_ids
        lane = event.lane
        authority = event.authority
        title = event.public_title
        summary = event.public_summary
        severity = event.severity
        metrics = event.metrics
        if authority != EpisodeAuthority.DECLARED.value and not (
            evidence_ids or usable_asset_ids
        ):
            lane = EpisodeTimelineLane.ALERT.value
            authority = EpisodeAuthority.DECLARED.value
            title = "Evidence unavailable"
            summary = (
                "The producer committed event metadata, but no supporting public evidence "
                "or available observation asset was committed."
            )
            severity = EpisodeSeverity.WARNING.value
            metrics = {}
            event_limitations.append(
                "The original non-declared event was withheld because its evidence is missing."
            )
            limitations.append(f"Event {event.event_id} was reduced to a missing-evidence alert.")
        public_events.append(
            EpisodeTimelineEvent(
                robot_id=record.robot_id,
                episode_id=record.episode_id,
                revision=record.revision,
                event_id=event.event_id,
                sequence=event.sequence,
                offset_ms=event.offset_ms,
                occurred_at=event.occurred_at,
                duration_ms=event.duration_ms,
                clock_domain=event.clock_domain,
                synchronization=event.synchronization,
                lane=lane,
                title=title,
                summary=summary,
                severity=severity,
                authority=authority,
                evidence_ids=evidence_ids,
                asset_ids=event.asset_ids,
                related_event_ids=event.related_event_ids,
                metrics=metrics,
                limitations=_unique_limitations(event_limitations),
            )
        )

    authority_for_kind = {
        EpisodeFindingKind.OBSERVED_FACT.value: EpisodeAuthority.OBSERVED.value,
        EpisodeFindingKind.CANDIDATE_CAUSE.value: EpisodeAuthority.INFERRED.value,
        EpisodeFindingKind.HUMAN_CONFIRMATION.value: EpisodeAuthority.HUMAN_CONFIRMED.value,
        EpisodeFindingKind.VERIFIED_OUTCOME.value: EpisodeAuthority.VERIFIED.value,
    }
    public_findings: list[EpisodeFindingSummary] = []
    for finding in record.findings:
        evidence_ids = _evidence_ids(record.robot_id, finding.evidence_refs)
        usable_assets = [value for value in finding.asset_ids if value in available_asset_ids]
        if not evidence_ids and not usable_assets:
            limitations.append(
                f"Finding {finding.finding_id} was withheld because supporting evidence is missing."
            )
            continue
        public_findings.append(
            EpisodeFindingSummary(
                robot_id=record.robot_id,
                episode_id=record.episode_id,
                revision=record.revision,
                finding_id=finding.finding_id,
                kind=finding.kind,
                authority=authority_for_kind[finding.kind],
                title=finding.public_title,
                summary=finding.public_summary,
                start_offset_ms=finding.start_offset_ms,
                end_offset_ms=finding.end_offset_ms,
                supporting_evidence_ids=evidence_ids,
                supporting_asset_ids=usable_assets,
                contradicting_evidence_ids=_evidence_ids(
                    record.robot_id,
                    finding.contradicting_evidence_refs,
                ),
                confidence=finding.confidence,
                verification=finding.verification,
                limitations=finding.limitations,
            )
        )

    synchronization = _worst_synchronization(record)
    if synchronization != EpisodeSynchronization.SYNCED.value:
        limitations.append(
            "Timeline clock synchronization is degraded or unavailable; offset_ms remains "
            "the ordering authority."
        )
    coverage = record.coverage
    if coverage != EpisodeCoverage.METADATA_ONLY.value and (
        synchronization != EpisodeSynchronization.SYNCED.value
        or len(public_findings) != len(record.findings)
        or any(
            asset.availability != EpisodeAssetAvailability.AVAILABLE.value
            for asset in record.assets
        )
    ):
        coverage = EpisodeCoverage.PARTIAL.value

    detail = EpisodeDetail(
        robot_id=record.robot_id,
        episode_id=record.episode_id,
        revision=record.revision,
        task_label=record.task_label,
        state=record.state,
        outcome=record.outcome,
        verification=record.verification,
        coverage=coverage,
        started_at=record.started_at,
        ended_at=record.ended_at,
        execution_id=record.execution_id,
        test_case_id=record.test_case_id,
        lifecycle_run_id=record.lifecycle_run_id,
        operation=record.operation,
        event_count=len(public_events),
        asset_count=len(public_assets),
        finding_count=len(public_findings),
        evidence_ids=_evidence_ids(record.robot_id, record.evidence_refs),
        limitations=_unique_limitations(limitations),
        as_of=record.committed_at,
        immutable=record.immutable,
        clock_domain=record.clock_domain,
        synchronization=synchronization,
        available_lanes=sorted({event.lane for event in public_events}),
        expected_behavior=record.expected_behavior,
        observed_behavior=record.observed_behavior,
        assets=public_assets,
        findings=public_findings,
    )
    projection = PublishedEpisodeProjection(detail=detail, timeline=public_events)
    _reject_unsafe_public_content(projection.model_dump(mode="json"))
    return projection


def write_committed_episode_record(
    artifact_root: Path,
    record: CommittedEpisodeRecord,
) -> Path:
    path = ArtifactLayout(artifact_root).episode_record(
        record.robot_id,
        record.episode_id,
        record.revision,
    )
    _require_artifact_path(artifact_root, path)
    encoded = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if path.is_file():
        existing = CommittedEpisodeRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if existing.content_sha256 == record.content_sha256:
            return path
        raise FileExistsError("committed Episode revision already exists with different content")
    try:
        atomic_write_text(path, encoded, require_absent=True)
    except FileExistsError:
        existing = CommittedEpisodeRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if existing.content_sha256 != record.content_sha256:
            raise FileExistsError(
                "committed Episode revision already exists with different content"
            ) from None
    return path


def publish_episode_record(
    artifact_root: Path,
    record: CommittedEpisodeRecord,
) -> PublishedEpisodeProjection:
    projection = project_episode_record(record)
    path = ArtifactLayout(artifact_root).episode_publication(record.robot_id, record.episode_id)
    _require_artifact_path(artifact_root, path)
    current: PublishedEpisodeProjection | None = None
    if path.is_file():
        current = _load_projection(path, record.robot_id, record.episode_id)
        if current.detail.revision > record.revision:
            raise ValueError("cannot replace a newer Episode publication")
        if current.detail.revision == record.revision:
            if current.model_dump(mode="json") != projection.model_dump(mode="json"):
                raise ValueError("published Episode revision has conflicting content")
        if current.detail.immutable:
            if current.detail.revision != record.revision:
                raise ValueError("cannot supersede an immutable Episode publication")
    write_committed_episode_record(artifact_root, record)
    if current is not None and current.detail.revision == record.revision:
        return current
    atomic_write_text(
        path,
        json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
    )
    return projection


def load_committed_episode_record(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    revision: int,
) -> CommittedEpisodeRecord:
    path = ArtifactLayout(artifact_root).episode_record(robot_id, episode_id, revision)
    _require_artifact_path(artifact_root, path)
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("committed Episode record is unavailable")
    record = CommittedEpisodeRecord.model_validate_json(path.read_text(encoding="utf-8"))
    if (
        record.robot_id != robot_id
        or record.episode_id != episode_id
        or record.revision != revision
    ):
        raise ValueError("committed Episode record identity does not match its location")
    return record


def episode_evidence_specs(
    artifact_root: Path,
    robot_id: str,
) -> dict[str, EpisodeEvidenceSpec]:
    specs: dict[str, EpisodeEvidenceSpec] = {}

    def add(
        reference: str,
        *,
        title: str,
        summary: str,
        authority: Literal["OBSERVED", "GATED"],
        source_kind: Literal[
            "episode_record",
            "episode_event",
            "episode_asset",
            "episode_finding",
        ],
        observed_at: datetime,
        limitations: list[str],
    ) -> None:
        evidence_id = evidence_id_for_reference(robot_id, reference)
        candidate = EpisodeEvidenceSpec(
            evidence_id=evidence_id,
            reference=reference,
            title=title,
            summary=summary,
            authority=authority,
            source_kind=source_kind,
            integrity_status="verified" if authority == "GATED" else "validated",
            observed_at=observed_at,
            confidence=1.0 if authority == "GATED" else 0.8,
            limitations=limitations,
        )
        current = specs.get(evidence_id)
        if current is None or (current.authority == "OBSERVED" and authority == "GATED"):
            specs[evidence_id] = candidate

    for publication_path in _publication_paths(artifact_root, robot_id):
        projection = _load_projection(publication_path, robot_id, publication_path.stem)
        try:
            record = load_committed_episode_record(
                artifact_root,
                robot_id,
                projection.detail.episode_id,
                projection.detail.revision,
            )
        except FileNotFoundError:
            # E1 allowed independently published sanitized projections. They remain readable,
            # but cannot create resolvable Evidence records without their E2 producer record.
            continue
        record_path = ArtifactLayout(artifact_root).episode_record(
            robot_id,
            record.episode_id,
            record.revision,
        )
        record_reference = ArtifactLayout(artifact_root).ref(record_path)
        add(
            record_reference,
            title=f"Committed Episode record: {record.task_label}",
            summary="Digest-validated producer metadata for one committed Episode revision.",
            authority="GATED" if record.verification == "VERIFIED" else "OBSERVED",
            source_kind="episode_record",
            observed_at=record.committed_at,
            limitations=["The raw producer record and its business payload are withheld."],
        )
        for reference in record.evidence_refs:
            record_authority: Literal["OBSERVED", "GATED"] = (
                "GATED" if record.verification == "VERIFIED" else "OBSERVED"
            )
            add(
                reference,
                title=f"Episode outcome evidence: {record.task_label}",
                summary="The committed Episode revision references this outcome evidence.",
                authority=record_authority,
                source_kind="episode_record",
                observed_at=record.committed_at,
                limitations=(
                    ["Verification remains scoped to the committed Episode outcome."]
                    if record_authority == "GATED"
                    else ["Episode outcome evidence is not independently verified."]
                ),
            )
        for event in record.events:
            authority: Literal["OBSERVED", "GATED"] = (
                "GATED" if event.authority == EpisodeAuthority.VERIFIED.value else "OBSERVED"
            )
            for reference in event.evidence_refs:
                add(
                    reference,
                    title=f"Episode event evidence: {event.public_title}",
                    summary="A committed Episode event references this evidence.",
                    authority=authority,
                    source_kind="episode_event",
                    observed_at=event.occurred_at,
                    limitations=(
                        ["This evidence supports an advisory inference, not a verified outcome."]
                        if event.authority == EpisodeAuthority.INFERRED.value
                        else []
                    ),
                )
        for asset in record.assets:
            if asset.artifact_ref is None or asset.data_classification == "SECRET":
                continue
            add(
                asset.artifact_ref,
                title=f"Episode observation asset: {asset.public_source_label}",
                summary="Sanitized metadata for a committed Episode observation asset.",
                authority="OBSERVED",
                source_kind="episode_asset",
                observed_at=asset.captured_at,
                limitations=["Asset bytes and storage location are not exposed."],
            )
        for finding in record.findings:
            authority = (
                "GATED"
                if finding.kind == EpisodeFindingKind.VERIFIED_OUTCOME.value
                else "OBSERVED"
            )
            for reference in [*finding.evidence_refs, *finding.contradicting_evidence_refs]:
                add(
                    reference,
                    title=f"Episode finding evidence: {finding.public_title}",
                    summary="A committed Episode finding references this bounded evidence.",
                    authority=authority,
                    source_kind="episode_finding",
                    observed_at=record.committed_at,
                    limitations=(
                        ["Candidate causes remain advisory until independently verified."]
                        if finding.kind == EpisodeFindingKind.CANDIDATE_CAUSE.value
                        else []
                    ),
                )
    return specs
