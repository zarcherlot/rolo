from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.stage_agent_read_models import stage_agent_event_page, stage_agent_run_detail
from rolo.stages.agent_runner import StageAgentRun
from rolo.stages.artifact_paths import ArtifactLayout


def _write_run(root: Path) -> None:
    layout = ArtifactLayout(root)
    run = StageAgentRun(
        stage="diagnose",
        robot_id="robot-1",
        run_id="run-1",
        status="RUNNING",
        provider="codex",
        executor="codex",
        task_ref="artifact://diagnose/robot-1/runs/run-1/task.json",
        started_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    store = ArtifactStore(root)
    run_path = layout.stage_run("diagnose", "robot-1", "run-1") / "run.json"
    store.write_json(layout.relative(run_path), run.model_dump(mode="json"))
    store.append_jsonl(
        "diagnose/robot-1/runs/run-1/stdout.jsonl",
        {"observed_at": "2026-08-28T00:00:01+00:00", "line": "hello"},
    )
    store.append_jsonl(
        "diagnose/robot-1/runs/run-1/stderr.jsonl",
        {"observed_at": "2026-08-28T00:00:02+00:00", "line": "warning"},
    )


def test_stage_agent_read_models_bind_identity_and_page_events(tmp_path: Path) -> None:
    _write_run(tmp_path)
    detail = stage_agent_run_detail(tmp_path, "diagnose", "robot-1", "run-1")
    page = stage_agent_event_page(tmp_path, "diagnose", "robot-1", "run-1", limit=1)

    assert detail.run.status == "RUNNING"
    assert detail.event_count == 2
    assert detail.available_streams == ["stderr", "stdout"]
    assert page.total == 2
    assert page.next_offset == 1
    assert page.items[0].line == "hello"
