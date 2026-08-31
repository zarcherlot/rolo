"""Sanitized R2 approval, gate, and recovery projections for persisted jobs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from rolo.jobs import Job, JobCheckpoint, JobEvent, JobStatus
from rolo.target_ref import TargetRef
from rolo.targets.profiles import TargetProfileStore

APPROVAL_GATE_API_FEATURES = ("workbench.approval-gate-read-model/v1",)


class ApprovalGateConflict(ValueError):
    """The persisted job cannot be bound to one producer-owned target revision."""

SafeText = Annotated[str, StringConstraints(min_length=1, max_length=240)]
OpaqueId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Revision = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]

_UNSAFE_TERMS = (
    "ssh://",
    "credential",
    "password",
    "secret",
    "token",
    "known_hosts",
    "private key",
    "command",
    "shell",
    "artifact",
    "local_path",
    "remote_path",
    "signed url",
    "request body",
    "http method",
    "workspace/",
    "c:\\",
    "/home/",
)


def _safe_text(value: str) -> str:
    value = value.strip()
    if not value or any(term in value.casefold() for term in _UNSAFE_TERMS):
        raise ValueError("approval-gate text contains a restricted reference")
    return value


class ApprovalGateStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["VERIFY_PLATFORM", "VERIFY_WORKSPACE", "INSTALL_COMPANION", "HEALTH_CHECK"]
    risk: Literal["READ_ONLY", "HOST_MUTATION"]
    approval_required: bool
    description: SafeText

    @field_validator("description")
    @classmethod
    def safe_description(cls, value: str) -> str:
        return _safe_text(value)


class ApprovalGateSummary(BaseModel):
    """Display-only state; it never contains an approval token or executable action."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-approval-gate-summary/v1"] = "rolo-approval-gate-summary/v1"
    job_id: OpaqueId
    target_id: OpaqueId
    producer_revision: Revision
    plan_status: Literal["READY", "APPROVAL_REQUIRED", "BLOCKED"]
    steps: list[ApprovalGateStep] = Field(min_length=1, max_length=8)
    required_approvals: list[SafeText] = Field(default_factory=list, max_length=8)
    approval_status: Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED"] | None
    gate_status: Literal["PENDING", "PASSED", "FAILED", "BLOCKED"]
    gate_checks: list[SafeText] = Field(min_length=1, max_length=16)
    recovery_state: Literal["NOT_REQUIRED", "AVAILABLE", "BLOCKED", "UNKNOWN"]
    blockers: list[SafeText] = Field(default_factory=list, max_length=10)
    limitations: list[SafeText] = Field(default_factory=list, max_length=10)
    observed_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    contains_secret_payloads: Literal[False] = False

    @field_validator("required_approvals", "gate_checks", "blockers", "limitations")
    @classmethod
    def safe_texts(cls, values: list[str]) -> list[str]:
        return [_safe_text(value) for value in values]

    @model_validator(mode="after")
    def require_unique_identities(self) -> ApprovalGateSummary:
        actions = [step.action for step in self.steps]
        if len(actions) != len(set(actions)):
            raise ValueError("approval-gate step identities must be unique")
        if len(self.required_approvals) != len(set(self.required_approvals)):
            raise ValueError("approval identities must be unique")
        if len(self.gate_checks) != len(set(self.gate_checks)):
            raise ValueError("gate check identities must be unique")
        return self


class ApprovalGateCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-approval-gate-collection/v1"] = "rolo-approval-gate-collection/v1"
    items: list[ApprovalGateSummary] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    producer_revision: Revision
    contains_secret_payloads: Literal[False] = False


def _job_root(config_root: Path) -> Path:
    return config_root.expanduser().resolve() / "jobs"


def _load_job_records(config_root: Path) -> list[tuple[Job, list[JobEvent], list[JobCheckpoint]]]:
    root = _job_root(config_root)
    if not root.is_dir():
        return []
    records: list[tuple[Job, list[JobEvent], list[JobCheckpoint]]] = []
    for path in sorted(root.glob("job_*.json"), key=lambda item: item.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            job = Job.model_validate(data["job"])
            events = [JobEvent.model_validate(item) for item in data.get("events", [])]
            checkpoints = [
                JobCheckpoint.model_validate(item) for item in data.get("checkpoints", [])
            ]
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"approval-gate job facts are unavailable: {path}") from exc
        if job.job_id != path.stem:
            raise ValueError("job identity does not match its persisted path")
        if any(event.job_id != job.job_id for event in events) or any(
            checkpoint.job_id != job.job_id for checkpoint in checkpoints
        ):
            raise ValueError("job event/checkpoint identity mismatch")
        sequences = [event.sequence for event in events]
        if sequences and sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("job event sequence regressed or repeated")
        if job.revision != (sequences[-1] if sequences else 0):
            raise ValueError("job revision does not match the latest event")
        checkpoint_sequences = [checkpoint.sequence for checkpoint in checkpoints]
        if checkpoint_sequences != sorted(checkpoint_sequences) or any(
            sequence > job.revision for sequence in checkpoint_sequences
        ):
            raise ValueError("job checkpoint sequence regressed or exceeds job revision")
        records.append((job, events, checkpoints))
    return records


def _target_id(config_root: Path, job: Job) -> str | None:
    try:
        target = TypeAdapter(TargetRef).validate_json(job.target)
    except (ValueError, TypeError):
        return None
    for profile in TargetProfileStore(config_root).list_profiles():
        if profile.target == target:
            return profile.profile_id
    return None


def _approval_status(job: Job, events: list[JobEvent]) -> str | None:
    for event in reversed(events):
        value = event.payload.get("approval_status")
        if value in {"PENDING", "APPROVED", "REJECTED", "EXPIRED"}:
            return value
        event_type = event.event_type.upper()
        if "APPROV" in event_type:
            if "REJECT" in event_type:
                return "REJECTED"
            if "EXPIRE" in event_type:
                return "EXPIRED"
            if "APPROV" in event_type or "GRANT" in event_type:
                return "APPROVED"
    if events and job.status in {JobStatus.RUNNING, JobStatus.SUCCEEDED, JobStatus.FAILED}:
        return "APPROVED"
    return "PENDING"


def _freshness(observed_at: datetime, *, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    age = max(0.0, (current - observed_at).total_seconds())
    return "fresh" if age <= 3600 else "stale"


def _revision(
    job: Job,
    events: list[JobEvent],
    checkpoints: list[JobCheckpoint],
    target_id: str,
) -> str:
    material = {
        "job": job.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
        "checkpoints": [checkpoint.model_dump(mode="json") for checkpoint in checkpoints],
        "target_id": target_id,
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def build_approval_gate_summary(
    config_root: Path,
    job: Job,
    events: list[JobEvent],
    checkpoints: list[JobCheckpoint],
    *,
    observed_at: datetime | None = None,
) -> ApprovalGateSummary:
    target_id = _target_id(config_root, job)
    if target_id is None:
        raise ApprovalGateConflict(
            "job target is not bound to a producer-owned target profile"
        )
    latest_times = [job.updated_at]
    latest_times.extend(event.occurred_at for event in events)
    latest_times.extend(checkpoint.created_at for checkpoint in checkpoints)
    timestamp = observed_at or max(latest_times)
    approval_status = _approval_status(job, events)
    plan_status = (
        "BLOCKED"
        if job.status is JobStatus.BLOCKED
        else "READY"
        if approval_status == "APPROVED"
        else "APPROVAL_REQUIRED"
    )
    gate_status = {
        JobStatus.CREATED: "PENDING",
        JobStatus.RUNNING: "PENDING",
        JobStatus.SUCCEEDED: "PASSED",
        JobStatus.FAILED: "FAILED",
        JobStatus.BLOCKED: "BLOCKED",
    }[job.status]
    recovery_state = {
        JobStatus.CREATED: "AVAILABLE",
        JobStatus.RUNNING: "AVAILABLE",
        JobStatus.SUCCEEDED: "NOT_REQUIRED",
        JobStatus.FAILED: "BLOCKED",
        JobStatus.BLOCKED: "BLOCKED",
    }[job.status]
    blockers: list[str] = []
    if plan_status == "BLOCKED":
        blockers.append("PLAN_BLOCKED")
    if approval_status in {"PENDING", "REJECTED", "EXPIRED"}:
        blockers.append(
            {
                "PENDING": "APPROVAL_REQUIRED",
                "REJECTED": "APPROVAL_REJECTED",
                "EXPIRED": "APPROVAL_EXPIRED",
            }[approval_status]
        )
    if gate_status == "FAILED":
        blockers.append("GATE_FAILED")
    if gate_status == "BLOCKED":
        blockers.append("JOB_BLOCKED")
    checks = ["PLAN_BOUND", "TARGET_ID_BOUND", "REVISION_MONOTONIC"]
    if approval_status == "PENDING":
        checks.append("APPROVAL_PENDING")
    elif approval_status == "APPROVED":
        checks.append("APPROVAL_APPROVED")
    else:
        checks.append(f"APPROVAL_{approval_status}")
    return ApprovalGateSummary(
        job_id=job.job_id,
        target_id=target_id,
        producer_revision=_revision(job, events, checkpoints, target_id),
        plan_status=plan_status,
        steps=[
            ApprovalGateStep(
                action="VERIFY_PLATFORM",
                risk="READ_ONLY",
                approval_required=False,
                description="Verify target platform compatibility.",
            ),
            ApprovalGateStep(
                action="VERIFY_WORKSPACE",
                risk="READ_ONLY",
                approval_required=False,
                description="Verify target workspace accessibility.",
            ),
            ApprovalGateStep(
                action="INSTALL_COMPANION",
                risk="HOST_MUTATION",
                approval_required=True,
                description="Install the target companion after explicit approval.",
            ),
            ApprovalGateStep(
                action="HEALTH_CHECK",
                risk="READ_ONLY",
                approval_required=False,
                description="Run the post-plan health assessment.",
            ),
        ],
        required_approvals=["target.bootstrap.execute"],
        approval_status=approval_status,
        gate_status=gate_status,
        gate_checks=checks,
        recovery_state=recovery_state,
        blockers=blockers,
        limitations=[
            "This projection reports state only; approval and recovery actions remain "
            "in the existing authorization chain.",
            "PASSED and APPROVED do not assert job success, physical outcome, or "
            "release readiness.",
        ],
        observed_at=timestamp,
        freshness=_freshness(timestamp),
    )


def _summaries(
    config_root: Path, *, observed_at: datetime | None = None
) -> list[ApprovalGateSummary]:
    summaries: list[ApprovalGateSummary] = []
    for job, events, checkpoints in _load_job_records(config_root):
        if job.operation != "target.bootstrap.execute":
            continue
        summaries.append(
            build_approval_gate_summary(
                config_root, job, events, checkpoints, observed_at=observed_at
            )
        )
    summaries.sort(key=lambda item: item.job_id)
    return summaries


def build_approval_gate_collection(
    config_root: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    observed_at: datetime | None = None,
) -> ApprovalGateCollection:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("approval-gate pagination is invalid")
    items_all = _summaries(config_root, observed_at=observed_at)
    timestamp = observed_at or datetime.now(timezone.utc)
    items = items_all[offset : offset + limit]
    total = len(items_all)
    next_offset = offset + limit if offset + limit < total else None
    freshness = "fresh" if all(item.freshness == "fresh" for item in items_all) else "stale"
    revision = hashlib.sha256(
        "|".join(item.producer_revision for item in items_all).encode("ascii")
    ).hexdigest()
    return ApprovalGateCollection(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        observed_at=timestamp,
        freshness=freshness,
        producer_revision=revision,
    )


def get_approval_gate_summary(config_root: Path, job_id: str) -> ApprovalGateSummary | None:
    if not job_id or "/" in job_id or "\\" in job_id or ".." in job_id:
        return None
    for job, events, checkpoints in _load_job_records(config_root):
        if job.job_id != job_id:
            continue
        if job.operation != "target.bootstrap.execute":
            return None
        return build_approval_gate_summary(config_root, job, events, checkpoints)
    return None
