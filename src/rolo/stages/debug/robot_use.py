"""Stage 2 robot_use semantic supervision service."""

from __future__ import annotations

from rolo.adapters.base import RobotUseBackend
from rolo.adapters.mock_robot_use import MockRobotUseBackend
from rolo.adapters.openai_robot_use import OpenAIRobotUseBackend
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.models import RobotUseRequest, RobotUseSupervision
from rolo.core.registry import RobotRegistry


def create_robot_use_backend(settings: Settings) -> RobotUseBackend:
    backend = settings.robot_use_backend.lower()
    if backend == "mock":
        return MockRobotUseBackend()
    if backend == "openai":
        return OpenAIRobotUseBackend(
            api_key=settings.openai_api_key or "",
            model=settings.openai_model or "",
        )
    raise ValueError(f"Unsupported ROBOT_USE_BACKEND: {settings.robot_use_backend}")


class RobotUseService:
    def __init__(
        self,
        *,
        registry: RobotRegistry,
        backend: RobotUseBackend,
        artifacts: ArtifactStore,
    ) -> None:
        self.registry = registry
        self.backend = backend
        self.artifacts = artifacts
        self._last_result: dict[str, RobotUseSupervision] = {}

    async def poll(self, request: RobotUseRequest) -> RobotUseSupervision:
        capability = self.registry.get(request.robot_id)
        robot_use = capability.features.get("robot_use", {})
        if not robot_use.get("supported", False):
            raise ValueError(f"robot_use is not supported by {request.robot_id}")
        if robot_use.get("local_visual_detection") is not False:
            raise ValueError("Local visual detection must be disabled in robot_use mode")

        result = await self.backend.evaluate(request)
        self._last_result[request.robot_id] = result
        self.artifacts.append_jsonl(
            "robot_use/supervision_results.jsonl",
            result.model_dump(mode="json"),
        )
        return result

    def status(self) -> dict[str, object]:
        return {
            "backend": self.backend.name,
            "local_visual_detection": False,
            "safety_authority": "none",
            "last_results": {
                robot_id: result.model_dump(mode="json")
                for robot_id, result in self._last_result.items()
            },
        }
