from __future__ import annotations

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.stages.verify.acceptance import (
    OracleKind,
    VerificationCase,
    VerificationCaseResult,
    VerificationEvidencePackage,
    VerificationOracle,
    VerificationPlan,
    VerificationReplayCase,
    VerificationReplayFixture,
    run_verification_replay,
    validate_structured_verification_evidence,
)


def _evidence() -> dict[str, object]:
    result = VerificationCaseResult(
        case_id="smoke",
        operation="linux.host.inventory",
        status="PASS",
        message="ok",
        provenance_ref="artifact://target/provenance.json",
        rollback_status="NOT_REQUIRED",
    )
    return {
        "schema_version": "rolo-verification-evidence/v2",
        "robot_id": "robot-1",
        "run_id": "verify-1",
        "target_provenance_ref": "artifact://target/provenance.json",
        "target_provenance_sha256": "a" * 64,
        "case_results": [result.model_dump(mode="json")],
        "safe_stop": "NOT_REQUIRED",
        "rollback": "NOT_REQUIRED",
        "replay_ref": "artifact://verify/replay.json",
    }


def test_structured_verification_evidence_is_replayable_and_target_bound(tmp_path) -> None:
    provenance = tmp_path / "target" / "provenance.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text('{"target":"robot-1"}\n', encoding="utf-8")
    replay = tmp_path / "verify" / "replay.json"
    replay.parent.mkdir(parents=True)
    replay.write_text('{"replayed":true}\n', encoding="utf-8")
    payload = _evidence()
    payload["target_provenance_sha256"] = sha256_file(provenance)
    evidence = validate_structured_verification_evidence(
        payload, robot_id="robot-1", artifact_root=tmp_path
    )
    assert evidence.case_results[0].status == "PASS"
    assert evidence.target_provenance_ref.startswith("artifact://")


def test_structured_verification_evidence_rejects_identity_and_duplicates() -> None:
    with pytest.raises(ValueError, match="robot identity"):
        validate_structured_verification_evidence(_evidence(), robot_id="other")
    payload = _evidence()
    payload["case_results"] = [payload["case_results"][0], payload["case_results"][0]]
    with pytest.raises(ValueError, match="case IDs"):
        VerificationEvidencePackage.model_validate(payload)


def test_verify_replay_produces_independent_evidence_and_failure_classification(tmp_path) -> None:
    provenance = tmp_path / "target" / "provenance.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text('{"target":"robot-1"}\n', encoding="utf-8")
    replay = tmp_path / "verify" / "replay.json"
    replay.parent.mkdir(parents=True)
    replay.write_text('{"fixture":"r1"}\n', encoding="utf-8")
    fixture = VerificationReplayFixture(
        fixture_id="r1",
        robot_id="robot-1",
        target_provenance_ref="artifact://target/provenance.json",
        target_provenance_sha256=sha256_file(provenance),
        replay_ref="artifact://verify/replay.json",
        cases=[
            VerificationReplayCase(
                case_id="status",
                operation="linux.host.inventory",
                result={"status": "ready"},
            ),
            VerificationReplayCase(
                case_id="timeout",
                operation="linux.service.inspect",
                status="TIMEOUT",
                message="captured timeout",
            ),
        ],
    )
    plan = VerificationPlan(
        robot_id="robot-1",
        cases=[
            VerificationCase(
                case_id="status",
                operation="linux.host.inventory",
                oracle=VerificationOracle(
                    kind=OracleKind.FIELD_EQUALS, path="status", expected="ready"
                ),
            ),
            VerificationCase(
                case_id="timeout",
                operation="linux.service.inspect",
                oracle=VerificationOracle(kind=OracleKind.FIELD_EXISTS, path="status"),
            ),
        ],
    )
    report = run_verification_replay(plan, fixture, artifacts=ArtifactStore(tmp_path))
    assert report.status == "FAIL"
    assert [item.status for item in report.case_results] == ["PASS", "TIMEOUT"]
    evidence = VerificationEvidencePackage.model_validate_json(
        (tmp_path / report.evidence_ref.removeprefix("artifact://")).read_text(encoding="utf-8")
    )
    assert evidence.replay_ref == "artifact://verify/replay.json"
