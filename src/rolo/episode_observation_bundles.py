from __future__ import annotations

import json
from enum import Enum
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
from rolo.episode_projection import _require_artifact_path
from rolo.episode_read_models import (
    EpisodeCursorError,
    EpisodePublicModel,
    EpisodeRevisionConflict,
    EpisodeSynchronization,
    EpisodeWorldKind,
    Identifier,
    LimitationText,
    PublishedEpisodeProjection,
    ShortText,
    _projection_for_revision,
    _reject_unsafe_public_content,
    _validate_publication_root,
)
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.workbench_read_models import evidence_id_for_reference

EvidenceReference = Annotated[str, StringConstraints(min_length=1, max_length=1_024)]
InternalText = Annotated[str, StringConstraints(min_length=1, max_length=1_024)]


class ObservationBundleTrigger(str, Enum):
    INITIAL = "INITIAL"
    SUPPLEMENTARY = "SUPPLEMENTARY"


class ObservationBundleStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationSourceKind(str, Enum):
    ONBOARD_SENSOR = "ONBOARD_SENSOR"
    EXTERNAL_MEASUREMENT = "EXTERNAL_MEASUREMENT"
    ROBOT_STATE = "ROBOT_STATE"
    SPATIAL_MODEL = "SPATIAL_MODEL"
    DETERMINISTIC_RENDER = "DETERMINISTIC_RENDER"
    TRUSTED_GUI_CAPTURE = "TRUSTED_GUI_CAPTURE"
    SIMULATION = "SIMULATION"


class ObservationSourceAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    STALE = "STALE"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationSpatialAlignment(str, Enum):
    ALIGNED = "ALIGNED"
    DEGRADED = "DEGRADED"
    UNALIGNED = "UNALIGNED"
    UNKNOWN = "UNKNOWN"


class ObservationWorldScope(str, Enum):
    NONE = "NONE"
    PHYSICAL_ONLY = "PHYSICAL_ONLY"
    SIMULATED_ONLY = "SIMULATED_ONLY"
    REPLAYED_ONLY = "REPLAYED_ONLY"
    MIXED = "MIXED"


class EpisodeObservationSourceCoverage(EpisodePublicModel):
    schema_version: Literal["rolo-episode-observation-source-coverage/v1"] = (
        "rolo-episode-observation-source-coverage/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    episode_revision: int = Field(ge=1)
    bundle_id: Identifier
    source_id: Identifier
    label: ShortText
    source_kind: ObservationSourceKind
    modality: Identifier
    world_kind: EpisodeWorldKind
    availability: ObservationSourceAvailability
    synchronization: EpisodeSynchronization
    spatial_alignment: ObservationSpatialAlignment
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_source_semantics(self) -> EpisodeObservationSourceCoverage:
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("observation source asset_ids must be unique")
        if self.availability in {
            ObservationSourceAvailability.MISSING.value,
            ObservationSourceAvailability.REJECTED.value,
            ObservationSourceAvailability.UNAVAILABLE.value,
        } and self.asset_ids:
            raise ValueError("non-bearing observation source cannot reference assets")
        degraded = (
            self.availability != ObservationSourceAvailability.AVAILABLE.value
            or self.synchronization != EpisodeSynchronization.SYNCED.value
            or self.spatial_alignment != ObservationSpatialAlignment.ALIGNED.value
        )
        if degraded and not self.limitations:
            raise ValueError("degraded observation source requires limitations")
        return self


def _world_scope_for_sources(
    sources: list[EpisodeObservationSourceCoverage],
) -> str:
    world_kinds = {source.world_kind for source in sources if source.asset_ids}
    if not world_kinds:
        return ObservationWorldScope.NONE.value
    if len(world_kinds) > 1:
        return ObservationWorldScope.MIXED.value
    world_kind = next(iter(world_kinds))
    return {
        EpisodeWorldKind.PHYSICAL.value: ObservationWorldScope.PHYSICAL_ONLY.value,
        EpisodeWorldKind.SIMULATED.value: ObservationWorldScope.SIMULATED_ONLY.value,
        EpisodeWorldKind.REPLAYED.value: ObservationWorldScope.REPLAYED_ONLY.value,
    }[world_kind]


class EpisodeObservationBundleSummary(EpisodePublicModel):
    schema_version: Literal["rolo-episode-observation-bundle-summary/v1"] = (
        "rolo-episode-observation-bundle-summary/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    episode_revision: int = Field(ge=1)
    bundle_id: Identifier
    sequence: int = Field(ge=1)
    parent_bundle_id: Identifier | None = None
    trigger_kind: ObservationBundleTrigger
    status: ObservationBundleStatus
    created_at: AwareDatetime
    window_start_offset_ms: int = Field(ge=0)
    window_end_offset_ms: int = Field(gt=0)
    synchronization: EpisodeSynchronization
    spatial_alignment: ObservationSpatialAlignment
    world_scope: ObservationWorldScope
    sources: list[EpisodeObservationSourceCoverage] = Field(default_factory=list, max_length=64)
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)
    influences_verification: Literal[False] = False

    @model_validator(mode="after")
    def validate_bundle_semantics(self) -> EpisodeObservationBundleSummary:
        if self.window_end_offset_ms <= self.window_start_offset_ms:
            raise ValueError("observation bundle window must be positive")
        source_ids = [source.source_id for source in self.sources]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("observation bundle source_id must be unique")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("observation bundle asset_ids must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("observation bundle evidence_ids must be unique")
        source_assets = [asset_id for source in self.sources for asset_id in source.asset_ids]
        if len(set(source_assets)) != len(source_assets):
            raise ValueError("observation asset cannot belong to multiple source records")
        if set(source_assets) != set(self.asset_ids):
            raise ValueError("bundle asset_ids must exactly match source asset_ids")
        for source in self.sources:
            if (
                source.robot_id != self.robot_id
                or source.episode_id != self.episode_id
                or source.episode_revision != self.episode_revision
                or source.bundle_id != self.bundle_id
            ):
                raise ValueError("observation source identity does not match bundle")
        if self.world_scope != _world_scope_for_sources(self.sources):
            raise ValueError("observation bundle world_scope is inconsistent")
        if self.status == ObservationBundleStatus.UNAVAILABLE.value and self.asset_ids:
            raise ValueError("unavailable observation bundle cannot reference assets")
        if self.status == ObservationBundleStatus.COMPLETE.value and any(
            source.availability
            in {
                ObservationSourceAvailability.MISSING.value,
                ObservationSourceAvailability.REJECTED.value,
                ObservationSourceAvailability.UNAVAILABLE.value,
            }
            for source in self.sources
        ):
            raise ValueError("complete observation bundle cannot contain absent sources")
        degraded = (
            self.status != ObservationBundleStatus.COMPLETE.value
            or self.synchronization != EpisodeSynchronization.SYNCED.value
            or self.spatial_alignment != ObservationSpatialAlignment.ALIGNED.value
            or self.world_scope == ObservationWorldScope.MIXED.value
        )
        if degraded and not self.limitations:
            raise ValueError("degraded observation bundle requires limitations")
        return self


class EpisodeObservationBundleCollection(EpisodePublicModel):
    schema_version: Literal["rolo-episode-observation-bundle-collection/v1"] = (
        "rolo-episode-observation-bundle-collection/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    episode_revision: int = Field(ge=1)
    items: list[EpisodeObservationBundleSummary]
    limit: int = Field(ge=1, le=20)
    cursor: str | None = Field(default=None, max_length=80)
    next_cursor: str | None = Field(default=None, max_length=80)
    as_of: AwareDatetime
    immutable: Literal[True] = True
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_page(self) -> EpisodeObservationBundleCollection:
        previous_sequence: int | None = None
        for item in self.items:
            if (
                item.robot_id != self.robot_id
                or item.episode_id != self.episode_id
                or item.episode_revision != self.episode_revision
            ):
                raise ValueError("observation bundle identity or revision does not match page")
            if previous_sequence is not None and item.sequence >= previous_sequence:
                raise ValueError("observation bundle page must be newest-first")
            previous_sequence = item.sequence
        return self


class PublishedEpisodeObservationBundleProjection(EpisodePublicModel):
    """Validated server-owned envelope; never returned directly by the API."""

    schema_version: Literal["rolo-episode-observation-bundle-published-projection/v1"] = (
        "rolo-episode-observation-bundle-published-projection/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    episode_revision: int = Field(ge=1)
    as_of: AwareDatetime
    immutable: Literal[True] = True
    items: list[EpisodeObservationBundleSummary] = Field(default_factory=list, max_length=100)
    limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_projection(self) -> PublishedEpisodeObservationBundleProjection:
        bundle_ids = [item.bundle_id for item in self.items]
        sequences = [item.sequence for item in self.items]
        if len(set(bundle_ids)) != len(bundle_ids):
            raise ValueError("observation bundle_id must be unique")
        if len(set(sequences)) != len(sequences):
            raise ValueError("observation bundle sequence must be unique")
        if sequences != sorted(sequences, reverse=True):
            raise ValueError("observation bundles must be newest-first")
        by_id = {item.bundle_id: item for item in self.items}
        for item in self.items:
            if (
                item.robot_id != self.robot_id
                or item.episode_id != self.episode_id
                or item.episode_revision != self.episode_revision
            ):
                raise ValueError("observation bundle identity does not match projection")
            if item.parent_bundle_id is None:
                if item.trigger_kind == ObservationBundleTrigger.SUPPLEMENTARY.value:
                    raise ValueError("supplementary observation bundle requires a parent")
                continue
            parent = by_id.get(item.parent_bundle_id)
            if parent is None:
                raise ValueError("observation bundle parent is unavailable")
            if parent.sequence >= item.sequence:
                raise ValueError("observation bundle parent must have a lower sequence")
        return self


class ObservationProducerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


def _bound_internal_mapping(value: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 64 * 1_024:
        raise ValueError("observation internal metadata exceeds the 65536-byte limit")
    return value


class EpisodeObservationProducerSource(ObservationProducerModel):
    schema_version: Literal["rolo-episode-observation-producer-source/v1"] = (
        "rolo-episode-observation-producer-source/v1"
    )
    source_id: Identifier
    public_label: ShortText
    source_kind: ObservationSourceKind
    modality: Identifier
    world_kind: EpisodeWorldKind
    availability: ObservationSourceAvailability
    synchronization: EpisodeSynchronization
    spatial_alignment: ObservationSpatialAlignment
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=256)
    public_limitations: list[LimitationText] = Field(default_factory=list, max_length=32)
    provider_identity: InternalText | None = None
    topic_name: InternalText | None = None
    device_path: InternalText | None = None
    internal_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("internal_metadata")
    @classmethod
    def bound_internal_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _bound_internal_mapping(value)


class EpisodeObservationProducerBundle(ObservationProducerModel):
    schema_version: Literal["rolo-episode-observation-producer-bundle/v1"] = (
        "rolo-episode-observation-producer-bundle/v1"
    )
    bundle_id: Identifier
    sequence: int = Field(ge=1)
    parent_bundle_id: Identifier | None = None
    trigger_kind: ObservationBundleTrigger
    status: ObservationBundleStatus
    created_at: AwareDatetime
    window_start_offset_ms: int = Field(ge=0)
    window_end_offset_ms: int = Field(gt=0)
    synchronization: EpisodeSynchronization
    spatial_alignment: ObservationSpatialAlignment
    sources: list[EpisodeObservationProducerSource] = Field(default_factory=list, max_length=64)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=256)
    public_limitations: list[LimitationText] = Field(default_factory=list, max_length=32)
    raw_context: dict[str, Any] = Field(default_factory=dict)
    influences_verification: Literal[False] = False

    @field_validator("raw_context")
    @classmethod
    def bound_raw_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _bound_internal_mapping(value)


class EpisodeObservationRecordContent(ObservationProducerModel):
    schema_version: Literal["rolo-episode-observation-producer-record/v1"] = (
        "rolo-episode-observation-producer-record/v1"
    )
    robot_id: Identifier
    episode_id: Identifier
    episode_revision: int = Field(ge=1)
    record_id: Identifier
    committed: Literal[True]
    committed_at: AwareDatetime
    producer: Identifier
    bundles: list[EpisodeObservationProducerBundle] = Field(default_factory=list, max_length=100)
    public_limitations: list[LimitationText] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_record(self) -> EpisodeObservationRecordContent:
        bundle_ids = {bundle.bundle_id for bundle in self.bundles}
        sequences = {bundle.sequence for bundle in self.bundles}
        if len(bundle_ids) != len(self.bundles):
            raise ValueError("producer observation bundle_id must be unique")
        if len(sequences) != len(self.bundles):
            raise ValueError("producer observation sequence must be unique")
        by_id = {bundle.bundle_id: bundle for bundle in self.bundles}
        for bundle in self.bundles:
            if bundle.parent_bundle_id is None:
                if bundle.trigger_kind == ObservationBundleTrigger.SUPPLEMENTARY.value:
                    raise ValueError("supplementary producer bundle requires a parent")
                continue
            parent = by_id.get(bundle.parent_bundle_id)
            if parent is None or parent.sequence >= bundle.sequence:
                raise ValueError("producer observation parent must be an earlier bundle")
        return self


def episode_observation_record_content_sha256(
    value: dict[str, Any] | EpisodeObservationRecordContent,
) -> str:
    if isinstance(value, EpisodeObservationRecordContent):
        content = value.model_dump(mode="json", exclude={"content_sha256"})
    else:
        raw = dict(value)
        raw.pop("content_sha256", None)
        content = EpisodeObservationRecordContent.model_validate(raw).model_dump(mode="json")
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class CommittedEpisodeObservationRecord(EpisodeObservationRecordContent):
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_digest(self) -> CommittedEpisodeObservationRecord:
        expected = episode_observation_record_content_sha256(self)
        if self.content_sha256 != expected:
            raise ValueError("Episode observation record content digest mismatch")
        return self


def _unique(values: list[str], *, limit: int) -> list[str]:
    return list(dict.fromkeys(values))[:limit]


def _safe_evidence_ids(projection: PublishedEpisodeProjection) -> set[str]:
    evidence_ids = set(projection.detail.evidence_ids)
    for event in projection.timeline:
        evidence_ids.update(event.evidence_ids)
    for asset in projection.detail.assets:
        if asset.evidence_id is not None:
            evidence_ids.add(asset.evidence_id)
    for finding in projection.detail.findings:
        evidence_ids.update(finding.supporting_evidence_ids)
        evidence_ids.update(finding.contradicting_evidence_ids)
    return evidence_ids


def _project_source(
    record: CommittedEpisodeObservationRecord,
    bundle: EpisodeObservationProducerBundle,
    source: EpisodeObservationProducerSource,
) -> EpisodeObservationSourceCoverage:
    return EpisodeObservationSourceCoverage(
        robot_id=record.robot_id,
        episode_id=record.episode_id,
        episode_revision=record.episode_revision,
        bundle_id=bundle.bundle_id,
        source_id=source.source_id,
        label=source.public_label,
        source_kind=source.source_kind,
        modality=source.modality,
        world_kind=source.world_kind,
        availability=source.availability,
        synchronization=source.synchronization,
        spatial_alignment=source.spatial_alignment,
        asset_ids=source.asset_ids,
        limitations=_unique(source.public_limitations, limit=32),
    )


def project_episode_observation_record(
    record: CommittedEpisodeObservationRecord,
    episode_projection: PublishedEpisodeProjection,
) -> PublishedEpisodeObservationBundleProjection:
    detail = episode_projection.detail
    if (
        detail.robot_id != record.robot_id
        or detail.episode_id != record.episode_id
        or detail.revision != record.episode_revision
    ):
        raise ValueError("Episode observation record identity does not match Episode revision")
    if not detail.immutable or detail.ended_at is None:
        raise ValueError("Episode observation projection requires an immutable Episode revision")
    duration_ms = int((detail.ended_at - detail.started_at).total_seconds() * 1_000)
    episode_asset_ids = {asset.asset_id for asset in detail.assets}
    safe_evidence_ids = _safe_evidence_ids(episode_projection)
    public_items: list[EpisodeObservationBundleSummary] = []
    for bundle in record.bundles:
        if bundle.window_end_offset_ms > duration_ms:
            raise ValueError("observation bundle window exceeds Episode interval")
        public_sources = [
            _project_source(record, bundle, source) for source in bundle.sources
        ]
        asset_ids = _unique(
            [asset_id for source in public_sources for asset_id in source.asset_ids],
            limit=256,
        )
        if not set(asset_ids) <= episode_asset_ids:
            raise ValueError("observation bundle references an unknown Episode asset")
        evidence_ids = _unique(
            [evidence_id_for_reference(record.robot_id, ref) for ref in bundle.evidence_refs],
            limit=256,
        )
        if not set(evidence_ids) <= safe_evidence_ids:
            raise ValueError("observation bundle references unpublished Evidence")
        public_items.append(
            EpisodeObservationBundleSummary(
                robot_id=record.robot_id,
                episode_id=record.episode_id,
                episode_revision=record.episode_revision,
                bundle_id=bundle.bundle_id,
                sequence=bundle.sequence,
                parent_bundle_id=bundle.parent_bundle_id,
                trigger_kind=bundle.trigger_kind,
                status=bundle.status,
                created_at=bundle.created_at,
                window_start_offset_ms=bundle.window_start_offset_ms,
                window_end_offset_ms=bundle.window_end_offset_ms,
                synchronization=bundle.synchronization,
                spatial_alignment=bundle.spatial_alignment,
                world_scope=_world_scope_for_sources(public_sources),
                sources=public_sources,
                asset_ids=asset_ids,
                evidence_ids=evidence_ids,
                limitations=_unique(bundle.public_limitations, limit=32),
            )
        )
    projection = PublishedEpisodeObservationBundleProjection(
        robot_id=record.robot_id,
        episode_id=record.episode_id,
        episode_revision=record.episode_revision,
        as_of=record.committed_at,
        items=sorted(public_items, key=lambda item: item.sequence, reverse=True),
        limitations=_unique(record.public_limitations, limit=32),
    )
    _validate_projection_against_episode(projection, episode_projection)
    _reject_unsafe_public_content(projection.model_dump(mode="json"))
    return projection


def _validate_projection_against_episode(
    projection: PublishedEpisodeObservationBundleProjection,
    episode_projection: PublishedEpisodeProjection,
) -> None:
    detail = episode_projection.detail
    if (
        projection.robot_id != detail.robot_id
        or projection.episode_id != detail.episode_id
        or projection.episode_revision != detail.revision
    ):
        raise ValueError("observation projection identity does not match Episode")
    if not detail.immutable:
        raise ValueError("observation projection requires an immutable Episode")
    asset_ids = {asset.asset_id for asset in detail.assets}
    evidence_ids = _safe_evidence_ids(episode_projection)
    for bundle in projection.items:
        if not set(bundle.asset_ids) <= asset_ids:
            raise ValueError("observation projection references an unknown Episode asset")
        if not set(bundle.evidence_ids) <= evidence_ids:
            raise ValueError("observation projection references unknown Evidence")


def write_committed_episode_observation_record(
    artifact_root: Path,
    record: CommittedEpisodeObservationRecord,
) -> Path:
    path = ArtifactLayout(artifact_root).episode_observation_record(
        record.robot_id,
        record.episode_id,
        record.episode_revision,
    )
    _require_artifact_path(artifact_root, path)
    encoded = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if path.is_file():
        existing = CommittedEpisodeObservationRecord.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if existing.content_sha256 == record.content_sha256:
            return path
        raise FileExistsError(
            "committed Episode observation revision already exists with different content"
        )
    atomic_write_text(path, encoded, require_absent=True)
    return path


def publish_episode_observation_record(
    artifact_root: Path,
    record: CommittedEpisodeObservationRecord,
) -> PublishedEpisodeObservationBundleProjection:
    episode_projection = _projection_for_revision(
        artifact_root,
        record.robot_id,
        record.episode_id,
        revision=record.episode_revision,
    )
    if episode_projection is None:
        raise FileNotFoundError("Episode revision is unavailable")
    projection = project_episode_observation_record(record, episode_projection)
    path = ArtifactLayout(artifact_root).episode_observation_publication(
        record.robot_id,
        record.episode_id,
        record.episode_revision,
    )
    _require_artifact_path(artifact_root, path)
    if path.is_file():
        current = _load_observation_projection(
            artifact_root,
            record.robot_id,
            record.episode_id,
            record.episode_revision,
            episode_projection,
        )
        if current.model_dump(mode="json") != projection.model_dump(mode="json"):
            raise ValueError("published Episode observation revision has conflicting content")
        write_committed_episode_observation_record(artifact_root, record)
        return current
    write_committed_episode_observation_record(artifact_root, record)
    atomic_write_text(
        path,
        json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
    )
    return projection


def _load_observation_projection(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    revision: int,
    episode_projection: PublishedEpisodeProjection,
) -> PublishedEpisodeObservationBundleProjection:
    layout = ArtifactLayout(artifact_root)
    root = layout.episode_observation_publications(robot_id, episode_id)
    _validate_publication_root(artifact_root, root)
    path = layout.episode_observation_publication(robot_id, episode_id, revision)
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("Episode observation publication is unavailable")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Episode observation publication is unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Episode observation publication must be an object")
    _reject_unsafe_public_content(raw)
    projection = PublishedEpisodeObservationBundleProjection.model_validate(raw)
    _validate_projection_against_episode(projection, episode_projection)
    return projection


def _observation_cursor_for(
    robot_id: str,
    episode_id: str,
    revision: int,
    offset: int,
) -> str:
    material = f"{robot_id}\0{episode_id}\0{revision}\0{offset}".encode()
    return f"epobcur_{sha256(material).hexdigest()[:40]}"


def build_episode_observation_bundle_collection(
    artifact_root: Path,
    robot_id: str,
    episode_id: str,
    *,
    revision: int,
    limit: int = 20,
    cursor: str | None = None,
) -> EpisodeObservationBundleCollection | None:
    episode_projection = _projection_for_revision(
        artifact_root,
        robot_id,
        episode_id,
        revision=revision,
    )
    if episode_projection is None:
        return None
    if not episode_projection.detail.immutable:
        raise EpisodeRevisionConflict(
            "Episode observation bundles require an immutable Episode revision"
        )
    layout = ArtifactLayout(artifact_root)
    path = layout.episode_observation_publication(robot_id, episode_id, revision)
    if path.is_symlink():
        raise ValueError("unsafe Episode observation publication path")
    if path.is_file():
        projection = _load_observation_projection(
            artifact_root,
            robot_id,
            episode_id,
            revision,
            episode_projection,
        )
        items = projection.items
        as_of = projection.as_of
        limitations = projection.limitations
    elif path.exists():
        raise ValueError("Episode observation publication path is not a file")
    else:
        items = []
        as_of = episode_projection.detail.as_of
        limitations = []
    start = 0
    if cursor is not None:
        for candidate in range(1, len(items) + 1):
            if cursor == _observation_cursor_for(
                robot_id,
                episode_id,
                revision,
                candidate,
            ):
                start = candidate
                break
        else:
            raise EpisodeCursorError(
                "Episode observation cursor is invalid for this revision"
            )
    end = min(start + limit, len(items))
    return EpisodeObservationBundleCollection(
        robot_id=robot_id,
        episode_id=episode_id,
        episode_revision=revision,
        items=items[start:end],
        limit=limit,
        cursor=cursor,
        next_cursor=(
            _observation_cursor_for(robot_id, episode_id, revision, end)
            if end < len(items)
            else None
        ),
        as_of=as_of,
        limitations=limitations,
    )
