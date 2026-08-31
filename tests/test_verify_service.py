from __future__ import annotations

from rolo.stages.contracts import StageStatus
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationOracle,
    VerificationPlan,
)
from rolo.stages.verify.service import (
    validate_verification_plan_operations,
    verification_outcome_status,
)


def _result(status: str = "PASS") -> dict[str, object]:
    return {"case_id": "case-1", "operation": "app.inspect", "status": status, "message": "ok"}


def _evidence(
    *, schema: str = "rolo-target-provenance/v2", status: str = "PASS"
) -> dict[str, object]:
    return {
        "robot_id": "robot-1",
        "run_id": "run-1",
        "target_provenance_ref": "artifact://provenance.json",
        "target_provenance_sha256": "a" * 64,
        "target_provenance_schema_version": schema,
        "case_results": [_result(status)],
        "safe_stop": "VERIFIED",
        "rollback": "NOT_REQUIRED",
    }


def test_verification_outcome_requires_independent_complete_evidence() -> None:
    report = {"status": "PASS", "decision": "PASS", "case_results": [_result()]}
    assert verification_outcome_status(report, _evidence()) is StageStatus.COMPLETE
    for bad_report in (
        {"status": "FAIL", "decision": "PASS", "case_results": [_result()]},
        {"status": "PASS", "decision": "INCONCLUSIVE", "case_results": [_result()]},
        {"status": "PASS", "decision": "PASS", "case_results": []},
        {"status": "PASS", "decision": "PASS", "case_results": [_result("FAIL")]},
    ):
        assert verification_outcome_status(bad_report, _evidence()) is StageStatus.DEGRADED
    assert (
        verification_outcome_status(report, _evidence(schema="rolo-target-provenance/v1"))
        is StageStatus.DEGRADED
    )
    assert verification_outcome_status(report, _evidence(status="FAIL")) is StageStatus.DEGRADED
    assert (
        verification_outcome_status(report, {**_evidence(), "safe_stop": "NOT_VERIFIED"})
        is StageStatus.DEGRADED
    )
    assert (
        verification_outcome_status(report, {**_evidence(), "rollback": "NOT_VERIFIED"})
        is StageStatus.DEGRADED
    )
    assert (
        verification_outcome_status(
            report, {**_evidence(), "case_results": [{**_result(), "case_id": "other"}]}
        )
        is StageStatus.DEGRADED
    )


def test_verification_plan_operations_are_allowlisted() -> None:
    plan = VerificationPlan(
        robot_id="robot-1",
        cases=[
            VerificationCase(
                case_id="case-1",
                operation="app.inspect",
                oracle=VerificationOracle(kind="FIELD_EXISTS", path="status"),
            )
        ],
    )
    validate_verification_plan_operations(plan, {"app.inspect"})
    try:
        validate_verification_plan_operations(plan, {"ros.topic.list"})
    except ValueError as exc:
        assert "non-allowlisted" in str(exc)
    else:
        raise AssertionError("non-allowlisted operation was accepted")
