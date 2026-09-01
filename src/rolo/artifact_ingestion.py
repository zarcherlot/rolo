"""Authenticated, idempotent registration of sanitized producer summaries."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from rolo.artifact_analysis import ArtifactAnalysisSummary
from rolo.core.persistence import atomic_write_text
from rolo.jobs import JobStore
from rolo.target_ref import TargetRef
from rolo.targets.profiles import TargetProfileStore

ARTIFACT_INGESTION_API_FEATURES = ("workbench.artifact-registration/v1",)
SafeId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9._:-]{0,127}$")]
SafeKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9._-]{0,127}$")]


class ArtifactRegistrationRequest(BaseModel):
    """A bounded registration envelope; the first supported kind is analysis_summary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-artifact-registration-request/v1"] = (
        "rolo-artifact-registration-request/v1"
    )
    kind: Literal["analysis_summary"]
    idempotency_key: SafeKey
    target_id: SafeId
    summary: ArtifactAnalysisSummary


class ArtifactRegistrationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-artifact-registration-receipt/v1"] = (
        "rolo-artifact-registration-receipt/v1"
    )
    registration_id: SafeId
    idempotency_key: SafeId
    kind: Literal["analysis_summary"]
    target_id: SafeId
    job_id: SafeId | None = None
    status: Literal["REGISTERED", "REPLAYED"]
    producer_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    registered_at: datetime
    limitations: list[str] = Field(max_length=8)


class ArtifactRegistrationConflict(ValueError):
    """The registration cannot safely be applied or replayed."""


def _registration_root(config_root: Path) -> Path:
    return config_root.expanduser().resolve() / "artifact-analysis" / "registrations"


def _registration_path(config_root: Path, idempotency_key: str) -> Path:
    if not re.fullmatch(r"^[a-z][a-z0-9._-]{0,127}$", idempotency_key):
        raise ArtifactRegistrationConflict("idempotency key is invalid")
    return _registration_root(config_root) / f"{idempotency_key}.json"


def _summary_path(config_root: Path, target_id: str) -> Path:
    if not re.fullmatch(r"^[a-z][a-z0-9_-]{2,63}$", target_id):
        raise ArtifactRegistrationConflict("target identity is invalid")
    return config_root.expanduser().resolve() / "artifact-analysis" / f"{target_id}.json"


def _target_id_for_job(config_root: Path, job_id: str) -> str | None:
    if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$", job_id):
        return None
    try:
        job, _, _ = JobStore(config_root.expanduser().resolve() / "jobs").load(job_id)
        target = TypeAdapter(TargetRef).validate_json(job.target)
    except (OSError, ValueError, TypeError, KeyError):
        return None
    for profile in TargetProfileStore(config_root).list_profiles():
        if profile.target == target:
            return profile.profile_id
    return None


def _request_digest(request: ArtifactRegistrationRequest) -> str:
    return hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def register_artifact_analysis(
    config_root: Path,
    request: ArtifactRegistrationRequest,
    *,
    now: datetime,
) -> ArtifactRegistrationReceipt:
    """Register one target-bound summary without replacing producer-owned state."""

    profiles = TargetProfileStore(config_root)
    try:
        profile = profiles.load(request.target_id)
    except FileNotFoundError as exc:
        raise ArtifactRegistrationConflict("target profile is not registered") from exc
    if (
        request.summary.target_id != request.target_id
        or request.summary.robot_id != profile.robot_id
    ):
        raise ArtifactRegistrationConflict("artifact-analysis target identity mismatch")
    if request.summary.job_id is not None:
        bound_target = _target_id_for_job(config_root, request.summary.job_id)
        if bound_target != request.target_id:
            raise ArtifactRegistrationConflict("artifact-analysis job target identity mismatch")

    registration_path = _registration_path(config_root, request.idempotency_key)
    request_digest = _request_digest(request)
    if registration_path.is_file():
        try:
            stored = json.loads(registration_path.read_text(encoding="utf-8"))
            if stored.get("request_digest") != request_digest:
                raise ArtifactRegistrationConflict(
                    "idempotency key was already used for another payload"
                )
            receipt = ArtifactRegistrationReceipt.model_validate(stored["receipt"])
        except ArtifactRegistrationConflict:
            raise
        except (OSError, ValueError, KeyError) as exc:
            raise ArtifactRegistrationConflict("registration record is invalid") from exc
        return receipt.model_copy(update={"status": "REPLAYED"})

    summary_path = _summary_path(config_root, request.target_id)
    if summary_path.exists():
        raise ArtifactRegistrationConflict(
            "artifact-analysis summary is already published for this target"
        )

    registration_id = "reg_" + hashlib.sha256(
        (request.target_id + chr(0) + request.idempotency_key).encode()
    ).hexdigest()[:24]
    receipt = ArtifactRegistrationReceipt(
        registration_id=registration_id,
        idempotency_key=request.idempotency_key,
        kind=request.kind,
        target_id=request.target_id,
        job_id=request.summary.job_id,
        status="REGISTERED",
        producer_revision=request.summary.producer_revision,
        registered_at=now,
        limitations=[
            (
                "Registration accepts sanitized summaries only; it does not fetch "
                "artifact URLs or bytes."
            ),
            (
                "Job, gate, and handoff registration kinds remain deferred until "
                "their canonical writers are integrated."
            ),
        ],
    )
    atomic_write_text(summary_path, request.summary.model_dump_json(indent=2), require_absent=True)
    atomic_write_text(
        registration_path,
        json.dumps(
            {"request_digest": request_digest, "receipt": receipt.model_dump(mode="json")},
            indent=2,
        ),
        require_absent=True,
    )
    return receipt
