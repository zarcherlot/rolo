from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolo.stages.diagnose.episode import TargetProvenance
from rolo.stages.verify.acceptance import VerificationEvidencePackage


def _p1_legacy_evidence_package() -> dict[str, object]:
    """Representative P1 v1 package; it must not cross the main v2 boundary."""

    return {
        "schema_version": "rolo-verification-evidence-package/v1",
        "robot_id": "robot-1",
        "provider_run_id": "verify-target-1",
        "status": "PASS",
        "plan_sha256": "a" * 64,
        "provider_manifest_sha256": "b" * 64,
        "provider_evidence_index_ref": "artifact://verify/robot-1/index.json",
        "provider_evidence_index_sha256": "c" * 64,
        "verification_evidence_ref": "artifact://verify/robot-1/evidence.json",
        "verification_evidence_sha256": "d" * 64,
        "evidence": ["artifact://verify/robot-1/case.json"],
        "release_authority": "none",
    }


def test_p1_v1_evidence_package_is_rejected_by_main_v2_contract() -> None:
    with pytest.raises(ValidationError):
        VerificationEvidencePackage.model_validate(_p1_legacy_evidence_package())


def test_p1_ssh_provenance_is_not_implicitly_promoted_to_target_provenance() -> None:
    legacy_provenance = {
        "schema_version": "rolo-verification-target-provenance/v1",
        "transport": "ssh",
        "host": "robot.example",
        "port": 22,
        "user": "robot",
        "workspace": "/opt/rolo",
        "known_hosts_sha256": "a" * 64,
        "expected_companion": "rolo-target 0.1.0",
    }

    with pytest.raises(ValidationError):
        TargetProvenance.model_validate(legacy_provenance)


def test_main_v2_package_requires_explicit_safety_outcomes() -> None:
    payload = {
        "schema_version": "rolo-verification-evidence/v2",
        "robot_id": "robot-1",
        "run_id": "verify-1",
        "target_provenance_ref": "artifact://targets/robot-1/provenance/verify-1.json",
        "target_provenance_sha256": "a" * 64,
        "target_provenance_schema_version": "rolo-target-provenance/v2",
        "case_results": [
            {
                "case_id": "health",
                "operation": "target.companion.health",
                "status": "PASS",
                "message": "ok",
            }
        ],
    }

    with pytest.raises(ValidationError):
        VerificationEvidencePackage.model_validate(payload)
