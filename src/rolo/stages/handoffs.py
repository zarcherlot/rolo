from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.artifacts import ArtifactStore
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
    diagnosis_report_ref: str | None = None
    diagnosis_report_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


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


# These are deliberately small, provider-neutral guards.  Diagnose/Verify Agents may use
# any internal report shape, but Rolo must reject an empty report or an Agent attempting to
# smuggle release authority through an otherwise untrusted JSON object.
_AUTHORITY_KEYS = {
    "release_authority",
    "publication_authority",
    "publish_release",
    "release_decision",
    "release_approved",
}
_AUTHORITY_VALUES = {"RELEASED", "VERIFIED", "APPROVED", "PUBLISHED"}
_NO_AUTHORITY_VALUES = {"", "NONE", "NO", "FALSE", "DENIED", "NOT_GRANTED", "UNAUTHORIZED"}


def _contains_release_claim(value: object, *, key: str = "") -> bool:
    normalized_key = key.strip().lower()
    if normalized_key in _AUTHORITY_KEYS:
        if isinstance(value, str):
            return value.strip().upper() not in _NO_AUTHORITY_VALUES
        return bool(value)
    if isinstance(value, str) and value.strip().upper() in _AUTHORITY_VALUES:
        return True
    if isinstance(value, Mapping):
        return any(
            _contains_release_claim(item, key=str(child_key))
            for child_key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_release_claim(item) for item in value)
    return False


def validate_diagnosis_result(
    frozen_config: Mapping[str, object], diagnosis_report: Mapping[str, object]
) -> None:
    """Validate the minimum safety envelope for an untrusted Diagnose result."""

    if not isinstance(frozen_config, Mapping) or not frozen_config:
        raise ValueError("diagnosis frozen_config must be a non-empty JSON object")
    if not isinstance(diagnosis_report, Mapping) or not diagnosis_report:
        raise ValueError("diagnosis_report must be a non-empty JSON object")
    if _contains_release_claim(diagnosis_report):
        raise ValueError("diagnosis_report cannot claim release or publication authority")
    if diagnosis_report.get("schema_version") == "rolo-diagnosis-report/v1":
        from rolo.stages.diagnose_contract import validate_structured_diagnosis_report

        validate_structured_diagnosis_report(diagnosis_report)


def validate_verification_result(
    regression_report: Mapping[str, object], evidence_package: Mapping[str, object]
) -> None:
    """Validate the minimum machine-evidence envelope for an untrusted Verify result."""

    if not isinstance(regression_report, Mapping) or not regression_report:
        raise ValueError("regression_report must be a non-empty JSON object")
    if not isinstance(evidence_package, Mapping) or not evidence_package:
        raise ValueError("evidence_package must be a non-empty JSON object")
    if _contains_release_claim(regression_report) or _contains_release_claim(evidence_package):
        raise ValueError("verification results cannot claim release or publication authority")
    # Require at least one observable result/evidence collection.  This keeps a prose-only
    # Agent response from becoming a COMPLETE Verify handoff while allowing domain-specific
    # names (checks, cases, artifacts, observations, ...).
    report_markers = {"passed", "failed", "status", "checks", "cases", "results", "outcome"}
    evidence_markers = {"artifacts", "checks", "evidence", "observations", "logs", "episodes"}
    if not any(key in regression_report for key in report_markers):
        raise ValueError("regression_report must contain a measurable result marker")
    if not any(key in evidence_package for key in evidence_markers):
        raise ValueError("evidence_package must contain an evidence collection marker")
    case_results = regression_report.get("case_results")
    if case_results is not None:
        if not isinstance(case_results, list) or not case_results:
            raise ValueError("regression_report case_results must be a non-empty list")
        allowed = {"PASS", "FAIL", "TIMEOUT", "CANCELLED", "ERROR"}
        for item in case_results:
            if not isinstance(item, Mapping):
                raise ValueError("each case result must be a JSON object")
            if not isinstance(item.get("case_id"), str) or not item.get("case_id"):
                raise ValueError("each case result requires case_id")
            if item.get("status") not in allowed:
                raise ValueError("each case result has an invalid status")


def _verify_refs(root: Path, pairs: tuple[tuple[str, str], ...]) -> None:
    for reference, expected in pairs:
        path = resolve_artifact_ref(root, reference)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"handoff artifact hash mismatch: {reference}")


def _load_mapping_ref(root: Path, reference: str, *, label: str) -> dict[str, object]:
    path = resolve_artifact_ref(root, reference)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _run_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _write_run_handoff(
    store: ArtifactStore,
    layout: ArtifactLayout,
    *,
    stage: Literal["diagnose", "verify"],
    robot_id: str,
    run_id: str,
    handoff: BaseModel,
) -> Path:
    run_path = store.write_json(
        layout.relative(layout.stage_run(stage, robot_id, run_id) / "handoff.json"),
        handoff.model_dump(mode="json"),
    )
    return run_path


def commit_diagnosis_handoff(
    artifact_root: Path,
    robot_id: str,
    *,
    frozen_config: Mapping[str, object],
    diagnosis_report: Mapping[str, object],
    run_id: str | None = None,
) -> DiagnosisHandoff:
    """Freeze a Diagnose result and publish only a validator-approved latest handoff."""
    from rolo.stages.adapt.conformance import latest_adapter_handoff_path, validate_adapter_handoff

    validate_diagnosis_result(frozen_config, diagnosis_report)
    layout = ArtifactLayout(artifact_root)
    store = ArtifactStore(artifact_root)
    adapter_path = latest_adapter_handoff_path(artifact_root, robot_id)
    validate_adapter_handoff(artifact_root, robot_id, adapter_path)
    selected_run = run_id or _run_id("diagnose")
    run_root = layout.stage_run("diagnose", robot_id, selected_run)
    frozen_path = store.write_json(
        layout.relative(run_root / "frozen_config.json"), dict(frozen_config)
    )
    report_path = store.write_json(
        layout.relative(run_root / "diagnosis_report.json"), dict(diagnosis_report)
    )
    handoff = DiagnosisHandoff(
        robot_id=robot_id,
        source_adapter_handoff_ref=layout.ref(adapter_path),
        source_adapter_handoff_sha256=sha256_file(adapter_path),
        frozen_config_ref=layout.ref(frozen_path),
        frozen_config_sha256=sha256_file(frozen_path),
        diagnosis_report_ref=layout.ref(report_path),
        diagnosis_report_sha256=sha256_file(report_path),
    )
    run_handoff = _write_run_handoff(
        store, layout, stage="diagnose", robot_id=robot_id, run_id=selected_run, handoff=handoff
    )
    validate_diagnosis_handoff(artifact_root, robot_id, handoff_path=run_handoff)
    store.write_json(
        layout.relative(layout.stage_latest("diagnose", robot_id) / "handoff.json"),
        handoff.model_dump(mode="json"),
    )
    validate_diagnosis_handoff(artifact_root, robot_id)
    return handoff


def commit_verification_handoff(
    artifact_root: Path,
    robot_id: str,
    *,
    regression_report: Mapping[str, object],
    evidence_package: Mapping[str, object],
    run_id: str | None = None,
) -> VerificationHandoff:
    """Freeze Verify outputs and publish only a validator-approved latest handoff."""
    validate_verification_result(regression_report, evidence_package)
    layout = ArtifactLayout(artifact_root)
    store = ArtifactStore(artifact_root)
    diagnosis_path = layout.stage_file("diagnose", robot_id, "handoff.json")
    validate_diagnosis_handoff(artifact_root, robot_id)
    selected_run = run_id or _run_id("verify")
    run_root = layout.stage_run("verify", robot_id, selected_run)
    report_path = store.write_json(
        layout.relative(run_root / "regression_report.json"), dict(regression_report)
    )
    evidence_path = store.write_json(
        layout.relative(run_root / "evidence_package.json"), dict(evidence_package)
    )
    handoff = VerificationHandoff(
        robot_id=robot_id,
        source_diagnosis_handoff_ref=layout.ref(diagnosis_path),
        source_diagnosis_handoff_sha256=sha256_file(diagnosis_path),
        regression_report_ref=layout.ref(report_path),
        regression_report_sha256=sha256_file(report_path),
        evidence_package_ref=layout.ref(evidence_path),
        evidence_package_sha256=sha256_file(evidence_path),
    )
    run_handoff = _write_run_handoff(
        store, layout, stage="verify", robot_id=robot_id, run_id=selected_run, handoff=handoff
    )
    validate_verification_handoff(artifact_root, robot_id, handoff_path=run_handoff)
    store.write_json(
        layout.relative(layout.stage_latest("verify", robot_id) / "handoff.json"),
        handoff.model_dump(mode="json"),
    )
    validate_verification_handoff(artifact_root, robot_id)
    return handoff


def validate_diagnosis_handoff(
    root: Path, robot_id: str, handoff_path: Path | None = None
) -> DiagnosisHandoff:
    layout = ArtifactLayout(root)
    path = handoff_path or layout.stage_file("diagnose", robot_id, "handoff.json")
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
    if bool(handoff.diagnosis_report_ref) != bool(handoff.diagnosis_report_sha256):
        raise ValueError("diagnosis report reference and hash must be provided together")
    _verify_refs(
        root,
        (
            (handoff.source_adapter_handoff_ref, handoff.source_adapter_handoff_sha256),
            (handoff.frozen_config_ref, handoff.frozen_config_sha256),
            *(
                ((handoff.diagnosis_report_ref, handoff.diagnosis_report_sha256),)
                if handoff.diagnosis_report_ref and handoff.diagnosis_report_sha256
                else ()
            ),
        ),
    )
    if handoff.diagnosis_report_ref and handoff.diagnosis_report_sha256:
        report = _load_mapping_ref(root, handoff.diagnosis_report_ref, label="diagnosis_report")
        # The same guard is applied at commit time and again at read time so an imported
        # handoff cannot bypass the result contract.
        frozen = _load_mapping_ref(root, handoff.frozen_config_ref, label="frozen_config")
        validate_diagnosis_result(frozen, report)
        if report.get("schema_version") == "rolo-diagnosis-report/v1":
            from rolo.stages.diagnose_contract import validate_structured_diagnosis_report

            structured = validate_structured_diagnosis_report(report, robot_id=robot_id)
            for reference in structured.episode_refs:
                episode_path = resolve_artifact_ref(root, reference)
                if not episode_path.is_file():
                    raise ValueError(f"diagnosis episode artifact is missing: {reference}")
                try:
                    episode_payload = json.loads(episode_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise ValueError(
                        f"diagnosis episode artifact is not valid JSON: {reference}"
                    ) from exc
                if not isinstance(episode_payload, Mapping):
                    raise ValueError(f"diagnosis episode artifact must be an object: {reference}")
                if episode_payload.get("schema_version") == "rolo-episode-publication/v1":
                    from rolo.stages.diagnose.episode import validate_published_episode

                    validate_published_episode(root, reference, robot_id=robot_id)
                elif episode_payload.get("schema_version") == "rolo-diagnosis-episode/v1":
                    from rolo.stages.diagnose.episode import DiagnosisEpisode

                    episode = DiagnosisEpisode.model_validate(episode_payload)
                    if episode.robot_id != robot_id:
                        raise ValueError("diagnosis episode robot identity mismatch")
                elif episode_payload.get("authority") != "UNVERIFIED_AGENT_OBSERVATION":
                    raise ValueError(
                        "diagnosis episode has no target provenance or unverified marker"
                    )
    return handoff


def validate_verification_handoff(
    root: Path, robot_id: str, handoff_path: Path | None = None
) -> VerificationHandoff:
    layout = ArtifactLayout(root)
    path = handoff_path or layout.stage_file("verify", robot_id, "handoff.json")
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
    report = _load_mapping_ref(root, handoff.regression_report_ref, label="regression_report")
    evidence = _load_mapping_ref(root, handoff.evidence_package_ref, label="evidence_package")
    validate_verification_result(report, evidence)
    if evidence.get("schema_version") == "rolo-verification-evidence/v2":
        from rolo.stages.verify.acceptance import validate_structured_verification_evidence

        validate_structured_verification_evidence(
            evidence, robot_id=robot_id, artifact_root=root
        )
    return handoff
