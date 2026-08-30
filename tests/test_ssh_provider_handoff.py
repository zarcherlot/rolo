from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from rolo.stages.verify.ssh_target_provider import SshTargetHealthProvider


def test_ssh_provider_materialize_handoff_uses_canonical_v2_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    provider = object.__new__(SshTargetHealthProvider)
    provenance = tmp_path / "targets" / "robot-1" / "provenance" / "run-1.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text("{}\n", encoding="utf-8")
    from rolo.core.hashing import sha256_file

    evidence = tmp_path / "verify" / "robot-1" / "runs" / "run-1" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    payload = {
        "schema_version": "rolo-verification-evidence/v2",
        "robot_id": "robot-1",
        "run_id": "run-1",
        "target_provenance_ref": "artifact://targets/robot-1/provenance/run-1.json",
        "target_provenance_sha256": sha256_file(provenance),
        "target_provenance_schema_version": "rolo-target-provenance/v1",
        "case_results": [
            {
                "case_id": "health",
                "operation": "target.companion.health",
                "status": "PASS",
                "message": "ok",
            }
        ],
        "safe_stop": "NOT_REQUIRED",
        "rollback": "NOT_REQUIRED",
    }
    evidence.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    report = SimpleNamespace(
        evidence_ref="artifact://verify/robot-1/runs/run-1/evidence.json",
        robot_id="robot-1",
        run_id="run-1",
        status="PASS",
        case_results=payload["case_results"],
    )
    captured: dict[str, object] = {}

    def _commit(root, robot_id, *, regression_report, evidence_package, run_id):
        captured.update(
            {
                "root": root,
                "robot_id": robot_id,
                "regression_report": regression_report,
                "evidence_package": evidence_package,
                "run_id": run_id,
            }
        )
        return SimpleNamespace(schema_version="robot-verification-handoff/v1")

    monkeypatch.setattr(
        "rolo.stages.verify.ssh_target_provider.commit_verification_handoff", _commit
    )
    result = provider.materialize_handoff(tmp_path, report)

    assert result.schema_version == "robot-verification-handoff/v1"
    assert captured["robot_id"] == "robot-1"
    assert captured["run_id"] == "run-1"
    assert captured["regression_report"]["schema_version"] == (
        "rolo-verification-regression-report/v1"
    )
    assert captured["evidence_package"]["schema_version"] == "rolo-verification-evidence/v2"
