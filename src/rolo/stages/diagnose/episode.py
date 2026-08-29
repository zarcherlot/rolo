"""Immutable target Episode contract used by real Diagnose providers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref


class EpisodePhase(str, Enum):
    BASELINE = "baseline"
    OBSERVE = "observe"
    HYPOTHESIS = "hypothesis"
    CHANGE = "change"
    SMOKE = "smoke"
    DECISION = "decision"


class TargetProvenance(BaseModel):
    """Evidence that an observation was collected from the requested target."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-provenance/v1", "rolo-target-provenance/v2"
    ] = "rolo-target-provenance/v1"
    target_id: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=256)
    collector_version: str = Field(min_length=1, max_length=128)
    collected_at: datetime
    clock_offset_ms: float
    target_binding_ref: str | None = Field(default=None, pattern=r"^artifact://")
    target_binding_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    collector_session_id: str | None = Field(default=None, min_length=1, max_length=256)
    clock_source: str | None = Field(default=None, min_length=1, max_length=128)
    monotonic_ns: int | None = Field(default=None, ge=0)

    @field_validator("clock_offset_ms")
    @classmethod
    def validate_clock_offset(cls, value: float) -> float:
        if not -5_000 <= value <= 5_000:
            raise ValueError("target provenance clock offset exceeds 5000 ms")
        return value

    @model_validator(mode="after")
    def validate_v2_binding(self) -> TargetProvenance:
        if self.collected_at.tzinfo is None:
            raise ValueError("target provenance collected_at must include timezone")
        if self.schema_version == "rolo-target-provenance/v2" and any(
            value is None
            for value in (
                self.target_binding_ref,
                self.target_binding_sha256,
                self.collector_session_id,
                self.clock_source,
                self.monotonic_ns,
            )
        ):
            raise ValueError("target provenance v2 requires identity, session, and clock binding")
        if bool(self.target_binding_ref) != bool(self.target_binding_sha256):
            raise ValueError("target provenance binding reference and hash must be paired")
        return self


class EpisodeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-episode-observation/v1"] = "rolo-episode-observation/v1"
    sequence: int = Field(ge=1)
    phase: EpisodePhase
    observed_at: datetime
    payload: dict[str, JsonValue] = Field(min_length=1)
    provenance: TargetProvenance


class DiagnosisEpisode(BaseModel):
    """Append-only, target-bound observation bundle for one Diagnose episode."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-diagnosis-episode/v1"] = "rolo-diagnosis-episode/v1"
    episode_id: str = Field(
        default_factory=lambda: f"episode-{uuid4().hex}",
        pattern=r"^[a-z][a-z0-9_.-]{0,127}$",
    )
    robot_id: str = Field(min_length=1, max_length=128)
    started_at: datetime
    ended_at: datetime
    observations: list[EpisodeObservation] = Field(min_length=1, max_length=2048)
    status: Literal["COMPLETE", "INCOMPLETE"] = "COMPLETE"

    @field_validator("observations")
    @classmethod
    def validate_sequence(cls, value: list[EpisodeObservation]) -> list[EpisodeObservation]:
        sequences = [item.sequence for item in value]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("episode observations must have unique increasing sequence numbers")
        return value

    @model_validator(mode="after")
    def validate_target_and_interval(self) -> DiagnosisEpisode:
        if self.ended_at < self.started_at:
            raise ValueError("episode ended_at must not precede started_at")
        if any(item.provenance.target_id != self.robot_id for item in self.observations):
            raise ValueError("episode observation provenance target does not match robot")
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("episode timestamps must include timezone")
        if any(item.observed_at.tzinfo is None for item in self.observations):
            raise ValueError("episode observation timestamps must include timezone")
        if any(
            item.observed_at < self.started_at or item.observed_at > self.ended_at
            for item in self.observations
        ):
            raise ValueError("episode observation timestamp is outside the episode interval")
        if self.status == "COMPLETE":
            phases = {item.phase for item in self.observations}
            required = set(EpisodePhase)
            if phases != required:
                missing = ", ".join(sorted(item.value for item in required - phases))
                raise ValueError(f"complete episode is missing phases: {missing}")
        return self


def publish_episode(artifact_root: Path, episode: DiagnosisEpisode) -> str:
    """Persist one immutable Episode record and return its publication reference."""

    layout = ArtifactLayout(artifact_root)
    store = ArtifactStore(artifact_root)
    record = store.write_json(
        layout.relative(layout.episode_record(episode.robot_id, episode.episode_id, 1)),
        episode.model_dump(mode="json"),
    )
    digest = sha256_file(record)
    publication = store.write_json(
        layout.relative(layout.episode_publication(episode.robot_id, episode.episode_id)),
        {
            "schema_version": "rolo-episode-publication/v1",
            "episode_id": episode.episode_id,
            "robot_id": episode.robot_id,
            "record_ref": layout.ref(record),
            "record_sha256": digest,
            "published_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return layout.ref(publication)


def validate_published_episode(
    artifact_root: Path, reference: str, *, robot_id: str | None = None
) -> DiagnosisEpisode:
    """Verify publication metadata, record hash, and target identity before consumption."""

    publication_path = resolve_artifact_ref(artifact_root, reference)
    try:
        payload = json.loads(publication_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("episode publication is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("episode publication must be a JSON object")
    if payload.get("schema_version") != "rolo-episode-publication/v1":
        raise ValueError("unsupported episode publication schema")
    if robot_id is not None and payload.get("robot_id") != robot_id:
        raise ValueError("episode publication robot identity mismatch")
    record_ref = payload.get("record_ref")
    expected = payload.get("record_sha256")
    if not isinstance(record_ref, str) or not isinstance(expected, str):
        raise ValueError("episode publication is missing record binding")
    record_path = resolve_artifact_ref(artifact_root, record_ref)
    if not record_path.is_file() or sha256_file(record_path) != expected:
        raise ValueError("episode record hash mismatch")
    episode = DiagnosisEpisode.model_validate_json(record_path.read_text(encoding="utf-8"))
    if (
        payload.get("episode_id") != episode.episode_id
        or payload.get("robot_id") != episode.robot_id
    ):
        raise ValueError("episode publication identity does not match record")
    if robot_id is not None and episode.robot_id != robot_id:
        raise ValueError("episode robot identity mismatch")
    return episode
