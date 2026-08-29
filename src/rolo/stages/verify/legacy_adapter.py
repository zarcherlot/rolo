"""Explicit, fail-closed adapter for the pre-R5 provider evidence envelope.

The adapter accepts P1's v1 evidence only when the caller supplies an already
published main-line target provenance artifact and the expected plan digest. It
never promotes the inline SSH provenance object into release evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.verify.acceptance import (
    VerificationCaseResult,
    VerificationEvidencePackage,
    validate_structured_verification_evidence,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LegacyProviderEvidence(BaseModel):
    """The P1 v1 envelope, kept private to this one-way migration boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-evidence/v1"]
    run_id: str = Field(min_length=1, max_length=256)
    robot_id: str = Field(min_length=1, max_length=128)
    status: Literal["PASS", "FAIL", "CANCELLED"]
    plan: dict[str, object]
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_results: list[VerificationCaseResult] = Field(min_length=1, max_length=256)
    target_provenance: dict[str, object] | None = None
    started_at: datetime
    completed_at: datetime


def adapt_legacy_provider_evidence(
    payload: Mapping[str, object],
    *,
    artifacts: ArtifactStore,
    expected_robot_id: str,
    expected_plan_sha256: str,
    target_provenance_ref: str,
    target_provenance_sha256: str,
    target_provenance_schema_version: Literal[
        "rolo-target-provenance/v1", "rolo-target-provenance/v2"
    ],
    safe_stop: Literal["VERIFIED", "NOT_REQUIRED", "NOT_VERIFIED"],
    rollback: Literal["VERIFIED", "NOT_REQUIRED", "NOT_VERIFIED"],
    replay_ref: str | None = None,
) -> tuple[VerificationEvidencePackage, str]:
    """Convert one legacy payload into a main v2 package after binding checks.

    ``target_provenance_ref`` and ``target_provenance_sha256`` must point to a
    canonical main-line provenance artifact. The legacy inline SSH object is
    retained only as an input consistency requirement and is never copied into
    the v2 package.
    """

    if not _SHA256.fullmatch(expected_plan_sha256):
        raise ValueError("expected plan digest must be a lowercase SHA256")
    if not _SHA256.fullmatch(target_provenance_sha256):
        raise ValueError("target provenance digest must be a lowercase SHA256")
    legacy = LegacyProviderEvidence.model_validate(payload)
    if legacy.robot_id != expected_robot_id:
        raise ValueError("legacy provider evidence robot identity mismatch")
    if legacy.plan_sha256 != expected_plan_sha256:
        raise ValueError("legacy provider evidence plan digest mismatch")
    if canonical_json_sha256(legacy.plan) != legacy.plan_sha256:
        raise ValueError("legacy provider evidence plan contents do not match its digest")
    if legacy.target_provenance is None:
        raise ValueError("legacy provider evidence is missing inline target provenance")

    provenance_path = resolve_artifact_ref(artifacts.root, target_provenance_ref)
    if (
        not provenance_path.is_file()
        or sha256_file(provenance_path) != target_provenance_sha256
    ):
        raise ValueError("canonical target provenance reference or hash is invalid")
    if replay_ref is not None and not resolve_artifact_ref(artifacts.root, replay_ref).is_file():
        raise ValueError("verification replay artifact is missing")

    package = VerificationEvidencePackage(
        robot_id=legacy.robot_id,
        run_id=legacy.run_id,
        target_provenance_ref=target_provenance_ref,
        target_provenance_sha256=target_provenance_sha256,
        target_provenance_schema_version=target_provenance_schema_version,
        case_results=legacy.case_results,
        safe_stop=safe_stop,
        rollback=rollback,
        replay_ref=replay_ref,
    )
    validate_structured_verification_evidence(
        package.model_dump(mode="json"),
        robot_id=expected_robot_id,
        artifact_root=artifacts.root,
    )
    path = artifacts.write_json(
        f"verify/{legacy.robot_id}/runs/{legacy.run_id}/adapted-evidence-v2.json",
        package.model_dump(mode="json"),
    )
    return package, ArtifactLayout(artifacts.root).ref(path)


__all__ = ["LegacyProviderEvidence", "adapt_legacy_provider_evidence"]
