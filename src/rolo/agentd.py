from __future__ import annotations

from fastapi import FastAPI, HTTPException

from rolo import __version__
from rolo.core.config import get_settings
from rolo.core.models import DiscoveryStatus, HealthState, RobotCapability, utc_now
from rolo.core.registry import RobotRegistry
from rolo.runtime import create_runtime
from rolo.stages.deploy.discovery import load_latest_report
from rolo.stages.pipeline import assess_pipeline


def create_bootstrap_agentd_app(robot_id: str) -> FastAPI:
    """Create the minimal, non-motion daemon used before discovery."""
    settings = get_settings()
    registry = RobotRegistry(settings.robot_config_dir)
    registry.load()
    try:
        capability = registry.get(robot_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    enrollment = capability.features.get("enrollment", {})
    safety_profile_confirmed = bool(enrollment.get("safety_profile_confirmed"))
    bootstrap = FastAPI(title=f"robot-bootstrap-agentd:{robot_id}", version=__version__)

    @bootstrap.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": HealthState.HEALTHY if safety_profile_confirmed else HealthState.UNHEALTHY,
            "service": "robot-bootstrap-agentd",
            "phase": "BOOTSTRAP_READY" if safety_profile_confirmed else "BOOTSTRAP_BLOCKED",
            "robot_id": robot_id,
            "timestamp": utc_now(),
        }

    @bootstrap.get("/v1/bootstrap")
    async def bootstrap_status() -> dict[str, object]:
        now = utc_now()
        return {
            "robot_id": robot_id,
            "profile_id": enrollment.get("profile_id"),
            "safety_profile_confirmed": safety_profile_confirmed,
            "motion_enabled": False,
            "discovery_ready": safety_profile_confirmed,
            "clock": {"status": "LOCAL_CLOCK_AVAILABLE", "utc": now},
            "timestamp": now,
        }

    @bootstrap.get("/v1/robots/{requested_robot_id}")
    async def enforce_robot_scope(requested_robot_id: str) -> dict[str, object]:
        if requested_robot_id != robot_id:
            raise HTTPException(status_code=404, detail="bootstrap agentd is scoped to one robot")
        return {
            "robot_id": robot_id,
            "profile_id": enrollment.get("profile_id"),
            "safety_profile_confirmed": safety_profile_confirmed,
        }

    return bootstrap


def create_agentd_app(robot_id: str) -> FastAPI:
    runtime = create_runtime()
    try:
        capability = runtime.registry.get(robot_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    enrollment = capability.features.get("enrollment", {})
    bindings_unbound = any(
        str(sensor.get("binding", "")).startswith("unbound://")
        for sensor in capability.sensors.values()
        if isinstance(sensor, dict)
    )
    configuration_ready = bool(
        enrollment.get("safety_profile_confirmed")
        and enrollment.get("bindings_verified")
        and enrollment.get("calibration_verified")
        and not bindings_unbound
    )

    def readiness() -> tuple[bool, str]:
        try:
            report = load_latest_report(runtime.settings.robot_loop_artifact_dir, robot_id)
        except FileNotFoundError:
            return False, "DISCOVERY_PENDING"
        if report.status == DiscoveryStatus.FAILED:
            return False, "DISCOVERY_FAILED"
        if report.status != DiscoveryStatus.SUCCEEDED:
            return False, "DISCOVERY_PARTIAL"
        compatibility = report.capability_manifest.get("compatibility", {})
        if compatibility.get("status") != "MATCH":
            return False, "CAPABILITY_MISMATCH"
        if not configuration_ready:
            return False, "AGENTD_DEGRADED"
        return True, "AGENTD_READY"

    agentd = FastAPI(title=f"robot-agentd:{robot_id}", version=__version__)

    @agentd.get("/health")
    async def health() -> dict[str, object]:
        ready, phase = readiness()
        return {
            "status": HealthState.HEALTHY if ready else HealthState.DEGRADED,
            "service": "robot-agentd",
            "phase": phase,
            "robot_id": robot_id,
            "adapter": capability.adapter,
            "timestamp": utc_now(),
        }

    @agentd.get("/v1/capability", response_model=RobotCapability)
    async def get_capability() -> RobotCapability:
        return capability

    @agentd.get("/v1/state/snapshot")
    async def state_snapshot() -> dict[str, object]:
        ready, phase = readiness()
        return {
            "robot_id": robot_id,
            "graph_version": 1,
            "runtime_phase": phase,
            "safety": {
                "estop": False,
                "motion_lease": None,
                "watchdog": "ARMED" if ready else "DISARMED",
            },
            "application": {
                "state": "IDLE",
                "localization": "READY" if ready else "NOT_READY",
                "navigation": "READY" if ready else "NOT_READY",
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

    @agentd.get("/v1/pipeline")
    async def pipeline_status() -> dict[str, object]:
        return assess_pipeline(
            runtime.settings.robot_loop_artifact_dir, robot_id
        ).model_dump(mode="json")

    @agentd.get("/v1/robots/{requested_robot_id}")
    async def enforce_robot_scope(requested_robot_id: str) -> RobotCapability:
        if requested_robot_id != robot_id:
            raise HTTPException(status_code=404, detail="robot-agentd is scoped to one robot")
        return capability

    return agentd
