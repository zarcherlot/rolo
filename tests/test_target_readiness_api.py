from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import rolo.api as api
from rolo.api import app
from rolo.target_readiness import TargetReadinessCollection, TargetReadinessSummary


def _summary() -> TargetReadinessSummary:
    return TargetReadinessSummary(
        target_id="demo_one",
        target_kind="local",
        state="READY",
        reachable=True,
        host_key_pinned=None,
        workspace_accessible=True,
        companion="NOT_REQUIRED",
        observed_at=datetime.now(timezone.utc),
        freshness="fresh",
        producer_revision="a" * 64,
    )


def test_target_readiness_routes_and_not_found(monkeypatch, tmp_path: Path) -> None:
    collection = TargetReadinessCollection(
        items=[_summary()],
        total=1,
        limit=50,
        offset=0,
        observed_at=datetime.now(timezone.utc),
        freshness="fresh",
        producer_revision="b" * 64,
    )
    monkeypatch.setattr(
        api, "build_target_readiness_collection", lambda *args, **kwargs: collection
    )
    monkeypatch.setattr(api, "get_target_readiness_summary", lambda *args, **kwargs: _summary())

    with TestClient(app) as client:
        listed = client.get("/v1/targets/readiness")
        detail = client.get("/v1/targets/demo_one/readiness")

    assert listed.status_code == 200
    assert listed.json()["schema_version"] == "rolo-target-readiness-collection/v1"
    assert detail.status_code == 200
    assert detail.json()["schema_version"] == "rolo-target-readiness-summary/v1"


def test_target_readiness_route_returns_stable_404(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_target_readiness_summary", lambda *args, **kwargs: None)
    with TestClient(app) as client:
        response = client.get("/v1/targets/missing_target/readiness")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "TARGET_NOT_FOUND"
