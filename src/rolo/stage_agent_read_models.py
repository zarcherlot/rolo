"""Read-only HTTP/MCP projections for downstream Stage Agent runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.stages.agent_runner import StageAgentRun
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref

Stage = Literal["diagnose", "verify"]


class StageAgentEvent(BaseModel):
    schema_version: Literal["rolo-stage-agent-event/v1"] = "rolo-stage-agent-event/v1"
    stage: Stage
    robot_id: str
    run_id: str
    sequence: int = Field(ge=0)
    stream: Literal["stdout", "stderr"]
    observed_at: datetime
    line: str = Field(max_length=8_000)


class StageAgentEventPage(BaseModel):
    schema_version: Literal["rolo-stage-agent-event-page/v1"] = (
        "rolo-stage-agent-event-page/v1"
    )
    stage: Stage
    robot_id: str
    run_id: str
    items: list[StageAgentEvent]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class StageAgentRunDetail(BaseModel):
    schema_version: Literal["rolo-stage-agent-run-detail/v1"] = (
        "rolo-stage-agent-run-detail/v1"
    )
    run: StageAgentRun
    event_count: int = Field(ge=0)
    available_streams: list[Literal["stdout", "stderr"]] = Field(default_factory=list)


def stage_agent_run_evidence(
    root: Path, stage: Stage, robot_id: str, run_id: str
) -> dict[str, object]:
    """Project only evidence/report artifacts explicitly emitted by one run.

    The projection is read-only: it follows the persisted run's output refs and
    never scans arbitrary paths or executes a provider.  This keeps rolo-vis
    replay views bounded to artifacts already validated by ``StageAgentRunner``.
    """

    run = load_stage_agent_run(root, stage, robot_id, run_id)
    artifacts: dict[str, object] = {}
    for name, reference in run.output_refs.items():
        if "evidence" not in name.casefold() and "report" not in name.casefold():
            continue
        path = resolve_artifact_ref(root, reference)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"stage Agent evidence artifact must be a JSON object: {reference}")
        artifacts[name] = {"ref": reference, "payload": payload}
    return {
        "schema_version": "rolo-stage-agent-evidence/v1",
        "stage": stage,
        "robot_id": robot_id,
        "run_id": run_id,
        "artifacts": artifacts,
    }


def _run_path(root: Path, stage: Stage, robot_id: str, run_id: str) -> Path:
    return ArtifactLayout(root).stage_run(stage, robot_id, run_id) / "run.json"


def load_stage_agent_run(root: Path, stage: Stage, robot_id: str, run_id: str) -> StageAgentRun:
    path = _run_path(root, stage, robot_id, run_id)
    run = StageAgentRun.model_validate_json(path.read_text(encoding="utf-8"))
    if run.stage != stage or run.robot_id != robot_id or run.run_id != run_id:
        raise ValueError("stage Agent run identity does not match the requested resource")
    return run


def _load_events(root: Path, stage: Stage, robot_id: str, run_id: str) -> list[StageAgentEvent]:
    events: list[StageAgentEvent] = []
    run_root = ArtifactLayout(root).stage_run(stage, robot_id, run_id)
    sequence = 0
    for stream in ("stdout", "stderr"):
        path = run_root / f"{stream}.jsonl"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("stage Agent event must be a JSON object")
            observed_at = payload.get("observed_at")
            text = payload.get("line")
            if not isinstance(observed_at, str) or not isinstance(text, str):
                raise ValueError("stage Agent event is missing observed_at or line")
            parsed_at = datetime.fromisoformat(observed_at)
            if parsed_at.tzinfo is None:
                raise ValueError("stage Agent event timestamp must include timezone")
            events.append(
                StageAgentEvent(
                    stage=stage,
                    robot_id=robot_id,
                    run_id=run_id,
                    sequence=sequence,
                    stream=stream,
                    observed_at=parsed_at.astimezone(timezone.utc),
                    line=text,
                )
            )
            sequence += 1
    events.sort(key=lambda item: (item.observed_at, item.sequence))
    return [event.model_copy(update={"sequence": index}) for index, event in enumerate(events)]


def stage_agent_run_detail(
    root: Path, stage: Stage, robot_id: str, run_id: str
) -> StageAgentRunDetail:
    run = load_stage_agent_run(root, stage, robot_id, run_id)
    events = _load_events(root, stage, robot_id, run_id)
    return StageAgentRunDetail(
        run=run,
        event_count=len(events),
        available_streams=sorted({event.stream for event in events}),
    )


def stage_agent_event_page(
    root: Path,
    stage: Stage,
    robot_id: str,
    run_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> StageAgentEventPage:
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("stage Agent event limit must be 1..500 and offset non-negative")
    load_stage_agent_run(root, stage, robot_id, run_id)
    events = _load_events(root, stage, robot_id, run_id)
    items = events[offset : offset + limit]
    return StageAgentEventPage(
        stage=stage,
        robot_id=robot_id,
        run_id=run_id,
        items=items,
        total=len(events),
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < len(events) else None,
    )
