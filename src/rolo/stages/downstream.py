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
from rolo.stages.artifact_paths import ArtifactLayout
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

    def build_task(
        self,
        robot_id: str,
        *,
        provider: str | None = None,
        executor: str | None = None,
        model: str | None = None,
    ) -> StageAgentTask:
        selected_provider = provider or self.settings.coding_agent_provider
        selected_executor = executor or self.settings.coding_agent_executor
        selected_model = model if model is not None else self.settings.coding_agent_model
        kwargs = {
            "provider": selected_provider,
            "executor": selected_executor,
            "model": selected_model,
        }
        additional_input_refs: dict[str, str] = {}
        if selected_executor.strip().lower() in {"local-target", "ssh-target"}:
            from rolo.stages.real_target import publish_target_binding
            from rolo.target_ref import LocalTargetRef
            from rolo.targets.profiles import TargetProfileStore

            profile = TargetProfileStore(self.settings.rolo_config_dir).load(robot_id)
            if isinstance(profile.target, LocalTargetRef):
                additional_input_refs["target_binding"] = publish_target_binding(
                    self.artifacts, self.settings, robot_id
                )
            else:
                # SSH identity is collected only after authorization.  The profile
                # itself is immutable and digest-bound into the Stage task.
                from rolo.core.hashing import canonical_json_sha256

                profile_path = self.artifacts.write_json(
                    f"targets/{robot_id}/profiles/{profile.profile_id}.json",
                    {
                        "profile_id": profile.profile_id,
                        "profile_sha256": canonical_json_sha256(
                            profile.model_dump(mode="json")
                        ),
                    },
                )
                additional_input_refs["target_profile"] = ArtifactLayout(
                    self.artifacts.root
                ).ref(profile_path)
        if self.stage == "diagnose":
            return build_diagnosis_task(
                self.artifacts.root,
                robot_id,
                additional_input_refs=additional_input_refs,
                **kwargs,
            )
        return build_verification_task(
            self.artifacts.root,
            robot_id,
            additional_input_refs=additional_input_refs,
            **kwargs,
        )

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
