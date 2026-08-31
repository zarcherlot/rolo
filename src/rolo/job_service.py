"""Stable service facade shared by CLI, API, natural language, TUI and GUI clients."""

from __future__ import annotations

import hashlib
from pathlib import Path

from rolo.jobs import JobEventPage, JobPage, JobRecovery, JobStore


def _opaque_target(target: str) -> str:
    """Expose a stable target handle without returning URI/path/credential material."""

    return f"target-{hashlib.sha256(target.encode('utf-8')).hexdigest()[:16]}"


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
            page = self.store.job_page(limit=limit, offset=offset)
            return page.model_copy(
                update={
                    "items": [
                        item.model_copy(update={"target": _opaque_target(item.target)})
                        for item in page.items
                    ]
                }
            )
        except ValueError as exc:
            raise JobServiceError("INVALID_PAGINATION", str(exc)) from exc

    def recover(self, job_id: str) -> JobRecovery:
        try:
            recovery = self.store.recover(job_id)
            return recovery.model_copy(
                update={
                    "job": recovery.job.model_copy(
                        update={"target": _opaque_target(recovery.job.target)}
                    )
                }
            )
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
