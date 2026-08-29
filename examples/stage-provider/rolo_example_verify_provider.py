"""Offline Verify provider staging fixture."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from rolo.stages.agent_runner import OutputCallback, StageAgentTask


class ExampleVerifyProvider:
    stage = "verify"

    def execute_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None = None,
    ) -> Mapping[str, str]:
        if task.stage != self.stage:
            raise ValueError(f"provider is bound to {self.stage}, got {task.stage}")
        if on_output:
            on_output("stdout", "verify provider staging preflight complete")
        return {"status": "staged"}


def factory(**_kwargs: object) -> ExampleVerifyProvider:
    return ExampleVerifyProvider()
