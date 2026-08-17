from __future__ import annotations

from typing import Protocol

from rolo.core.models import RobotUseRequest, RobotUseSupervision


class RobotUseBackend(Protocol):
    @property
    def name(self) -> str: ...

    async def evaluate(self, request: RobotUseRequest) -> RobotUseSupervision: ...
