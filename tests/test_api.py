import json
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
        fleet = client.get("/v1/fleet")
        blockers = client.get("/v1/blockers?limit=1")
        pipeline = client.get("/v1/robots/demo_diff/pipeline")
        overview = client.get("/v1/robots/demo_diff/overview")
        topology = client.get("/v1/robots/demo_diff/topology")
        topology_payload = topology.json()
        topology_path = client.get(
            "/v1/robots/demo_diff/topology/path",
            params={
                "from": topology_payload["edges"][0]["source"],
                "to": topology_payload["edges"][0]["target"],
            },
        )
        capabilities = client.get("/v1/robots/demo_diff/capabilities?limit=10")
        runs = client.get("/v1/robots/demo_diff/runs")
        evidence = client.get("/v1/robots/demo_diff/evidence?limit=5")
        status = client.get("/v1/robot-use/status")

    assert health.status_code == 200
    assert health.json()["status"] == "HEALTHY"
    assert health.json()["robots"] == 2
    assert robots.status_code == 200
    assert {robot["robot_id"] for robot in robots.json()} == {"demo_diff", "demo_ackermann"}
    assert fleet.status_code == 200
    assert fleet.json()["schema_version"] == "rolo-fleet-collection/v1"
    assert fleet.json()["total"] == 2
    assert fleet.json()["attention"] == 2
    assert fleet.json()["blocker_count"] == blockers.json()["total"]
    assert blockers.status_code == 200
    assert blockers.json()["schema_version"] == "rolo-fleet-blocker-collection/v1"
    assert blockers.json()["total"] > 0
    assert len(blockers.json()["items"]) == 1
    assert blockers.json()["next_offset"] == 1
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
    assert topology_path.status_code == 200
    assert topology_path.json()["schema_version"] == "rolo-topology-path-explanation/v1"
    assert topology_path.json()["found"] is True
    assert topology_path.json()["hop_count"] == 1
    assert topology_path.json()["steps"][0]["evidence_ids"]
    assert capabilities.status_code == 200
    assert capabilities.json()["schema_version"] == "rolo-capability-collection/v1"
    assert capabilities.json()["total"] == 294
    assert len(capabilities.json()["items"]) == 10
    assert capabilities.json()["source_kind"] == "product_registry"
    assert {
        "Hardware",
        "Linux",
        "Middleware",
        "Application",
    }.issuperset({item["layer"] for item in capabilities.json()["items"]})
    assert runs.status_code == 200
    assert runs.json()["schema_version"] == "rolo-lifecycle-run-collection/v1"
    assert runs.json()["items"] == []
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
        capabilities = client.get("/v1/robots/not-a-robot/capabilities")
        capability = client.get(
            "/v1/robots/not-a-robot/capabilities/tool.catalog"
        )
        runs = client.get("/v1/robots/not-a-robot/runs")
        evidence = client.get("/v1/robots/not-a-robot/evidence")
        evidence_detail = client.get("/v1/evidence/ev_unknown")

    assert response.status_code == 404
    assert overview.status_code == 404
    assert topology.status_code == 404
    assert capabilities.status_code == 404
    assert capability.status_code == 404
    assert runs.status_code == 404
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


def test_capabilities_are_filterable_and_detail_is_contract_bound() -> None:
    with TestClient(app) as client:
        page = client.get(
            "/v1/robots/demo_diff/capabilities"
            "?limit=5&layer=Middleware&risk=R0&availability=AVAILABLE"
        )
        search = client.get(
            "/v1/robots/demo_diff/capabilities?query=tool%20catalog"
        )
        detail = client.get(
            "/v1/robots/demo_diff/capabilities/tool.catalog"
        )
        unknown = client.get(
            "/v1/robots/demo_diff/capabilities/not.a.real.operation"
        )
        invalid_limit = client.get(
            "/v1/robots/demo_diff/capabilities?limit=101"
        )

    assert page.status_code == 200
    assert all(item["layer"] == "Middleware" for item in page.json()["items"])
    assert all(item["risk"] == "R0" for item in page.json()["items"])
    assert all(item["availability"] == "AVAILABLE" for item in page.json()["items"])
    assert search.status_code == 200
    assert [item["operation"] for item in search.json()["items"]] == ["tool.catalog"]
    assert detail.status_code == 200
    assert detail.json()["schema_version"] == "rolo-capability-detail/v1"
    assert detail.json()["capability"]["operation"] == "tool.catalog"
    assert detail.json()["capability"]["registration"] == "BUILTIN"
    assert detail.json()["capability"]["availability"] == "AVAILABLE"
    assert detail.json()["contract"]["input_schema"]["type"] == "object"
    assert detail.json()["contract"]["result_semantics"] == "OBSERVATION"
    assert unknown.status_code == 404
    assert invalid_limit.status_code == 422


def test_lifecycle_runs_expose_bounded_gate_and_evidence_metadata(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_root = artifact_root / "adapt/demo_diff/runs/run-failed"
    run_root.mkdir(parents=True)
    now = "2026-08-20T08:00:00Z"
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-adapter-agent-run/v1",
                "run_id": "run-failed",
                "robot_id": "demo_diff",
                "source_discovery_id": "discovery-1",
                "provider": "codex",
                "model": "test-model",
                "status": "FAILED",
                "workspace": "C:/private/workspace",
                "command": ["codex", "exec"],
                "prompt_ref": "artifact://prompt",
                "event_log_ref": "artifact://events",
                "stderr_ref": "artifact://stderr",
                "final_message_ref": "artifact://final",
                "event_count": 4,
                "exit_code": 1,
                "error": "failed at C:/private/workspace",
                "started_at": now,
                "completed_at": now,
                "duration_s": 2.5,
            }
        ),
        encoding="utf-8",
    )
    (run_root / "gate.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-adapt-gate/v1",
                "run_id": "run-failed",
                "robot_id": "demo_diff",
                "discovery_id": "discovery-1",
                "status": "FAILED",
                "checks": ["frozen output hashes and schemas"],
                "error": "private path must not be returned",
                "checked_at": now,
            }
        ),
        encoding="utf-8",
    )

    with TestClient(app) as client:
        runs = client.get("/v1/robots/demo_diff/runs?stage=adapt&status=FAILED")
        detail = client.get("/v1/robots/demo_diff/runs/run-failed")
        unknown = client.get("/v1/robots/demo_diff/runs/not-a-run")
        evidence_id = detail.json()["run"]["evidence_ids"][0]
        evidence = client.get(f"/v1/evidence/{evidence_id}")

    assert runs.status_code == 200
    assert runs.json()["total"] == 1
    assert runs.json()["items"][0]["status"] == "FAILED"
    assert detail.status_code == 200
    assert detail.json()["run"]["provider"] == "codex"
    assert detail.json()["run"]["model"] == "test-model"
    assert detail.json()["run"]["handoff_status"] == "MISSING"
    assert [item["status"] for item in detail.json()["gate_checks"]] == [
        "PASSED",
        "FAILED",
    ]
    assert "private" not in detail.text.lower()
    assert unknown.status_code == 404
    assert evidence.status_code == 200
    assert evidence.json()["source_kind"] == "lifecycle_run"
    assert "private" not in evidence.text.lower()


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
    capability_schema = openapi["components"]["schemas"]["CapabilityCollection"]
    assert (
        capability_schema["properties"]["schema_version"]["const"]
        == "rolo-capability-collection/v1"
    )
    lifecycle_schema = openapi["components"]["schemas"]["LifecycleRunCollection"]
    assert (
        lifecycle_schema["properties"]["schema_version"]["const"]
        == "rolo-lifecycle-run-collection/v1"
    )
    topology_diff_schema = openapi["components"]["schemas"]["TopologyDiff"]
    assert (
        topology_diff_schema["properties"]["schema_version"]["const"]
        == "rolo-topology-diff/v1"
    )
    topology_path_schema = openapi["components"]["schemas"]["TopologyPathExplanation"]
    assert (
        topology_path_schema["properties"]["schema_version"]["const"]
        == "rolo-topology-path-explanation/v1"
    )
    wiki_schema = openapi["components"]["schemas"]["RobotWikiSnapshot"]
    assert wiki_schema["properties"]["schema_version"]["const"] == "rolo-robot-wiki/v1"
    discovery_history_schema = openapi["components"]["schemas"][
        "DiscoverySnapshotCollection"
    ]
    assert (
        discovery_history_schema["properties"]["schema_version"]["const"]
        == "rolo-discovery-snapshot-collection/v1"
    )
    fleet_schema = openapi["components"]["schemas"]["FleetCollection"]
    assert fleet_schema["properties"]["schema_version"]["const"] == "rolo-fleet-collection/v1"
    blocker_schema = openapi["components"]["schemas"]["FleetBlockerCollection"]
    assert (
        blocker_schema["properties"]["schema_version"]["const"]
        == "rolo-fleet-blocker-collection/v1"
    )


def test_robot_wiki_is_unavailable_without_verified_discovery(tmp_path: Path, monkeypatch) -> None:
    from rolo.core.config import get_settings

    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/v1/robots/demo_diff/wiki")

    assert response.status_code == 404
    assert response.json()["detail"] == "robot Wiki is unavailable"


def test_discovery_history_has_a_verified_empty_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from rolo.core.config import get_settings

    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/v1/robots/demo_diff/discoveries?limit=10&offset=0")

    assert response.status_code == 200
    assert response.json()["schema_version"] == (
        "rolo-discovery-snapshot-collection/v1"
    )
    assert response.json()["items"] == []
    assert response.json()["integrity_status"] == "verified"
    assert "physical outcomes" in " ".join(response.json()["limitations"])


def test_topology_snapshot_history_requires_verified_release_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from rolo.core.config import get_settings

    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()
    with TestClient(app) as client:
        snapshots = client.get("/v1/robots/demo_diff/topology/snapshots")
        unknown = client.get(
            "/v1/robots/demo_diff/topology/diff?from=unknown&to=missing"
        )

    assert snapshots.status_code == 200
    assert snapshots.json()["schema_version"] == "rolo-topology-snapshot-collection/v1"
    assert snapshots.json()["items"] == []
    assert "No verified topology" in " ".join(snapshots.json()["limitations"])
    assert unknown.status_code == 404


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
