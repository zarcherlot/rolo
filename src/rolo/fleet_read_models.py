from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.models import RobotCapability, utc_now
from rolo.read_models import OverviewState, RobotOverview, build_robot_overview
from rolo.stages.contracts import PipelineAssessment, StageName, StageStatus


class FleetRobotSummary(BaseModel):
    schema_version: Literal["rolo-fleet-robot-summary/v1"] = (
        "rolo-fleet-robot-summary/v1"
    )
    robot_id: str
    adapter: str
    architecture: str
    ros_distro: str
    state: OverviewState
    active_stage: StageName | None = None
    active_status: StageStatus | None = None
    blocker_count: int = Field(ge=0)
    next_action: str
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["computed_robot_overview"] = "computed_robot_overview"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"


class FleetBlockerSummary(BaseModel):
    schema_version: Literal["rolo-fleet-blocker-summary/v1"] = (
        "rolo-fleet-blocker-summary/v1"
    )
    blocker_id: str
    robot_id: str
    stage: StageName
    message: str
    recommended_action: str
    owner: str
    evidence_ids: list[str] = Field(default_factory=list)
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["pipeline_assessment"] = "pipeline_assessment"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"


class FleetCollection(BaseModel):
    schema_version: Literal["rolo-fleet-collection/v1"] = "rolo-fleet-collection/v1"
    items: list[FleetRobotSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    ready: int = Field(ge=0)
    attention: int = Field(ge=0)
    degraded: int = Field(ge=0)
    not_ready: int = Field(ge=0)
    blocker_count: int = Field(ge=0)
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["computed_fleet_overviews"] = "computed_fleet_overviews"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"


class FleetBlockerCollection(BaseModel):
    schema_version: Literal["rolo-fleet-blocker-collection/v1"] = (
        "rolo-fleet-blocker-collection/v1"
    )
    items: list[FleetBlockerSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Literal["fresh"] = "fresh"
    source_kind: Literal["computed_pipeline_blockers"] = (
        "computed_pipeline_blockers"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    integrity_status: Literal["validated"] = "validated"


def _active_stage(overview: RobotOverview):
    if not overview.pipeline.stages:
        return None
    return next(
        (
            stage
            for stage in overview.pipeline.stages
            if stage.status is not StageStatus.COMPLETE
        ),
        overview.pipeline.stages[-1],
    )


def _robot_summary(
    robot: RobotCapability,
    overview: RobotOverview,
) -> FleetRobotSummary:
    active = _active_stage(overview)
    return FleetRobotSummary(
        robot_id=robot.robot_id,
        adapter=robot.adapter,
        architecture=str(robot.platform.get("architecture", "unknown"))[:80],
        ros_distro=str(robot.platform.get("ros_distro", "unknown"))[:80],
        state=overview.state,
        active_stage=active.stage if active else None,
        active_status=active.status if active else None,
        blocker_count=len(overview.blockers),
        next_action=overview.next_action,
        observed_at=overview.observed_at,
    )


def _fleet_blockers(overview: RobotOverview) -> list[FleetBlockerSummary]:
    return [
        FleetBlockerSummary(
            blocker_id=blocker.blocker_id,
            robot_id=overview.robot_id,
            stage=StageName(blocker.stage),
            message=blocker.message,
            recommended_action=blocker.recommended_action,
            owner=blocker.owner,
            evidence_ids=blocker.evidence_ids,
            observed_at=blocker.observed_at,
        )
        for blocker in overview.blockers
    ]


def _overviews(
    robots: list[RobotCapability],
    pipelines: dict[str, PipelineAssessment],
) -> list[tuple[RobotCapability, RobotOverview]]:
    return [
        (robot, build_robot_overview(robot, pipelines[robot.robot_id]))
        for robot in robots
        if robot.robot_id in pipelines
    ]


def build_fleet_collection(
    robots: list[RobotCapability],
    pipelines: dict[str, PipelineAssessment],
    *,
    limit: int = 50,
    offset: int = 0,
    state: OverviewState | None = None,
    query: str | None = None,
) -> FleetCollection:
    overviews = _overviews(robots, pipelines)
    all_items = [_robot_summary(robot, overview) for robot, overview in overviews]
    normalized_query = (query or "").strip().casefold()
    items = [
        item
        for item in all_items
        if (state is None or item.state is state)
        and (
            not normalized_query
            or normalized_query
            in " ".join(
                [
                    item.robot_id,
                    item.adapter,
                    item.architecture,
                    item.ros_distro,
                    item.next_action,
                ]
            ).casefold()
        )
    ]
    items.sort(key=lambda item: (item.state.value, item.robot_id))
    total = len(items)
    next_offset = offset + limit if offset + limit < total else None
    observed_at = max(
        (overview.observed_at for _, overview in overviews),
        default=utc_now(),
    )
    counts = {fleet_state: 0 for fleet_state in OverviewState}
    for item in all_items:
        counts[item.state] += 1
    return FleetCollection(
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        ready=counts[OverviewState.READY],
        attention=counts[OverviewState.ATTENTION],
        degraded=counts[OverviewState.DEGRADED],
        not_ready=counts[OverviewState.NOT_READY],
        blocker_count=sum(item.blocker_count for item in all_items),
        observed_at=observed_at,
    )


def build_fleet_blocker_collection(
    robots: list[RobotCapability],
    pipelines: dict[str, PipelineAssessment],
    *,
    limit: int = 50,
    offset: int = 0,
    robot_id: str | None = None,
    stage: StageName | None = None,
) -> FleetBlockerCollection:
    overviews = _overviews(robots, pipelines)
    items = [
        blocker
        for _, overview in overviews
        for blocker in _fleet_blockers(overview)
        if (robot_id is None or blocker.robot_id == robot_id)
        and (stage is None or blocker.stage is stage)
    ]
    items.sort(key=lambda item: (item.observed_at, item.robot_id, item.blocker_id), reverse=True)
    total = len(items)
    next_offset = offset + limit if offset + limit < total else None
    observed_at = max(
        (overview.observed_at for _, overview in overviews),
        default=utc_now(),
    )
    return FleetBlockerCollection(
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        observed_at=observed_at,
    )
