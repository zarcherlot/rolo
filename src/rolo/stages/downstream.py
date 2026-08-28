"""Canonical execution service for provider-neutral Diagnose and Verify Agents."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from rolo.agent_provider import create_stage_agent_executor
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.stages.agent_runner import StageAgentRun, StageAgentRunner, StageAgentTask
from rolo.stages.diagnose.service import build_diagnosis_task
from rolo.stages.handoffs import validate_diagnosis_handoff, validate_verification_handoff
from rolo.stages.verify.service import build_verification_task

Stage = Literal["diagnose", "verify"]


@contextmanager
def _stage_workspace(settings: Settings, stage: Stage) -> Iterator[Path]:
    """Create an ephemeral plugin workspace outside the canonical artifact root."""
    parent = settings.rolo_scratch_dir.expanduser().resolve() if settings.rolo_scratch_dir else None
    artifact_root = settings.rolo_artifact_dir.expanduser().resolve()
    if parent is not None:
        try:
            parent.relative_to(artifact_root)
        except ValueError:
            pass
        else:
            raise ValueError("ROLO_SCRATCH_DIR must not contain ROLO_ARTIFACT_DIR")
        try:
            artifact_root.relative_to(parent)
        except ValueError:
            pass
        else:
            raise ValueError("ROLO_ARTIFACT_DIR must not contain ROLO_SCRATCH_DIR")
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"rolo-{stage}-", dir=parent))
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


class DownstreamStageService:
    """Resolve, authorize, execute and validate one downstream Agent stage."""

    def __init__(self, settings: Settings, stage: Stage) -> None:
        self.settings = settings
        self.stage = stage
        self.artifacts = ArtifactStore(settings.rolo_artifact_dir)

    def build_task(self, robot_id: str) -> StageAgentTask:
        kwargs = {
            "provider": self.settings.coding_agent_provider,
            "executor": self.settings.coding_agent_executor,
            "model": self.settings.coding_agent_model,
        }
        if self.stage == "diagnose":
            return build_diagnosis_task(self.artifacts.root, robot_id, **kwargs)
        return build_verification_task(self.artifacts.root, robot_id, **kwargs)

    def run(
        self,
        robot_id: str,
        *,
        confirmed: bool,
        authorization_ref: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
    ) -> StageAgentRun:
        task = self.build_task(robot_id)
        executor = create_stage_agent_executor(
            task.executor,
            artifacts=self.artifacts,
            settings=self.settings,
            stage=self.stage,
        )
        if self.stage == "diagnose":
            def validator(_task: StageAgentTask) -> None:
                validate_diagnosis_handoff(self.artifacts.root, robot_id)
        else:
            def validator(_task: StageAgentTask) -> None:
                validate_verification_handoff(self.artifacts.root, robot_id)
        with _stage_workspace(self.settings, self.stage) as workspace:
            return StageAgentRunner(
                self.artifacts,
                executor,
                handoff_validator=validator,
            ).run(
                task,
                workspace=workspace,
                confirmed=confirmed,
                authorization_ref=authorization_ref,
                on_output=on_output,
            )
