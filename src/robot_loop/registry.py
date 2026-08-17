from __future__ import annotations

from pathlib import Path

from robot_loop.config import load_yaml
from robot_loop.models import RobotCapability


class RobotRegistry:
    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._robots: dict[str, RobotCapability] = {}

    def load(self) -> None:
        if not self._config_dir.exists():
            raise FileNotFoundError(f"Robot config directory not found: {self._config_dir}")
        loaded: dict[str, RobotCapability] = {}
        for path in sorted(self._config_dir.glob("*.yaml")):
            capability = RobotCapability.model_validate(load_yaml(path))
            if capability.robot_id in loaded:
                raise ValueError(f"Duplicate robot_id: {capability.robot_id}")
            loaded[capability.robot_id] = capability
        if not loaded:
            raise ValueError(f"No robot manifests found in {self._config_dir}")
        self._robots = loaded

    def list(self) -> list[RobotCapability]:
        return list(self._robots.values())

    def get(self, robot_id: str) -> RobotCapability:
        try:
            return self._robots[robot_id]
        except KeyError as exc:
            raise KeyError(f"Unknown robot_id: {robot_id}") from exc

    def __len__(self) -> int:
        return len(self._robots)
