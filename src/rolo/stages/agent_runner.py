"""Provider-neutral execution envelope for downstream lifecycle Agents.

Diagnose and Verify intentionally share this runner.  A product-specific plugin
implements the small ``StageAgentExecutor`` protocol; Rolo owns authorization,
run identity, stream persistence, and the handoff validation callback supplied by
each stage after execution.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref

StageName = Literal["diagnose", "verify"]
OutputCallback = Callable[[str, str], None]
HandoffValidator = Callable[["StageAgentTask"], None]
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|token|secret|password|credential)\b\s*[=:]\s*)[^\s,;]+"
)
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def _redact_stream(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(r"\1<redacted>", value)
    return _BEARER.sub("Bearer <redacted>", value)


class StageAgentTask(BaseModel):
    """Immutable, secret-free task envelope passed to a downstream Agent plugin."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-stage-agent-task/v1"] = "rolo-stage-agent-task/v1"
    stage: StageName
    robot_id: str = Field(min_length=1, max_length=128)
    task: str = Field(min_length=1, max_length=20_000)
    input_refs: dict[str, str] = Field(default_factory=dict)
    input_sha256: dict[str, str] = Field(default_factory=dict)
    output_contract: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=128)
    executor: str = Field(min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=256)
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StageAgentRun(BaseModel):
    """Persisted execution envelope; it is not a release or handoff decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-stage-agent-run/v1"] = "rolo-stage-agent-run/v1"
    stage: StageName
    robot_id: str
    run_id: str
    status: Literal["WAITING_FOR_AUTH", "RUNNING", "SUCCEEDED", "FAILED"]
    provider: str
    executor: str
    model: str | None = None
    task_ref: str
    request_ref: str | None = None
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    output_refs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class StageAgentExecutor(Protocol):
    """Plugin boundary for a Diagnose or Verify Agent product."""

    def execute_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None = None,
    ) -> Mapping[str, str]: ...


def list_stage_authorization_requests(
    artifact_root: Path,
    *,
    stage: StageName | None = None,
    robot_id: str | None = None,
) -> list[dict[str, object]]:
    """Return pending downstream-Agent approvals with exact stage/robot identity.

    This read-only helper is shared by MCP and the HTTP/UI surface.  It deliberately
    filters on the persisted payload as well as the directory selected by the caller,
    preventing a UI from presenting an approval for a different robot or stage.
    """

    layout = ArtifactLayout(artifact_root)
    stages: tuple[StageName, ...] = (stage,) if stage else ("diagnose", "verify")
    requests: list[dict[str, object]] = []
    for selected_stage in stages:
        stage_root = artifact_root / selected_stage
        if robot_id:
            robot_roots = (layout.stage_latest(selected_stage, robot_id).parent,)
        else:
            robot_roots = tuple(stage_root.iterdir()) if stage_root.is_dir() else ()
        for robot_root in robot_roots:
            request_root = robot_root / "authorization" / "requests"
            if not request_root.is_dir():
                continue
            for request_path in request_root.glob("*.json"):
                try:
                    payload = json_load(request_path)
                except (OSError, ValueError):
                    continue
                if not isinstance(payload, dict) or payload.get("status") != "PENDING":
                    continue
                if payload.get("stage") != selected_stage:
                    continue
                if robot_id and payload.get("robot_id") != robot_id:
                    continue
                requests.append(payload)
    requests.sort(key=lambda item: str(item.get("created_at", "")))
    return requests


def recover_stale_stage_runs(
    artifact_root: Path,
    stage: StageName,
    robot_id: str,
    *,
    stale_after_s: float = 3600.0,
) -> list[StageAgentRun]:
    """Mark abandoned RUNNING stage runs as FAILED after a bounded lease.

    Recovery is deliberately conservative: only persisted runs whose start time is
    older than the lease are changed.  A live executor keeps its run younger than the
    lease; a later run can therefore be retried explicitly without reusing a stale
    authorization or pretending that an interrupted process completed.
    """

    if stale_after_s <= 0:
        raise ValueError("stale_after_s must be positive")
    runs_root = ArtifactLayout(artifact_root).stage_latest(stage, robot_id).parent / "runs"
    if not runs_root.is_dir():
        return []
    now = datetime.now(timezone.utc)
    recovered: list[StageAgentRun] = []
    for run_path in sorted(runs_root.glob("*/run.json")):
        try:
            run = StageAgentRun.model_validate_json(run_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if run.status != "RUNNING":
            continue
        age_s = (now - run.started_at).total_seconds()
        if age_s <= stale_after_s:
            continue
        with interprocess_lock(run_path):
            try:
                current = StageAgentRun.model_validate_json(run_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if current.status != "RUNNING":
                continue
            failed = current.model_copy(
                update={
                    "status": "FAILED",
                    "error": "stage Agent run lease expired; recovered after interruption",
                    "completed_at": now,
                }
            )
            atomic_write_text(
                run_path,
                json.dumps(failed.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
                acquire_lock=False,
            )
            recovered.append(failed)
    return recovered


class StageAgentRunner:
    """Run one downstream Agent with explicit user authorization and audit refs."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        executor: StageAgentExecutor,
        *,
        handoff_validator: HandoffValidator | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.executor = executor
        self.handoff_validator = handoff_validator

    def run(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        confirmed: bool,
        authorization_ref: str | None = None,
        on_output: OutputCallback | None = None,
    ) -> StageAgentRun:
        layout = ArtifactLayout(self.artifacts.root)
        if authorization_ref and not confirmed:
            raise ValueError(
                "resuming a Stage Agent authorization requires explicit current-user confirmation"
            )
        # Validate digest-bound inputs before consuming a pending approval. A changed
        # artifact must leave the request pending so the user can review a fresh plan.
        self._validate_input_hashes(task)
        request: dict[str, object] | None = None
        request_path: Path | None = None
        if authorization_ref:
            request_path = resolve_artifact_ref(self.artifacts.root, authorization_ref)
            request = json_load(request_path)
            self._validate_authorization_request(request, task)
            run_id = str(request["run_id"])
            expected_task_ref = layout.ref(
                self.artifacts.root / task.stage / task.robot_id / "runs" / run_id / "task.json"
            )
            with interprocess_lock(request_path):
                request = json_load(request_path)
                self._validate_authorization_request(request, task)
                if request.get("task_ref") != expected_task_ref:
                    raise ValueError(
                        "authorization request task reference does not match the resumed task"
                    )
                request["status"] = "APPROVED"
                request["approved_at"] = datetime.now(timezone.utc).isoformat()
                atomic_write_text(
                    request_path,
                    json.dumps(request, ensure_ascii=False, indent=2, default=str) + "\n",
                    acquire_lock=False,
                )
        else:
            run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        started = datetime.now(timezone.utc)
        task_payload = task.model_dump(mode="json")
        task_path = self.artifacts.write_json(
            f"{task.stage}/{task.robot_id}/runs/{run_id}/task.json", task_payload
        )
        task_ref = layout.ref(task_path)
        if request is not None and request.get("task_ref") != task_ref:
            raise ValueError("authorization request task reference does not match the resumed task")
        if not confirmed:
            request = {
                "schema_version": "rolo-authorization-request/v1",
                "request_id": f"auth-{uuid4().hex}",
                "status": "PENDING",
                "run_id": run_id,
                "scope": f"{task.stage}.agent.execute",
                "stage": task.stage,
                "robot_id": task.robot_id,
                "executor": task.executor,
                "provider": task.provider,
                "model": task.model,
                "task_ref": task_ref,
                "plan_sha256": task.plan_sha256,
                "created_at": started.isoformat(),
                "expires_at": (started + timedelta(minutes=15)).isoformat(),
            }
            request_ref = layout.ref(
                self.artifacts.write_json(
                    f"{task.stage}/{task.robot_id}/authorization/requests/{request['request_id']}.json",
                    request,
                )
            )
            run = StageAgentRun(
                stage=task.stage,
                robot_id=task.robot_id,
                run_id=run_id,
                status="WAITING_FOR_AUTH",
                provider=task.provider,
                executor=task.executor,
                model=task.model,
                task_ref=task_ref,
                request_ref=request_ref,
                started_at=started,
            )
            self.artifacts.write_json(
                f"{task.stage}/{task.robot_id}/runs/{run_id}/run.json",
                run.model_dump(mode="json"),
            )
            return run

        request_ref = authorization_ref

        run_root = layout.stage_run(task.stage, task.robot_id, run_id)
        run_root.mkdir(parents=True, exist_ok=True)
        running = StageAgentRun(
            stage=task.stage,
            robot_id=task.robot_id,
            run_id=run_id,
            status="RUNNING",
            provider=task.provider,
            executor=task.executor,
            model=task.model,
            task_ref=task_ref,
            request_ref=request_ref,
            started_at=started,
        )
        self.artifacts.write_json(
            f"{task.stage}/{task.robot_id}/runs/{run_id}/run.json",
            running.model_dump(mode="json"),
        )
        stream_paths: dict[str, Path] = {}

        def stream_output(stream: str, line: str) -> None:
            if stream not in {"stdout", "stderr"}:
                raise ValueError(f"unsupported Stage Agent output stream: {stream}")
            safe_line = _redact_stream(line[:8_000])
            path = self.artifacts.append_jsonl(
                f"{task.stage}/{task.robot_id}/runs/{run_id}/{stream}.jsonl",
                {"observed_at": datetime.now(timezone.utc).isoformat(), "line": safe_line},
            )
            stream_paths[stream] = path
            if on_output is not None:
                on_output(stream, safe_line)

        try:
            # A robot/stage gets one active downstream executor.  Fail fast when a
            # second caller races an existing run; it may retry after the first run
            # is persisted instead of interleaving evidence or handoffs.
            execution_lock = (
                self.artifacts.root / task.stage / task.robot_id / ".stage-execution.lock"
            )
            with interprocess_lock(execution_lock, timeout_s=0.0, stale_after_s=3600.0):
                result = self.executor.execute_stage(
                    task, workspace=workspace, on_output=stream_output
                )
                output_refs = dict(result)
                self._validate_output_refs(output_refs)
                if self.handoff_validator is not None:
                    self.handoff_validator(task)
                completed = datetime.now(timezone.utc)
                stdout_ref = (
                    layout.ref(stream_paths["stdout"]) if "stdout" in stream_paths else None
                )
                stderr_ref = (
                    layout.ref(stream_paths["stderr"]) if "stderr" in stream_paths else None
                )
                run = StageAgentRun(
                    stage=task.stage,
                    robot_id=task.robot_id,
                    run_id=run_id,
                    status="SUCCEEDED",
                    provider=task.provider,
                    executor=task.executor,
                    model=task.model,
                    task_ref=task_ref,
                    request_ref=request_ref,
                    stdout_ref=stdout_ref,
                    stderr_ref=stderr_ref,
                    output_refs=output_refs,
                    started_at=started,
                    completed_at=completed,
                )
        except Exception as exc:
            stdout_ref = layout.ref(stream_paths["stdout"]) if "stdout" in stream_paths else None
            stderr_ref = layout.ref(stream_paths["stderr"]) if "stderr" in stream_paths else None
            run = StageAgentRun(
                stage=task.stage,
                robot_id=task.robot_id,
                run_id=run_id,
                status="FAILED",
                provider=task.provider,
                executor=task.executor,
                model=task.model,
                task_ref=task_ref,
                request_ref=request_ref,
                stdout_ref=stdout_ref,
                stderr_ref=stderr_ref,
                error=_redact_stream(str(exc)[:2_000]),
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )
        self.artifacts.write_json(
            f"{task.stage}/{task.robot_id}/runs/{run_id}/run.json",
            run.model_dump(mode="json"),
        )
        return run

    @staticmethod
    def _validate_authorization_request(
        request: dict[str, object], task: StageAgentTask
    ) -> None:
        if request.get("schema_version") != "rolo-authorization-request/v1":
            raise ValueError("unsupported authorization request schema")
        if request.get("status") != "PENDING":
            raise ValueError("authorization request is not pending")
        if request.get("stage") != task.stage or request.get("robot_id") != task.robot_id:
            raise ValueError("authorization request target does not match the task")
        if request.get("executor") != task.executor or request.get("provider") != task.provider:
            raise ValueError("authorization request Agent selection does not match the task")
        if request.get("plan_sha256") != task.plan_sha256:
            raise ValueError("authorization request plan digest does not match the task")
        expires_at = request.get("expires_at")
        if not isinstance(expires_at, str):
            raise ValueError("authorization request expiry is missing")
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise ValueError("authorization request expiry is invalid") from exc
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError("authorization request has expired")

    def _validate_output_refs(self, output_refs: Mapping[str, str]) -> None:
        for name, reference in output_refs.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("stage Agent output reference names must be non-empty strings")
            if not isinstance(reference, str):
                raise ValueError(f"stage Agent output reference is not a string: {name}")
            path = resolve_artifact_ref(self.artifacts.root, reference)
            if not path.is_file():
                raise ValueError(f"stage Agent output artifact is missing: {reference}")

    def _validate_input_hashes(self, task: StageAgentTask) -> None:
        """Reject a task whose immutable input snapshot changed after planning."""

        unknown = set(task.input_sha256) - set(task.input_refs)
        if unknown:
            raise ValueError("stage Agent input hash has no matching input reference")
        for name, expected in task.input_sha256.items():
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError(f"stage Agent input hash is invalid: {name}")
            path = resolve_artifact_ref(self.artifacts.root, task.input_refs[name])
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"stage Agent input artifact hash mismatch: {name}")


def json_load(path: Path) -> dict[str, object]:
    """Load a small JSON control artifact and reject non-object payloads."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"authorization request must be a JSON object: {path}")
    return payload
