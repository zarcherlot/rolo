from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rolo.api import app
from rolo.artifact_analysis import ArtifactAnalysisConflict, ArtifactAnalysisSummary
from rolo.core.config import get_settings
from rolo.target_ref import LocalTargetRef
from rolo.targets.profiles import CredentialReference, TargetProfileStore


def _summary(
    target_id: str = "demo-target", *, job_id: str | None = None
) -> ArtifactAnalysisSummary:
    return ArtifactAnalysisSummary(
        analysis_id="analysis-demo",
        target_id=target_id,
        robot_id=target_id,
        job_id=job_id,
        run_id="run-demo",
        discovery_id="discovery-demo",
        source_label="Sanitized producer summary",
        observed_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
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
                "timestamp": "00:00:00Z",
                "detail": "Complete.",
            }
        ],
        findings=[{"tone": "blue", "title": "Advisory", "body": "No release effect."}],
        hashes=[("summary", "a1b2c3d4e5f60718")],
        limitations=["Bounded and advisory."],
    )


def _write_fixture(root: Path, summary: ArtifactAnalysisSummary) -> None:
    robots = root / "robots"
    robots.mkdir(parents=True)
    source = Path(__file__).parent / "fixtures" / "robots" / "demo_diff.yaml"
    shutil.copy2(source, robots / source.name)
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    TargetProfileStore(root).create(
        robot_id=summary.target_id,
        target=LocalTargetRef(workspace=workspace),
        credential=CredentialReference(kind="platform-keychain", reference="demo:target"),
        now=summary.observed_at,
    )
    path = root / "artifact-analysis" / f"{summary.target_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")


def test_artifact_endpoint_is_bounded_and_feature_negotiated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "runtime-artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "runtime-output"))
    get_settings.cache_clear()
    summary = _summary()
    _write_fixture(tmp_path, summary)
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            response = client.get("/v1/targets/demo-target/artifact-analysis")
            missing = client.get("/v1/targets/other-target/artifact-analysis")
        assert "workbench.artifact-analysis-read-model/v1" in health.json()["api_features"]
        assert response.status_code == 200
        assert response.json()["source_kind"] == "rolo_api"
        assert response.json()["contains_secret_payloads"] is False
        assert missing.status_code == 404
        (tmp_path / "artifact-analysis" / "demo-target.json").unlink()
        unavailable = client.get("/v1/targets/demo-target/artifact-analysis")
        assert unavailable.status_code == 200
        assert unavailable.json()["gate_status"] == "NOT_AVAILABLE"
    finally:
        get_settings.cache_clear()


def test_artifact_endpoint_rejects_identity_and_secret_payloads(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ArtifactAnalysisSummary.model_validate(
            {**_summary().model_dump(), "contains_secret_payloads": True}
        )
    with pytest.raises(ValueError):
        ArtifactAnalysisSummary.model_validate(
            {**_summary().model_dump(), "source_kind": "demo_fixture"}
        )

    raw = _summary().model_dump(mode="json")
    raw["target_id"] = "other-target"
    with pytest.raises(ArtifactAnalysisConflict):
        _write_fixture(tmp_path, _summary())
        path = tmp_path / "artifact-analysis" / "demo-target.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        from rolo.artifact_analysis import get_artifact_analysis

        get_artifact_analysis(tmp_path, "demo-target")


def test_artifact_summary_rejects_oversized_and_unsafe_nested_values() -> None:
    base = _summary().model_dump()
    with pytest.raises(ValueError):
        ArtifactAnalysisSummary.model_validate({**base, "findings": [base["findings"][0]] * 41})
    unsafe = {
        **base,
        "operations": [
            {
                "name": "app.inspect",
                "route": "observed",
                "route_status": "observed",
                "checks": ["bounded"],
                "contract": "safe",
                "download_url": "https://example.invalid/report",
            }
        ],
    }
    with pytest.raises(ValueError):
        ArtifactAnalysisSummary.model_validate(unsafe)
