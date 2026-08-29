"""Deterministic local Stage Agent used to exercise Diagnose/Verify contracts.

The fake executor is intentionally not a general Adapt executor and is never the
default provider.  It creates explicitly synthetic, non-release evidence so a
developer can run the authorization, handoff materializer and validator loop
without Codex credentials, ROS, hardware or a target machine.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.stages.agent_runner import OutputCallback, StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.handoffs import commit_diagnosis_handoff, commit_verification_handoff

Stage = Literal["diagnose", "verify"]


class FakeStageAgentExecutor:
    """Produce deterministic synthetic outputs for a downstream stage."""

    def __init__(
        self,
        *,
        artifacts: ArtifactStore,
        settings: Settings,
        stage: Stage,
    ) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.stage = stage

    def execute_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None = None,
    ) -> Mapping[str, str]:
        del workspace
        if task.stage != self.stage:
            raise ValueError(f"fake Stage executor is bound to {self.stage}, got {task.stage}")
        if on_output is not None:
            on_output("stdout", f"fake {self.stage} provider: synthetic result")

        run_id = f"fake-{task.plan_sha256[:16]}"
        layout = ArtifactLayout(self.artifacts.root)
        if self.stage == "diagnose":
            episode = self.artifacts.write_json(
                layout.relative(
                    layout.stage_run(self.stage, task.robot_id, run_id)
                    / "episodes"
                    / "fake-observation.json"
                ),
                {
                    "schema_version": "rolo-fake-stage-observation/v1",
                    "robot_id": task.robot_id,
                    "stage": self.stage,
                    "source_input_refs": list(task.input_refs.values()),
                    "execution": "NOT_EXECUTED",
                    "authority": "UNVERIFIED_FAKE_PROVIDER",
                },
            )
            report = {
                "schema_version": "rolo-diagnosis-report/v1",
                "robot_id": task.robot_id,
                "baseline": {"source": "fake-provider"},
                "observations": [{"kind": "synthetic", "status": "NOT_EXECUTED"}],
                "hypotheses": [{"kind": "synthetic", "confidence": "UNKNOWN"}],
                "changes": [{"kind": "none", "applied": False}],
                "smoke": {"status": "NOT_RUN"},
                "decision": "INCONCLUSIVE",
                "episode_refs": [layout.ref(episode)],
                "limitations": [
                    "No target runtime episode was executed; this is a fake-provider result."
                ],
            }
            handoff = commit_diagnosis_handoff(
                self.artifacts.root,
                task.robot_id,
                frozen_config={
                    "source": "fake-provider",
                    "robot_id": task.robot_id,
                    "execution": "NOT_EXECUTED",
                },
                diagnosis_report=report,
                run_id=run_id,
            )
            output_refs = {
                "handoff": layout.ref(layout.stage_file("diagnose", task.robot_id, "handoff.json")),
                "frozen_config": handoff.frozen_config_ref,
            }
            if handoff.diagnosis_report_ref:
                output_refs["diagnosis_report"] = handoff.diagnosis_report_ref
            return output_refs

        handoff = commit_verification_handoff(
            self.artifacts.root,
            task.robot_id,
            regression_report={
                "status": "ERROR",
                "mode": "FAKE_UNEXECUTED",
                "case_results": [
                    {
                        "case_id": "fake-provider",
                        "status": "ERROR",
                        "reason": "No target or hardware execution was requested.",
                    }
                ],
            },
            evidence_package={
                "mode": "FAKE_UNEXECUTED",
                "verified": False,
                "artifacts": list(task.input_refs.values()),
            },
            run_id=run_id,
        )
        return {
            "handoff": layout.ref(layout.stage_file("verify", task.robot_id, "handoff.json")),
            "regression_report": handoff.regression_report_ref,
            "evidence_package": handoff.evidence_package_ref,
        }
