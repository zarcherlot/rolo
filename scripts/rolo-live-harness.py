"""Start a deterministic, read-only Rolo control plane for consumer live gates.

The harness creates a temporary config root containing sanitized target profiles,
approval jobs, and one artifact-analysis summary.  It never connects to a host or
executes a bootstrap; the process only serves the existing GET API.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from rolo.artifact_analysis import ArtifactAnalysisSummary
from rolo.core.config import get_settings
from rolo.jobs import Job, JobEvent, JobStatus
from rolo.target_ref import LocalTargetRef, SshTargetRef
from rolo.targets.profiles import (
    CredentialReference,
    HostKeyDecision,
    TargetProfileStore,
)

_NOW = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)


def _write_job(root: Path, job: Job, events: list[JobEvent]) -> None:
    path = root / "jobs" / f"{job.job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "job": job.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in events],
                "checkpoints": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _seed(root: Path) -> None:
    source_robots = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "robots"
    (root / "robots").mkdir(parents=True, exist_ok=True)
    for source in source_robots.glob("*.yaml"):
        shutil.copy2(source, root / "robots" / source.name)
    ready_workspace = root / "workspaces" / "ready"
    ready_workspace.mkdir(parents=True, exist_ok=True)
    profiles = TargetProfileStore(root)
    profiles.create(
        robot_id="ready-local",
        target=LocalTargetRef(workspace=ready_workspace),
        credential=CredentialReference(kind="platform-keychain", reference="demo:ready-local"),
        now=_NOW,
    )
    profiles.create(
        robot_id="missing-local",
        target=LocalTargetRef(workspace=root / "workspaces" / "missing"),
        credential=CredentialReference(kind="platform-keychain", reference="demo:missing-local"),
        now=_NOW,
    )
    profiles.create(
        robot_id="pending-ssh",
        target=SshTargetRef(host="robot-pending.example", user="operator", workspace="/srv/rolo"),
        credential=CredentialReference(kind="ssh-agent", reference="demo:pending-ssh"),
        now=_NOW,
    )
    approved = profiles.create(
        robot_id="unreachable-ssh",
        target=SshTargetRef(
            host="robot-unreachable.example", user="operator", workspace="/srv/rolo"
        ),
        credential=CredentialReference(kind="ssh-agent", reference="demo:unreachable-ssh"),
        now=_NOW,
    )
    profiles.save(
        approved.model_copy(
            update={
                "host_key": HostKeyDecision(
                    status="APPROVED",
                    host="robot-unreachable.example",
                    fingerprint="SHA256:DemoFingerprint",
                    decided_at=_NOW,
                    decided_by="harness",
                )
            }
        )
    )

    _write_job(
        root,
        Job(
            job_id="job_approved_pending",
            operation="target.bootstrap.execute",
            target=approved.target.model_dump_json(),
            status=JobStatus.RUNNING,
            revision=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        [
            JobEvent(
                job_id="job_approved_pending",
                sequence=1,
                event_type="JOB_STARTED",
                status=JobStatus.RUNNING,
                occurred_at=_NOW,
                payload={"approval_status": "APPROVED"},
            )
        ],
    )
    _write_job(
        root,
        Job(
            job_id="job_approved_failed",
            operation="target.bootstrap.execute",
            target=approved.target.model_dump_json(),
            status=JobStatus.FAILED,
            revision=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        [
            JobEvent(
                job_id="job_approved_failed",
                sequence=1,
                event_type="BOOTSTRAP_FAILED",
                status=JobStatus.FAILED,
                occurred_at=_NOW,
                payload={"approval_status": "APPROVED"},
            )
        ],
    )
    _write_job(
        root,
        Job(
            job_id="job_pending",
            operation="target.bootstrap.execute",
            target=profiles.load("ready-local").target.model_dump_json(),
            status=JobStatus.CREATED,
            revision=0,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        [],
    )
    _write_job(
        root,
        Job(
            job_id="job_blocked",
            operation="target.bootstrap.execute",
            target=profiles.load("missing-local").target.model_dump_json(),
            status=JobStatus.BLOCKED,
            revision=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        [
            JobEvent(
                job_id="job_blocked",
                sequence=1,
                event_type="JOB_BLOCKED",
                status=JobStatus.BLOCKED,
                occurred_at=_NOW,
                payload={"approval_status": "PENDING"},
            )
        ],
    )

    analysis = ArtifactAnalysisSummary(
        analysis_id="analysis-ready-local",
        target_id="ready-local",
        robot_id="ready-local",
        job_id="job_approved_pending",
        run_id="run-ready-local",
        discovery_id="discovery-ready-local",
        source_label="Live sanitized artifact analysis",
        observed_at=_NOW,
        freshness="fresh",
        kind="Artifact analysis summary",
        run_status="COMPLETE",
        title="Bounded readiness analysis",
        description="Producer-authored summary with no artifact contents.",
        gate_status="PASSED",
        gate_label="Analysis complete",
        gate_tone="green",
        release_status="SHADOW_ONLY",
        release_label="No release effect",
        release_tone="amber",
        run_duration="42s",
        event_count=4,
        eligible_operation_count=2,
        route_review_flags="0 / 2",
        context_bars=[{"label": "Nodes", "value": 3, "display": "3 observed", "tone": "blue"}],
        evidence_note="Read-only bounded summary.",
        operations=[
            {
                "name": "app.inspect",
                "route": "observed route",
                "route_status": "observed",
                "checks": ["bounded"],
                "contract": "DISCOVERED_UNVERIFIED",
            }
        ],
        graph_nodes=[{"label": "target", "state": "bound", "tone": "green"}],
        stages=[
            {
                "label": "Analysis",
                "status": "passed",
                "timestamp": "00:00:42Z",
                "detail": "Summary complete.",
            }
        ],
        findings=[
            {
                "tone": "blue",
                "title": "Advisory",
                "body": "Analysis does not establish physical or release readiness.",
            }
        ],
        hashes=[("summary", "a1b2c3d4e5f60718")],
        limitations=[
            "Bounded summary only; artifact contents are withheld.",
            "Analysis is advisory and independent from capability readiness.",
        ],
    )
    (root / "artifact-analysis").mkdir(parents=True, exist_ok=True)
    (root / "artifact-analysis" / "ready-local.json").write_text(
        analysis.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--no-serve", action="store_true", help="seed config and print its path")
    args = parser.parse_args()
    holder = (
        tempfile.TemporaryDirectory(prefix="rolo-live-harness-")
        if args.config_dir is None
        else None
    )
    root = args.config_dir or Path(holder.name)
    _seed(root)
    print(f"ROLO_CONFIG_DIR={root}")
    if args.no_serve:
        return 0
    import os

    os.environ["ROLO_CONFIG_DIR"] = str(root)
    os.environ.setdefault("ROLO_ARTIFACT_DIR", str(root / "runtime-artifacts"))
    os.environ.setdefault("ROLO_OUTPUT_DIR", str(root / "runtime-output"))
    get_settings.cache_clear()
    try:
        uvicorn.run("rolo.api:app", host=args.host, port=args.port, log_level="info")
    finally:
        if holder is not None:
            holder.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
