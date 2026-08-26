from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import append_text_record, atomic_write_text, interprocess_lock
from rolo.targets.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    DeploymentCommand,
    DeploymentEvent,
    DeploymentEventType,
    DeploymentJob,
    DeploymentJobState,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_PRINCIPAL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_ARTIFACT_PATTERN = re.compile(r"^artifact://[^\x00\r\n]{1,4096}$")
_TERMINAL_STATES = {
    DeploymentJobState.BLOCKED,
    DeploymentJobState.COMPLETE,
    DeploymentJobState.FAILED,
    DeploymentJobState.CANCELLED,
}
_MUTATING_STATES = {
    DeploymentJobState.BOOTSTRAPPING,
    DeploymentJobState.ROLLING_BACK,
    DeploymentJobState.DISCOVERING,
    DeploymentJobState.ENROLLING,
    DeploymentJobState.ADAPTING,
    DeploymentJobState.GATING,
}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|private[_-]?key)\b"
    r"\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_PEM = re.compile(
    r"-----BEGIN [^-\r\n]+-----.*?-----END [^-\r\n]+-----",
    re.DOTALL,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def sanitize_deployment_summary(value: str) -> str:
    """Produce a bounded one-line event summary and redact common secret forms."""

    if "\x00" in value:
        raise ValueError("deployment summary contains a NUL character")
    sanitized = _PEM.sub("<redacted-pem>", value)
    sanitized = _BEARER.sub("Bearer <redacted>", sanitized)
    sanitized = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", sanitized)
    sanitized = " ".join(sanitized.replace("\r", " ").replace("\n", " ").split())
    if not sanitized:
        raise ValueError("deployment summary is empty")
    return sanitized[:1000]


def _validate_artifact_refs(values: list[str]) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError("artifact refs must be unique and sorted")
    if any(_ARTIFACT_PATTERN.fullmatch(value) is None for value in values):
        raise ValueError("artifact ref is invalid")
    return values


class DeploymentStepStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class DeploymentRemoteState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


class DeploymentStepCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-step-checkpoint/v1"] = (
        "rolo-deployment-step-checkpoint/v1"
    )
    step_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    attempt: int = Field(ge=1, le=100)
    status: DeploymentStepStatus
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    remote_state: DeploymentRemoteState = DeploymentRemoteState.NOT_APPLICABLE
    started_at: datetime
    updated_at: datetime
    outcome_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    artifact_refs: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def require_consistent_checkpoint(self) -> DeploymentStepCheckpoint:
        self.artifact_refs = _validate_artifact_refs(self.artifact_refs)
        if self.updated_at < self.started_at:
            raise ValueError("checkpoint update precedes its start")
        if self.status == DeploymentStepStatus.RUNNING and self.outcome_sha256 is not None:
            raise ValueError("running checkpoint cannot contain an outcome digest")
        if self.status == DeploymentStepStatus.COMPLETE and self.outcome_sha256 is None:
            raise ValueError("complete checkpoint requires an outcome digest")
        if self.status == DeploymentStepStatus.UNKNOWN:
            if self.remote_state != DeploymentRemoteState.UNKNOWN:
                raise ValueError("unknown checkpoint requires unknown remote state")
        elif self.remote_state == DeploymentRemoteState.UNKNOWN:
            raise ValueError("unknown remote state requires an unknown checkpoint")
        return self


class DeploymentRecoveryDisposition(str, Enum):
    NONE = "NONE"
    RESUMABLE = "RESUMABLE"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"


class DeploymentRemoteReconciliationOutcome(str, Enum):
    EXACT = "EXACT"
    NOT_COMMITTED = "NOT_COMMITTED"
    DIVERGED = "DIVERGED"


class DeploymentJobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-job-record/v1"] = (
        "rolo-deployment-job-record/v1"
    )
    job: DeploymentJob
    revision: int = Field(default=1, ge=1)
    attempt: int = Field(default=1, ge=1, le=100)
    cancel_requested: bool = False
    recovery_disposition: DeploymentRecoveryDisposition = DeploymentRecoveryDisposition.NONE
    checkpoints: list[DeploymentStepCheckpoint] = Field(default_factory=list, max_length=512)
    final_artifact_refs: list[str] = Field(default_factory=list, max_length=64)
    last_event_sequence: int = Field(default=0, ge=0)
    last_event_record_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def require_consistent_record(self) -> DeploymentJobRecord:
        self.final_artifact_refs = _validate_artifact_refs(self.final_artifact_refs)
        identities = [(item.attempt, item.step_id) for item in self.checkpoints]
        if identities != sorted(set(identities)):
            raise ValueError("deployment checkpoints must be unique and sorted")
        if self.last_event_sequence == 0:
            if self.last_event_record_sha256 is not None:
                raise ValueError("empty event log cannot have a record digest")
        elif self.last_event_record_sha256 is None:
            raise ValueError("non-empty event log requires a record digest")
        if self.job.state == DeploymentJobState.COMPLETE and not self.final_artifact_refs:
            raise ValueError("complete deployment job requires final artifact refs")
        if self.recovery_disposition == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION:
            if self.job.state != DeploymentJobState.BLOCKED:
                raise ValueError("reconciliation disposition requires a blocked job")
        return self


class DeploymentJobRecoverySnapshot(BaseModel):
    """Journal-contained state needed to rebuild a lagging atomic job snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-job-recovery-snapshot/v1"] = (
        "rolo-deployment-job-recovery-snapshot/v1"
    )
    job: DeploymentJob
    revision: int = Field(ge=1)
    attempt: int = Field(ge=1, le=100)
    cancel_requested: bool
    recovery_disposition: DeploymentRecoveryDisposition
    checkpoints: list[DeploymentStepCheckpoint] = Field(default_factory=list, max_length=512)
    final_artifact_refs: list[str] = Field(default_factory=list, max_length=64)

    @classmethod
    def from_record(cls, record: DeploymentJobRecord) -> DeploymentJobRecoverySnapshot:
        return cls(
            job=record.job,
            revision=record.revision,
            attempt=record.attempt,
            cancel_requested=record.cancel_requested,
            recovery_disposition=record.recovery_disposition,
            checkpoints=record.checkpoints,
            final_artifact_refs=record.final_artifact_refs,
        )

    def to_record(
        self,
        *,
        last_event_sequence: int,
        last_event_record_sha256: str,
    ) -> DeploymentJobRecord:
        return DeploymentJobRecord(
            job=self.job,
            revision=self.revision,
            attempt=self.attempt,
            cancel_requested=self.cancel_requested,
            recovery_disposition=self.recovery_disposition,
            checkpoints=self.checkpoints,
            final_artifact_refs=self.final_artifact_refs,
            last_event_sequence=last_event_sequence,
            last_event_record_sha256=last_event_record_sha256,
        )


class DeploymentEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-event-record/v1"] = (
        "rolo-deployment-event-record/v1"
    )
    sequence: int = Field(ge=1)
    previous_record_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    event: DeploymentEvent
    recovery_snapshot: DeploymentJobRecoverySnapshot
    record_sha256: str = Field(pattern=_SHA256_PATTERN)

    def digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "previous_record_sha256": self.previous_record_sha256,
            "event": self.event.model_dump(mode="json"),
            "recovery_snapshot": self.recovery_snapshot.model_dump(mode="json"),
        }

    def compute_sha256(self) -> str:
        return _canonical_sha256(self.digest_payload())

    @model_validator(mode="after")
    def require_record_digest(self) -> DeploymentEventRecord:
        if self.record_sha256 != self.compute_sha256():
            raise ValueError("deployment event record digest mismatch")
        if self.sequence == 1 and self.previous_record_sha256 is not None:
            raise ValueError("first deployment event cannot have a previous digest")
        if self.sequence > 1 and self.previous_record_sha256 is None:
            raise ValueError("deployment event chain is incomplete")
        return self


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-approval-decision/v1"] = "rolo-approval-decision/v1"
    decision_id: str = Field(pattern=r"^decision-[0-9a-f]{32}$")
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    action: ApprovalAction
    principal: str = Field(pattern=_PRINCIPAL_PATTERN)
    status: Literal[ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]
    decided_at: datetime
    expires_at: datetime
    sanitized_reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_decision_lifetime(self) -> ApprovalDecision:
        if self.decided_at >= self.expires_at:
            raise ValueError("approval decision is not valid at its decision time")
        return self


class DeploymentRecoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-recovery-result/v1"] = (
        "rolo-deployment-recovery-result/v1"
    )
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    previous_state: DeploymentJobState
    recovered_state: DeploymentJobState
    disposition: DeploymentRecoveryDisposition
    recovered_at: datetime


class DeploymentJobStateConflict(ValueError):
    pass


def _transition_allowed(old: DeploymentJobState, new: DeploymentJobState) -> bool:
    if old == new:
        return True
    if old in _TERMINAL_STATES:
        return False
    if new in {DeploymentJobState.BLOCKED, DeploymentJobState.FAILED, DeploymentJobState.CANCELLED}:
        return True
    order = [
        DeploymentJobState.CREATED,
        DeploymentJobState.CONNECTING,
        DeploymentJobState.HOST_KEY_APPROVAL_REQUIRED,
        DeploymentJobState.PREFLIGHT,
        DeploymentJobState.BOOTSTRAPPING,
        DeploymentJobState.ROLLING_BACK,
        DeploymentJobState.ENROLLING,
        DeploymentJobState.COLLECTING_EVIDENCE,
        DeploymentJobState.DISCOVERING,
        DeploymentJobState.ADAPTING,
        DeploymentJobState.GATING,
        DeploymentJobState.COMPLETE,
    ]
    try:
        old_index = order.index(old)
        new_index = order.index(new)
    except ValueError:
        return False
    # Command-specific jobs legitimately skip unrelated phases (for example a connection
    # assessment can move from CONNECTING directly to COMPLETE). Forward-only remains strict.
    return new_index >= old_index


class DeploymentJobStore:
    """Atomic job snapshots plus a durable, hash-chained append-only event journal."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("deployment job store root cannot be a symbolic link")
        self.root.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, job_id: str) -> Path:
        if re.fullmatch(r"deployment-[0-9a-f]{32}", job_id) is None:
            raise ValueError("invalid deployment job id")
        return self.root / "jobs" / job_id

    def _job_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _events_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "events.jsonl"

    def _approval_dir(self, approval_id: str) -> Path:
        if re.fullmatch(r"approval-[0-9a-f]{32}", approval_id) is None:
            raise ValueError("invalid approval id")
        return self.root / "approvals" / approval_id

    @staticmethod
    def _load_record(path: Path) -> DeploymentJobRecord:
        if path.is_symlink() or not path.is_file():
            raise ValueError("deployment job record is unavailable")
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("deployment job record exceeds its size limit")
        return DeploymentJobRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def load_job(self, job_id: str) -> DeploymentJobRecord:
        path = self._job_path(job_id)
        with interprocess_lock(path):
            return self._load_synchronized_record(path)

    def list_jobs(self, *, limit: int = 1000) -> list[DeploymentJobRecord]:
        if not 1 <= limit <= 10_000:
            raise ValueError("deployment job list limit is out of bounds")
        jobs_root = self.root / "jobs"
        if not jobs_root.exists():
            return []
        records: list[DeploymentJobRecord] = []
        for child in sorted(jobs_root.iterdir(), key=lambda path: path.name):
            if len(records) >= limit:
                break
            if child.is_symlink() or not child.is_dir():
                continue
            records.append(self.load_job(child.name))
        return records

    def _load_synchronized_record(self, path: Path) -> DeploymentJobRecord:
        record = self._load_record(path)
        events = self.read_events(record.job.job_id, limit=10_000)
        if not events:
            if record.last_event_sequence != 0:
                raise ValueError("deployment snapshot is ahead of an empty event journal")
            return record
        if record.last_event_sequence > len(events):
            raise ValueError("deployment snapshot is ahead of its event journal")
        if record.last_event_sequence:
            snapshot_event = events[record.last_event_sequence - 1]
            if snapshot_event.record_sha256 != record.last_event_record_sha256:
                raise ValueError("deployment snapshot event pointer is inconsistent")
        if record.last_event_sequence == len(events):
            if record.last_event_record_sha256 != events[-1].record_sha256:
                raise ValueError("deployment snapshot final event digest is inconsistent")
            return record
        latest = events[-1]
        recovered = latest.recovery_snapshot.to_record(
            last_event_sequence=latest.sequence,
            last_event_record_sha256=latest.record_sha256,
        )
        atomic_write_text(
            path,
            recovered.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
        )
        return recovered

    def _find_by_idempotency(self, command: DeploymentCommand) -> DeploymentJobRecord | None:
        for record in self.list_jobs(limit=10_000):
            if record.job.command.idempotency_key == command.idempotency_key:
                if record.job.command_sha256 != command.canonical_sha256():
                    raise DeploymentJobStateConflict(
                        "deployment idempotency key belongs to a different command"
                    )
                return record
        return None

    def create_job(
        self,
        command: DeploymentCommand,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> DeploymentJobRecord:
        observed_at = now or _utc_now()
        store_lock = self.root / "store-index"
        with interprocess_lock(store_lock):
            existing = self._find_by_idempotency(command)
            if existing is not None:
                return existing
            identity = job_id or f"deployment-{uuid4().hex}"
            path = self._job_path(identity)
            if path.exists() or path.is_symlink():
                raise DeploymentJobStateConflict("deployment job already exists")
            job = DeploymentJob(
                job_id=identity,
                command=command,
                command_sha256=command.canonical_sha256(),
                created_at=observed_at,
                updated_at=observed_at,
            )
            record = DeploymentJobRecord(job=job)
            atomic_write_text(
                path,
                record.model_dump_json(indent=2) + "\n",
                require_absent=True,
            )
            return self.append_event(
                identity,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="job-created",
                summary="Deployment job created.",
                now=observed_at,
            )

    def read_events(
        self,
        job_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> list[DeploymentEventRecord]:
        if after_sequence < 0 or not 1 <= limit <= 10_000:
            raise ValueError("deployment event query bounds are invalid")
        path = self._events_path(job_id)
        if path.is_symlink():
            raise ValueError("deployment event log cannot be a symbolic link")
        if not path.exists():
            return []
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("deployment event log exceeds its size limit")
        records: list[DeploymentEventRecord] = []
        previous: str | None = None
        expected_sequence = 1
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if len(line.encode("utf-8")) > 4 * 1024 * 1024:
                    raise ValueError("deployment event record exceeds its size limit")
                record = DeploymentEventRecord.model_validate_json(line)
                if (
                    record.event.job_id != job_id
                    or record.sequence != expected_sequence
                    or record.previous_record_sha256 != previous
                ):
                    raise ValueError("deployment event chain is inconsistent")
                previous = record.record_sha256
                expected_sequence += 1
                if record.sequence > after_sequence and len(records) < limit:
                    records.append(record)
        return records

    def _append_event_locked(
        self,
        record: DeploymentJobRecord,
        *,
        event_type: DeploymentEventType,
        step_id: str,
        summary: str,
        now: datetime,
        state: DeploymentJobState | None = None,
        artifact_refs: list[str] | None = None,
        approval_ref: str | None = None,
        checkpoints: list[DeploymentStepCheckpoint] | None = None,
        final_artifact_refs: list[str] | None = None,
        cancel_requested: bool | None = None,
        recovery_disposition: DeploymentRecoveryDisposition | None = None,
        attempt: int | None = None,
        blockers: list[str] | None = None,
    ) -> DeploymentJobRecord:
        new_state = state or record.job.state
        if not _transition_allowed(record.job.state, new_state):
            raise DeploymentJobStateConflict(
                f"invalid deployment state transition: {record.job.state.value}->{new_state.value}"
            )
        refs = _validate_artifact_refs(sorted(artifact_refs or []))
        sequence = record.last_event_sequence + 1
        if sequence > 10_000:
            raise DeploymentJobStateConflict("deployment event limit reached")
        event = DeploymentEvent(
            event_id=f"event-{uuid4().hex}",
            job_id=record.job.job_id,
            step_id=step_id,
            target_id=record.job.command.target_id,
            event_type=event_type,
            timestamp=now,
            attempt=attempt or record.attempt,
            state=new_state,
            sanitized_summary=sanitize_deployment_summary(summary),
            artifact_refs=refs,
            approval_ref=approval_ref,
        )
        updated_job = record.job.model_copy(
            update={
                "state": new_state,
                "current_step": step_id,
                "blockers": blockers if blockers is not None else record.job.blockers,
                "updated_at": now,
            }
        )
        updated_base = record.model_copy(
            update={
                "job": updated_job,
                "revision": record.revision + 1,
                "attempt": attempt or record.attempt,
                "cancel_requested": (
                    record.cancel_requested
                    if cancel_requested is None
                    else cancel_requested
                ),
                "recovery_disposition": (
                    record.recovery_disposition
                    if recovery_disposition is None
                    else recovery_disposition
                ),
                "checkpoints": checkpoints if checkpoints is not None else record.checkpoints,
                "final_artifact_refs": (
                    final_artifact_refs
                    if final_artifact_refs is not None
                    else record.final_artifact_refs
                ),
            }
        )
        updated_base = DeploymentJobRecord.model_validate(
            updated_base.model_dump(mode="json")
        )
        recovery_snapshot = DeploymentJobRecoverySnapshot.from_record(updated_base)
        payload = {
            "schema_version": "rolo-deployment-event-record/v1",
            "sequence": sequence,
            "previous_record_sha256": record.last_event_record_sha256,
            "event": event.model_dump(mode="json"),
            "recovery_snapshot": recovery_snapshot.model_dump(mode="json"),
        }
        event_record = DeploymentEventRecord(
            **payload,
            record_sha256=_canonical_sha256(payload),
        )
        updated = updated_base.model_copy(
            update={
                "last_event_sequence": sequence,
                "last_event_record_sha256": event_record.record_sha256,
            }
        )
        updated = DeploymentJobRecord.model_validate(updated.model_dump(mode="json"))
        append_text_record(
            self._events_path(record.job.job_id),
            event_record.model_dump_json() + "\n",
        )
        atomic_write_text(
            self._job_path(record.job.job_id),
            updated.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
        )
        return updated

    def append_event(
        self,
        job_id: str,
        *,
        event_type: DeploymentEventType,
        step_id: str,
        summary: str,
        now: datetime | None = None,
        state: DeploymentJobState | None = None,
        artifact_refs: list[str] | None = None,
        approval_ref: str | None = None,
    ) -> DeploymentJobRecord:
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            return self._append_event_locked(
                record,
                event_type=event_type,
                step_id=step_id,
                summary=summary,
                now=now or _utc_now(),
                state=state,
                artifact_refs=artifact_refs,
                approval_ref=approval_ref,
            )

    def start_step(
        self,
        job_id: str,
        *,
        step_id: str,
        state: DeploymentJobState,
        remote: bool = False,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        observed_at = now or _utc_now()
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            checkpoint = DeploymentStepCheckpoint(
                step_id=step_id,
                attempt=record.attempt,
                status=DeploymentStepStatus.RUNNING,
                command_sha256=record.job.command_sha256,
                remote_state=(
                    DeploymentRemoteState.CONFIRMED
                    if remote
                    else DeploymentRemoteState.NOT_APPLICABLE
                ),
                started_at=observed_at,
                updated_at=observed_at,
            )
            checkpoints = [
                item
                for item in record.checkpoints
                if (item.attempt, item.step_id) != (record.attempt, step_id)
            ]
            checkpoints.append(checkpoint)
            checkpoints.sort(key=lambda item: (item.attempt, item.step_id))
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STEP_STARTED,
                step_id=step_id,
                summary=f"Step {step_id} started.",
                now=observed_at,
                state=state,
                checkpoints=checkpoints,
            )

    def complete_step(
        self,
        job_id: str,
        *,
        step_id: str,
        outcome_sha256: str,
        artifact_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        observed_at = now or _utc_now()
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            matched = False
            checkpoints: list[DeploymentStepCheckpoint] = []
            for item in record.checkpoints:
                if (item.attempt, item.step_id) == (record.attempt, step_id):
                    if item.status != DeploymentStepStatus.RUNNING:
                        raise DeploymentJobStateConflict("deployment step is not running")
                    item = item.model_copy(
                        update={
                            "status": DeploymentStepStatus.COMPLETE,
                            "remote_state": (
                                DeploymentRemoteState.CONFIRMED
                                if item.remote_state == DeploymentRemoteState.CONFIRMED
                                else DeploymentRemoteState.NOT_APPLICABLE
                            ),
                            "updated_at": observed_at,
                            "outcome_sha256": outcome_sha256,
                            "artifact_refs": sorted(artifact_refs or []),
                        }
                    )
                    matched = True
                checkpoints.append(item)
            if not matched:
                raise DeploymentJobStateConflict("deployment step checkpoint is absent")
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STEP_COMPLETED,
                step_id=step_id,
                summary=f"Step {step_id} completed.",
                now=observed_at,
                artifact_refs=artifact_refs,
                checkpoints=checkpoints,
            )

    def fail_step(
        self,
        job_id: str,
        *,
        step_id: str,
        remote_state_known: bool,
        outcome_sha256: str | None = None,
        artifact_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        observed_at = now or _utc_now()
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            matched = False
            checkpoints: list[DeploymentStepCheckpoint] = []
            for item in record.checkpoints:
                if (item.attempt, item.step_id) == (record.attempt, step_id):
                    if item.status != DeploymentStepStatus.RUNNING:
                        raise DeploymentJobStateConflict("deployment step is not running")
                    item = item.model_copy(
                        update={
                            "status": (
                                DeploymentStepStatus.FAILED
                                if remote_state_known
                                else DeploymentStepStatus.UNKNOWN
                            ),
                            "remote_state": (
                                DeploymentRemoteState.CONFIRMED
                                if remote_state_known
                                else DeploymentRemoteState.UNKNOWN
                            ),
                            "updated_at": observed_at,
                            "outcome_sha256": outcome_sha256,
                            "artifact_refs": sorted(artifact_refs or []),
                        }
                    )
                    matched = True
                checkpoints.append(item)
            if not matched:
                raise DeploymentJobStateConflict("deployment step checkpoint is absent")
            if remote_state_known:
                state = DeploymentJobState.FAILED
                disposition = DeploymentRecoveryDisposition.NONE
                blockers: list[str] = []
                summary = f"Step {step_id} failed with confirmed remote state."
            else:
                state = DeploymentJobState.BLOCKED
                disposition = DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
                blockers = ["REQUIRES_REMOTE_RECONCILIATION"]
                summary = f"Step {step_id} failed with unknown remote state."
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STEP_FAILED,
                step_id=step_id,
                summary=summary,
                now=observed_at,
                state=state,
                artifact_refs=artifact_refs,
                checkpoints=checkpoints,
                recovery_disposition=disposition,
                blockers=blockers,
            )

    def block_step(
        self,
        job_id: str,
        *,
        step_id: str,
        blocker_codes: list[str],
        outcome_sha256: str,
        artifact_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        """Finish a known-state step with deterministic product blockers, not reconciliation."""

        if not blocker_codes or blocker_codes != sorted(set(blocker_codes)):
            raise ValueError("deployment blocker codes must be non-empty, unique and sorted")
        if any(
            re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code) is None
            for code in blocker_codes
        ):
            raise ValueError("deployment blocker code is invalid")
        observed_at = now or _utc_now()
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            matched = False
            checkpoints: list[DeploymentStepCheckpoint] = []
            for item in record.checkpoints:
                if (item.attempt, item.step_id) == (record.attempt, step_id):
                    if item.status != DeploymentStepStatus.RUNNING:
                        raise DeploymentJobStateConflict("deployment step is not running")
                    item = item.model_copy(
                        update={
                            "status": DeploymentStepStatus.FAILED,
                            "remote_state": DeploymentRemoteState.CONFIRMED,
                            "updated_at": observed_at,
                            "outcome_sha256": outcome_sha256,
                            "artifact_refs": sorted(artifact_refs or []),
                        }
                    )
                    matched = True
                checkpoints.append(item)
            if not matched:
                raise DeploymentJobStateConflict("deployment step checkpoint is absent")
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STEP_FAILED,
                step_id=step_id,
                summary=f"Step {step_id} stopped on known product blockers.",
                now=observed_at,
                state=DeploymentJobState.BLOCKED,
                artifact_refs=artifact_refs,
                checkpoints=checkpoints,
                recovery_disposition=DeploymentRecoveryDisposition.NONE,
                blockers=blocker_codes,
            )

    def complete_job(
        self,
        job_id: str,
        *,
        artifact_refs: list[str],
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        refs = _validate_artifact_refs(sorted(artifact_refs))
        if not refs:
            raise ValueError("complete deployment job requires final artifact refs")
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            if any(item.status == DeploymentStepStatus.RUNNING for item in record.checkpoints):
                raise DeploymentJobStateConflict("deployment job has a running checkpoint")
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="job-complete",
                summary="Deployment job completed with verified final artifacts.",
                now=now or _utc_now(),
                state=DeploymentJobState.COMPLETE,
                artifact_refs=refs,
                final_artifact_refs=refs,
                cancel_requested=False,
                recovery_disposition=DeploymentRecoveryDisposition.NONE,
            )

    def request_cancel(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            if record.job.state in _TERMINAL_STATES:
                raise DeploymentJobStateConflict("terminal deployment job cannot be cancelled")
            if record.cancel_requested:
                return record
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="cancel-requested",
                summary="Cancellation requested; executor termination is pending confirmation.",
                now=now or _utc_now(),
                cancel_requested=True,
            )

    def resolve_cancel(
        self,
        job_id: str,
        *,
        remote_termination_confirmed: bool,
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            if not record.cancel_requested:
                raise DeploymentJobStateConflict("deployment cancellation was not requested")
            if remote_termination_confirmed:
                state = DeploymentJobState.CANCELLED
                disposition = DeploymentRecoveryDisposition.NONE
                blockers: list[str] = []
                summary = "Cancellation completed and remote termination was confirmed."
            else:
                state = DeploymentJobState.BLOCKED
                disposition = DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
                blockers = ["REQUIRES_REMOTE_RECONCILIATION"]
                summary = "Cancellation left remote state unknown; reconciliation is required."
            return self._append_event_locked(
                record,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="cancel-resolved",
                summary=summary,
                now=now or _utc_now(),
                state=state,
                cancel_requested=False,
                recovery_disposition=disposition,
                blockers=blockers,
            )

    def retry_job(self, job_id: str, *, now: datetime | None = None) -> DeploymentJobRecord:
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            if record.job.state not in {
                DeploymentJobState.BLOCKED,
                DeploymentJobState.FAILED,
                DeploymentJobState.CANCELLED,
            }:
                raise DeploymentJobStateConflict("deployment job is not retryable")
            if record.recovery_disposition == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION:
                raise DeploymentJobStateConflict(
                    "deployment job requires reconciliation before retry"
                )
            if record.attempt >= 100:
                raise DeploymentJobStateConflict("deployment job attempt limit reached")
            # Retry is the one intentional terminal-state escape; build the event from a copy.
            retryable_job = record.job.model_copy(update={"state": DeploymentJobState.CREATED})
            retryable = record.model_copy(update={"job": retryable_job})
            return self._append_event_locked(
                retryable,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="job-retried",
                summary="Deployment job scheduled for a new attempt.",
                now=now or _utc_now(),
                state=DeploymentJobState.CREATED,
                attempt=record.attempt + 1,
                cancel_requested=False,
                recovery_disposition=DeploymentRecoveryDisposition.RESUMABLE,
                blockers=[],
            )

    def resume_job(self, job_id: str, *, now: datetime | None = None) -> DeploymentJobRecord:
        record = self.load_job(job_id)
        if record.recovery_disposition != DeploymentRecoveryDisposition.RESUMABLE:
            raise DeploymentJobStateConflict("deployment job is not marked resumable")
        return self.retry_job(job_id, now=now)

    def reconcile_remote_step(
        self,
        job_id: str,
        *,
        step_id: str,
        outcome: DeploymentRemoteReconciliationOutcome,
        outcome_sha256: str,
        artifact_refs: list[str],
        now: datetime | None = None,
    ) -> DeploymentJobRecord:
        """Resolve one unknown checkpoint from an independently observed remote state."""

        refs = _validate_artifact_refs(sorted(artifact_refs))
        if not refs:
            raise ValueError("remote reconciliation requires an observation artifact")
        if re.fullmatch(_SHA256_PATTERN, outcome_sha256) is None:
            raise ValueError("remote reconciliation outcome digest is invalid")
        observed_at = now or _utc_now()
        path = self._job_path(job_id)
        with interprocess_lock(path):
            record = self._load_synchronized_record(path)
            if (
                record.job.state != DeploymentJobState.BLOCKED
                or record.recovery_disposition
                != DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
            ):
                raise DeploymentJobStateConflict(
                    "deployment job does not require remote reconciliation"
                )
            matched = False
            checkpoint_refs: list[str] = []
            checkpoints: list[DeploymentStepCheckpoint] = []
            for item in record.checkpoints:
                if (item.attempt, item.step_id) == (record.attempt, step_id):
                    if (
                        item.status != DeploymentStepStatus.UNKNOWN
                        or item.remote_state != DeploymentRemoteState.UNKNOWN
                    ):
                        raise DeploymentJobStateConflict(
                            "deployment checkpoint is not remotely unknown"
                        )
                    checkpoint_refs = sorted(set(item.artifact_refs + refs))
                    item = item.model_copy(
                        update={
                            "status": (
                                DeploymentStepStatus.COMPLETE
                                if outcome == DeploymentRemoteReconciliationOutcome.EXACT
                                else DeploymentStepStatus.FAILED
                            ),
                            "remote_state": DeploymentRemoteState.CONFIRMED,
                            "updated_at": observed_at,
                            "outcome_sha256": outcome_sha256,
                            "artifact_refs": checkpoint_refs,
                        }
                    )
                    matched = True
                checkpoints.append(item)
            if not matched:
                raise DeploymentJobStateConflict(
                    "deployment reconciliation checkpoint is absent"
                )

            if outcome == DeploymentRemoteReconciliationOutcome.EXACT:
                state = DeploymentJobState.COMPLETE
                disposition = DeploymentRecoveryDisposition.NONE
                blockers: list[str] = []
                final_refs = sorted(set(record.final_artifact_refs + checkpoint_refs))
                summary = "Remote state exactly matches the approved plan."
            elif outcome == DeploymentRemoteReconciliationOutcome.NOT_COMMITTED:
                state = DeploymentJobState.BLOCKED
                disposition = DeploymentRecoveryDisposition.RESUMABLE
                blockers = ["REMOTE_STATE_CONFIRMED_NOT_COMMITTED"]
                final_refs = record.final_artifact_refs
                summary = "Remote state confirms the approved plan was not committed."
            else:
                state = DeploymentJobState.BLOCKED
                disposition = DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
                blockers = ["REMOTE_STATE_DIVERGED"]
                final_refs = record.final_artifact_refs
                summary = "Remote state differs from the approved plan; manual repair is required."

            # Reconciliation is the only intentional BLOCKED terminal-state resolution.
            mutable_job = record.job.model_copy(update={"state": state})
            mutable_record = record.model_copy(update={"job": mutable_job})
            return self._append_event_locked(
                mutable_record,
                event_type=DeploymentEventType.STATE_CHANGED,
                step_id="remote-reconciled",
                summary=summary,
                now=observed_at,
                state=state,
                artifact_refs=refs,
                checkpoints=checkpoints,
                final_artifact_refs=final_refs,
                recovery_disposition=disposition,
                blockers=blockers,
            )

    @contextmanager
    def target_lease(
        self,
        target_id: str,
        *,
        timeout_s: float = 10.0,
    ) -> Iterator[None]:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", target_id) is None:
            raise ValueError("invalid target id for deployment lease")
        lease_path = self.root / "target-leases" / f"{target_id}.lease"
        with interprocess_lock(lease_path, timeout_s=timeout_s, stale_after_s=3600.0):
            yield

    def request_approval(
        self,
        job_id: str,
        *,
        action: ApprovalAction,
        risk: Literal["R1", "R2", "R3"],
        approver_principal: str,
        summary: str,
        expires_at: datetime,
        authorization_scope_sha256: str | None = None,
        now: datetime | None = None,
        approval_id: str | None = None,
    ) -> ApprovalRequest:
        observed_at = now or _utc_now()
        record = self.load_job(job_id)
        request = ApprovalRequest(
            approval_id=approval_id or f"approval-{uuid4().hex}",
            job_id=job_id,
            target_id=record.job.command.target_id,
            command_sha256=record.job.command_sha256,
            authorization_scope_sha256=authorization_scope_sha256,
            requester_principal=record.job.command.requested_by,
            approver_principal=approver_principal,
            action=action,
            risk=risk,
            sanitized_summary=sanitize_deployment_summary(summary),
            requested_at=observed_at,
            expires_at=expires_at,
        )
        directory = self._approval_dir(request.approval_id)
        atomic_write_text(
            directory / "request.json",
            request.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        self.append_event(
            job_id,
            event_type=DeploymentEventType.APPROVAL_REQUIRED,
            step_id=f"approval-{action.value.casefold()}",
            summary=request.sanitized_summary,
            now=observed_at,
            approval_ref=request.approval_id,
        )
        return request

    def load_approval_request(self, approval_id: str) -> ApprovalRequest:
        path = self._approval_dir(approval_id) / "request.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError("approval request is unavailable")
        return ApprovalRequest.model_validate_json(path.read_text(encoding="utf-8"))

    def list_approval_requests(self, *, limit: int = 1000) -> list[ApprovalRequest]:
        if not 1 <= limit <= 10_000:
            raise ValueError("deployment approval list limit is out of bounds")
        approvals_root = self.root / "approvals"
        if not approvals_root.exists():
            return []
        requests: list[ApprovalRequest] = []
        for child in sorted(approvals_root.iterdir(), key=lambda path: path.name):
            if len(requests) >= limit:
                break
            if child.is_symlink() or not child.is_dir():
                continue
            requests.append(self.load_approval_request(child.name))
        return requests

    def decide_approval(
        self,
        approval_id: str,
        *,
        principal: str,
        approve: bool,
        reason: str,
        now: datetime | None = None,
        decision_id: str | None = None,
    ) -> ApprovalDecision:
        observed_at = now or _utc_now()
        request = self.load_approval_request(approval_id)
        if principal != request.approver_principal:
            raise ValueError("approval decision principal does not match its request")
        if observed_at >= request.expires_at:
            raise ValueError("approval request is expired")
        decision = ApprovalDecision(
            decision_id=decision_id or f"decision-{uuid4().hex}",
            approval_id=request.approval_id,
            request_sha256=request.canonical_sha256(),
            job_id=request.job_id,
            target_id=request.target_id,
            command_sha256=request.command_sha256,
            action=request.action,
            principal=principal,
            status=ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED,
            decided_at=observed_at,
            expires_at=request.expires_at,
            sanitized_reason=sanitize_deployment_summary(reason),
        )
        path = self._approval_dir(approval_id) / "decision.json"
        atomic_write_text(
            path,
            decision.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        self.append_event(
            request.job_id,
            event_type=DeploymentEventType.APPROVAL_DECIDED,
            step_id=f"approval-{request.action.value.casefold()}",
            summary=(
                f"Approval {request.action.value} was "
                f"{decision.status.value.casefold()} by the bound principal."
            ),
            now=observed_at,
            approval_ref=request.approval_id,
        )
        return decision

    def load_approval_decision(self, approval_id: str) -> ApprovalDecision:
        path = self._approval_dir(approval_id) / "decision.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError("approval decision is unavailable")
        return ApprovalDecision.model_validate_json(path.read_text(encoding="utf-8"))

    def get_approval_decision(self, approval_id: str) -> ApprovalDecision | None:
        path = self._approval_dir(approval_id) / "decision.json"
        if not path.exists() and not path.is_symlink():
            return None
        return self.load_approval_decision(approval_id)

    def verify_approval(
        self,
        approval_id: str,
        *,
        job_id: str,
        target_id: str,
        command_sha256: str,
        action: ApprovalAction,
        now: datetime | None = None,
    ) -> ApprovalDecision:
        request = self.load_approval_request(approval_id)
        decision = self.load_approval_decision(approval_id)
        observed_at = now or _utc_now()
        if (
            decision.status != ApprovalStatus.APPROVED
            or decision.request_sha256 != request.canonical_sha256()
            or decision.approval_id != request.approval_id
            or decision.job_id != request.job_id
            or decision.target_id != request.target_id
            or decision.command_sha256 != request.command_sha256
            or decision.action != request.action
            or decision.principal != request.approver_principal
            or request.job_id != job_id
            or request.target_id != target_id
            or request.command_sha256 != command_sha256
            or request.action != action
            or observed_at >= request.expires_at
        ):
            raise ValueError("approval decision does not authorize the requested command")
        return decision

    def recover_incomplete_jobs(
        self,
        *,
        now: datetime | None = None,
    ) -> list[DeploymentRecoveryResult]:
        observed_at = now or _utc_now()
        results: list[DeploymentRecoveryResult] = []
        for current in self.list_jobs(limit=10_000):
            if current.job.state in _TERMINAL_STATES:
                continue
            previous = current.job.state
            needs_reconciliation = previous in _MUTATING_STATES or any(
                item.status == DeploymentStepStatus.RUNNING
                and item.remote_state == DeploymentRemoteState.CONFIRMED
                for item in current.checkpoints
            )
            disposition = (
                DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
                if needs_reconciliation
                else DeploymentRecoveryDisposition.RESUMABLE
            )
            blockers = [
                "REQUIRES_REMOTE_RECONCILIATION"
                if needs_reconciliation
                else "RESTART_RESUME_REQUIRED"
            ]
            path = self._job_path(current.job.job_id)
            with interprocess_lock(path):
                latest = self._load_synchronized_record(path)
                if latest.job.state in _TERMINAL_STATES:
                    continue
                self._append_event_locked(
                    latest,
                    event_type=DeploymentEventType.STATE_CHANGED,
                    step_id="restart-recovery",
                    summary=(
                        "Controller restart requires remote reconciliation."
                        if needs_reconciliation
                        else "Controller restart left a resumable job checkpoint."
                    ),
                    now=observed_at,
                    state=DeploymentJobState.BLOCKED,
                    recovery_disposition=disposition,
                    blockers=blockers,
                )
            results.append(
                DeploymentRecoveryResult(
                    job_id=current.job.job_id,
                    previous_state=previous,
                    recovered_state=DeploymentJobState.BLOCKED,
                    disposition=disposition,
                    recovered_at=observed_at,
                )
            )
        return results

    def iter_sse(
        self,
        job_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> Iterator[str]:
        for record in self.read_events(
            job_id,
            after_sequence=after_sequence,
            limit=limit,
        ):
            data = _canonical_json(record.model_dump(mode="json"))
            yield (
                f"id: {record.sequence}\n"
                f"event: {record.event.event_type.value.casefold()}\n"
                f"data: {data}\n\n"
            )
