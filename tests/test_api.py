from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_artifact_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_and_robot_registry() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        robots = client.get("/v1/robots")
        pipeline = client.get("/v1/robots/demo_diff/pipeline")
        overview = client.get("/v1/robots/demo_diff/overview")
        topology = client.get("/v1/robots/demo_diff/topology")
        evidence = client.get("/v1/robots/demo_diff/evidence?limit=5")
        status = client.get("/v1/robot-use/status")

    assert health.status_code == 200
    assert health.json()["status"] == "HEALTHY"
    assert health.json()["robots"] == 2
    assert robots.status_code == 200
    assert {robot["robot_id"] for robot in robots.json()} == {"demo_diff", "demo_ackermann"}
    assert [stage["stage"] for stage in pipeline.json()["stages"]] == [
        "adapt",
        "diagnose",
        "verify",
    ]
    assert overview.status_code == 200
    assert overview.json()["schema_version"] == "rolo-robot-overview/v2"
    assert overview.json()["robot_id"] == "demo_diff"
    assert overview.json()["state"] == "ATTENTION"
    assert overview.json()["next_action"] == "Run adapt discovery"
    assert overview.json()["blockers"][0] == {
        "schema_version": "rolo-blocker-summary/v2",
        "blocker_id": overview.json()["blockers"][0]["blocker_id"],
        "stage": "adapt",
        "message": "Run adapt discovery",
        "recommended_action": "Run adapt discovery",
        "owner": "adapter_agent",
        "observed_at": overview.json()["blockers"][0]["observed_at"],
        "freshness": "fresh",
        "source_kind": "pipeline_assessment",
        "confidence": 1.0,
        "integrity_status": "validated",
        "evidence_ids": [],
    }
    assert topology.status_code == 200
    assert topology.json()["schema_version"] == "rolo-robot-topology/v1"
    assert topology.json()["coverage"] == "REGISTRY_ONLY"
    assert {node["layer"] for node in topology.json()["nodes"]} == {
        "Hardware",
        "Linux",
        "Application",
    }
    assert all(node["evidence_ids"] for node in topology.json()["nodes"])
    assert evidence.status_code == 200
    assert evidence.json()["schema_version"] == "rolo-evidence-collection/v1"
    assert evidence.json()["total"] >= len(evidence.json()["items"]) > 0
    assert evidence.json()["offset"] == 0
    assert evidence.json()["next_offset"] == 5
    evidence_id = evidence.json()["items"][0]["evidence_id"]
    assert evidence_id.startswith("ev_")
    with TestClient(app) as client:
        evidence_detail = client.get(f"/v1/evidence/{evidence_id}")
    assert evidence_detail.status_code == 200
    assert evidence_detail.json()["schema_version"] == "rolo-evidence-record/v1"
    assert evidence_detail.json()["reference_hint"] != ""
    assert "tests/" not in evidence_detail.text
    assert status.json()["local_visual_detection"] is False


def test_unknown_robot_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/robots/not-a-robot")
        overview = client.get("/v1/robots/not-a-robot/overview")
        topology = client.get("/v1/robots/not-a-robot/topology")
        evidence = client.get("/v1/robots/not-a-robot/evidence")
        evidence_detail = client.get("/v1/evidence/ev_unknown")

    assert response.status_code == 404
    assert overview.status_code == 404
    assert topology.status_code == 404
    assert evidence.status_code == 404
    assert evidence_detail.status_code == 404


def test_evidence_list_is_bounded_filterable_and_validates_pagination() -> None:
    with TestClient(app) as client:
        page = client.get(
            "/v1/robots/demo_diff/evidence?limit=2&offset=1&authority=DECLARED"
        )
        invalid_limit = client.get("/v1/robots/demo_diff/evidence?limit=101")
        invalid_authority = client.get(
            "/v1/robots/demo_diff/evidence?authority=UNTRUSTED"
        )

    assert page.status_code == 200
    assert page.json()["limit"] == 2
    assert page.json()["offset"] == 1
    assert len(page.json()["items"]) == 2
    assert {item["authority"] for item in page.json()["items"]} == {"DECLARED"}
    assert invalid_limit.status_code == 422
    assert invalid_authority.status_code == 422


def test_overview_openapi_contract_is_versioned() -> None:
    openapi = app.openapi()
    operation = openapi["paths"]["/v1/robots/{robot_id}/overview"]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response == {"$ref": "#/components/schemas/RobotOverview"}

    schema = openapi["components"]["schemas"]["RobotOverview"]
    assert set(schema["required"]) >= {
        "robot_id",
        "state",
        "summary",
        "next_action",
        "pipeline",
        "observed_at",
    }
    assert schema["properties"]["schema_version"]["const"] == "rolo-robot-overview/v2"
    pipeline_schema = openapi["components"]["schemas"]["PipelineAssessment"]
    assert (
        pipeline_schema["properties"]["schema_version"]["const"]
        == "robot-three-stage-pipeline/v1"
    )
    stage_schema = openapi["components"]["schemas"]["StageAssessment"]
    assert (
        stage_schema["properties"]["schema_version"]["const"]
        == "robot-stage-assessment/v1"
    )
    topology_schema = openapi["components"]["schemas"]["RobotTopology"]
    assert (
        topology_schema["properties"]["schema_version"]["const"]
        == "rolo-robot-topology/v1"
    )
    evidence_schema = openapi["components"]["schemas"]["EvidenceRecord"]
    assert (
        evidence_schema["properties"]["schema_version"]["const"]
        == "rolo-evidence-record/v1"
    )


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
