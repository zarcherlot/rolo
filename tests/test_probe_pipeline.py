from __future__ import annotations

from pathlib import Path

from rolo.stages.contracts import AgentRequirement, StageName, StageStatus
from rolo.stages.pipeline import assess_pipeline, assess_stage


def test_v2_pipeline_exposes_probe_trace_certify_with_probe_as_only_active_stage(
    tmp_path: Path,
) -> None:
    assessment = assess_pipeline(tmp_path / "artifacts", "robot")

    assert [stage.stage for stage in assessment.stages] == [
        StageName.PROBE,
        StageName.TRACE,
        StageName.CERTIFY,
    ]
    probe, trace, certify = assessment.stages
    assert probe.status == StageStatus.NOT_STARTED
    assert probe.agent_requirement == AgentRequirement.PROBE_AGENT
    assert probe.optional is False
    assert trace.status == StageStatus.NOT_STARTED
    assert trace.agent_requirement == AgentRequirement.TRACE_AGENT
    assert trace.optional is True
    assert certify.status == StageStatus.NOT_STARTED
    assert certify.agent_requirement == AgentRequirement.CERTIFY_AGENT
    assert certify.optional is True


def test_probe_stage_becomes_ready_only_when_target_evidence_exists(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    evidence_path = tmp_path / "config" / "target-evidence" / "robot-bundle.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text("{}\n", encoding="utf-8")

    stage = assess_stage(StageName.PROBE, artifact_root, "robot")

    assert stage.status == StageStatus.READY
    assert stage.optional is False
    assert stage.artifacts["target_evidence"] == str(evidence_path)
