from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rolo.api import app
from rolo.core.config import get_settings
from rolo.core.models import RobotCapability
from rolo.episode_projection import (
    CommittedEpisodeRecord,
    episode_record_content_sha256,
    project_episode_record,
    publish_episode_record,
)
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.workbench_read_models import (
    build_evidence_collection,
    evidence_id_for_reference,
    find_evidence,
)

RECORD_FIXTURE = Path(
    "tests/fixtures/episode_records/mentorpi-ros-discovery-partial.json"
)
ROBOT_FIXTURE = Path("tests/fixtures/episode_records/mentorpi.yaml")
E1_PUBLICATION_FIXTURE = Path(
    "tests/fixtures/episodes/demo_diff/published/ep-nav-001.json"
)
ROS_REFERENCE = (
    "artifact://discovery/mentorpi/runs/"
    "disc-20260820T115700-f8f2b8ec/ros.json"
)


def _payload() -> dict[str, object]:
    return json.loads(RECORD_FIXTURE.read_text(encoding="utf-8"))


def _record() -> CommittedEpisodeRecord:
    return CommittedEpisodeRecord.model_validate(_payload())


def _robot() -> RobotCapability:
    return RobotCapability.model_validate(
        yaml.safe_load(ROBOT_FIXTURE.read_text(encoding="utf-8"))
    )


def _with_digest(payload: dict[str, object]) -> dict[str, object]:
    payload["content_sha256"] = episode_record_content_sha256(payload)
    return payload


def test_mentorpi_record_projects_clock_and_missing_evidence_semantics() -> None:
    projection = project_episode_record(_record())
    detail = projection.detail

    assert detail.robot_id == "mentorpi"
    assert detail.coverage == "PARTIAL"
    assert detail.synchronization == "DEGRADED"
    assert detail.immutable is True
    assert detail.asset_count == 1
    assert detail.assets[0].availability == "MISSING"
    assert detail.assets[0].evidence_id is None
    assert detail.finding_count == 2
    assert {finding.kind for finding in detail.findings} == {
        "OBSERVED_FACT",
        "CANDIDATE_CAUSE",
    }
    candidate = next(
        finding for finding in detail.findings if finding.kind == "CANDIDATE_CAUSE"
    )
    assert candidate.authority == "INFERRED"
    assert candidate.verification == "UNVERIFIED"
    assert candidate.contradicting_evidence_ids
    camera = next(event for event in projection.timeline if event.event_id == "evt-camera-missing")
    assert camera.lane == "ALERT"
    assert camera.authority == "DECLARED"
    assert camera.title == "Evidence unavailable"
    assert any("withheld" in limitation for limitation in detail.limitations)
    assert any("offset_ms" in limitation for limitation in detail.limitations)

    encoded = json.dumps(projection.model_dump(mode="json"), ensure_ascii=False)
    assert "artifact://" not in encoded
    assert "raw_payload" not in encoded
    assert "model_prompt" not in encoded
    assert "model_response" not in encoded
    assert "camera/image_raw" not in encoded


def test_committed_record_digest_rejects_tampering() -> None:
    payload = _payload()
    payload["task_label"] = "Tampered label"

    with pytest.raises(ValidationError, match="content digest mismatch"):
        CommittedEpisodeRecord.model_validate(payload)


def test_publish_is_idempotent_and_committed_revision_is_immutable(tmp_path: Path) -> None:
    record = _record()
    first = publish_episode_record(tmp_path, record)
    second = publish_episode_record(tmp_path, record)
    layout = ArtifactLayout(tmp_path)

    assert first.model_dump() == second.model_dump()
    assert layout.episode_record("mentorpi", record.episode_id, 1).is_file()
    assert layout.episode_publication("mentorpi", record.episode_id).is_file()

    conflict_payload = _payload()
    conflict_payload["task_label"] = "Conflicting committed task"
    conflict = CommittedEpisodeRecord.model_validate(_with_digest(conflict_payload))
    with pytest.raises(ValueError, match="conflicting content"):
        publish_episode_record(tmp_path, conflict)

    next_payload = _payload()
    next_payload["revision"] = 2
    next_payload["parent_revision"] = 1
    next_payload["commit_id"] = "commit-mentorpi-discovery-2"
    next_record = CommittedEpisodeRecord.model_validate(_with_digest(next_payload))
    with pytest.raises(ValueError, match="immutable Episode publication"):
        publish_episode_record(tmp_path, next_record)
    assert not layout.episode_record("mentorpi", record.episode_id, 2).exists()


def test_episode_evidence_is_resolvable_without_exposing_internal_reference(
    tmp_path: Path,
) -> None:
    record = _record()
    publish_episode_record(tmp_path, record)
    robot = _robot()
    evidence_id = evidence_id_for_reference("mentorpi", ROS_REFERENCE)

    collection = build_evidence_collection(
        robot,
        tmp_path / "output",
        artifact_root=tmp_path,
        limit=100,
    )
    detail = find_evidence(
        [robot],
        tmp_path / "output",
        evidence_id,
        artifact_root=tmp_path,
    )

    assert evidence_id in {item.evidence_id for item in collection.items}
    assert detail is not None
    assert detail.source_kind == "episode_event"
    assert detail.reference_hint == "artifact://…/ros.json"
    assert "discovery/mentorpi/runs" not in detail.model_dump_json()


def test_e1_publication_without_producer_record_remains_evidence_compatible(
    tmp_path: Path,
) -> None:
    target = ArtifactLayout(tmp_path).episode_publication("demo_diff", "ep-nav-001")
    target.parent.mkdir(parents=True)
    shutil.copyfile(E1_PUBLICATION_FIXTURE, target)
    robot = RobotCapability.model_validate(
        yaml.safe_load(Path("tests/fixtures/robots/demo_diff.yaml").read_text(encoding="utf-8"))
    )

    collection = build_evidence_collection(
        robot,
        tmp_path / "output",
        artifact_root=tmp_path,
        limit=100,
    )

    assert collection.total > 0
    assert all(not item.source_kind.startswith("episode_") for item in collection.items)


def test_episode_projection_is_available_through_read_only_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    config_root = tmp_path / "config"
    robot_root = config_root / "robots"
    robot_root.mkdir(parents=True)
    shutil.copyfile(ROBOT_FIXTURE, robot_root / "mentorpi.yaml")
    publish_episode_record(artifact_root, _record())
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(config_root))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()
    evidence_id = evidence_id_for_reference("mentorpi", ROS_REFERENCE)

    with TestClient(app) as client:
        collection = client.get("/v1/robots/mentorpi/episodes")
        detail = client.get("/v1/robots/mentorpi/episodes/ep-discovery-20260820")
        timeline = client.get(
            "/v1/robots/mentorpi/episodes/ep-discovery-20260820/timeline",
            params={"revision": 1},
        )
        evidence = client.get(f"/v1/evidence/{evidence_id}")

    assert collection.status_code == 200
    assert collection.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["synchronization"] == "DEGRADED"
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 6
    assert evidence.status_code == 200
    assert evidence.json()["source_kind"] == "episode_event"
    assert "disc-20260820T115700-f8f2b8ec" not in evidence.text
