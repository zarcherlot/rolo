from __future__ import annotations

from typing import Protocol

from robot_loop.models import RobotUseRequest, RobotUseSupervision


class RobotUseBackend(Protocol):
    @property
    def name(self) -> str: ...

    async def evaluate(self, request: RobotUseRequest) -> RobotUseSupervision: ...
