from __future__ import annotations

import pytest

from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.contracts import StageStatus
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationOracle,
    VerificationPlan,
)
from rolo.stages.verify.service import (
    build_verification_task,
    publish_verification_plan,
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


def test_build_and_publish_verification_task_binds_input_digests(tmp_path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    layout = ArtifactLayout(artifact_root)
    diagnosis = layout.stage_file("diagnose", "robot-1", "handoff.json")
    inputs = layout.stage_file("verify", "robot-1", "inputs.json")
    diagnosis.parent.mkdir(parents=True)
    inputs.parent.mkdir(parents=True)
    diagnosis.write_text("{}", encoding="utf-8")
    inputs.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("rolo.stages.verify.service.validate_diagnosis_handoff", lambda *args: None)
    task = build_verification_task(
        artifact_root,
        "robot-1",
        provider="fake",
        executor="fake",
        additional_input_refs={"extra": layout.ref(inputs)},
    )
    assert task.stage == "verify"
    assert set(task.input_refs) == {"verification_inputs", "diagnosis_handoff", "extra"}
    assert set(task.input_sha256) == set(task.input_refs)
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
    reference = publish_verification_plan(
        artifact_root, "robot-1", plan, allowed_operations={"app.inspect"}
    )
    assert reference.endswith("/acceptance_plan.json")
    with pytest.raises(ValueError, match="duplicate verification task input"):
        build_verification_task(
            artifact_root,
            "robot-1",
            provider="fake",
            executor="fake",
            additional_input_refs={"verification_inputs": layout.ref(inputs)},
        )
