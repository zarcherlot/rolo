"""Stable service facade shared by CLI, API, natural language, TUI and GUI clients."""

from __future__ import annotations

from pathlib import Path

from rolo.jobs import JobEventPage, JobPage, JobRecovery, JobStore


class JobService:
    def __init__(self, root: Path) -> None:
        self.store = JobStore(root)

    def list(self, *, limit: int = 20, offset: int = 0) -> JobPage:
        return self.store.job_page(limit=limit, offset=offset)

    def recover(self, job_id: str) -> JobRecovery:
        return self.store.recover(job_id)

    def events(self, job_id: str, *, limit: int = 20, offset: int = 0) -> JobEventPage:
        return self.store.event_page(job_id, limit=limit, offset=offset)
