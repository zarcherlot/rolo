from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rolo.api import app
from rolo.core.config import get_settings
from rolo.episode_observation_bundles import (
    CommittedEpisodeObservationRecord,
    EpisodeObservationBundleCollection,
    EpisodeObservationSourceCoverage,
    PublishedEpisodeObservationBundleProjection,
    build_episode_observation_bundle_collection,
    episode_observation_record_content_sha256,
    project_episode_observation_record,
    publish_episode_observation_record,
)
from rolo.episode_projection import (
    CommittedEpisodeRecord,
    episode_record_content_sha256,
    project_episode_record,
    publish_episode_record,
)
from rolo.stages.artifact_paths import ArtifactLayout

EPISODE_FIXTURE = Path(
    "tests/fixtures/episode_records/mentorpi-ros-discovery-partial.json"
)
OBSERVATION_FIXTURE = Path(
    "tests/fixtures/episode_observation_records/mentorpi-observation-bundles.json"
)
ROBOT_FIXTURE = Path("tests/fixtures/episode_records/mentorpi.yaml")


def _episode_payload() -> dict[str, object]:
    return json.loads(EPISODE_FIXTURE.read_text(encoding="utf-8"))


def _episode_record(payload: dict[str, object] | None = None) -> CommittedEpisodeRecord:
    return CommittedEpisodeRecord.model_validate(payload or _episode_payload())


def _observation_payload() -> dict[str, object]:
    return json.loads(OBSERVATION_FIXTURE.read_text(encoding="utf-8"))


def _observation_record(
    payload: dict[str, object] | None = None,
) -> CommittedEpisodeObservationRecord:
    return CommittedEpisodeObservationRecord.model_validate(
        payload or _observation_payload()
    )


def _with_episode_digest(payload: dict[str, object]) -> dict[str, object]:
    payload["content_sha256"] = episode_record_content_sha256(payload)
    return payload


def _with_observation_digest(payload: dict[str, object]) -> dict[str, object]:
    payload["content_sha256"] = episode_observation_record_content_sha256(payload)
    return payload


def _publish_fixture(artifact_root: Path) -> None:
    publish_episode_record(artifact_root, _episode_record())
    publish_episode_observation_record(artifact_root, _observation_record())


def test_e22b_projects_partial_and_unavailable_bundle_history_without_internal_data(
    tmp_path: Path,
) -> None:
    episode = publish_episode_record(tmp_path, _episode_record())
    record = _observation_record()
    projection = project_episode_observation_record(record, episode)
    published = publish_episode_observation_record(tmp_path, record)
    repeated = publish_episode_observation_record(tmp_path, record)

    assert published.model_dump() == projection.model_dump()
    assert repeated.model_dump() == projection.model_dump()
    assert [item.sequence for item in projection.items] == [2, 1]
    assert [item.status for item in projection.items] == ["UNAVAILABLE", "PARTIAL"]
    assert [item.world_scope for item in projection.items] == ["NONE", "NONE"]
    assert projection.items[0].parent_bundle_id == "bundle-initial"
    assert projection.items[0].sources[0].availability == "REJECTED"
    assert projection.items[1].sources[1].availability == "MISSING"
    assert all(item.influences_verification is False for item in projection.items)

    encoded = projection.model_dump_json()
    for unsafe in [
        "artifact://",
        "provider_identity",
        "topic_name",
        "device_path",
        "raw_context",
        "internal_metadata",
        "mentorpi.local",
        "/camera/image_raw",
        "/dev/video0",
        "model_prompt",
        "renderer_config",
        "diagnosis-agent",
    ]:
        assert unsafe not in encoded

    layout = ArtifactLayout(tmp_path)
    assert layout.episode_observation_record("mentorpi", record.episode_id, 1).is_file()
    assert layout.episode_observation_publication("mentorpi", record.episode_id, 1).is_file()

    conflict_payload = _observation_payload()
    conflict_payload["record_id"] = "obs-mentorpi-conflicting-1"
    conflict_payload["public_limitations"] = ["Conflicting immutable publication."]
    conflict = _observation_record(_with_observation_digest(conflict_payload))
    with pytest.raises(ValueError, match="conflicting content"):
        publish_episode_observation_record(tmp_path, conflict)


def test_e22b_derives_mixed_world_scope_only_from_asset_bearing_sources() -> None:
    episode_payload = _episode_payload()
    episode_payload["assets"].extend(
        [
            {
                "schema_version": "rolo-episode-producer-asset/v1",
                "asset_id": "asset-physical-ok",
                "modality": "camera",
                "public_source_label": "Physical camera",
                "captured_at": "2026-08-20T11:57:01Z",
                "offset_ms": 1000,
                "world_kind": "PHYSICAL",
                "evidence_kind": "RAW",
                "frame": "camera-frame",
                "clock_domain": "host-wall-clock",
                "synchronization": "SYNCED",
                "media_type": "image/png",
                "byte_count": 128,
                "digest": "a" * 64,
                "data_classification": "INTERNAL",
                "availability": "AVAILABLE",
                "artifact_ref": "artifact://episodes/mentorpi/assets/physical.png",
                "limitations": [],
            },
            {
                "schema_version": "rolo-episode-producer-asset/v1",
                "asset_id": "asset-simulated-ok",
                "modality": "simulation-view",
                "public_source_label": "Simulation view",
                "captured_at": "2026-08-20T11:57:01Z",
                "offset_ms": 1000,
                "world_kind": "SIMULATED",
                "evidence_kind": "RENDERED",
                "frame": "map",
                "clock_domain": "host-wall-clock",
                "synchronization": "SYNCED",
                "media_type": "image/png",
                "byte_count": 128,
                "digest": "b" * 64,
                "data_classification": "INTERNAL",
                "availability": "AVAILABLE",
                "artifact_ref": "artifact://episodes/mentorpi/assets/simulated.png",
                "limitations": [],
            },
        ]
    )
    episode = project_episode_record(
        _episode_record(_with_episode_digest(episode_payload))
    )

    observation_payload = _observation_payload()
    observation_payload["record_id"] = "obs-mentorpi-mixed-1"
    observation_payload["bundles"] = [
        {
            "schema_version": "rolo-episode-observation-producer-bundle/v1",
            "bundle_id": "bundle-mixed",
            "sequence": 1,
            "parent_bundle_id": None,
            "trigger_kind": "INITIAL",
            "status": "COMPLETE",
            "created_at": "2026-08-20T11:57:05Z",
            "window_start_offset_ms": 0,
            "window_end_offset_ms": 3000,
            "synchronization": "SYNCED",
            "spatial_alignment": "ALIGNED",
            "sources": [
                {
                    "schema_version": "rolo-episode-observation-producer-source/v1",
                    "source_id": "source-physical",
                    "public_label": "Physical camera",
                    "source_kind": "ONBOARD_SENSOR",
                    "modality": "camera",
                    "world_kind": "PHYSICAL",
                    "availability": "AVAILABLE",
                    "synchronization": "SYNCED",
                    "spatial_alignment": "ALIGNED",
                    "asset_ids": ["asset-physical-ok"],
                    "public_limitations": [],
                    "provider_identity": None,
                    "topic_name": None,
                    "device_path": None,
                    "internal_metadata": {},
                },
                {
                    "schema_version": "rolo-episode-observation-producer-source/v1",
                    "source_id": "source-simulated",
                    "public_label": "Simulation view",
                    "source_kind": "SIMULATION",
                    "modality": "simulation-view",
                    "world_kind": "SIMULATED",
                    "availability": "AVAILABLE",
                    "synchronization": "SYNCED",
                    "spatial_alignment": "ALIGNED",
                    "asset_ids": ["asset-simulated-ok"],
                    "public_limitations": [],
                    "provider_identity": None,
                    "topic_name": None,
                    "device_path": None,
                    "internal_metadata": {},
                },
            ],
            "evidence_refs": [],
            "public_limitations": [
                "Physical and simulated assets remain separate inputs."
            ],
            "raw_context": {},
            "influences_verification": False,
        }
    ]
    record = _observation_record(_with_observation_digest(observation_payload))
    projection = project_episode_observation_record(record, episode)

    assert projection.items[0].world_scope == "MIXED"
    assert projection.items[0].status == "COMPLETE"
    assert projection.items[0].asset_ids == [
        "asset-physical-ok",
        "asset-simulated-ok",
    ]


def test_e22b_keeps_source_availability_states_fail_closed() -> None:
    stale = EpisodeObservationSourceCoverage(
        robot_id="mentorpi",
        episode_id="ep-discovery-20260820",
        episode_revision=1,
        bundle_id="bundle-stale",
        source_id="source-stale",
        label="Stale source",
        source_kind="ONBOARD_SENSOR",
        modality="camera",
        world_kind="PHYSICAL",
        availability="STALE",
        synchronization="DEGRADED",
        spatial_alignment="UNKNOWN",
        asset_ids=["asset-stale"],
        limitations=["The published observation is stale."],
    )
    assert stale.availability == "STALE"

    with pytest.raises(ValidationError, match="cannot reference assets"):
        EpisodeObservationSourceCoverage.model_validate(
            stale.model_dump()
            | {
                "source_id": "source-rejected",
                "availability": "REJECTED",
            }
        )


def test_e22b_rejects_tampering_unknown_cross_model_references_and_authority() -> None:
    episode = project_episode_record(_episode_record())

    digest_tamper = _observation_payload()
    digest_tamper["producer"] = "tampered-producer"
    with pytest.raises(ValidationError, match="content digest mismatch"):
        _observation_record(digest_tamper)

    unknown_evidence = _observation_payload()
    unknown_evidence["record_id"] = "obs-unknown-evidence"
    unknown_evidence["bundles"][0]["evidence_refs"] = [
        "artifact://episodes/mentorpi/unpublished.json"
    ]
    record = _observation_record(_with_observation_digest(unknown_evidence))
    with pytest.raises(ValueError, match="unpublished Evidence"):
        project_episode_observation_record(record, episode)

    unknown_asset = _observation_payload()
    unknown_asset["record_id"] = "obs-unknown-asset"
    source = unknown_asset["bundles"][0]["sources"][0]
    source["asset_ids"] = ["asset-does-not-exist"]
    record = _observation_record(_with_observation_digest(unknown_asset))
    with pytest.raises(ValueError, match="unknown Episode asset"):
        project_episode_observation_record(record, episode)

    authority = _observation_payload()
    authority["bundles"][0]["influences_verification"] = True
    with pytest.raises(ValidationError, match="False"):
        episode_observation_record_content_sha256(authority)


def test_e22b_paginates_exact_revision_and_exposes_empty_collection(
    tmp_path: Path,
) -> None:
    publish_episode_record(tmp_path, _episode_record())
    empty = build_episode_observation_bundle_collection(
        tmp_path,
        "mentorpi",
        "ep-discovery-20260820",
        revision=1,
        limit=1,
    )
    assert empty is not None
    assert empty.items == []
    assert empty.next_cursor is None

    publish_episode_observation_record(tmp_path, _observation_record())
    first = build_episode_observation_bundle_collection(
        tmp_path,
        "mentorpi",
        "ep-discovery-20260820",
        revision=1,
        limit=1,
    )
    assert first is not None
    assert [item.sequence for item in first.items] == [2]
    assert first.next_cursor is not None
    second = build_episode_observation_bundle_collection(
        tmp_path,
        "mentorpi",
        "ep-discovery-20260820",
        revision=1,
        limit=1,
        cursor=first.next_cursor,
    )
    assert second is not None
    assert [item.sequence for item in second.items] == [1]
    assert second.next_cursor is None


def test_e22b_api_is_feature_negotiated_revision_pinned_and_integrity_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    config_root = tmp_path / "config"
    robot_root = config_root / "robots"
    robot_root.mkdir(parents=True)
    shutil.copyfile(ROBOT_FIXTURE, robot_root / "mentorpi.yaml")
    _publish_fixture(artifact_root)
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(config_root))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()

    endpoint = "/v1/robots/mentorpi/episodes/ep-discovery-20260820/observation-bundles"
    with TestClient(app) as client:
        health = client.get("/health")
        first = client.get(endpoint, params={"revision": 1, "limit": 1})
        second = client.get(
            endpoint,
            params={
                "revision": 1,
                "limit": 1,
                "cursor": first.json()["next_cursor"],
            },
        )
        stale = client.get(endpoint, params={"revision": 2})
        invalid_cursor = client.get(
            endpoint,
            params={"revision": 1, "cursor": "epobcur_invalid"},
        )
        missing = client.get(
            "/v1/robots/mentorpi/episodes/not-an-episode/observation-bundles",
            params={"revision": 1},
        )

    assert "workbench.episode-observation-bundle/v1" in health.json()["api_features"]
    assert first.status_code == 200, first.text
    assert first.json()["schema_version"] == "rolo-episode-observation-bundle-collection/v1"
    assert first.json()["items"][0]["sequence"] == 2
    assert second.status_code == 200
    assert second.json()["items"][0]["sequence"] == 1
    assert stale.status_code == 409
    assert invalid_cursor.status_code == 422
    assert missing.status_code == 404

    publication = ArtifactLayout(artifact_root).episode_observation_publication(
        "mentorpi",
        "ep-discovery-20260820",
        1,
    )
    unsafe = json.loads(publication.read_text(encoding="utf-8"))
    unsafe["items"][0]["content_url"] = "https://unsafe.example/asset"
    publication.write_text(json.dumps(unsafe), encoding="utf-8")
    get_settings.cache_clear()
    with TestClient(app) as client:
        rejected = client.get(endpoint, params={"revision": 1})
    assert rejected.status_code == 500
    assert "unsafe.example" not in rejected.text


def test_e22b_generated_schemas_match_the_runtime_models() -> None:
    tracked = {
        "CommittedEpisodeObservationRecord.schema.json": (
            CommittedEpisodeObservationRecord
        ),
        "EpisodeObservationBundleCollection.schema.json": (
            EpisodeObservationBundleCollection
        ),
        "PublishedEpisodeObservationBundleProjection.schema.json": (
            PublishedEpisodeObservationBundleProjection
        ),
    }
    for name, model in tracked.items():
        schema = json.loads((Path("schemas") / name).read_text(encoding="utf-8"))
        assert schema == model.model_json_schema()
