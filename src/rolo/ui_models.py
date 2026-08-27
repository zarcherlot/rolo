"""Presentation-neutral Job view models for TUI and GUI clients."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rolo.job_service import JobServiceError
from rolo.jobs import JobEventPage, JobPage, JobRecovery
from rolo.query_adapter import JobQueryAdapter


class JobRow(BaseModel):
    job_id: str
    operation: str
    target: str
    status: str
    revision: int = Field(ge=0)
    updated_at: str


class JobListView(BaseModel):
    schema_version: str = "rolo-job-list-view/v1"
    rows: list[JobRow]
    total: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class JobDetailView(BaseModel):
    schema_version: str = "rolo-job-detail-view/v1"
    job: JobRow
    latest_event: dict[str, object] | None = None
    latest_checkpoint: dict[str, object] | None = None
    resumable: bool
    limitations: list[str] = Field(default_factory=list)


class JobUiError(BaseModel):
    schema_version: str = "rolo-job-ui-error/v1"
    code: str
    message: str


class JobListState(BaseModel):
    schema_version: str = "rolo-job-list-state/v1"
    status: str
    view: JobListView | None = None
    error: JobUiError | None = None


class JobDetailState(BaseModel):
    schema_version: str = "rolo-job-detail-state/v1"
    status: str
    view: JobDetailView | None = None
    error: JobUiError | None = None


class JobUiAdapter:
    """Convert shared service models into stable, read-only UI view models."""

    def __init__(self, query: JobQueryAdapter) -> None:
        self.query = query

    def list_view(self, *, limit: int = 20, offset: int = 0) -> JobListView:
        page: JobPage = self.query.list(limit=limit, offset=offset)
        return JobListView(
            rows=[
                JobRow(
                    job_id=item.job_id,
                    operation=item.operation,
                    target=item.target,
                    status=item.status.value,
                    revision=item.revision,
                    updated_at=item.updated_at.isoformat(),
                )
                for item in page.items
            ],
            total=page.total,
            next_offset=page.next_offset,
        )

    def detail_view(self, job_id: str) -> JobDetailView:
        recovery: JobRecovery = self.query.recover(job_id)
        job = recovery.job
        return JobDetailView(
            job=JobRow(
                job_id=job.job_id,
                operation=job.operation,
                target=job.target,
                status=job.status.value,
                revision=job.revision,
                updated_at=job.updated_at.isoformat(),
            ),
            latest_event=(
                recovery.latest_event.model_dump(mode="json")
                if recovery.latest_event
                else None
            ),
            latest_checkpoint=(
                recovery.latest_checkpoint.model_dump(mode="json")
                if recovery.latest_checkpoint
                else None
            ),
            resumable=recovery.resumable,
            limitations=recovery.limitations,
        )

    def events(self, job_id: str, *, limit: int = 20, offset: int = 0) -> JobEventPage:
        return self.query.events(job_id, limit=limit, offset=offset)

    def safe_list_view(self, *, limit: int = 20, offset: int = 0) -> JobListState:
        try:
            return JobListState(status="READY", view=self.list_view(limit=limit, offset=offset))
        except (OSError, ValueError) as exc:
            return JobListState(
                status="ERROR", error=JobUiError(code="JOB_QUERY_FAILED", message=str(exc))
            )

    def safe_detail_view(self, job_id: str) -> JobDetailState:
        try:
            return JobDetailState(status="READY", view=self.detail_view(job_id))
        except (FileNotFoundError, OSError, ValueError) as exc:
            code = (
                "JOB_NOT_FOUND"
                if isinstance(exc, JobServiceError) and exc.code == "JOB_NOT_FOUND"
                else "JOB_QUERY_FAILED"
            )
            return JobDetailState(status="ERROR", error=JobUiError(code=code, message=str(exc)))
