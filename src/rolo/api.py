from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request

from rolo import __version__
from rolo.core.models import HealthResponse, HealthState, RobotCapability, RobotUseRequest
from rolo.read_models import RobotOverview, build_robot_overview
from rolo.runtime import RobotUseRuntime, create_robot_use_runtime
from rolo.stages.contracts import PipelineAssessment
from rolo.stages.pipeline import assess_pipeline
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
    )


@app.get("/v1/robots", response_model=list[RobotCapability])
async def list_robots(request: Request) -> list[RobotCapability]:
    return get_runtime(request).registry.list()


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


@app.get("/v1/robots/{robot_id}/topology", response_model=RobotTopology)
async def get_robot_topology(robot_id: str, request: Request) -> RobotTopology:
    runtime = get_runtime(request)
    try:
        robot = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    topology, _ = build_robot_topology(robot, runtime.settings.rolo_output_dir)
    return topology


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
