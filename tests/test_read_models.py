from datetime import datetime, timezone

import pytest

from rolo.core.models import RobotCapability
from rolo.read_models import OverviewState, build_robot_overview
from rolo.stages.contracts import (
    AgentRequirement,
    PipelineAssessment,
    StageAssessment,
    StageName,
    StageStatus,
)

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
ROBOT = RobotCapability(
    schema_version="robot-capability/v1",
    robot_id="test_robot",
    adapter="test-adapter",
    platform={},
    geometry={},
    sensors={},
    features={},
)


def stage(status: StageStatus, blockers: list[str] | None = None) -> StageAssessment:
    return StageAssessment(
        stage=StageName.ADAPT,
        robot_id=ROBOT.robot_id,
        status=status,
        summary=f"Adapt is {status.value.lower()}",
        blockers=blockers or [],
        agent_requirement=AgentRequirement.ADAPTER_AGENT,
        observed_at=NOW,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (StageStatus.READY, OverviewState.READY),
        (StageStatus.COMPLETE, OverviewState.READY),
        (StageStatus.DEGRADED, OverviewState.DEGRADED),
        (StageStatus.NOT_STARTED, OverviewState.NOT_READY),
    ],
)
def test_overview_state_follows_pipeline_status(
    status: StageStatus,
    expected: OverviewState,
) -> None:
    pipeline = PipelineAssessment(robot_id=ROBOT.robot_id, stages=[stage(status)], observed_at=NOW)

    overview = build_robot_overview(ROBOT, pipeline)

    assert overview.state is expected
    assert overview.schema_version == "rolo-robot-overview/v2"
    assert overview.pipeline.schema_version == "robot-three-stage-pipeline/v1"


def test_blocked_overview_has_stable_evidence_bound_blocker() -> None:
    pipeline = PipelineAssessment(
        robot_id=ROBOT.robot_id,
        stages=[stage(StageStatus.BLOCKED, ["Run adapt discovery"])],
        observed_at=NOW,
    )

    first = build_robot_overview(ROBOT, pipeline)
    second = build_robot_overview(ROBOT, pipeline)

    assert first.state is OverviewState.ATTENTION
    assert first.blockers[0].blocker_id == second.blockers[0].blocker_id
    assert first.blockers[0].recommended_action == "Run adapt discovery"
    assert first.blockers[0].source_kind == "pipeline_assessment"


def test_overview_exposes_opaque_evidence_ids_instead_of_artifact_paths() -> None:
    raw_path = r"C:\private\adapt\inputs.json"
    escaped_path = raw_path.replace("\\", "\\\\")
    blocked = stage(StageStatus.BLOCKED, [f"Fix missing input at {escaped_path}"])
    blocked.prerequisites = [raw_path]
    blocked.artifacts = {"inputs": raw_path}
    pipeline = PipelineAssessment(
        robot_id=ROBOT.robot_id,
        stages=[blocked],
        observed_at=NOW,
    )

    overview = build_robot_overview(ROBOT, pipeline)

    assert overview.blockers[0].evidence_ids[0].startswith("ev_")
    assert overview.blockers[0].message == "Fix missing input at artifact:inputs.json"
    assert overview.pipeline.stages[0].prerequisites == ["artifact:inputs.json"]
    assert overview.pipeline.stages[0].artifacts == {"inputs": "artifact:inputs.json"}
    assert r"C:\private" not in overview.model_dump_json()


def test_empty_pipeline_is_not_ready_instead_of_crashing() -> None:
    pipeline = PipelineAssessment(robot_id=ROBOT.robot_id, stages=[], observed_at=NOW)

    overview = build_robot_overview(ROBOT, pipeline)

    assert overview.state is OverviewState.NOT_READY
    assert overview.summary == "No pipeline assessments are available."
    assert overview.next_action == "Run adapt discovery"
