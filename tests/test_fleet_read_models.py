from datetime import datetime, timezone

from rolo.core.models import RobotCapability
from rolo.fleet_read_models import (
    build_fleet_blocker_collection,
    build_fleet_collection,
)
from rolo.read_models import OverviewState
from rolo.stages.contracts import (
    AgentRequirement,
    PipelineAssessment,
    StageAssessment,
    StageName,
    StageStatus,
)

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _robot(robot_id: str) -> RobotCapability:
    return RobotCapability(
        schema_version="robot-capability/v1",
        robot_id=robot_id,
        adapter="test-adapter",
        platform={"architecture": "arm64", "ros_distro": "humble"},
        geometry={},
        sensors={},
        features={},
    )


def _pipeline(robot_id: str, status: StageStatus) -> PipelineAssessment:
    reference = rf"C:\private\{robot_id}\adapt.json"
    return PipelineAssessment(
        robot_id=robot_id,
        stages=[
            StageAssessment(
                stage=StageName.ADAPT,
                robot_id=robot_id,
                status=status,
                summary="Adapt assessment",
                prerequisites=[reference],
                artifacts={"adapt": reference},
                blockers=[f"Inspect {reference}"] if status is StageStatus.BLOCKED else [],
                agent_requirement=AgentRequirement.ADAPTER_AGENT,
                observed_at=NOW,
            )
        ],
        observed_at=NOW,
    )


def test_fleet_collection_aggregates_validated_overviews() -> None:
    robots = [_robot("ready"), _robot("blocked")]
    pipelines = {
        "ready": _pipeline("ready", StageStatus.READY),
        "blocked": _pipeline("blocked", StageStatus.BLOCKED),
    }

    fleet = build_fleet_collection(robots, pipelines)
    attention = build_fleet_collection(
        robots,
        pipelines,
        state=OverviewState.ATTENTION,
    )

    assert fleet.schema_version == "rolo-fleet-collection/v1"
    assert fleet.total == 2
    assert fleet.ready == 1
    assert fleet.attention == 1
    assert fleet.blocker_count == 1
    assert {item.robot_id for item in fleet.items} == {"ready", "blocked"}
    assert attention.total == 1
    assert attention.items[0].robot_id == "blocked"
    assert attention.items[0].active_stage is StageName.ADAPT
    assert attention.items[0].integrity_status == "validated"


def test_blocker_inbox_is_bounded_sanitized_and_evidence_bound() -> None:
    robots = [_robot("blocked")]
    pipelines = {"blocked": _pipeline("blocked", StageStatus.BLOCKED)}

    blockers = build_fleet_blocker_collection(
        robots,
        pipelines,
        limit=1,
        offset=0,
        robot_id="blocked",
        stage=StageName.ADAPT,
    )

    assert blockers.schema_version == "rolo-fleet-blocker-collection/v1"
    assert blockers.total == 1
    assert len(blockers.items) == 1
    blocker = blockers.items[0]
    assert blocker.robot_id == "blocked"
    assert blocker.owner == "adapter_agent"
    assert blocker.evidence_ids[0].startswith("ev_")
    assert "C:\\private" not in blocker.model_dump_json()
    assert "artifact:adapt.json" in blocker.message
