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
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)

    @staticmethod
    def _check_revision(job: Job, expected_revision: int) -> None:
        if job.revision != expected_revision:
            raise ValueError(
                f"job revision conflict: expected {expected_revision}, current {job.revision}"
            )
