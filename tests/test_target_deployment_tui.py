from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from rolo.targets import (
    ApprovalAction,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    TargetBootstrapJobSpecStore,
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetProfile,
    TargetProfileRegistry,
    TargetProjectEvidenceIntentStore,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceJobSubmission,
    TargetProjectEvidenceSubmissionService,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    render_target_deployment_tui,
)


def test_tui_pages_reuse_persistent_state_and_render_canonical_cli(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    registrations = TargetRegistrationService(TargetProfileRegistry(tmp_path / "profiles"))
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="wheeltec",
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root="/home/robot/wheeltec_ws",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="operator@example.com",
        idempotency_key="tui-register-wheeltec",
        now=now,
    )
    jobs = DeploymentJobStore(tmp_path / "jobs")
    job = jobs.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.ADAPT,
            target_id="wheeltec",
            workspace_root="/home/robot/wheeltec_ws",
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="tui-adapt-wheeltec",
        ),
        now=now,
    )
    approval = jobs.request_approval(
        job.job.job_id,
        action=ApprovalAction.STAGE_RELEASE,
        risk="R3",
        approver_principal="reviewer@example.com",
        summary="Review exact target release digest.",
        expires_at=now + timedelta(minutes=15),
        authorization_scope_sha256="a" * 64,
        now=now,
        approval_id="approval-" + "a" * 32,
    )
    tui = TargetDeploymentTui(
        registrations,
        jobs,
        TargetBootstrapJobSpecStore(tmp_path / "specs"),
    )

    fleet = tui.snapshot(TargetDeploymentTuiPage.FLEET, now=now)
    target = tui.snapshot(TargetDeploymentTuiPage.TARGET, target_id="wheeltec", now=now)
    job_page = tui.snapshot(TargetDeploymentTuiPage.JOB, job_id=job.job.job_id, now=now)
    approval_page = tui.snapshot(
        TargetDeploymentTuiPage.APPROVAL,
        approval_id=approval.approval_id,
        now=now,
    )
    approval_list = tui.snapshot(TargetDeploymentTuiPage.APPROVAL, now=now)

    assert fleet.rows[0].identity == "wheeltec"
    assert target.rows[1].identity == job.job.job_id
    assert job_page.rows[0].canonical_cli is not None
    assert "target adapt submit" in job_page.rows[0].canonical_cli
    assert approval_page.rows[0].status == "PENDING"
    assert approval_list.title == "Approvals"
    assert approval_list.rows == approval_page.rows
    assert "target approval decide" in approval_page.rows[0].canonical_cli
    approval_fields = {field.name: field.value for field in approval_page.rows[0].fields}
    assert approval_fields["target"] == "wheeltec"
    assert approval_fields["action"] == "STAGE_RELEASE"
    assert approval_fields["desired_version"] == "0.2.0"
    assert approval_fields["workspace"] == "/home/robot/wheeltec_ws"
    assert approval_fields["command_sha256"] == job.job.command_sha256
    rendered = render_target_deployment_tui(approval_page)
    assert "Approval" in rendered
    assert "reviewer@example.com" in rendered
    assert "private" not in rendered.casefold()
    gui = tui.workbench_snapshot(
        TargetDeploymentTuiPage.APPROVAL,
        approval_id=approval.approval_id,
        now=now,
    )
    assert gui.schema_version == "rolo-target-deployment-workbench-snapshot/v1"
    assert gui.rows == approval_page.rows

    jobs.start_step(
        job.job.job_id,
        step_id="remote-adapt",
        state=DeploymentJobState.ADAPTING,
        remote=True,
        now=now + timedelta(seconds=1),
    )
    jobs.fail_step(
        job.job.job_id,
        step_id="remote-adapt",
        remote_state_known=False,
        now=now + timedelta(seconds=2),
    )
    blockers = tui.snapshot(TargetDeploymentTuiPage.BLOCKER, now=now)

    assert blockers.rows[0].kind == "BLOCKER"
    assert blockers.rows[0].status == "BLOCKED"
    assert any(
        field.name == "recovery" and field.value == "REQUIRES_RECONCILIATION"
        for field in blockers.rows[0].fields
    )


def test_tui_renders_exact_project_evidence_submission(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registrations = TargetRegistrationService(TargetProfileRegistry(tmp_path / "profiles"))
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="alpha",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.LOCAL,
                workspace_root=str(workspace.absolute()),
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="operator@example.com",
        idempotency_key="tui-register-project-evidence-alpha",
        now=now,
    )
    jobs = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetProjectEvidenceJobSpecStore(tmp_path / "specs")
    result = TargetProjectEvidenceSubmissionService(
        store=jobs,
        specs=specs,
        intents=TargetProjectEvidenceIntentStore(tmp_path / "intents"),
        registrations=registrations,
    ).submit(
        target_id="alpha",
        submission=TargetProjectEvidenceJobSubmission(
            approver_principal="reviewer@example.com"
        ),
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.TUI,
        idempotency_key="tui-project-evidence-alpha",
        now=now,
    )
    tui = TargetDeploymentTui(
        registrations,
        jobs,
        TargetBootstrapJobSpecStore(tmp_path / "bootstrap-specs"),
        project_evidence_specs=specs,
    )

    job_page = tui.snapshot(
        TargetDeploymentTuiPage.JOB,
        job_id=result.job.job.job_id,
        now=now,
    )
    approval_page = tui.snapshot(
        TargetDeploymentTuiPage.APPROVAL,
        approval_id=result.approval.approval_id,
        now=now,
    )

    cli = job_page.rows[0].canonical_cli
    assert cli is not None
    assert "target project-evidence submit" in cli
    assert "--candidates-json" in cli
    assert "CMakeLists.txt" in cli
    fields = {field.name: field.value for field in approval_page.rows[0].fields}
    assert fields["action"] == ApprovalAction.READ_PROJECT_EVIDENCE.value
    assert fields["candidate_count"] == "6"
    assert len(fields["workspace_sha256"]) == 64
