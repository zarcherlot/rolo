"""Transport-neutral Job/Event/Checkpoint contracts for resumable Adapt work."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from rolo.core.models import utc_now
from rolo.core.persistence import atomic_write_text
from rolo.targets.approvals import BootstrapApprovalDecision, BootstrapApprovalRequest
from rolo.targets.bootstrap import BootstrapExecutionResult, BootstrapTransport, execute_bootstrap
from rolo.targets.models import TargetBootstrapPlan


class JobStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class JobEvent(BaseModel):
    schema_version: Literal["rolo-job-event/v1"] = "rolo-job-event/v1"
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}", min_length=1)
    job_id: str
    sequence: int = Field(ge=0)
    event_type: str = Field(min_length=1, max_length=128)
    status: JobStatus
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class JobCheckpoint(BaseModel):
    schema_version: Literal["rolo-job-checkpoint/v1"] = "rolo-job-checkpoint/v1"
    checkpoint_id: str = Field(default_factory=lambda: f"chk_{uuid4().hex}", min_length=1)
    job_id: str
    sequence: int = Field(ge=0)
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Job(BaseModel):
    schema_version: Literal["rolo-job/v1"] = "rolo-job/v1"
    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex}", min_length=1)
    operation: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=1024)
    status: JobStatus = JobStatus.CREATED
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime


class JobSummary(BaseModel):
    schema_version: Literal["rolo-job-summary/v1"] = "rolo-job-summary/v1"
    job_id: str
    operation: str
    target: str
    status: JobStatus
    revision: int = Field(ge=0)
    updated_at: datetime


class JobRecovery(BaseModel):
    schema_version: Literal["rolo-job-recovery/v1"] = "rolo-job-recovery/v1"
    job: Job
    latest_event: JobEvent | None = None
    latest_checkpoint: JobCheckpoint | None = None
    resumable: bool
    limitations: list[str] = Field(default_factory=list)


class JobPage(BaseModel):
    schema_version: Literal["rolo-job-page/v1"] = "rolo-job-page/v1"
    items: list[JobSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class JobEventPage(BaseModel):
    schema_version: Literal["rolo-job-event-page/v1"] = "rolo-job-event-page/v1"
    job_id: str
    items: list[JobEvent]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class JobStore:
    """Small append-only JSON repository with optimistic revision checks."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, operation: str, target: str, *, now: datetime | None = None) -> Job:
        timestamp = now or utc_now()
        job = Job(
            operation=operation, target=target, created_at=timestamp, updated_at=timestamp
        )
        self._write(
            job.job_id,
            {"job": job.model_dump(mode="json"), "events": [], "checkpoints": []},
        )
        return job

    def load(self, job_id: str) -> tuple[Job, list[JobEvent], list[JobCheckpoint]]:
        data = json.loads(self._path(job_id).read_text(encoding="utf-8"))
        return (
            Job.model_validate(data["job"]),
            [JobEvent.model_validate(item) for item in data["events"]],
            [JobCheckpoint.model_validate(item) for item in data["checkpoints"]],
        )

    def list_jobs(self, *, limit: int = 100, offset: int = 0) -> list[JobSummary]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("job list limit must be 1..100 and offset must be non-negative")
        summaries: list[JobSummary] = []
        for path in sorted(
            self.root.glob("job_*.json"), key=lambda item: item.stat().st_mtime, reverse=True
        ):
            try:
                job, _, _ = self.load(path.stem)
            except (OSError, ValueError, KeyError):
                continue
            summaries.append(
                JobSummary(
                    job_id=job.job_id,
                    operation=job.operation,
                    target=job.target,
                    status=job.status,
                    revision=job.revision,
                    updated_at=job.updated_at,
                )
            )
        return summaries[offset : offset + limit]

    def job_page(self, *, limit: int = 100, offset: int = 0) -> JobPage:
        items = self.list_jobs(limit=limit, offset=offset)
        total = len(list(self.root.glob("job_*.json")))
        next_offset = offset + limit if offset + limit < total else None
        return JobPage(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            next_offset=next_offset,
        )

    def recover(self, job_id: str) -> JobRecovery:
        job, events, checkpoints = self.load(job_id)
        return JobRecovery(
            job=job,
            latest_event=events[-1] if events else None,
            latest_checkpoint=checkpoints[-1] if checkpoints else None,
            resumable=job.status in {JobStatus.CREATED, JobStatus.RUNNING},
            limitations=[
                "Recovery returns state only; it never resumes host mutation automatically."
            ],
        )

    def find_completed_bootstrap(
        self, *, plan_sha256: str, target: str
    ) -> tuple[Job, BootstrapExecutionResult] | None:
        """Return a successful bootstrap for the same plan and target."""
        for path in self.root.glob("job_*.json"):
            try:
                job, events, checkpoints = self.load(path.stem)
            except (OSError, ValueError, KeyError):
                continue
            if job.operation != "target.bootstrap.execute" or job.target != target:
                continue
            if job.status != JobStatus.SUCCEEDED:
                continue
            if not any(event.payload.get("plan_sha256") == plan_sha256 for event in events):
                continue
            for checkpoint in reversed(checkpoints):
                result = checkpoint.state.get("result")
                if isinstance(result, dict):
                    try:
                        return job, BootstrapExecutionResult.model_validate(result)
                    except ValueError:
                        break
        return None

    def list_events(self, job_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEvent]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("event list limit must be 1..100 and offset must be non-negative")
        _, events, _ = self.load(job_id)
        return events[offset : offset + limit]

    def event_page(self, job_id: str, *, limit: int = 100, offset: int = 0) -> JobEventPage:
        _, events, _ = self.load(job_id)
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("event list limit must be 1..100 and offset must be non-negative")
        items = events[offset : offset + limit]
        next_offset = offset + limit if offset + limit < len(events) else None
        return JobEventPage(
            job_id=job_id,
            items=items,
            total=len(events),
            limit=limit,
            offset=offset,
            next_offset=next_offset,
        )

    def append_event(
        self,
        job_id: str,
        event_type: str,
        status: JobStatus,
        *,
        expected_revision: int,
        payload: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> JobEvent:
        job, events, checkpoints = self.load(job_id)
        self._check_revision(job, expected_revision)
        timestamp = now or utc_now()
        event = JobEvent(
            job_id=job_id,
            sequence=job.revision + 1,
            event_type=event_type,
            status=status,
            occurred_at=timestamp,
            payload=payload or {},
        )
        updated = job.model_copy(
            update={"status": status, "revision": event.sequence, "updated_at": timestamp}
        )
        self._write(
            job_id,
            {
                "job": updated.model_dump(mode="json"),
                "events": [
                    *[item.model_dump(mode="json") for item in events],
                    event.model_dump(mode="json"),
                ],
                "checkpoints": [item.model_dump(mode="json") for item in checkpoints],
            },
        )
        return event

    def save_checkpoint(
        self,
        job_id: str,
        state: dict[str, Any],
        *,
        expected_revision: int,
        now: datetime | None = None,
    ) -> JobCheckpoint:
        job, events, checkpoints = self.load(job_id)
        self._check_revision(job, expected_revision)
        checkpoint = JobCheckpoint(
            job_id=job_id,
            sequence=job.revision,
            state=state,
            created_at=now or utc_now(),
        )
        self._write(
            job_id,
            {
                "job": job.model_dump(mode="json"),
                "events": [item.model_dump(mode="json") for item in events],
                "checkpoints": [
                    *[item.model_dump(mode="json") for item in checkpoints],
                    checkpoint.model_dump(mode="json"),
                ],
            },
        )
        return checkpoint

    def _path(self, job_id: str) -> Path:
        if not job_id or "/" in job_id or "\\" in job_id or ".." in job_id:
            raise ValueError("unsafe job id")
        return self.root / f"{job_id}.json"

    def _write(self, job_id: str, data: dict[str, Any]) -> None:
        path = self._path(job_id)
        atomic_write_text(
            path,
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        )

    @staticmethod
    def _check_revision(job: Job, expected_revision: int) -> None:
        if job.revision != expected_revision:
            raise ValueError(
                f"job revision conflict: expected {expected_revision}, current {job.revision}"
            )


def run_bootstrap_job(
    store: JobStore,
    plan: TargetBootstrapPlan,
    request: BootstrapApprovalRequest,
    decision: BootstrapApprovalDecision,
    *,
    manifest_path: Path,
    package_path: Path,
    verification_key: bytes,
    transport: BootstrapTransport,
    timeout_s: float = 60.0,
    rollback_on_failure: bool = False,
    now: datetime | None = None,
) -> tuple[Job, BootstrapExecutionResult]:
    """Execute approved bootstrap while recording a resumable lifecycle."""
    existing = store.find_completed_bootstrap(
        plan_sha256=request.plan_sha256,
        target=plan.target.model_dump_json(),
    )
    if existing is not None:
        return existing
    job = store.create("target.bootstrap.execute", plan.target.model_dump_json(), now=now)
    store.append_event(
        job.job_id,
        "JOB_STARTED",
        JobStatus.RUNNING,
        expected_revision=0,
        now=now,
        payload={"plan_sha256": request.plan_sha256, "approval_request_id": request.request_id},
    )
    store.save_checkpoint(
        job.job_id,
        {"phase": "authority-verified", "plan_sha256": request.plan_sha256},
        expected_revision=1,
        now=now,
    )
    try:
        result = execute_bootstrap(
            plan,
            request,
            decision,
            manifest_path=manifest_path,
            package_path=package_path,
            verification_key=verification_key,
            transport=transport,
            timeout_s=timeout_s,
            rollback_on_failure=rollback_on_failure,
            now=now,
        )
    except (OSError, ValueError) as exc:
        store.append_event(
            job.job_id,
            "BOOTSTRAP_FAILED",
            JobStatus.FAILED,
            expected_revision=1,
            now=now,
            payload={"error": str(exc)},
        )
        raise
    store.save_checkpoint(
        job.job_id,
        {"phase": "completed", "result": result.model_dump(mode="json")},
        expected_revision=1,
        now=now,
    )
    final_status = JobStatus.SUCCEEDED if result.status == "SUCCEEDED" else JobStatus.FAILED
    store.append_event(
        job.job_id,
        "BOOTSTRAP_COMPLETED" if result.status == "SUCCEEDED" else "BOOTSTRAP_FAILED",
        final_status,
        expected_revision=1,
        now=now,
        payload={"diagnostics": result.diagnostics},
    )
    return store.load(job.job_id)[0], result
