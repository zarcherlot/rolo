from datetime import datetime, timezone

from fastapi.testclient import TestClient

import rolo.api as api
from rolo.api import app
from rolo.approval_gate_read_models import ApprovalGateCollection, ApprovalGateSummary


def _summary() -> ApprovalGateSummary:
    return ApprovalGateSummary(
        job_id="job_demo",
        target_id="target_demo",
        producer_revision="a" * 64,
        plan_status="APPROVAL_REQUIRED",
        steps=[
            {
                "action": "VERIFY_PLATFORM",
                "risk": "READ_ONLY",
                "approval_required": False,
                "description": "Verify target platform compatibility.",
            }
        ],
        required_approvals=["target.bootstrap.execute"],
        approval_status="PENDING",
        gate_status="PENDING",
        gate_checks=["PLAN_BOUND"],
        recovery_state="AVAILABLE",
        observed_at=datetime.now(timezone.utc),
        freshness="fresh",
    )


def test_approval_gate_routes(monkeypatch) -> None:
    summary = _summary()
    collection = ApprovalGateCollection(
        items=[summary],
        total=1,
        limit=50,
        offset=0,
        observed_at=summary.observed_at,
        freshness="fresh",
        producer_revision="b" * 64,
    )
    monkeypatch.setattr(api, "build_approval_gate_collection", lambda *a, **k: collection)
    monkeypatch.setattr(api, "get_approval_gate_summary", lambda *a, **k: summary)
    with TestClient(app) as client:
        listed = client.get("/v1/approval-gates")
        detail = client.get("/v1/jobs/job_demo/approval-gate")
    assert listed.status_code == 200
    assert listed.json()["schema_version"] == "rolo-approval-gate-collection/v1"
    assert detail.status_code == 200
    assert detail.json()["job_id"] == "job_demo"


def test_approval_gate_detail_returns_stable_404(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_approval_gate_summary", lambda *a, **k: None)
    with TestClient(app) as client:
        response = client.get("/v1/jobs/missing/approval-gate")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"
