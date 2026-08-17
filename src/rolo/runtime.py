from __future__ import annotations

from dataclasses import dataclass

from rolo.adapters.base import RobotUseBackend
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings, get_settings
from rolo.core.registry import RobotRegistry
from rolo.stages.debug.robot_use import RobotUseService, create_robot_use_backend


@dataclass
class Runtime:
    settings: Settings
    registry: RobotRegistry
    robot_use_backend: RobotUseBackend
    robot_use: RobotUseService


def create_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or get_settings()
    registry = RobotRegistry(settings.robot_config_dir)
    registry.load()
    artifacts = ArtifactStore(settings.robot_loop_artifact_dir)
    backend = create_robot_use_backend(settings)
    return Runtime(
        settings=settings,
        registry=registry,
        robot_use_backend=backend,
        robot_use=RobotUseService(
            registry=registry,
            backend=backend,
            artifacts=artifacts,
        ),
    )
