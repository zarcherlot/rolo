"""Immutable Episode capture helpers for real target read-only observations.

The first P1 Episode slice deliberately captures only the target connection assessment.
It records what was observed and its limitations, but never upgrades metadata into
physical verification or release authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rolo.episode_projection import (
    CommittedEpisodeRecord,
    EpisodeProducerEvent,
    episode_record_content_sha256,
    publish_episode_record,
)
from rolo.episode_read_models import (
    EpisodeAuthority,
    EpisodeCoverage,
    EpisodeOutcome,
    EpisodeSeverity,
    EpisodeState,
    EpisodeSynchronization,
    EpisodeTimelineLane,
    EpisodeVerification,
)
from rolo.targets.models import TargetConnectionAssessment, TargetConnectionState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_target_inspection_episode(
    assessment: TargetConnectionAssessment,
    *,
    robot_id: str,
    episode_id: str,
    captured_at: datetime | None = None,
    execution_id: str | None = None,
) -> CommittedEpisodeRecord:
    """Build a committed, metadata-only Episode from a target inspection.

    The target URI and diagnostics are intentionally not copied into public Episode
    content.  This prevents hostnames, paths, credentials, or command output from
    becoming public read-model content while preserving the useful state decision.
    """

    if assessment.target is None:  # pragma: no cover - defensive for custom models
        raise ValueError("target inspection assessment must include a target")
    if not robot_id or not episode_id:
        raise ValueError("robot_id and episode_id are required")
    observed_at = captured_at or _utc_now()
    ready = assessment.state == TargetConnectionState.READY
    state = EpisodeState.COMPLETED if ready else EpisodeState.PARTIAL
    outcome = EpisodeOutcome.SUCCEEDED if ready else EpisodeOutcome.UNKNOWN
    summary = (
        "Target connection and workspace readiness were observed."
        if ready
        else f"Target inspection stopped with state {assessment.state.value}."
    )
    limitations = [
        "This Episode contains target metadata only; it is not physical verification.",
        "Remote clock synchronization and sensor observations were not collected.",
    ]
    if assessment.blockers:
        limitations.append("Target inspection reported one or more blockers.")
    event = EpisodeProducerEvent(
        event_id=f"{episode_id}-target-inspection",
        sequence=0,
        offset_ms=0,
        occurred_at=observed_at,
        clock_domain="host-wall-clock",
        synchronization=EpisodeSynchronization.UNKNOWN,
        lane=EpisodeTimelineLane.STATE,
        public_title="Target readiness observed",
        public_summary=summary,
        severity=EpisodeSeverity.INFO if ready else EpisodeSeverity.WARNING,
        authority=EpisodeAuthority.OBSERVED,
        limitations=["Remote clock synchronization was not collected."],
    )
    content = {
        "schema_version": "rolo-episode-producer-record/v1",
        "robot_id": robot_id,
        "episode_id": episode_id,
        "revision": 1,
        "parent_revision": None,
        "commit_id": f"{episode_id}-commit-1",
        "committed": True,
        "committed_at": observed_at,
        "producer": "target.inspect",
        "task_label": "Inspect target readiness",
        "state": state,
        "outcome": outcome,
        "verification": EpisodeVerification.UNVERIFIED,
        "coverage": EpisodeCoverage.METADATA_ONLY,
        "started_at": observed_at,
        "ended_at": observed_at,
        "immutable": True,
        "execution_id": execution_id or f"target-inspect-{episode_id}",
        "test_case_id": "target-inspect",
        "lifecycle_run_id": None,
        "operation": "target.inspect",
        "clock_domain": "host-wall-clock",
        "synchronization": EpisodeSynchronization.UNKNOWN,
        "expected_behavior": "The target is reachable and its workspace is accessible.",
        "observed_behavior": summary,
        "evidence_refs": [],
        "events": [event],
        "assets": [],
        "findings": [],
        "limitations": limitations,
    }
    content_sha256 = episode_record_content_sha256(content)
    return CommittedEpisodeRecord(**content, content_sha256=content_sha256)


def capture_target_inspection_episode(
    artifact_root: Path,
    assessment: TargetConnectionAssessment,
    *,
    robot_id: str,
    episode_id: str,
    captured_at: datetime | None = None,
    execution_id: str | None = None,
) -> tuple[CommittedEpisodeRecord, str]:
    """Persist and publish a target inspection Episode, returning its artifact ref."""

    record = build_target_inspection_episode(
        assessment,
        robot_id=robot_id,
        episode_id=episode_id,
        captured_at=captured_at,
        execution_id=execution_id,
    )
    publish_episode_record(artifact_root, record)
    return record, f"artifact://episodes/{robot_id}/published/{episode_id}.json"


__all__ = [
    "build_target_inspection_episode",
    "capture_target_inspection_episode",
]
