from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request

from rolo import __version__
from rolo.adapt_observability_read_models import (
    AdaptBaselineStatus,
    FleetSliceStability,
    SliceReviewPacket,
    SliceRunDetail,
    SliceStabilityComparison,
    build_adapt_baseline_status,
    build_fleet_slice_stability,
    build_slice_review_packet,
    build_slice_run_detail,
    build_slice_stability_comparison,
)
from rolo.adapt_read_models import (
    ADAPT_API_FEATURES,
    OperationGovernanceCollection,
    build_operation_governance_collection,
    build_robot_slice_stability,
    build_robot_target_operation_slice,
)
from rolo.capability_read_models import (
    CapabilityAvailability,
    CapabilityCollection,
    CapabilityDetail,
    CapabilityLayer,
    build_capability_collection,
    get_capability_detail,
)
from rolo.core.models import HealthResponse, HealthState, RobotCapability, RobotUseRequest
from rolo.discovery_history_read_models import (
    DiscoverySnapshotCollection,
    build_discovery_snapshot_collection,
)
from rolo.fleet_read_models import (
    FleetBlockerCollection,
    FleetCollection,
    build_fleet_blocker_collection,
    build_fleet_collection,
)
from rolo.lifecycle_read_models import (
    LifecycleRunCollection,
    LifecycleRunDetail,
    LifecycleRunStatus,
    build_lifecycle_run_collection,
    get_lifecycle_run_detail,
)
from rolo.read_models import OverviewState, RobotOverview, build_robot_overview
from rolo.runtime import RobotUseRuntime, create_robot_use_runtime
from rolo.stages.adapt.operation_governance import (
    ExecutionClass,
    MigrationStatus,
)
from rolo.stages.adapt.operation_governance import (
    SemanticLayer as GovernanceSemanticLayer,
)
from rolo.stages.adapt.slice_observability import SliceStabilityReport
from rolo.stages.adapt.workset import TargetOperationSlice
from rolo.stages.contracts import PipelineAssessment, StageName
from rolo.stages.pipeline import assess_pipeline
from rolo.topology_history_read_models import (
    TopologyDiff,
    TopologySnapshotCollection,
    build_topology_diff,
    build_topology_snapshot_collection,
)
from rolo.topology_path_read_models import (
    TopologyPathExplanation,
    explain_topology_path,
)
from rolo.wiki_read_models import RobotWikiSnapshot, build_robot_wiki
from rolo.workbench_read_models import (
    EvidenceAuthority,
    EvidenceCollection,
    EvidenceRecord,
    RobotTopology,
    build_evidence_collection,
    build_robot_topology,
    find_evidence,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = create_robot_use_runtime()
    yield


app = FastAPI(
    title="rolo Control Plane",
    version=__version__,
    lifespan=lifespan,
)


def get_runtime(request: Request) -> RobotUseRuntime:
    return request.app.state.runtime


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    runtime = get_runtime(request)
    return HealthResponse(
        status=HealthState.HEALTHY,
        version=__version__,
        robots=len(runtime.registry),
        robot_use_backend=runtime.robot_use_backend.name,
        openai_key_configured=bool(runtime.settings.openai_api_key),
        api_features=list(ADAPT_API_FEATURES),
    )


@app.get("/v1/robots", response_model=list[RobotCapability])
async def list_robots(request: Request) -> list[RobotCapability]:
    return get_runtime(request).registry.list()


@app.get("/v1/operations/governance", response_model=OperationGovernanceCollection)
async def list_operation_governance(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    query: Annotated[str | None, Query(max_length=128)] = None,
    semantic_layer: Annotated[GovernanceSemanticLayer | None, Query()] = None,
    execution_class: Annotated[ExecutionClass | None, Query()] = None,
    migration_status: Annotated[MigrationStatus | None, Query()] = None,
) -> OperationGovernanceCollection:
    return build_operation_governance_collection(
        limit=limit,
        offset=offset,
        query=query,
        semantic_layer=semantic_layer,
        execution_class=execution_class,
        migration_status=migration_status,
    )


@app.get("/v1/adapt/baseline", response_model=AdaptBaselineStatus)
def get_adapt_baseline_status() -> AdaptBaselineStatus:
    try:
        return build_adapt_baseline_status()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt protected baseline failed integrity validation",
        ) from exc


@app.get("/v1/adapt/slice-fleet", response_model=FleetSliceStability)
def get_fleet_slice_stability(
    request: Request,
    max_runs_per_robot: Annotated[int, Query(ge=1, le=100)] = 20,
    min_successful_canary_runs: Annotated[int, Query(ge=1, le=100)] = 10,
) -> FleetSliceStability:
    runtime = get_runtime(request)
    try:
        return build_fleet_slice_stability(
            runtime.settings.rolo_artifact_dir,
            [robot.robot_id for robot in runtime.registry.list()],
            max_runs_per_robot=max_runs_per_robot,
            min_successful_canary_runs=min_successful_canary_runs,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Fleet Adapt Slice evidence failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/adapt/operation-slice",
    response_model=TargetOperationSlice,
)
def get_robot_target_operation_slice(
    robot_id: str,
    request: Request,
) -> TargetOperationSlice:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_robot_target_operation_slice(
            runtime.artifacts,
            runtime.settings.rolo_output_dir,
            robot_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Adapt target operation slice is unavailable",
        ) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt target operation slice failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/adapt/slice-stability",
    response_model=SliceStabilityReport,
)
def get_robot_slice_stability(
    robot_id: str,
    request: Request,
    max_runs: Annotated[int, Query(ge=1, le=100)] = 50,
    min_successful_canary_runs: Annotated[int, Query(ge=1, le=100)] = 10,
) -> SliceStabilityReport:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_robot_slice_stability(
            runtime.settings.rolo_artifact_dir,
            robot_id,
            max_runs=max_runs,
            min_successful_canary_runs=min_successful_canary_runs,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt Slice stability evidence failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/adapt/slice-stability/comparison",
    response_model=SliceStabilityComparison,
)
def get_robot_slice_stability_comparison(
    robot_id: str,
    request: Request,
    recent_observations: Annotated[int, Query(ge=1, le=50)] = 10,
    previous_observations: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SliceStabilityComparison:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_slice_stability_comparison(
            runtime.settings.rolo_artifact_dir,
            robot_id,
            recent_observations=recent_observations,
            previous_observations=previous_observations,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt Slice stability comparison failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/adapt/slice-review",
    response_model=SliceReviewPacket,
)
def get_robot_slice_review_packet(
    robot_id: str,
    request: Request,
    max_runs: Annotated[int, Query(ge=1, le=100)] = 50,
    min_successful_canary_runs: Annotated[int, Query(ge=1, le=100)] = 10,
    max_evidence_runs: Annotated[int, Query(ge=1, le=20)] = 20,
) -> SliceReviewPacket:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_slice_review_packet(
            runtime.settings.rolo_artifact_dir,
            robot_id,
            max_runs=max_runs,
            min_successful_canary_runs=min_successful_canary_runs,
            max_evidence_runs=max_evidence_runs,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt Slice review evidence failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/adapt/slice-runs/{run_id}",
    response_model=SliceRunDetail,
)
def get_robot_slice_run_detail(
    robot_id: str,
    run_id: str,
    request: Request,
) -> SliceRunDetail:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_slice_run_detail(
            runtime.settings.rolo_artifact_dir,
            robot_id,
            run_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Adapt Slice run decision is unavailable",
        ) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Adapt Slice run decision failed integrity validation",
        ) from exc


def _fleet_pipelines(runtime: RobotUseRuntime) -> dict[str, PipelineAssessment]:
    return {
        robot.robot_id: assess_pipeline(
            runtime.settings.rolo_artifact_dir,
            robot.robot_id,
        )
        for robot in runtime.registry.list()
    }


@app.get("/v1/fleet", response_model=FleetCollection)
async def get_fleet(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    state: Annotated[OverviewState | None, Query()] = None,
    query: Annotated[str | None, Query(max_length=128)] = None,
) -> FleetCollection:
    runtime = get_runtime(request)
    return build_fleet_collection(
        runtime.registry.list(),
        _fleet_pipelines(runtime),
        limit=limit,
        offset=offset,
        state=state,
        query=query,
    )


@app.get("/v1/blockers", response_model=FleetBlockerCollection)
async def list_fleet_blockers(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    robot_id: Annotated[str | None, Query(max_length=128)] = None,
    stage: Annotated[StageName | None, Query()] = None,
) -> FleetBlockerCollection:
    runtime = get_runtime(request)
    return build_fleet_blocker_collection(
        runtime.registry.list(),
        _fleet_pipelines(runtime),
        limit=limit,
        offset=offset,
        robot_id=robot_id,
        stage=stage,
    )


@app.get("/v1/robots/{robot_id}", response_model=RobotCapability)
async def get_robot(robot_id: str, request: Request) -> RobotCapability:
    try:
        return get_runtime(request).registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/robots/{robot_id}/pipeline", response_model=PipelineAssessment)
async def get_robot_pipeline(robot_id: str, request: Request) -> PipelineAssessment:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return assess_pipeline(runtime.settings.rolo_artifact_dir, robot_id)


@app.get("/v1/robots/{robot_id}/overview", response_model=RobotOverview)
async def get_robot_overview(robot_id: str, request: Request) -> RobotOverview:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pipeline = assess_pipeline(runtime.settings.rolo_artifact_dir, robot_id)
    return build_robot_overview(robot, pipeline)


@app.get("/v1/robots/{robot_id}/wiki", response_model=RobotWikiSnapshot)
async def get_robot_wiki(robot_id: str, request: Request) -> RobotWikiSnapshot:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_robot_wiki(runtime.settings.rolo_artifact_dir, robot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="robot Wiki is unavailable") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="robot Wiki evidence failed integrity validation",
        ) from exc


@app.get(
    "/v1/robots/{robot_id}/discoveries",
    response_model=DiscoverySnapshotCollection,
)
async def list_robot_discoveries(
    robot_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DiscoverySnapshotCollection:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_discovery_snapshot_collection(
        runtime.settings.rolo_artifact_dir,
        robot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/v1/robots/{robot_id}/topology", response_model=RobotTopology)
async def get_robot_topology(robot_id: str, request: Request) -> RobotTopology:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    topology, _ = build_robot_topology(
        robot,
        runtime.settings.rolo_output_dir,
        artifact_root=runtime.settings.rolo_artifact_dir,
    )
    return topology


@app.get(
    "/v1/robots/{robot_id}/topology/path",
    response_model=TopologyPathExplanation,
)
async def get_robot_topology_path(
    robot_id: str,
    request: Request,
    from_node: Annotated[str, Query(alias="from", min_length=1, max_length=128)],
    to_node: Annotated[str, Query(alias="to", min_length=1, max_length=128)],
    max_hops: Annotated[int, Query(ge=1, le=12)] = 8,
) -> TopologyPathExplanation:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    topology, _ = build_robot_topology(robot, runtime.settings.rolo_output_dir)
    try:
        return explain_topology_path(
            topology,
            from_node,
            to_node,
            max_hops=max_hops,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown topology node") from exc


@app.get(
    "/v1/robots/{robot_id}/topology/snapshots",
    response_model=TopologySnapshotCollection,
)
async def list_robot_topology_snapshots(
    robot_id: str,
    request: Request,
) -> TopologySnapshotCollection:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_topology_snapshot_collection(
        robot,
        runtime.settings.rolo_artifact_dir,
        runtime.settings.rolo_output_dir,
    )


@app.get("/v1/robots/{robot_id}/topology/diff", response_model=TopologyDiff)
async def get_robot_topology_diff(
    robot_id: str,
    request: Request,
    from_snapshot: Annotated[str, Query(alias="from", min_length=1, max_length=128)],
    to_snapshot: Annotated[str, Query(alias="to", min_length=1, max_length=128)],
) -> TopologyDiff:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    diff = build_topology_diff(
        robot,
        runtime.settings.rolo_artifact_dir,
        runtime.settings.rolo_output_dir,
        from_snapshot,
        to_snapshot,
    )
    if diff is None:
        raise HTTPException(status_code=404, detail="topology snapshot was not found")
    return diff


@app.get("/v1/robots/{robot_id}/capabilities", response_model=CapabilityCollection)
async def list_robot_capabilities(
    robot_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    query: Annotated[str | None, Query(max_length=128)] = None,
    layer: Annotated[CapabilityLayer | None, Query()] = None,
    lifecycle: Annotated[
        Literal["DRAFT", "GATEABLE", "RELEASED", "DEPRECATED"] | None,
        Query(),
    ] = None,
    risk: Annotated[Literal["R0", "R1", "R2", "R3"] | None, Query()] = None,
    availability: Annotated[CapabilityAvailability | None, Query()] = None,
) -> CapabilityCollection:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_capability_collection(
        robot,
        runtime.settings.rolo_artifact_dir,
        runtime.settings.rolo_output_dir,
        limit=limit,
        offset=offset,
        query=query,
        layer=layer,
        lifecycle=lifecycle,
        risk=risk,
        availability=availability,
    )


@app.get("/v1/robots/{robot_id}/runs", response_model=LifecycleRunCollection)
async def list_robot_runs(
    robot_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    stage: Annotated[StageName | None, Query()] = None,
    status: Annotated[LifecycleRunStatus | None, Query()] = None,
) -> LifecycleRunCollection:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pipeline = assess_pipeline(runtime.settings.rolo_artifact_dir, robot_id)
    return build_lifecycle_run_collection(
        runtime.settings.rolo_artifact_dir,
        runtime.settings.rolo_output_dir,
        robot_id,
        stage=stage,
        status=status,
        limit=limit,
        offset=offset,
        pipeline=pipeline,
    )


@app.get("/v1/robots/{robot_id}/runs/{run_id}", response_model=LifecycleRunDetail)
async def get_robot_run(
    robot_id: str,
    run_id: str,
    request: Request,
) -> LifecycleRunDetail:
    runtime = get_runtime(request)
    try:
        runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        detail = get_lifecycle_run_detail(
            runtime.settings.rolo_artifact_dir,
            runtime.settings.rolo_output_dir,
            robot_id,
            run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown lifecycle run")
    return detail


@app.get(
    "/v1/robots/{robot_id}/capabilities/{operation}",
    response_model=CapabilityDetail,
)
async def get_robot_capability(
    robot_id: str,
    operation: str,
    request: Request,
) -> CapabilityDetail:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    detail = get_capability_detail(
        robot,
        runtime.settings.rolo_artifact_dir,
        runtime.settings.rolo_output_dir,
        operation,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown canonical operation")
    return detail


@app.get("/v1/robots/{robot_id}/evidence", response_model=EvidenceCollection)
async def list_robot_evidence(
    robot_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    authority: Annotated[EvidenceAuthority | None, Query()] = None,
) -> EvidenceCollection:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_evidence_collection(
        robot,
        runtime.settings.rolo_output_dir,
        artifact_root=runtime.settings.rolo_artifact_dir,
        limit=limit,
        offset=offset,
        authority=authority,
        pipeline=assess_pipeline(runtime.settings.rolo_artifact_dir, robot_id),
    )


@app.get("/v1/evidence/{evidence_id}", response_model=EvidenceRecord)
async def get_evidence(evidence_id: str, request: Request) -> EvidenceRecord:
    runtime = get_runtime(request)
    record = find_evidence(
        runtime.registry.list(),
        runtime.settings.rolo_output_dir,
        evidence_id,
        artifact_root=runtime.settings.rolo_artifact_dir,
        pipelines={
            robot.robot_id: assess_pipeline(
                runtime.settings.rolo_artifact_dir,
                robot.robot_id,
            )
            for robot in runtime.registry.list()
        },
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown evidence ID")
    return record


@app.get("/v1/robot-use/status")
async def robot_use_status(request: Request) -> dict[str, object]:
    return get_runtime(request).robot_use.status()


@app.post("/v1/robot-use/poll")
async def robot_use_poll(payload: RobotUseRequest, request: Request):
    try:
        return await get_runtime(request).robot_use.poll(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
