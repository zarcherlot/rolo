from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rolo.core.config import get_settings
from rolo.episode_capture import (
    build_target_inspection_episode,
    capture_target_inspection_episode,
)
from rolo.episode_projection import load_committed_episode_record
from rolo.product_cli import app
from rolo.target_ref import LocalTargetRef
from rolo.targets.models import (
    CompanionStatus,
    TargetConnectionAssessment,
    TargetConnectionState,
)


def _assessment(tmp_path: Path, state: TargetConnectionState) -> TargetConnectionAssessment:
    return TargetConnectionAssessment(
        target=LocalTargetRef(workspace=tmp_path),
        state=state,
        reachable=state == TargetConnectionState.READY,
        host_key_pinned=None,
        platform="linux",
        architecture="x86_64",
        workspace_accessible=state == TargetConnectionState.READY,
        companion=(
            CompanionStatus.AVAILABLE
            if state == TargetConnectionState.READY
            else CompanionStatus.UNKNOWN
        ),
        blockers=[] if state == TargetConnectionState.READY else ["target is not ready"],
    )


def test_target_inspection_episode_is_unverified_metadata(tmp_path: Path) -> None:
    captured_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    record = build_target_inspection_episode(
        _assessment(tmp_path, TargetConnectionState.READY),
        robot_id="robot-01",
        episode_id="ep-inspect-01",
        captured_at=captured_at,
    )

    assert record.immutable is True
    assert record.verification == "UNVERIFIED"
    assert record.coverage == "METADATA_ONLY"
    assert record.outcome == "SUCCEEDED"
    assert record.events[0].authority == "OBSERVED"
    assert record.events[0].raw_payload == {}


def test_target_inspection_episode_persists_idempotently(tmp_path: Path) -> None:
    assessment = _assessment(tmp_path, TargetConnectionState.UNREACHABLE)
    captured_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    first, reference = capture_target_inspection_episode(
        tmp_path / "artifacts",
        assessment,
        robot_id="robot-01",
        episode_id="ep-inspect-02",
        captured_at=captured_at,
    )
    second, same_reference = capture_target_inspection_episode(
        tmp_path / "artifacts",
        assessment,
        robot_id="robot-01",
        episode_id="ep-inspect-02",
        captured_at=captured_at,
    )

    assert reference == same_reference == "artifact://episodes/robot-01/published/ep-inspect-02.json"
    assert first.content_sha256 == second.content_sha256
    loaded = load_committed_episode_record(
        tmp_path / "artifacts", "robot-01", "ep-inspect-02", 1
    )
    assert loaded.state == "PARTIAL"
    assert loaded.outcome == "UNKNOWN"


def test_target_episode_capture_cli_is_read_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    from typer.testing import CliRunner

    result = CliRunner().invoke(
        app,
        [
            "target",
            "episode-capture",
            str(tmp_path),
            "--robot",
            "robot-cli",
            "--episode-id",
            "ep-cli-01",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert '"status": "EPISODE_CAPTURED"' in result.stdout
    assert (tmp_path / "artifacts" / "episodes" / "robot-cli" / "published").is_dir()
    get_settings.cache_clear()
