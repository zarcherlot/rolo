from __future__ import annotations

from dataclasses import dataclass

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings, get_settings
from rolo.core.registry import RobotRegistry
from rolo.integrations.robot_use.base import RobotUseBackend
from rolo.stages.diagnose.robot_use import RobotUseService, create_robot_use_backend


@dataclass
class Runtime:
    settings: Settings
    registry: RobotRegistry
    artifacts: ArtifactStore


@dataclass
class RobotUseRuntime(Runtime):
    robot_use_backend: RobotUseBackend
    robot_use: RobotUseService


def create_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or get_settings()
    registry = RobotRegistry(settings.robot_config_dir)
    registry.load()
    artifacts = ArtifactStore(settings.rolo_artifact_dir)
    return Runtime(
        settings=settings,
        registry=registry,
        artifacts=artifacts,
    )


def create_robot_use_runtime(settings: Settings | None = None) -> RobotUseRuntime:
    runtime = create_runtime(settings)
    backend = create_robot_use_backend(runtime.settings)
    return RobotUseRuntime(
        settings=runtime.settings,
        registry=runtime.registry,
        artifacts=runtime.artifacts,
        robot_use_backend=backend,
        robot_use=RobotUseService(
            registry=runtime.registry,
            backend=backend,
            artifacts=runtime.artifacts,
        ),
    )
