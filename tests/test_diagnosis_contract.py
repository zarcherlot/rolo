from __future__ import annotations

import pytest

from rolo.stages.diagnose_contract import DiagnosisReport


def _report() -> dict[str, object]:
    return {
        "schema_version": "rolo-diagnosis-report/v1",
        "robot_id": "robot-1",
        "baseline": {"state": "idle"},
        "observations": [{"fact": "camera available"}],
        "hypotheses": [{"cause": "stale calibration"}],
        "changes": [{"kind": "parameter-review", "applied": False}],
        "smoke": {"status": "PASS"},
        "decision": "INCONCLUSIVE",
        "episode_refs": ["artifact://episodes/robot-1/records/episode-1/revision-1.json"],
        "limitations": ["No actuator test was requested"],
    }


def test_diagnosis_report_requires_closed_loop_and_episode_reference() -> None:
    report = DiagnosisReport.model_validate(_report())
    assert report.decision == "INCONCLUSIVE"
    assert report.episode_refs[0].startswith("artifact://")


def test_diagnosis_report_rejects_missing_closed_loop_step() -> None:
    payload = _report()
    payload["observations"] = []
    with pytest.raises(ValueError, match="observations"):
        DiagnosisReport.model_validate(payload)
