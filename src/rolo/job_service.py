"""Stable service facade shared by CLI, API, natural language, TUI and GUI clients."""

from __future__ import annotations

from pathlib import Path

from rolo.jobs import JobEventPage, JobPage, JobRecovery, JobStore


class JobServiceError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class JobService:
    def __init__(self, root: Path) -> None:
        self.store = JobStore(root)

    def list(self, *, limit: int = 20, offset: int = 0) -> JobPage:
        try:
            return self.store.job_page(limit=limit, offset=offset)
        except ValueError as exc:
            raise JobServiceError("INVALID_PAGINATION", str(exc)) from exc

    def recover(self, job_id: str) -> JobRecovery:
        try:
            return self.store.recover(job_id)
        except FileNotFoundError as exc:
            raise JobServiceError("JOB_NOT_FOUND", "job not found", status_code=404) from exc
        except ValueError as exc:
            raise JobServiceError("INVALID_JOB_ID", str(exc)) from exc

    def events(self, job_id: str, *, limit: int = 20, offset: int = 0) -> JobEventPage:
        try:
            return self.store.event_page(job_id, limit=limit, offset=offset)
        except FileNotFoundError as exc:
            raise JobServiceError("JOB_NOT_FOUND", "job not found", status_code=404) from exc
        except ValueError as exc:
            code = (
                "INVALID_PAGINATION"
                if "limit" in str(exc) or "offset" in str(exc)
                else "INVALID_JOB_ID"
            )
            raise JobServiceError(code, str(exc)) from exc
