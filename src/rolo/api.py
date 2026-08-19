from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from rolo import __version__
from rolo.core.models import HealthResponse, HealthState, RobotCapability, RobotUseRequest
from rolo.runtime import RobotUseRuntime, create_robot_use_runtime
from rolo.stages.contracts import PipelineAssessment
from rolo.stages.pipeline import assess_pipeline


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
