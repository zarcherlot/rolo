from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.stages.downstream_tools import DownstreamToolConsumer
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationOracle,
    VerificationPlan,
    evaluate_oracle,
    run_verification_plan,
)
from tests.test_downstream_tools import NOW, _Gateway, _session


def _consumer() -> DownstreamToolConsumer:
    session = _session(stage="verify")
    from rolo.stages.downstream_tools import DownstreamToolHandoff

    handoff = DownstreamToolHandoff(
        stage="verify",
        robot_id="robot-1",
        caller="verify-agent",
        tool_session_ref="artifact://verify/robot-1/latest/tool_session.json",
        tool_session_sha256="a" * 64,
        session_id=session.session_id,
        release_id=session.release_id,
        tool_catalog_sha256=session.tool_catalog_sha256,
        state_graph_sha256=session.state_graph_sha256,
    )
    return DownstreamToolConsumer(
        handoff=handoff,
        session=session,
        gateway=_Gateway(),
        clock=lambda: NOW,
    )


def test_oracle_evaluation_is_deterministic_and_bounded() -> None:
    oracle = VerificationOracle(
        kind="NUMERIC_BETWEEN",
        path="metrics.latency",
        minimum=1,
        maximum=5,
    )
    assert evaluate_oracle(oracle, {"metrics": {"latency": 3}}) == (
        True,
        "numeric value is within bounds",
    )
    assert evaluate_oracle(oracle, {"metrics": {"latency": 9}})[0] is False


def test_verification_plan_persists_case_evidence_and_passes(tmp_path: Path) -> None:
    provenance = tmp_path / "target-provenance.json"
    provenance.write_text('{"target":"robot-1"}\n', encoding="utf-8")
    from rolo.core.hashing import sha256_file

    plan = VerificationPlan(
        robot_id="robot-1",
        cases=[
            VerificationCase(
                case_id="camera-frame",
                operation="app.camera.snapshot",
                oracle=VerificationOracle(kind="FIELD_EQUALS", path="frame", expected=7),
            )
        ],
    )
    report = run_verification_plan(
        plan,
        consumer=_consumer(),
        artifacts=ArtifactStore(tmp_path),
        clock=lambda: NOW,
        target_provenance_ref="artifact://target-provenance.json",
        target_provenance_sha256=sha256_file(provenance),
    )
    assert report.status == "PASS"
    assert report.case_results[0].audit_ref == "audit:event-1"
    assert (tmp_path / report.evidence_ref.removeprefix("artifact://")).is_file()


def test_verification_plan_honors_cancellation_before_invocation(tmp_path: Path) -> None:
    provenance = tmp_path / "target-provenance.json"
    provenance.write_text('{"target":"robot-1"}\n', encoding="utf-8")
    from rolo.core.hashing import sha256_file

    plan = VerificationPlan(
        robot_id="robot-1",
        cases=[
            VerificationCase(
                case_id="cancelled",
                operation="app.camera.snapshot",
                oracle=VerificationOracle(kind="FIELD_EXISTS", path="frame"),
            )
        ],
    )
    cancel = threading.Event()
    cancel.set()
    report = run_verification_plan(
        plan,
        consumer=_consumer(),
        artifacts=ArtifactStore(tmp_path),
        cancel_event=cancel,
        clock=lambda: datetime.now(timezone.utc),
        target_provenance_ref="artifact://target-provenance.json",
        target_provenance_sha256=sha256_file(provenance),
    )
    assert report.status == "CANCELLED"
    assert report.case_results[0].status == "CANCELLED"
