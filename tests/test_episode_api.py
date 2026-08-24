from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings
from rolo.stages.artifact_paths import ArtifactLayout

FIXTURE = Path("tests/fixtures/episodes/demo_diff/published/ep-nav-001.json")


def _publish_fixture(artifact_root: Path) -> None:
    target = ArtifactLayout(artifact_root).episode_publication("demo_diff", "ep-nav-001")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, target)


def test_episode_api_exposes_empty_collection_without_demo_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/v1/robots/demo_diff/episodes")

    assert response.status_code == 200
    assert response.json()["schema_version"] == "rolo-episode-collection/v1"
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_episode_api_reads_completed_projection_and_pins_timeline_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _publish_fixture(artifact_root)
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()

    with TestClient(app) as client:
        collection = client.get(
            "/v1/robots/demo_diff/episodes",
            params={"state": "COMPLETED", "limit": 10},
        )
        detail = client.get("/v1/robots/demo_diff/episodes/ep-nav-001")
        first = client.get(
            "/v1/robots/demo_diff/episodes/ep-nav-001/timeline",
            params={"revision": 1, "limit": 1},
        )
        stale = client.get(
            "/v1/robots/demo_diff/episodes/ep-nav-001/timeline",
            params={"revision": 2},
        )
        invalid_cursor = client.get(
            "/v1/robots/demo_diff/episodes/ep-nav-001/timeline",
            params={"revision": 1, "cursor": "epcur_invalid"},
        )

    assert collection.status_code == 200
    assert collection.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["immutable"] is True
    assert first.status_code == 200
    assert first.json()["items"][0]["event_id"] == "evt-command"
    assert first.json()["next_cursor"].startswith("epcur_")
    assert stale.status_code == 409
    assert invalid_cursor.status_code == 422


def test_episode_api_rejects_unknown_robot_invalid_window_and_unknown_episode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()

    with TestClient(app) as client:
        robot = client.get("/v1/robots/not-a-robot/episodes")
        window = client.get(
            "/v1/robots/demo_diff/episodes",
            params={
                "since": "2026-08-24T00:00:00Z",
                "until": "2026-08-23T00:00:00Z",
            },
        )
        timezone_missing = client.get(
            "/v1/robots/demo_diff/episodes",
            params={"since": "2026-08-23T00:00:00"},
        )
        episode = client.get("/v1/robots/demo_diff/episodes/not-an-episode")

    assert robot.status_code == 404
    assert window.status_code == 422
    assert timezone_missing.status_code == 422
    assert episode.status_code == 404
