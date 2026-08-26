from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rolo.core.models import DiscoveryStatus
from rolo.stages.adapt.journey import AdaptJourneyResult, ProjectEvidence
from rolo.targets import (
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobRecoverySnapshot,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentRecoveryDisposition,
    InteractionSurface,
    OrchestratorPlacement,
    TargetAdaptJobRunner,
    TargetAdaptJobSpecStore,
    TargetAdaptJobSubmission,
    TargetAdaptJobSubmissionService,
    TargetBootstrapJobSpecStore,
    TargetConnectionProfile,
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetProfile,
    TargetProfileRegistry,
    TargetProjectEvidenceArtifactStore,
    TargetProjectEvidenceExecutionResult,
    TargetProjectEvidenceHit,
    TargetProjectEvidenceJobArtifact,
    TargetProjectEvidenceJobArtifactStatus,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceSnapshot,
    TargetProjectEvidenceStatus,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetSourceDiscoveryArtifactStore,
    TargetSourceDiscoveryExecutionResult,
    TargetSourceDiscoveryJobArtifact,
    TargetSourceDiscoveryJobArtifactStatus,
    TargetSourceDiscoverySnapshot,
    TargetSourceProjectSummary,
    TargetTransport,
    TargetTrustLevel,
    TargetWorkspaceFile,
    TargetWorkspaceManifest,
    TargetWorkspaceRef,
    build_target_adapt_job_spec,
    resolve_target_adapt_project_evidence_binding,
    resolve_target_adapt_source_discovery_binding,
    target_connection_binding_sha256,
)


def _registration(tmp_path: Path) -> tuple[TargetRegistrationService, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("robot", encoding="utf-8")
    service = TargetRegistrationService(TargetProfileRegistry(tmp_path / "profiles"))
    service.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="wheeltec",
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root=str(project.absolute()),
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="operator@example.com",
        idempotency_key="adapt-job-register-wheeltec",
    )
    return service, project


def _journey(project: Path, *, status: str = "DISCOVERY_COMPLETE") -> AdaptJourneyResult:
    return AdaptJourneyResult(
        status=status,
        robot_id="wheeltec",
        enrollment="EXISTING",
        doctor_status="READY",
        evidence=ProjectEvidence(project_root=project, source_roots=[project]),
        blockers=["No route is ready."] if status == "BLOCKED" else [],
        workbench_url="http://127.0.0.1:8080",
    )


def test_adapt_job_is_idempotent_and_recovers_from_persisted_journey(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registrations, project = _registration(tmp_path)
    spec = build_target_adapt_job_spec(
        registrations.load("wheeltec"),
        TargetAdaptJobSubmission(active_probe="none"),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetAdaptJobSpecStore(tmp_path / "specs")
    submission = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="adapt-job-wheeltec-0001",
    )
    repeated = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.API,
        idempotency_key="adapt-job-wheeltec-0001",
    )
    calls = 0

    def execute(_spec, _command):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return _journey(project)

    runner = TargetAdaptJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        settings=object(),
        journey_runner=execute,
    )
    persist_artifact = runner._persist_artifact
    crashed = False

    def persist_then_crash(artifact):  # type: ignore[no-untyped-def]
        nonlocal crashed
        if not crashed:
            crashed = True
            raise RuntimeError("simulated Controller interruption")
        persist_artifact(artifact)

    monkeypatch.setattr(runner, "_persist_artifact", persist_then_crash)
    with pytest.raises(RuntimeError, match="Controller interruption"):
        runner.run(submission.job.job_id)
    monkeypatch.setattr(runner, "_persist_artifact", persist_artifact)
    completed = runner.run(submission.job.job_id)

    assert repeated.job.job_id == submission.job.job_id
    assert completed.job.state == DeploymentJobState.COMPLETE
    assert completed.checkpoints[0].status.value == "COMPLETE"
    assert calls == 1
    assert len(completed.final_artifact_refs) == 2


def test_adapt_job_known_journey_blocker_is_not_remote_reconciliation(
    tmp_path: Path,
) -> None:
    registrations, project = _registration(tmp_path)
    spec = build_target_adapt_job_spec(
        registrations.load("wheeltec"),
        TargetAdaptJobSubmission(active_probe="none"),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetAdaptJobSpecStore(tmp_path / "specs")
    job = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="adapt-job-wheeltec-blocked",
    )
    runner = TargetAdaptJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        settings=object(),
        journey_runner=lambda _spec, _command: _journey(project, status="BLOCKED"),
    )

    blocked = runner.run(job.job.job_id)

    assert blocked.job.state == DeploymentJobState.BLOCKED
    assert blocked.recovery_disposition.value == "NONE"
    assert blocked.job.blockers == ["ADAPT_JOURNEY_BLOCKED"]
    assert blocked.checkpoints[0].remote_state.value == "CONFIRMED"


def test_adapt_job_rejects_remote_and_agent_release_without_required_orchestration(
    tmp_path: Path,
) -> None:
    registrations, _ = _registration(tmp_path)
    with pytest.raises(ValueError, match="release-scoped approvals"):
        build_target_adapt_job_spec(
            registrations.load("wheeltec"),
            TargetAdaptJobSubmission(run_adapter_agent=True),
        )
    remote = TargetRegistrationRequest(
        target=TargetProfile(
            target_id="remote-arm",
            orchestrator_placement=OrchestratorPlacement.CONTROLLER,
            transport=TargetTransport.SSH,
            connection_profile_id="connection-remote-arm",
            workspace_root="/home/robot/ws",
            desired_rolo_version="0.2.0",
            trust_level=TargetTrustLevel.STRICT,
        ),
        connection=TargetConnectionProfile(
            connection_profile_id="connection-remote-arm",
            host="192.0.2.20",
            port=22,
            user="robot",
                credential_ref="file://ssh/remote-arm",
                known_hosts_path=str((tmp_path / "known_hosts").absolute()),
                trust_level=TargetTrustLevel.STRICT,
                expected_host_key_sha256="SHA256:" + "A" * 43,
            ),
        )
    with pytest.raises(ValueError, match="completed target project evidence"):
        build_target_adapt_job_spec(remote, TargetAdaptJobSubmission())


def test_ssh_adapt_binds_completed_project_metadata_without_local_path_scan(
    tmp_path: Path,
) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("remote ssh-ed25519 AAAATEST\n", encoding="utf-8")
    registrations = TargetRegistrationService(TargetProfileRegistry(tmp_path / "profiles"))
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="remote-arm",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id="connection-remote-arm",
                workspace_root="/home/robot/ws",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            ),
            connection=TargetConnectionProfile(
                connection_profile_id="connection-remote-arm",
                host="192.0.2.20",
                port=22,
                user="robot",
                credential_ref="file://ssh/remote-arm",
                known_hosts_path=str(known_hosts.absolute()),
                trust_level=TargetTrustLevel.STRICT,
                expected_host_key_sha256="SHA256:" + "A" * 43,
            ),
        ),
        principal="operator@example.com",
        idempotency_key="register-remote-arm-for-adapt",
    )
    registration = registrations.load("remote-arm")
    registration_sha256 = target_connection_binding_sha256(
        registration.target,
        registration.connection,
    )
    now = datetime.now(timezone.utc)
    jobs = DeploymentJobStore(tmp_path / "jobs")
    evidence_job = jobs.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.COLLECT_EVIDENCE,
            target_id="remote-arm",
            run_adapter_agent=False,
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="remote-project-evidence-for-adapt",
            parameters_sha256="1" * 64,
        ),
        now=now,
    )
    workspace = TargetWorkspaceRef(
        workspace_id="workspace-remote-arm",
        target_id="remote-arm",
        robot_id="remote-arm",
        root="/home/robot/ws",
    )
    workspace_file = TargetWorkspaceFile(
        path="README.md",
        size_bytes=5,
        sha256="2" * 64,
        role="SOURCE",
    )
    draft = TargetWorkspaceManifest.model_construct(
        workspace=workspace,
        files=[workspace_file],
        total_size_bytes=5,
        content_sha256="0" * 64,
        observed_at=now,
    )
    manifest = TargetWorkspaceManifest(
        workspace=workspace,
        files=[workspace_file],
        total_size_bytes=5,
        content_sha256=draft.compute_content_sha256(),
        observed_at=now,
    )
    snapshot = TargetProjectEvidenceSnapshot(
        request_id="project-evidence-remote-arm",
        request_sha256="3" * 64,
        target_id="remote-arm",
        robot_id="remote-arm",
        workspace_id=workspace.workspace_id,
        status=TargetProjectEvidenceStatus.OBSERVED,
        hits=[
            TargetProjectEvidenceHit(
                path="README.md",
                kind=TargetProjectEvidenceKind.DOCUMENTATION,
                role="SOURCE",
            )
        ],
        manifest=manifest,
        observed_at=now,
    )
    artifact = TargetProjectEvidenceJobArtifact(
        job_id=evidence_job.job.job_id,
        command_sha256=evidence_job.job.command_sha256,
        spec_sha256="4" * 64,
        target_id="remote-arm",
        target_registration_sha256=registration_sha256,
        status=TargetProjectEvidenceJobArtifactStatus.SUCCEEDED,
        execution=TargetProjectEvidenceExecutionResult(
            request_id=snapshot.request_id,
            request_sha256=snapshot.request_sha256,
            target_id="remote-arm",
            robot_id="remote-arm",
            workspace_id=workspace.workspace_id,
            executor_kind=TargetExecutorKind.SSH,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            snapshot=snapshot,
        ),
        completed_at=now,
    )
    evidence_artifacts = TargetProjectEvidenceArtifactStore(tmp_path / "artifacts")
    evidence_artifacts.persist(artifact)
    jobs.start_step(
        evidence_job.job.job_id,
        step_id="project-evidence",
        state=DeploymentJobState.COLLECTING_EVIDENCE,
        remote=True,
        now=now,
    )
    jobs.complete_step(
        evidence_job.job.job_id,
        step_id="project-evidence",
        outcome_sha256=artifact.canonical_sha256(),
        artifact_refs=["artifact://project-evidence"],
        now=now,
    )
    jobs.complete_job(
        evidence_job.job.job_id,
        artifact_refs=["artifact://project-evidence"],
        now=now,
    )
    binding = resolve_target_adapt_project_evidence_binding(
        job_id=evidence_job.job.job_id,
        target_id="remote-arm",
        target_registration_sha256=registration_sha256,
        jobs=jobs,
        artifacts=evidence_artifacts,
        max_age_s=900,
        now=now,
    )
    source_job = jobs.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.COLLECT_EVIDENCE,
            target_id="remote-arm",
            run_adapter_agent=False,
            requested_by="operator@example.com",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="remote-source-discovery-for-adapt",
            parameters_sha256="5" * 64,
        ),
        now=now,
    )
    source_values = {
        "request_id": "source-discovery-remote-arm",
        "request_sha256": "6" * 64,
        "target_id": "remote-arm",
        "robot_id": "remote-arm",
        "workspace_id": workspace.workspace_id,
        "workspace_sha256": workspace.canonical_sha256(),
        "status": DiscoveryStatus.SUCCEEDED,
        "projects": [
            TargetSourceProjectSummary(
                root=".",
                file_count_scanned=3,
                scan_truncated=False,
                build_systems=["python/pyproject"],
                packages=["remote-driver"],
                languages=["python"],
                manifest_digests={"pyproject.toml": "7" * 64},
                source_revision="8" * 40,
            )
        ],
        "route_evidence": [],
        "warnings": [],
        "summary_sha256": "0" * 64,
        "observed_at": now,
    }
    source_draft = TargetSourceDiscoverySnapshot.model_construct(**source_values)
    source_values["summary_sha256"] = source_draft.compute_summary_sha256()
    source_snapshot = TargetSourceDiscoverySnapshot.model_validate(source_values)
    source_artifact = TargetSourceDiscoveryJobArtifact(
        job_id=source_job.job.job_id,
        command_sha256=source_job.job.command_sha256,
        spec_sha256="9" * 64,
        target_id="remote-arm",
        target_registration_sha256=registration_sha256,
        status=TargetSourceDiscoveryJobArtifactStatus.SUCCEEDED,
        execution=TargetSourceDiscoveryExecutionResult(
            request_id=source_snapshot.request_id,
            request_sha256=source_snapshot.request_sha256,
            target_id="remote-arm",
            robot_id="remote-arm",
            workspace_id=workspace.workspace_id,
            executor_kind=TargetExecutorKind.SSH,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            snapshot=source_snapshot,
        ),
        completed_at=now,
    )
    source_artifacts = TargetSourceDiscoveryArtifactStore(tmp_path / "source-artifacts")
    source_artifacts.persist(source_artifact)
    jobs.start_step(
        source_job.job.job_id,
        step_id="source-discovery",
        state=DeploymentJobState.COLLECTING_EVIDENCE,
        remote=True,
        now=now,
    )
    jobs.complete_step(
        source_job.job.job_id,
        step_id="source-discovery",
        outcome_sha256=source_artifact.canonical_sha256(),
        artifact_refs=["artifact://source-discovery"],
        now=now,
    )
    jobs.complete_job(
        source_job.job.job_id,
        artifact_refs=["artifact://source-discovery"],
        now=now,
    )
    source_binding = resolve_target_adapt_source_discovery_binding(
        job_id=source_job.job.job_id,
        target_id="remote-arm",
        target_registration_sha256=registration_sha256,
        workspace_sha256=binding.workspace_sha256,
        jobs=jobs,
        artifacts=source_artifacts,
        max_age_s=900,
        now=now,
    )
    spec = build_target_adapt_job_spec(
        registration,
        TargetAdaptJobSubmission(
            active_probe="none",
            project_evidence_job_id=evidence_job.job.job_id,
            source_discovery_job_id=source_job.job.job_id,
        ),
        project_evidence=binding,
        source_discovery=source_binding,
    )
    adapt_specs = TargetAdaptJobSpecStore(tmp_path / "adapt-specs")
    adapt_job = TargetAdaptJobSubmissionService(jobs, adapt_specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="ssh-adapt-remote-arm-metadata",
        now=now,
    )
    observed: list[ProjectEvidence] = []
    observed_source = []

    def execute(bound_spec, _command):  # type: ignore[no-untyped-def]
        loaded = runner._load_bound_project_evidence(bound_spec)
        loaded_source = runner._load_bound_source_discovery(bound_spec)
        observed.append(loaded)
        observed_source.append(loaded_source)
        return AdaptJourneyResult(
            status="DISCOVERY_COMPLETE",
            robot_id="remote-arm",
            enrollment="EXISTING",
            doctor_status="READY",
            evidence=loaded,
            workbench_url="http://127.0.0.1:8080",
        )

    runner = TargetAdaptJobRunner(
        jobs,
        registrations,
        adapt_specs,
        tmp_path / "adapt-artifacts",
        settings=object(),
        project_evidence_artifacts=evidence_artifacts,
        source_discovery_artifacts=source_artifacts,
        journey_runner=execute,
    )
    completed = runner.run(adapt_job.job.job_id)

    assert completed.job.state == DeploymentJobState.COMPLETE
    assert spec.parameters.project_root_location == "TARGET"
    assert spec.parameters.project_root == "/home/robot/ws"
    assert observed[0].observation_mode == "TARGET_METADATA"
    assert observed[0].source_roots == []
    assert observed[0].target_observed_paths == ["README.md"]
    assert observed_source[0].projects[0].packages == ["remote-driver"]
    assert spec.source_discovery is not None
    tui = TargetDeploymentTui(
        registrations,
        jobs,
        TargetBootstrapJobSpecStore(tmp_path / "bootstrap-specs"),
        adapt_specs=adapt_specs,
    )
    tui_job = tui.snapshot(
        TargetDeploymentTuiPage.JOB,
        job_id=adapt_job.job.job_id,
        now=now,
    )
    assert tui_job.rows[0].canonical_cli is not None
    assert "--project-evidence-job-id" in tui_job.rows[0].canonical_cli
    assert "--project-evidence-max-age-s 900" in tui_job.rows[0].canonical_cli
    assert evidence_job.job.job_id in tui_job.rows[0].canonical_cli
    assert "--source-discovery-job-id" in tui_job.rows[0].canonical_cli
    assert "--source-discovery-max-age-s 900" in tui_job.rows[0].canonical_cli
    assert source_job.job.job_id in tui_job.rows[0].canonical_cli

    with pytest.raises(DeploymentJobStateConflict, match="expired"):
        resolve_target_adapt_project_evidence_binding(
            job_id=evidence_job.job.job_id,
            target_id="remote-arm",
            target_registration_sha256=registration_sha256,
            jobs=jobs,
            artifacts=evidence_artifacts,
            max_age_s=900,
            now=now + timedelta(seconds=901),
        )

    tamper_spec = spec.model_copy(
        update={"schema_version": "rolo-target-adapt-job-spec/v2"}
    )
    tamper_job = TargetAdaptJobSubmissionService(jobs, adapt_specs).submit(
        tamper_spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="ssh-adapt-remote-arm-tamper",
        now=now,
    )
    changed_artifact = artifact.model_copy(
        update={"completed_at": artifact.completed_at + timedelta(seconds=1)}
    )
    evidence_artifacts.path(artifact.job_id).write_text(
        changed_artifact.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DeploymentJobStateConflict, match="frozen binding"):
        runner.run(tamper_job.job.job_id)


def test_adapt_job_registration_drift_fails_before_journey(tmp_path: Path) -> None:
    registrations, _ = _registration(tmp_path)
    spec = build_target_adapt_job_spec(
        registrations.load("wheeltec"),
        TargetAdaptJobSubmission(active_probe="none"),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetAdaptJobSpecStore(tmp_path / "specs")
    job = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="adapt-job-wheeltec-drift",
        now=datetime.now(timezone.utc),
    )
    profile = registrations.load("wheeltec").target.model_copy(
        update={"desired_rolo_version": "0.3.0"}
    )
    registrations.registry.save_target(profile)
    calls = 0

    def execute(_spec, _command):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise AssertionError("journey must not run")

    runner = TargetAdaptJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        settings=object(),
        journey_runner=execute,
    )

    failed = runner.run(job.job.job_id)

    assert failed.job.state == DeploymentJobState.FAILED
    assert calls == 0
    with pytest.raises(DeploymentJobStateConflict):
        specs.persist(job.job.job_id, spec.model_copy(update={"workspace_root": "C:/other"}))


def test_adapt_job_restart_without_persisted_result_requires_reconciliation(
    tmp_path: Path,
) -> None:
    registrations, _ = _registration(tmp_path)
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetAdaptJobSpecStore(tmp_path / "adapt-specs")
    spec = build_target_adapt_job_spec(
        registrations.load("wheeltec"),
        TargetAdaptJobSubmission(active_probe="none"),
    )
    job = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="adapt-restart-unknown",
    )
    store.start_step(
        job.job.job_id,
        step_id="adapt-discovery",
        state=DeploymentJobState.DISCOVERING,
    )

    recovered = store.recover_incomplete_jobs()

    assert recovered[0].disposition == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION
    snapshot = DeploymentJobRecoverySnapshot.from_record(store.load_job(job.job.job_id))
    assert snapshot.recovery_disposition == DeploymentRecoveryDisposition.REQUIRES_RECONCILIATION


def test_known_adapt_blocker_survives_restart_recovery_scan(tmp_path: Path) -> None:
    registrations, project = _registration(tmp_path)
    spec = build_target_adapt_job_spec(
        registrations.load("wheeltec"),
        TargetAdaptJobSubmission(active_probe="none"),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    specs = TargetAdaptJobSpecStore(tmp_path / "specs")
    job = TargetAdaptJobSubmissionService(store, specs).submit(
        spec,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="adapt-known-blocker",
    )
    runner = TargetAdaptJobRunner(
        store,
        registrations,
        specs,
        tmp_path / "artifacts",
        settings=object(),
        journey_runner=lambda _spec, _command: _journey(project, status="BLOCKED"),
    )
    blocked = runner.run(job.job.job_id)

    assert blocked.job.state == DeploymentJobState.BLOCKED
    assert store.recover_incomplete_jobs() == []
    unchanged = store.load_job(job.job.job_id)
    assert unchanged.job.blockers == ["ADAPT_JOURNEY_BLOCKED"]
    assert unchanged.recovery_disposition == DeploymentRecoveryDisposition.NONE
