from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.episode_read_models import (
    EpisodeAssetSummary,
    EpisodeCursorError,
    EpisodeFindingSummary,
    EpisodeRevisionConflict,
    EpisodeState,
    EpisodeTimelineEvent,
    build_episode_collection,
    build_episode_revision_collection,
    build_episode_timeline_page,
    get_episode_detail,
)
from rolo.stages.artifact_paths import ArtifactLayout

FIXTURE = Path("tests/fixtures/episodes/demo_diff/published/ep-nav-001.json")


def _publish_fixture(artifact_root: Path) -> Path:
    target = ArtifactLayout(artifact_root).episode_publication("demo_diff", "ep-nav-001")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, target)
    return target


def test_empty_episode_collection_is_explicit_and_bounded(tmp_path: Path) -> None:
    collection = build_episode_collection(
        tmp_path,
        "demo_diff",
        limit=10,
        as_of=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )

    assert collection.schema_version == "rolo-episode-collection/v1"
    assert collection.robot_id == "demo_diff"
    assert collection.items == []
    assert collection.total == 0
    assert collection.next_offset is None


def test_completed_projection_supports_list_detail_and_revision_pinned_timeline(
    tmp_path: Path,
) -> None:
    _publish_fixture(tmp_path)

    collection = build_episode_collection(
        tmp_path,
        "demo_diff",
        state=EpisodeState.COMPLETED,
        since=datetime(2026, 8, 23, 2, tzinfo=timezone.utc),
        until=datetime(2026, 8, 23, 4, tzinfo=timezone.utc),
        limit=10,
    )
    detail = get_episode_detail(tmp_path, "demo_diff", "ep-nav-001")
    revisions = build_episode_revision_collection(
        tmp_path,
        "demo_diff",
        "ep-nav-001",
    )
    first = build_episode_timeline_page(
        tmp_path,
        "demo_diff",
        "ep-nav-001",
        revision=1,
        limit=1,
    )

    assert collection.total == 1
    assert collection.items[0].schema_version == "rolo-episode-summary/v1"
    assert collection.items[0].coverage == "METADATA_ONLY"
    assert detail is not None
    assert detail.schema_version == "rolo-episode-detail/v1"
    assert detail.immutable is True
    assert detail.outcome == "SUCCEEDED"
    assert detail.verification == "UNVERIFIED"
    assert revisions is not None
    assert revisions.current_revision == 1
    assert [item.revision for item in revisions.items] == [1]
    assert revisions.items[0].source_kind == "published_episode_projection"
    assert revisions.limitations
    assert first is not None
    assert [event.event_id for event in first.items] == ["evt-command"]
    assert first.next_cursor is not None

    second = build_episode_timeline_page(
        tmp_path,
        "demo_diff",
        "ep-nav-001",
        revision=1,
        limit=1,
        cursor=first.next_cursor,
    )
    assert second is not None
    assert [event.event_id for event in second.items] == ["evt-outcome"]
    assert second.next_cursor is None


def test_timeline_rejects_stale_revision_and_unbound_cursor(tmp_path: Path) -> None:
    _publish_fixture(tmp_path)

    with pytest.raises(EpisodeRevisionConflict):
        get_episode_detail(
            tmp_path,
            "demo_diff",
            "ep-nav-001",
            revision=2,
        )
    with pytest.raises(EpisodeRevisionConflict):
        build_episode_timeline_page(
            tmp_path,
            "demo_diff",
            "ep-nav-001",
            revision=2,
        )
    with pytest.raises(EpisodeCursorError):
        build_episode_timeline_page(
            tmp_path,
            "demo_diff",
            "ep-nav-001",
            revision=1,
            cursor="epcur_0000000000000000000000000000000000000000",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_ref", "artifact://episodes/demo/raw.json"),
        ("model_prompt", "private prompt"),
        ("signed_url", "https://example.invalid/private"),
    ],
)
def test_publication_rejects_unsafe_fields_recursively(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    target = _publish_fixture(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["detail"]["timeline_metadata"] = {field: value}
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe public Episode field"):
        get_episode_detail(tmp_path, "demo_diff", "ep-nav-001")


def test_publication_rejects_raw_host_paths_even_in_known_text_fields(tmp_path: Path) -> None:
    target = _publish_fixture(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["detail"]["limitations"] = [r"C:\Users\operator\episode.json"]
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe public Episode string"):
        get_episode_detail(tmp_path, "demo_diff", "ep-nav-001")


def test_inference_cannot_claim_verified_authority_or_verification() -> None:
    with pytest.raises(ValidationError):
        EpisodeFindingSummary(
            robot_id="demo_diff",
            episode_id="ep-nav-001",
            revision=1,
            finding_id="finding-cause",
            kind="CANDIDATE_CAUSE",
            authority="VERIFIED",
            title="Candidate localization drift",
            summary="A heuristic suggested localization drift.",
            start_offset_ms=100,
            end_offset_ms=200,
            supporting_evidence_ids=["ev_localization"],
            verification="VERIFIED",
        )


def test_non_declared_event_requires_evidence_or_asset_support() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        EpisodeTimelineEvent(
            robot_id="demo_diff",
            episode_id="ep-nav-001",
            revision=1,
            event_id="evt-unsupported",
            sequence=2,
            offset_ms=4000,
            occurred_at="2026-08-23T03:00:04Z",
            clock_domain="robot-monotonic",
            synchronization="SYNCED",
            lane="AGENT",
            title="Unsupported inference",
            summary="The Agent emitted an inference without public evidence.",
            severity="WARNING",
            authority="INFERRED",
        )


def test_verified_episode_requires_public_evidence_ids(tmp_path: Path) -> None:
    target = _publish_fixture(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["detail"]["verification"] = "VERIFIED"
    payload["detail"]["evidence_ids"] = []
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="VERIFIED episode requires evidence_ids"):
        get_episode_detail(tmp_path, "demo_diff", "ep-nav-001")


def test_secret_asset_metadata_cannot_expose_a_digest() -> None:
    with pytest.raises(ValidationError, match="must not expose a digest"):
        EpisodeAssetSummary(
            robot_id="demo_diff",
            episode_id="ep-nav-001",
            revision=1,
            asset_id="asset-secret",
            modality="camera",
            source_label="Restricted camera",
            captured_at="2026-08-23T03:00:01Z",
            offset_ms=1000,
            world_kind="PHYSICAL",
            evidence_kind="RAW",
            clock_domain="robot-monotonic",
            synchronization="SYNCED",
            media_type="image/png",
            digest="0" * 64,
            data_classification="SECRET",
            availability="REDACTED",
        )


def test_simulated_asset_cannot_support_verified_outcome(tmp_path: Path) -> None:
    target = _publish_fixture(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["detail"]["verification"] = "VERIFIED"
    payload["detail"]["asset_count"] = 1
    payload["detail"]["finding_count"] = 1
    payload["detail"]["assets"] = [
        {
            "schema_version": "rolo-episode-asset-summary/v1",
            "robot_id": "demo_diff",
            "episode_id": "ep-nav-001",
            "revision": 1,
            "asset_id": "asset-sim-camera",
            "modality": "camera",
            "source_label": "Simulation camera",
            "captured_at": "2026-08-23T03:00:03Z",
            "offset_ms": 3000,
            "world_kind": "SIMULATED",
            "evidence_kind": "RAW",
            "clock_domain": "sim-clock",
            "synchronization": "SYNCED",
            "media_type": "image/png",
            "digest": "1" * 64,
            "data_classification": "INTERNAL",
            "availability": "AVAILABLE",
            "limitations": [],
        }
    ]
    payload["detail"]["findings"] = [
        {
            "schema_version": "rolo-episode-finding-summary/v1",
            "robot_id": "demo_diff",
            "episode_id": "ep-nav-001",
            "revision": 1,
            "finding_id": "finding-verified",
            "kind": "VERIFIED_OUTCOME",
            "authority": "VERIFIED",
            "title": "Physical waypoint reached",
            "summary": "The robot reached the physical inspection waypoint.",
            "start_offset_ms": 3000,
            "end_offset_ms": 3200,
            "supporting_asset_ids": ["asset-sim-camera"],
            "verification": "VERIFIED",
            "limitations": [],
        }
    ]
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="non-physical assets cannot support"):
        get_episode_detail(tmp_path, "demo_diff", "ep-nav-001")
