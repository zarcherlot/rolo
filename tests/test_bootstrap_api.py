from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings
from rolo.target_ref import parse_target_ref
from rolo.targets.approvals import BootstrapApprovalDecision, BootstrapApprovalRequest
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan


def test_bootstrap_execute_api_defaults_to_plan_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()
    now = datetime.now(timezone.utc)
    plan = TargetBootstrapPlan(
        target=parse_target_ref("ssh://robot@example.test/home/robot/workspace"),
        assessment_state="READY",
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        required_approvals=["target.bootstrap.execute"],
    )
    request = BootstrapApprovalRequest(
        request_id="bar-" + "a" * 32,
        plan_sha256="b" * 64,
        scope="target.bootstrap.execute",
        requested_by="agent",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    decision = BootstrapApprovalDecision(
        request_id=request.request_id,
        plan_sha256=request.plan_sha256,
        scope=request.scope,
        approved_by="operator",
        approved_at=now,
    )
    files = {}
    for name, model in (("plan", plan), ("request", request), ("decision", decision)):
        path = tmp_path / f"{name}.json"
        path.write_text(model.model_dump_json(), encoding="utf-8")
        files[name] = path
    payload = {
        "plan_file": str(files["plan"]),
        "request_file": str(files["request"]),
        "decision_file": str(files["decision"]),
        "manifest_file": str(tmp_path / "manifest.json"),
        "package_file": str(tmp_path / "package.pkg"),
        "verification_key_file": str(tmp_path / "key"),
        "known_hosts": str(tmp_path / "known_hosts"),
    }
    with TestClient(app) as client:
        response = client.post("/v1/targets/bootstrap-execute", json=payload)
    get_settings.cache_clear()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "BOOTSTRAP_EXECUTION_READY"
    assert body["mutation_started"] is False
