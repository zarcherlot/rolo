from __future__ import annotations

from fastapi import FastAPI, HTTPException

from robot_loop import __version__
from robot_loop.discovery import load_latest_report
from robot_loop.models import HealthState, RobotCapability, utc_now
from robot_loop.runtime import create_runtime


def create_agentd_app(robot_id: str) -> FastAPI:
    runtime = create_runtime()
    try:
        capability = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    agentd = FastAPI(title=f"robot-agentd:{robot_id}", version=__version__)

    @agentd.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": HealthState.HEALTHY,
            "service": "robot-agentd",
            "robot_id": robot_id,
            "adapter": capability.adapter,
            "timestamp": utc_now(),
        }

    @agentd.get("/v1/capability", response_model=RobotCapability)
    async def get_capability() -> RobotCapability:
        return capability

    @agentd.get("/v1/state/snapshot")
    async def state_snapshot() -> dict[str, object]:
        return {
            "robot_id": robot_id,
            "graph_version": 1,
            "safety": {
                "estop": False,
                "motion_lease": None,
                "watchdog": "ARMED",
            },
            "application": {
                "state": "IDLE",
                "localization": "READY",
                "navigation": "READY",
            },
            "timestamp": utc_now(),
        }

    @agentd.get("/v1/discovery")
    async def discovery_report() -> dict[str, object]:
        try:
            report = load_latest_report(runtime.settings.robot_loop_artifact_dir, robot_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return report.model_dump(mode="json")

    @agentd.get("/v1/tools")
    async def tool_catalog() -> dict[str, object]:
        try:
            report = load_latest_report(runtime.settings.robot_loop_artifact_dir, robot_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "schema_version": "robot-tool-catalog/v1",
            "robot_id": robot_id,
            "discovery_id": report.discovery_id,
            "tools": [tool.model_dump(mode="json") for tool in report.tool_catalog],
        }

    @agentd.get("/v1/robots/{requested_robot_id}")
    async def enforce_robot_scope(requested_robot_id: str) -> RobotCapability:
        if requested_robot_id != robot_id:
            raise HTTPException(status_code=404, detail="robot-agentd is scoped to one robot")
        return capability

    return agentd
