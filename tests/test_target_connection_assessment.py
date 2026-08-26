from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rolo.targets import (
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    DeploymentStepStatus,
    InteractionSurface,
    OrchestratorPlacement,
    TargetConnectionAssessmentArtifact,
    TargetConnectionAssessmentFailureCode,
    TargetConnectionAssessmentStatus,
    TargetDeploymentJobRunner,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    target_connection_binding_sha256,
)

NOW = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


class _FakeExecutor:
    def __init__(self, *, succeed: bool = True, cancelled: bool = False) -> None:
        self.succeed = succeed
        self.cancelled = cancelled
        self.calls = 0

    def inspect(
        self,
        request: TargetInspectionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetInspectionResult:
        self.calls += 1
        error_code = None
        if not self.succeed:
            error_code = (
                TargetExecutionErrorCode.CANCELLED
                if self.cancelled
                else TargetExecutionErrorCode.CONNECTION_FAILED
            )
        return TargetInspectionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            executor_kind=TargetExecutorKind.LOCAL,
            status=(
                TargetExecutionStatus.SUCCEEDED
                if self.succeed
                else TargetExecutionStatus.FAILED
            ),
            error_code=error_code,
            exit_code=0 if self.succeed else None,
            stdout='{"ok":true}' if self.succeed else "",
            stderr="connection unavailable" if not self.succeed else "",
            cancelled=self.cancelled,
            started_at=NOW,
            finished_at=NOW,
        )


def _setup(
    tmp_path: Path,
    *,
    active_probe: str = "runtime-readonly",
    command_kind: DeploymentCommandKind = DeploymentCommandKind.ASSESS_CONNECTION,
) -> tuple[DeploymentJobStore, TargetRegistrationService, str]:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    service = TargetRegistrationService(registry)
    target = TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.1.0",
        trust_level=TargetTrustLevel.STRICT,
    )
    service.register(
        TargetRegistrationRequest(target=target),
        principal="operator@example.com",
        idempotency_key="assessment-register-wheeltec",
        now=NOW,
    )
    registration = service.load("wheeltec")
    command = DeploymentCommand(
        command=command_kind,
        target_id="wheeltec",
        workspace_root=(
            "/home/robot/wheeltec_ws"
            if command_kind
            in {
                DeploymentCommandKind.BOOTSTRAP,
                DeploymentCommandKind.ADAPT,
                DeploymentCommandKind.BOOTSTRAP_AND_ADAPT,
            }
            else None
        ),
        active_probe=active_probe,
        run_adapter_agent=False,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="assessment-job-wheeltec-0001",
        parameters_sha256=target_connection_binding_sha256(
            registration.target,
            registration.connection,
        ),
    )
    store = DeploymentJobStore(tmp_path / "jobs")
    record = store.create_job(
        command,
        job_id="deployment-" + "a" * 32,
        now=NOW,
    )
    return store, service, record.job.job_id


def _runner(
    tmp_path: Path,
    store: DeploymentJobStore,
    service: TargetRegistrationService,
    executor: _FakeExecutor | None = None,
) -> TargetDeploymentJobRunner:
    return TargetDeploymentJobRunner(
        store,
        service,
        tmp_path / "artifacts",
        executor_factory=(lambda _profile: executor) if executor is not None else None,
    )


def _artifact(tmp_path: Path, job_id: str) -> TargetConnectionAssessmentArtifact:
    return TargetConnectionAssessmentArtifact.model_validate_json(
        (tmp_path / "artifacts" / job_id / "connection-assessment.json").read_text(
            encoding="utf-8"
        )
    )


def test_profile_only_assessment_completes_without_constructing_executor(
    tmp_path: Path,
) -> None:
    store, service, job_id = _setup(tmp_path, active_probe="none")
    runner = TargetDeploymentJobRunner(
        store,
        service,
        tmp_path / "artifacts",
        executor_factory=lambda _profile: pytest.fail("executor must not be constructed"),
    )

    record = runner.run(job_id)
    artifact = _artifact(tmp_path, job_id)

    assert record.job.state == DeploymentJobState.COMPLETE
    assert artifact.status == TargetConnectionAssessmentStatus.PROFILE_VALIDATED
    assert record.checkpoints[0].status == DeploymentStepStatus.COMPLETE
    assert record.final_artifact_refs == [
        f"artifact://deployment-jobs/{job_id}/connection-assessment.json"
    ]


def test_successful_assessment_persists_bound_artifact_and_is_idempotent(
    tmp_path: Path,
) -> None:
    store, service, job_id = _setup(tmp_path)
    executor = _FakeExecutor()
    runner = _runner(tmp_path, store, service, executor)

    first = runner.run(job_id)
    second = runner.run(job_id)
    artifact = _artifact(tmp_path, job_id)

    assert first == second
    assert first.job.state == DeploymentJobState.COMPLETE
    assert artifact.status == TargetConnectionAssessmentStatus.SUCCEEDED
    assert artifact.command_sha256 == first.job.command_sha256
    assert executor.calls == 1


def test_failed_inspection_records_confirmed_failure_and_artifact(
    tmp_path: Path,
) -> None:
    store, service, job_id = _setup(tmp_path, active_probe="help")
    executor = _FakeExecutor(succeed=False)

    record = _runner(tmp_path, store, service, executor).run(job_id)
    artifact = _artifact(tmp_path, job_id)

    assert record.job.state == DeploymentJobState.FAILED
    assert record.checkpoints[0].status == DeploymentStepStatus.FAILED
    assert artifact.status == TargetConnectionAssessmentStatus.FAILED
    assert artifact.inspection_result is not None
    assert artifact.inspection_result.error_code == TargetExecutionErrorCode.CONNECTION_FAILED
    assert record.checkpoints[0].artifact_refs == [
        f"artifact://deployment-jobs/{job_id}/connection-assessment.json"
    ]
    assert record.final_artifact_refs == []


def test_cancellation_before_or_during_read_only_probe_is_terminal(
    tmp_path: Path,
) -> None:
    store, service, job_id = _setup(tmp_path)
    cancel = threading.Event()
    cancel.set()
    executor = _FakeExecutor()

    before = _runner(tmp_path, store, service, executor).run(
        job_id,
        cancel_event=cancel,
    )

    assert before.job.state == DeploymentJobState.CANCELLED
    assert executor.calls == 0


def test_artifact_and_completed_step_recover_without_reexecuting_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, service, job_id = _setup(tmp_path)
    executor = _FakeExecutor()
    runner = _runner(tmp_path, store, service, executor)
    complete_step = store.complete_step
    crashed = False

    def complete_then_crash(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal crashed
        result = complete_step(*args, **kwargs)
        if not crashed:
            crashed = True
            raise RuntimeError("simulated controller crash")
        return result

    monkeypatch.setattr(store, "complete_step", complete_then_crash)
    with pytest.raises(RuntimeError, match="simulated controller crash"):
        runner.run(job_id)
    monkeypatch.setattr(store, "complete_step", complete_step)

    recovered = runner.run(job_id)

    assert recovered.job.state == DeploymentJobState.COMPLETE
    assert recovered.checkpoints[0].status == DeploymentStepStatus.COMPLETE
    assert executor.calls == 1


def test_registration_drift_fails_closed_with_bounded_artifact(tmp_path: Path) -> None:
    store, service, job_id = _setup(tmp_path)
    current = service.load("wheeltec").target
    service.registry.save_target(current.model_copy(update={"desired_rolo_version": "0.2.0"}))
    executor = _FakeExecutor()

    record = _runner(tmp_path, store, service, executor).run(job_id)
    artifact = _artifact(tmp_path, job_id)

    assert record.job.state == DeploymentJobState.FAILED
    assert artifact.failure_code == (
        TargetConnectionAssessmentFailureCode.TARGET_REGISTRATION_CHANGED
    )
    assert artifact.observed_target_registration_sha256 is not None
    assert artifact.inspection_result is None
    assert executor.calls == 0


def test_runner_error_is_secret_closed_and_unsupported_kind_is_not_mutated(
    tmp_path: Path,
) -> None:
    store, service, job_id = _setup(tmp_path)

    def explode(_profile: TargetProfile):
        raise RuntimeError("token=do-not-persist")

    failed = TargetDeploymentJobRunner(
        store,
        service,
        tmp_path / "artifacts",
        executor_factory=explode,
    ).run(job_id)
    artifact_text = (
        tmp_path / "artifacts" / job_id / "connection-assessment.json"
    ).read_text(encoding="utf-8")

    assert failed.job.state == DeploymentJobState.FAILED
    assert "do-not-persist" not in artifact_text
    assert _artifact(tmp_path, job_id).failure_code == (
        TargetConnectionAssessmentFailureCode.RUNNER_ERROR
    )

    other_store, other_service, other_job_id = _setup(
        tmp_path / "other",
        command_kind=DeploymentCommandKind.BOOTSTRAP,
    )
    with pytest.raises(DeploymentJobStateConflict, match="handler is unavailable"):
        _runner(tmp_path / "other", other_store, other_service).run(other_job_id)
    assert other_store.load_job(other_job_id).job.state == DeploymentJobState.CREATED
