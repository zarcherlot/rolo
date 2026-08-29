from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.verify.readiness import (
    ReadinessCheck,
    RealVerifyReadinessReportV2,
    VerificationProviderManifestV2,
    validate_readiness_report,
)


def _manifest() -> VerificationProviderManifestV2:
    return VerificationProviderManifestV2(
        provider_id="target-health",
        provider_version="2.0.0",
        executor_id="ssh-bounded",
        supported_operations=["target.platform.read", "target.workspace.readiness"],
    )


def _ready() -> RealVerifyReadinessReportV2:
    digest = "a" * 64
    return RealVerifyReadinessReportV2(
        robot_id="r1",
        status="READY",
        checks={"manifest": ReadinessCheck(status="PASS", detail="manifest accepted")},
        provider_run_id="run-1",
        plan_sha256=digest,
        provider_manifest_ref="artifact://verify/r1/manifest.json",
        provider_manifest_sha256=digest,
        target_provenance_ref="artifact://verify/r1/provenance.json",
        target_provenance_sha256=digest,
        evidence_ref="artifact://verify/r1/evidence.json",
        evidence_sha256=digest,
    )


def test_manifest_is_v2_and_cannot_claim_legacy_evidence() -> None:
    manifest = _manifest()
    assert manifest.evidence_contract == "rolo-verification-evidence/v2"
    assert manifest.target_provenance_schema_version == "rolo-target-provenance/v2"
    with pytest.raises(ValueError):
        VerificationProviderManifestV2.model_validate(
            {**manifest.model_dump(), "schema_version": "rolo-verification-provider-manifest/v1"}
        )


def test_ready_requires_all_pass_and_canonical_bindings() -> None:
    report = _ready()
    assert report.status == "READY"
    with pytest.raises(ValueError, match="requires all checks"):
        RealVerifyReadinessReportV2.model_validate(
            {**report.model_dump(), "checks": {"manifest": {"status": "FAIL", "detail": "bad"}}}
        )
    with pytest.raises(ValueError, match="canonical artifact bindings"):
        RealVerifyReadinessReportV2.model_validate(
            {**report.model_dump(), "evidence_ref": None, "evidence_sha256": None}
        )


def test_blocked_requires_explanation_and_preserves_release_boundary() -> None:
    report = RealVerifyReadinessReportV2(
        robot_id="r1",
        status="BLOCKED",
        checks={"target": ReadinessCheck(status="FAIL", detail="unreachable")},
        blockers=["target is unreachable"],
    )
    assert report.release_authority == "none"
    with pytest.raises(ValueError, match="explain"):
        RealVerifyReadinessReportV2.model_validate(
            {**report.model_dump(), "blockers": []}
        )


def test_manifest_digest_tamper_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    layout = ArtifactLayout(tmp_path)
    path = store.write_json(
        "verify/r1/manifest.json", _manifest().model_dump(mode="json")
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = RealVerifyReadinessReportV2(
        robot_id="r1",
        status="BLOCKED",
        checks={"manifest": ReadinessCheck(status="FAIL", detail="not approved")},
        provider_manifest_ref=layout.ref(path),
        provider_manifest_sha256=digest,
        blockers=["approval is pending"],
    )
    path.write_text(path.read_text(encoding="utf-8") + "tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest artifact hash mismatch"):
        validate_readiness_report(report.model_dump(mode="json"), artifact_root=tmp_path)


def test_schema_exports_are_explicitly_versioned() -> None:
    assert "rolo-real-verify-readiness/v2" in RealVerifyReadinessReportV2.model_json_schema()[
        "properties"
    ]["schema_version"]["const"]
    assert "rolo-verification-provider-manifest/v2" in VerificationProviderManifestV2.model_json_schema()[
        "properties"
    ]["schema_version"]["const"]
