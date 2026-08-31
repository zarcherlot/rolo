"""Start a deterministic, read-only Rolo control plane for consumer live gates.

The harness creates a temporary config root containing sanitized target profiles,
approval jobs, and one artifact-analysis summary.  It never connects to a host or
executes a bootstrap; the process only serves the existing GET API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from rolo.approval_gate_read_models import build_approval_gate_collection
from rolo.artifact_analysis import ArtifactAnalysisSummary
from rolo.core.config import get_settings
from rolo.device_hardening_evidence import StagingHarnessManifest
from rolo.jobs import Job, JobEvent, JobStatus
from rolo.target_readiness import build_target_readiness_collection
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
            # Keep the pending approval job bound to the same target as the
            # sanitized analysis summary below.  The failed SSH job remains
            # separately bound to the approved-but-unreachable fixture so the
            # harness still exercises an independent failure state.
            target=profiles.load("ready-local").target.model_dump_json(),
            status=JobStatus.RUNNING,
            revision=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        [
            JobEvent(
                event_id="evt_job_approved_pending_1",
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
                event_id="evt_job_approved_failed_1",
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
                event_id="evt_job_blocked_1",
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


def _rolo_revision() -> str:
    configured = os.environ.get("ROLO_REVISION")
    if configured:
        return configured
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    if not revision:
        raise RuntimeError("staging harness requires a git revision")
    return revision


def _manifest(root: Path) -> dict[str, object]:
    readiness = build_target_readiness_collection(root, observed_at=_NOW)
    approvals = build_approval_gate_collection(root, observed_at=_NOW)
    artifact = ArtifactAnalysisSummary.model_validate_json(
        (root / "artifact-analysis" / "ready-local.json").read_text(encoding="utf-8")
    )
    # Approval revisions are derived from persisted transport targets in the
    # core read model.  Replace those root-specific details with the bounded
    # identity/status tuple so the harness manifest is stable across temp roots.
    approval_revision = hashlib.sha256(
        "|".join(
            f"{item.job_id}:{item.target_id}:{item.gate_status}:{item.recovery_state}"
            for item in approvals.items
        ).encode("utf-8")
    ).hexdigest()
    return StagingHarnessManifest.model_validate(
        {
            "schema_version": "rolo-staging-harness-manifest/v1",
            "status": "BLOCKED",
            "release_line": "0.1.x",
            "rolo_revision": _rolo_revision(),
            "producer_revisions": {
                "target_readiness": readiness.producer_revision,
                "approval_gate": approval_revision,
                "artifact_analysis": artifact.producer_revision,
            },
            "target_ids": [item.target_id for item in readiness.items],
            "job_ids": [item.job_id for item in approvals.items],
            "gate_results": {
                "r0_jobs": "BLOCKED",
                "r1_target_readiness": "BLOCKED",
                "r2_approval_gate": "PENDING",
                "r4_artifact_analysis": "PASS",
            },
            "failure_semantics": {
                "blocked_target": "BLOCKED",
                "pending_approval": "PENDING",
                "external_device": "PENDING_EXTERNAL",
            },
            "limitations": [
                "Harness is deterministic and read-only; it never connects to a host.",
                "PASS means the read model path is available, not physical or release readiness.",
            ],
        }
    ).model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Write the deterministic harness manifest to this path",
    )
    parser.add_argument("--no-serve", action="store_true", help="seed config and print its path")
    args = parser.parse_args()
    holder = (
        tempfile.TemporaryDirectory(prefix="rolo-live-harness-")
        if args.config_dir is None
        else None
    )
    root = args.config_dir or Path(holder.name)
    _seed(root)
    manifest_path = args.manifest or root / "harness-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(_manifest(root), indent=2) + "\n", encoding="utf-8")
    print(f"ROLO_CONFIG_DIR={root}")
    print(f"ROLO_HARNESS_MANIFEST={manifest_path}")
    if args.no_serve:
        return 0
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
