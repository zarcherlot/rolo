from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from rolo.adapters.mock_robot_use import MockRobotUseBackend
from rolo.core.artifacts import ArtifactStore
from rolo.core.models import ImageFrame, RobotUseRequest, RobotUseVerdict
from rolo.core.registry import RobotRegistry
from rolo.robot_use import RobotUseService


def make_request(*, progress_delta: float, commanded_speed_mps: float) -> RobotUseRequest:
    now = datetime.now(UTC)
    return RobotUseRequest(
        request_id="req-test",
        robot_id="demo_diff",
        execution_id="exec-test",
        window_start=now - timedelta(seconds=10),
        window_end=now,
        frames=[
            ImageFrame(
                timestamp=now,
                image_url="data:image/png;base64,iVBORw0KGgo=",
            )
        ],
        task_contract={"intent": "navigate"},
        telemetry_summary={
            "progress_delta": progress_delta,
            "commanded_speed_mps": commanded_speed_mps,
        },
    )


@pytest.mark.asyncio
async def test_mock_robot_use_reports_normal(tmp_path: Path) -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    service = RobotUseService(
        registry=registry,
        backend=MockRobotUseBackend(),
        artifacts=ArtifactStore(tmp_path),
    )

    result = await service.poll(make_request(progress_delta=0.2, commanded_speed_mps=0.2))

    assert result.verdict == RobotUseVerdict.NORMAL
    assert (tmp_path / "robot_use/supervision_results.jsonl").exists()


@pytest.mark.asyncio
async def test_mock_robot_use_reports_suspected_stall(tmp_path: Path) -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    service = RobotUseService(
        registry=registry,
        backend=MockRobotUseBackend(),
        artifacts=ArtifactStore(tmp_path),
    )

    result = await service.poll(make_request(progress_delta=0.0, commanded_speed_mps=0.2))

    assert result.verdict == RobotUseVerdict.SUSPECTED_FAILURE
    assert result.failure_type == "NO_PHYSICAL_PROGRESS"
