from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_artifact_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_and_robot_registry() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        robots = client.get("/v1/robots")
        pipeline = client.get("/v1/robots/demo_diff/pipeline")
        status = client.get("/v1/robot-use/status")

    assert health.status_code == 200
    assert health.json()["status"] == "HEALTHY"
    assert health.json()["robots"] == 2
    assert robots.status_code == 200
    assert {robot["robot_id"] for robot in robots.json()} == {"demo_diff", "demo_ackermann"}
    assert [stage["stage"] for stage in pipeline.json()["stages"]] == [
        "build",
        "debug",
        "test",
    ]
    assert status.json()["local_visual_detection"] is False


def test_unknown_robot_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/robots/not-a-robot")

    assert response.status_code == 404


def test_robot_use_poll_uses_offline_backend() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "request_id": "req-api-test",
        "robot_id": "demo_diff",
        "execution_id": "exec-api-test",
        "window_start": (now - timedelta(seconds=10)).isoformat(),
        "window_end": now.isoformat(),
        "frames": [
            {
                "timestamp": now.isoformat(),
                "image_url": "data:image/png;base64,iVBORw0KGgo=",
            }
        ],
        "task_contract": {"intent": "navigate"},
        "telemetry_summary": {
            "commanded_speed_mps": 0.2,
            "progress_delta": 0.0,
        },
    }

    with TestClient(app) as client:
        response = client.post("/v1/robot-use/poll", json=payload)

    assert response.status_code == 200
    assert response.json()["verdict"] == "SUSPECTED_FAILURE"
