from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.hashing import sha256_file
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref


class DiagnosisHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-diagnosis-handoff/v1"] = "robot-diagnosis-handoff/v1"
    robot_id: str
    source_adapter_handoff_ref: str
    source_adapter_handoff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_config_ref: str
    frozen_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerificationHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-verification-handoff/v1"] = "robot-verification-handoff/v1"
    robot_id: str
    source_diagnosis_handoff_ref: str
    source_diagnosis_handoff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    regression_report_ref: str
    regression_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_package_ref: str
    evidence_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _verify_refs(root: Path, pairs: tuple[tuple[str, str], ...]) -> None:
    for reference, expected in pairs:
        path = resolve_artifact_ref(root, reference)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"handoff artifact hash mismatch: {reference}")


def validate_diagnosis_handoff(root: Path, robot_id: str) -> DiagnosisHandoff:
    layout = ArtifactLayout(root)
    path = layout.stage_file("diagnose", robot_id, "handoff.json")
    handoff = DiagnosisHandoff.model_validate_json(path.read_text(encoding="utf-8"))
    if handoff.robot_id != robot_id:
        raise ValueError("diagnosis handoff robot identity mismatch")
    from rolo.stages.adapt.conformance import (
        latest_adapter_handoff_path,
        validate_adapter_handoff,
    )

    adapter_path = latest_adapter_handoff_path(root, robot_id)
    if resolve_artifact_ref(root, handoff.source_adapter_handoff_ref) != adapter_path.resolve():
        raise ValueError("diagnosis handoff does not bind the canonical adapter handoff")
    validate_adapter_handoff(root, robot_id, adapter_path)
    _verify_refs(
        root,
        (
            (handoff.source_adapter_handoff_ref, handoff.source_adapter_handoff_sha256),
            (handoff.frozen_config_ref, handoff.frozen_config_sha256),
        ),
    )
    return handoff


def validate_verification_handoff(root: Path, robot_id: str) -> VerificationHandoff:
    layout = ArtifactLayout(root)
    path = layout.stage_file("verify", robot_id, "handoff.json")
    handoff = VerificationHandoff.model_validate_json(path.read_text(encoding="utf-8"))
    if handoff.robot_id != robot_id:
        raise ValueError("verification handoff robot identity mismatch")
    diagnosis_path = layout.stage_file("diagnose", robot_id, "handoff.json")
    if resolve_artifact_ref(root, handoff.source_diagnosis_handoff_ref) != diagnosis_path.resolve():
        raise ValueError("verification handoff does not bind the canonical diagnosis handoff")
    validate_diagnosis_handoff(root, robot_id)
    _verify_refs(
        root,
        (
            (handoff.source_diagnosis_handoff_ref, handoff.source_diagnosis_handoff_sha256),
            (handoff.regression_report_ref, handoff.regression_report_sha256),
            (handoff.evidence_package_ref, handoff.evidence_package_sha256),
        ),
    )
    return handoff
