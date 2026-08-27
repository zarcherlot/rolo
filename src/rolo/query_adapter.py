"""Read-only query adapter for TUI/GUI clients."""

from __future__ import annotations

from typing import Protocol

from rolo.job_service import JobService
from rolo.jobs import JobEventPage, JobPage, JobRecovery


class JobQueryAdapter(Protocol):
    def list(self, *, limit: int = 20, offset: int = 0) -> JobPage: ...

    def recover(self, job_id: str) -> JobRecovery: ...

    def events(self, job_id: str, *, limit: int = 20, offset: int = 0) -> JobEventPage: ...


class ServiceJobQueryAdapter:
    """Thin client-facing adapter; it never starts or resumes a Job."""

    def __init__(self, service: JobService) -> None:
        self.service = service

    def list(self, *, limit: int = 20, offset: int = 0) -> JobPage:
        return self.service.list(limit=limit, offset=offset)

    def recover(self, job_id: str) -> JobRecovery:
        return self.service.recover(job_id)

    def events(self, job_id: str, *, limit: int = 20, offset: int = 0) -> JobEventPage:
        return self.service.events(job_id, limit=limit, offset=offset)
