from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from rolo.api import app
from rolo.artifact_analysis import ArtifactAnalysisSummary
from rolo.artifact_ingestion import (
    ArtifactRegistrationRequest,
    register_artifact_analysis,
)
from rolo.core.config import get_settings
from rolo.jobs import JobStore
from rolo.target_ref import LocalTargetRef
from rolo.targets.profiles import CredentialReference, TargetProfileStore


def _summary(target_id: str = "demo-target") -> ArtifactAnalysisSummary:
    return ArtifactAnalysisSummary(
        analysis_id="analysis-registration",
        target_id=target_id,
        robot_id=target_id,
        discovery_id="discovery-registration",
        source_label="Sanitized producer summary",
        observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        freshness="fresh",
        kind="Artifact analysis",
        run_status="COMPLETE",
        title="Bounded analysis",
        description="A safe summary.",
        gate_status="PASSED",
        gate_label="Analysis passed",
        gate_tone="green",
        release_status="SHADOW_ONLY",
        release_label="No release effect",
        release_tone="amber",
        run_duration="1m",
        event_count=1,
        eligible_operation_count=0,
        route_review_flags="0 / 0",
        context_bars=[{"label": "Nodes", "value": 1, "display": "1 observed", "tone": "blue"}],
        evidence_note="Read-only summary.",
        operations=[],
        graph_nodes=[{"label": "target", "state": "bound", "tone": "green"}],
        stages=[
            {
                "label": "Analysis",
                "status": "passed",
                "timestamp": "2026-09-01T00:00:00Z",
                "detail": "Complete.",
            }
        ],
        findings=[],
        hashes=[("summary", "a1b2c3d4e5f60718")],
        limitations=["Bounded and advisory."],
    )


def _profile(root: Path, target_id: str = "demo-target") -> None:
    robots = root / "robots"
    robots.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).parent / "fixtures" / "robots" / "demo_diff.yaml"
    (robots / fixture.name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    workspace = root / f"workspace-{target_id}"
    workspace.mkdir(parents=True, exist_ok=True)
    TargetProfileStore(root).create(
        robot_id=target_id,
        target=LocalTargetRef(workspace=workspace),
        credential=CredentialReference(kind="platform-keychain", reference="demo:target"),
    )


def _request(summary: ArtifactAnalysisSummary, key: str = "registration-1") -> dict[str, object]:
    return {
        "schema_version": "rolo-artifact-registration-request/v1",
        "kind": "analysis_summary",
        "idempotency_key": key,
        "target_id": summary.target_id,
        "summary": summary.model_dump(mode="json"),
    }


def test_registration_requires_write_scope_and_publishes_target_summary(
    tmp_path: Path, monkeypatch
) -> None:
    _profile(tmp_path)
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ROLO_HOST", "0.0.0.0")
    monkeypatch.setenv("ROLO_API_TOKEN", "ingest-token")
    monkeypatch.setenv(
        "ROLO_API_TOKEN_SCOPES", "artifact-analysis:write,artifact-analysis:read"
    )
    get_settings.cache_clear()
    body = _request(_summary())
    headers = {"Authorization": "Bearer ingest-token"}
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            denied = client.post("/v1/artifact-registrations", json=body)
            registered = client.post("/v1/artifact-registrations", json=body, headers=headers)
            replayed = client.post("/v1/artifact-registrations", json=body, headers=headers)
            published = client.get(
                "/v1/targets/demo-target/artifact-analysis",
                headers={"Authorization": "Bearer ingest-token"},
            )
        assert "workbench.artifact-registration/v1" in health.json()["api_features"]
        assert denied.status_code == 401
        assert registered.status_code == 201
        assert registered.json()["status"] == "REGISTERED"
        assert replayed.status_code == 201
        assert replayed.json()["status"] == "REPLAYED"
        assert published.status_code == 200
        assert published.json()["analysis_id"] == "analysis-registration"
    finally:
        get_settings.cache_clear()


def test_registration_rejects_reuse_conflict_and_existing_summary(tmp_path: Path) -> None:
    _profile(tmp_path)
    summary = _summary()
    request = ArtifactRegistrationRequest.model_validate(_request(summary))
    receipt = register_artifact_analysis(
        tmp_path, request, now=datetime(2026, 9, 1, tzinfo=timezone.utc)
    )
    assert receipt.status == "REGISTERED"
    conflicting = request.model_copy(
        update={"summary": _summary().model_copy(update={"title": "Different"})}
    )
    try:
        register_artifact_analysis(
            tmp_path, conflicting, now=datetime(2026, 9, 1, tzinfo=timezone.utc)
        )
    except ValueError as exc:
        assert "idempotency key" in str(exc)
    else:
        raise AssertionError("idempotency reuse must be rejected")


def test_registration_rejects_job_bound_to_another_target(tmp_path: Path) -> None:
    _profile(tmp_path, "ready-local")
    _profile(tmp_path, "other-target")
    other_workspace = TargetProfileStore(tmp_path).load("other-target").target
    job = JobStore(tmp_path / "jobs").create(
        "target.bootstrap.execute",
        other_workspace.model_dump_json(),
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    summary = _summary("ready-local").model_copy(update={"job_id": job.job_id})
    request = ArtifactRegistrationRequest.model_validate(_request(summary, "mismatch-1"))

    try:
        register_artifact_analysis(
            tmp_path, request, now=datetime(2026, 9, 1, tzinfo=timezone.utc)
        )
    except ValueError as exc:
        assert "job target identity mismatch" in str(exc)
    else:
        raise AssertionError("a job bound to another target must be rejected")
