from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from robot_loop import __version__
from robot_loop.models import HealthResponse, HealthState, RobotCapability, RobotUseRequest
from robot_loop.runtime import Runtime, create_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = create_runtime()
    yield


app = FastAPI(
    title="Robot Loop Control Plane",
    version=__version__,
    lifespan=lifespan,
)


def get_runtime(request: Request) -> Runtime:
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
