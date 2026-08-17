from __future__ import annotations

from pathlib import Path

from rolo.core.models import DiscoveryStatus
from rolo.stages.contracts import StageAssessment, StageName, StageStatus
from rolo.stages.deploy.discovery import load_latest_report


def assess_deploy(artifact_root: Path, robot_id: str) -> StageAssessment:
    try:
        report = load_latest_report(artifact_root, robot_id)
    except FileNotFoundError:
        return StageAssessment(
            stage=StageName.DEPLOY,
            robot_id=robot_id,
            status=StageStatus.NOT_STARTED,
            summary="Deployment is enrolled but discovery has not produced a handoff",
            blockers=["Run deploy discovery"],
        )

    handoff = artifact_root / "deploy" / robot_id / "latest" / "handoff.json"
    if not handoff.is_file():
        return StageAssessment(
            stage=StageName.DEPLOY,
            robot_id=robot_id,
            status=StageStatus.DEGRADED,
            summary="Discovery predates the four-stage contract and has no deployment handoff",
            artifacts={
                "discovery_report": str(
                    artifact_root / "discovery" / robot_id / "latest" / "report.json"
                )
            },
            blockers=["Rerun deploy discovery to generate the deployment handoff"],
        )
    if report.status == DiscoveryStatus.FAILED:
        status = StageStatus.BLOCKED
        summary = "Discovery failed; build cannot start"
    elif report.status == DiscoveryStatus.PARTIAL:
        status = StageStatus.DEGRADED
        summary = "Deployment handoff exists with partial discovery evidence"
    else:
        status = StageStatus.COMPLETE
        summary = "Deployment handoff is ready for the build stage"
    return StageAssessment(
        stage=StageName.DEPLOY,
        robot_id=robot_id,
        status=status,
        summary=summary,
        artifacts={
            "handoff": str(handoff),
            "discovery_report": str(
                artifact_root / "discovery" / robot_id / "latest" / "report.json"
            ),
        },
        blockers=[] if status != StageStatus.BLOCKED else ["Resolve failed discovery probes"],
    )
