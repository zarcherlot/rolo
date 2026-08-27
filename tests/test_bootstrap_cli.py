import json
from datetime import datetime, timedelta, timezone

from typer.testing import CliRunner

from rolo.product_cli import app
from rolo.target_ref import parse_target_ref
from rolo.targets.approvals import BootstrapApprovalDecision, BootstrapApprovalRequest
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan


def test_bootstrap_execute_plan_only_never_constructs_transport(tmp_path):
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
    result = CliRunner().invoke(
        app,
        [
            "target",
            "bootstrap-execute",
            str(files["plan"]),
            str(files["request"]),
            str(files["decision"]),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--package",
            str(tmp_path / "package.pkg"),
            "--verification-key-file",
            str(tmp_path / "key"),
            "--known-hosts",
            str(tmp_path / "known_hosts"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "BOOTSTRAP_EXECUTION_READY"
    assert payload["mutation_started"] is False
