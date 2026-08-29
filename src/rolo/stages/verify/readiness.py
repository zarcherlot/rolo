"""Canonical v2 Verify provider manifest and readiness gate.

The readiness report is a product-side gate, not release authority.  It binds a
provider manifest, target provenance, plan and evidence package by digest and
rejects the legacy P1 v1 provider envelope instead of silently promoting it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.hashing import sha256_file
from rolo.stages.artifact_paths import resolve_artifact_ref


ArtifactDigest = str


class VerificationProviderManifestV2(BaseModel):
    """Frozen capabilities for a provider that emits canonical v2 evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-provider-manifest/v2"] = (
        "rolo-verification-provider-manifest/v2"
    )
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    provider_version: str = Field(min_length=1, max_length=128)
    executor_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    model: str | None = Field(default=None, max_length=256)
    supported_operations: list[str] = Field(min_length=1, max_length=256)
    max_case_timeout_s: float = Field(default=600.0, gt=0.0, le=600.0)
    read_only: Literal[True] = True
    cancellation_supported: Literal[True] = True
    safe_stop_supported: Literal[True] = True
    evidence_contract: Literal["rolo-verification-evidence/v2"] = (
        "rolo-verification-evidence/v2"
    )
    target_provenance_schema_version: Literal["rolo-target-provenance/v2"] = (
        "rolo-target-provenance/v2"
    )

    @field_validator("supported_operations")
    @classmethod
    def unique_operations(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 256 for item in value):
            raise ValueError("provider operations must be non-empty strings")
        if len(value) != len(set(value)):
            raise ValueError("provider operations must be unique")
        return value


class ReadinessCheck(BaseModel):
    """One named, deterministic readiness assertion."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["PASS", "FAIL"]
    detail: str = Field(min_length=1, max_length=2_000)


class RealVerifyReadinessReportV2(BaseModel):
    """Machine-readable gate for beginning a physical target Verify run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-real-verify-readiness/v2"] = (
        "rolo-real-verify-readiness/v2"
    )
    robot_id: str = Field(min_length=1, max_length=128)
    status: Literal["READY", "BLOCKED"]
    checks: dict[str, ReadinessCheck] = Field(min_length=1, max_length=128)
    provider_run_id: str | None = Field(default=None, max_length=256)
    plan_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_manifest_ref: str | None = Field(default=None, pattern=r"^artifact://")
    provider_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    target_provenance_ref: str | None = Field(default=None, pattern=r"^artifact://")
    target_provenance_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_ref: str | None = Field(default=None, pattern=r"^artifact://")
    evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    blockers: list[str] = Field(default_factory=list, max_length=128)
    release_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def validate_gate(self) -> RealVerifyReadinessReportV2:
        if self.status == "READY":
            if self.blockers:
                raise ValueError("READY readiness report cannot contain blockers")
            if any(check.status != "PASS" for check in self.checks.values()):
                raise ValueError("READY readiness report requires all checks to PASS")
            required = (
                self.provider_manifest_ref,
                self.provider_manifest_sha256,
                self.target_provenance_ref,
                self.target_provenance_sha256,
                self.evidence_ref,
                self.evidence_sha256,
            )
            if any(value is None for value in required):
                raise ValueError("READY readiness report requires all canonical artifact bindings")
        elif not self.blockers:
            raise ValueError("BLOCKED readiness report must explain at least one blocker")
        if bool(self.provider_manifest_ref) != bool(self.provider_manifest_sha256):
            raise ValueError("provider manifest reference and digest must be paired")
        if bool(self.target_provenance_ref) != bool(self.target_provenance_sha256):
            raise ValueError("target provenance reference and digest must be paired")
        if bool(self.evidence_ref) != bool(self.evidence_sha256):
            raise ValueError("evidence reference and digest must be paired")
        return self


def validate_readiness_report(
    payload: Mapping[str, object],
    *,
    artifact_root: Path | None = None,
    robot_id: str | None = None,
) -> RealVerifyReadinessReportV2:
    """Validate report structure and, when available, every bound artifact digest."""

    report = RealVerifyReadinessReportV2.model_validate(payload)
    if robot_id is not None and report.robot_id != robot_id:
        raise ValueError("readiness robot identity mismatch")
    if artifact_root is None:
        return report

    def checked_path(reference: str, digest: str, label: str) -> Path:
        path = resolve_artifact_ref(artifact_root, reference)
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"{label} artifact hash mismatch")
        return path

    if report.provider_manifest_ref and report.provider_manifest_sha256:
        manifest_path = checked_path(
            report.provider_manifest_ref, report.provider_manifest_sha256, "provider manifest"
        )
        manifest = VerificationProviderManifestV2.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        if manifest.evidence_contract != "rolo-verification-evidence/v2":
            raise ValueError("provider manifest must emit canonical v2 evidence")

    if report.target_provenance_ref and report.target_provenance_sha256:
        provenance_path = checked_path(
            report.target_provenance_ref, report.target_provenance_sha256, "target provenance"
        )
        from rolo.stages.diagnose.episode import TargetProvenance

        provenance = TargetProvenance.model_validate_json(
            provenance_path.read_text(encoding="utf-8")
        )
        if provenance.schema_version != "rolo-target-provenance/v2":
            raise ValueError("readiness requires canonical v2 target provenance")
        if provenance.target_id != report.robot_id:
            raise ValueError("target provenance identity mismatch")

    if report.evidence_ref and report.evidence_sha256:
        evidence_path = checked_path(report.evidence_ref, report.evidence_sha256, "evidence")
        from rolo.stages.verify.acceptance import VerificationEvidencePackage

        evidence = VerificationEvidencePackage.model_validate_json(
            evidence_path.read_text(encoding="utf-8")
        )
        if evidence.schema_version != "rolo-verification-evidence/v2":
            raise ValueError("readiness requires canonical v2 evidence")
        if evidence.robot_id != report.robot_id:
            raise ValueError("evidence robot identity mismatch")
    return report
