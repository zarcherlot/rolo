from __future__ import annotations

import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from rolo.targets import agent_broker as agent_broker_module
from rolo.targets.adapt_jobs import (
    TargetAdaptJobSpecStore,
    TargetAdaptProjectEvidenceBinding,
)
from rolo.targets.agent_broker import (
    SessionAgentAction,
    SessionAgentBroker,
    SessionAgentCommand,
    SessionAgentOpenRequest,
    SessionAgentSessionStore,
    SessionAgentSubject,
    SessionAgentTurnStatus,
    build_session_agent_tool_catalog,
)
from rolo.targets.agent_runtime import (
    CodexSessionAgentProvider,
    SessionAgentDecisionKind,
    SessionAgentModelDecision,
    SessionAgentProviderError,
    SessionAgentProviderErrorCode,
    SessionAgentRuntime,
    SessionAgentRuntimeStatus,
    SessionAgentTurnRequest,
)
from rolo.targets.bootstrap_jobs import (
    TargetBootstrapJobSpecStore,
    TargetBootstrapPublicSubmissionService,
)
from rolo.targets.connection_assessment import TargetDeploymentJobRunner
from rolo.targets.deployment_jobs import DeploymentJobStore
from rolo.targets.deployment_tui import TargetDeploymentTui
from rolo.targets.models import (
    ApprovalAction,
    DeploymentCommand,
    DeploymentCommandKind,
    InteractionSurface,
    OrchestratorPlacement,
    TargetConnectionProfile,
    TargetProfile,
    TargetTransport,
    TargetTrustLevel,
)
from rolo.targets.project_evidence_jobs import (
    TargetProjectEvidenceIntentStore,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceSubmissionService,
)
from rolo.targets.registration import (
    TargetRegistrationRequest,
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.registry import TargetProfileRegistry
from rolo.targets.source_discovery_jobs import (
    TargetSourceDiscoveryIntentStore,
    TargetSourceDiscoveryJobSpecStore,
    TargetSourceDiscoverySubmissionService,
)


class _UnexpectedBootstrap:
    def submit(self, **_: object) -> None:
        raise AssertionError("bootstrap service must not be reached")


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


def _register_local(
    registrations: TargetRegistrationService,
    tmp_path: Path,
    target_id: str,
) -> None:
    workspace = tmp_path / f"{target_id}-workspace"
    workspace.mkdir()
    registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id=target_id,
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.LOCAL,
                workspace_root=str(workspace.absolute()),
                desired_rolo_version="0.1.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="fixture",
        idempotency_key=f"agent-broker-register-{target_id}",
    )


def _broker(
    tmp_path: Path,
    *,
    clock: _Clock | None = None,
) -> tuple[SessionAgentBroker, TargetRegistrationService, DeploymentJobStore]:
    registrations = TargetRegistrationService(
        TargetProfileRegistry(tmp_path / "profiles")
    )
    _register_local(registrations, tmp_path, "alpha")
    _register_local(registrations, tmp_path, "beta")
    jobs = DeploymentJobStore(tmp_path / "jobs")
    bootstrap_specs = TargetBootstrapJobSpecStore(tmp_path / "bootstrap-specs")
    workbench = TargetDeploymentTui(registrations, jobs, bootstrap_specs)
    broker = SessionAgentBroker(
        sessions=SessionAgentSessionStore(tmp_path / "agent-sessions"),
        registrations=registrations,
        jobs=jobs,
        adapt_specs=TargetAdaptJobSpecStore(tmp_path / "adapt-specs"),
        bootstrap_submissions=cast(
            TargetBootstrapPublicSubmissionService,
            cast(Any, _UnexpectedBootstrap()),
        ),
        job_runner=TargetDeploymentJobRunner(
            jobs,
            registrations,
            tmp_path / "job-artifacts",
        ),
        workbench=workbench,
        now=clock or _Clock(),
    )
    return broker, registrations, jobs


def _subject(*permissions: str, principal: str = "operator@example.com") -> SessionAgentSubject:
    return SessionAgentSubject(
        principal=principal,
        permissions=sorted(permissions),
    )


def test_agent_catalog_has_no_shell_credentials_identity_or_approval_decision() -> None:
    catalog = build_session_agent_tool_catalog()

    assert catalog.raw_shell_available is False
    assert catalog.approval_decision_available is False
    assert catalog.credential_material_available is False
    assert catalog.model_generated_identity_available is False
    assert catalog.raw_target_output_available is False
    assert {tool.action for tool in catalog.tools} == set(SessionAgentAction)
    assert "APPROVAL_DECIDE" not in {tool.action.value for tool in catalog.tools}
    assert all(
        "principal" not in tool.allowed_parameters
        and "idempotency_key" not in tool.allowed_parameters
        and "shell" not in tool.allowed_parameters
        and "argv" not in tool.allowed_parameters
        for tool in catalog.tools
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SessionAgentCommand.model_validate(
            {
                "sequence": 1,
                "action": "LIST_TARGETS",
                "shell": "robotctl target approval decide",
            }
        )
    with pytest.raises(ValidationError, match="does not accept"):
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.LIST_TARGETS,
            target_id="alpha",
        )


def test_read_session_filters_targets_and_cannot_create_jobs(tmp_path: Path) -> None:
    broker, _, jobs = _broker(tmp_path)
    subject = _subject()
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(
            allowed_target_ids=["alpha"],
            max_tool_calls=2,
        ),
        idempotency_key="agent-open-read-alpha",
    )

    listed = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(sequence=1, action=SessionAgentAction.LIST_TARGETS),
    )

    assert listed.status == SessionAgentTurnStatus.COMPLETED
    assert listed.projection is not None
    assert [row.identity for row in listed.projection.rows] == ["alpha"]
    assert all(row.canonical_cli is None for row in listed.projection.rows)
    with pytest.raises(PermissionError, match="lacks permission"):
        broker.execute(
            session.session_id,
            subject,
            SessionAgentCommand(
                sequence=2,
                action=SessionAgentAction.ASSESS_CONNECTION,
                target_id="alpha",
            ),
        )
    assert jobs.list_jobs() == []
    assert broker.sessions.load(session.session_id).next_sequence == 2


def test_broker_derives_principal_idempotency_and_audits_each_command(
    tmp_path: Path,
) -> None:
    broker, _, jobs = _broker(tmp_path)
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(
            allowed_target_ids=["alpha"],
            max_tool_calls=2,
        ),
        idempotency_key="agent-open-write-alpha",
    )

    submitted = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.ASSESS_CONNECTION,
            target_id="alpha",
        ),
    )
    assert submitted.status == SessionAgentTurnStatus.SUBMITTED
    assert submitted.job_id is not None
    created = jobs.load_job(submitted.job_id)
    assert created.job.command.requested_by == subject.principal
    assert created.job.command.interaction_surface == InteractionSurface.NATURAL_LANGUAGE
    assert created.job.command.idempotency_key.startswith(
        f"agent:{session.session_id.removeprefix('agent-session-')}:1:"
    )
    assert created.job.command.canonical_sha256() == created.job.command.model_copy(
        update={"interaction_surface": InteractionSurface.CLI}
    ).canonical_sha256()

    repeated = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.ASSESS_CONNECTION,
            target_id="alpha",
        ),
    )
    assert repeated == submitted
    assert len(jobs.list_jobs()) == 1
    with pytest.raises(ValueError, match="another command"):
        broker.execute(
            session.session_id,
            subject,
            SessionAgentCommand(
                sequence=1,
                action=SessionAgentAction.GET_JOB,
                job_id=submitted.job_id,
            ),
        )
    read = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=2,
            action=SessionAgentAction.GET_JOB,
            job_id=submitted.job_id,
        ),
    )
    assert read.status == SessionAgentTurnStatus.COMPLETED
    persisted = broker.sessions.load(session.session_id)
    assert [item.sequence for item in persisted.receipts] == [1, 2]
    assert persisted.next_sequence == 3
    with pytest.raises(RuntimeError, match="budget"):
        broker.execute(
            session.session_id,
            subject,
            SessionAgentCommand(sequence=3, action=SessionAgentAction.LIST_TARGETS),
        )


def test_broker_enforces_target_allowlist_before_job_access(tmp_path: Path) -> None:
    broker, registrations, jobs = _broker(tmp_path)
    beta = registrations.load("beta")
    job = jobs.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.ASSESS_CONNECTION,
            target_id="beta",
            run_adapter_agent=False,
            requested_by="fixture",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="agent-broker-beta-assessment",
            parameters_sha256=target_connection_binding_sha256(
                beta.target,
                beta.connection,
            ),
        )
    )
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-open-allowlist-alpha",
    )

    with pytest.raises(PermissionError, match="allowlist"):
        broker.execute(
            session.session_id,
            subject,
            SessionAgentCommand(
                sequence=1,
                action=SessionAgentAction.GET_JOB,
                job_id=job.job.job_id,
            ),
        )
    assert broker.sessions.load(session.session_id).receipts == []


def test_broker_rejects_self_approval_and_subject_substitution(tmp_path: Path) -> None:
    broker, _, _ = _broker(tmp_path)
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-open-approval-alpha",
    )

    with pytest.raises(PermissionError, match="requester as approver"):
        broker.execute(
            session.session_id,
            subject,
            SessionAgentCommand(
                sequence=1,
                action=SessionAgentAction.SUBMIT_BOOTSTRAP,
                target_id="alpha",
                package_ref="rolo-target@" + "a" * 64,
                approver_principal=subject.principal,
            ),
        )
    with pytest.raises(PermissionError, match="another principal"):
        broker.execute(
            session.session_id,
            _subject("target:write", principal="attacker@example.com"),
            SessionAgentCommand(sequence=1, action=SessionAgentAction.LIST_TARGETS),
        )
    assert broker.sessions.load(session.session_id).receipts == []


def test_broker_hands_project_evidence_to_an_external_approver(
    tmp_path: Path,
) -> None:
    broker, registrations, jobs = _broker(tmp_path)
    broker.project_evidence_submissions = TargetProjectEvidenceSubmissionService(
        store=jobs,
        specs=TargetProjectEvidenceJobSpecStore(tmp_path / "project-evidence-specs"),
        intents=TargetProjectEvidenceIntentStore(
            tmp_path / "project-evidence-intents"
        ),
        registrations=registrations,
    )
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-open-project-evidence-alpha",
    )

    submitted = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.SUBMIT_PROJECT_EVIDENCE,
            target_id="alpha",
            approver_principal="reviewer@example.com",
        ),
    )

    assert submitted.status == SessionAgentTurnStatus.APPROVAL_REQUIRED
    assert submitted.job_id is not None
    assert submitted.approval_id is not None
    assert submitted.canonical_cli is not None
    assert "target project-evidence submit" in submitted.canonical_cli
    assert "--approver reviewer@example.com" in submitted.canonical_cli
    job = jobs.load_job(submitted.job_id)
    approval = jobs.load_approval_request(submitted.approval_id)
    assert job.job.command.command == DeploymentCommandKind.COLLECT_EVIDENCE
    assert approval.action == ApprovalAction.READ_PROJECT_EVIDENCE
    assert approval.risk == "R2"
    assert approval.approver_principal == "reviewer@example.com"

    self_approval_session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-open-project-evidence-self-approval",
    )
    with pytest.raises(PermissionError, match="requester as approver"):
        broker.execute(
            self_approval_session.session_id,
            subject,
            SessionAgentCommand(
                sequence=1,
                action=SessionAgentAction.SUBMIT_PROJECT_EVIDENCE,
                target_id="alpha",
                approver_principal=subject.principal,
            ),
        )


def test_broker_hands_source_discovery_to_an_external_approver(
    tmp_path: Path,
) -> None:
    broker, registrations, jobs = _broker(tmp_path)
    broker.source_discovery_submissions = TargetSourceDiscoverySubmissionService(
        store=jobs,
        specs=TargetSourceDiscoveryJobSpecStore(tmp_path / "source-discovery-specs"),
        intents=TargetSourceDiscoveryIntentStore(
            tmp_path / "source-discovery-intents"
        ),
        registrations=registrations,
    )
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-open-source-discovery-alpha",
    )

    submitted = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.SUBMIT_SOURCE_DISCOVERY,
            target_id="alpha",
            approver_principal="reviewer@example.com",
        ),
    )

    assert submitted.status == SessionAgentTurnStatus.APPROVAL_REQUIRED
    assert submitted.job_id is not None
    assert submitted.approval_id is not None
    assert submitted.canonical_cli is not None
    assert "target source-discovery submit" in submitted.canonical_cli
    approval = jobs.load_approval_request(submitted.approval_id)
    assert approval.action == ApprovalAction.ANALYZE_PROJECT_SOURCE
    assert approval.risk == "R2"
    assert approval.approver_principal == "reviewer@example.com"


def test_broker_submits_ssh_adapt_from_a_bound_project_evidence_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, registrations, jobs = _broker(tmp_path)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("remote ssh-ed25519 AAAATEST\n", encoding="utf-8")
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
                user="robot",
                credential_ref="file://ssh/remote-arm",
                known_hosts_path=str(known_hosts.absolute()),
                trust_level=TargetTrustLevel.STRICT,
                expected_host_key_sha256="SHA256:" + "A" * 43,
            ),
        ),
        principal="fixture",
        idempotency_key="agent-register-remote-arm",
    )
    evidence_job_id = "deployment-" + "c" * 32
    observed_at = broker.now()

    def resolve(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["job_id"] == evidence_job_id
        return TargetAdaptProjectEvidenceBinding(
            job_id=evidence_job_id,
            artifact_sha256="1" * 64,
            command_sha256="2" * 64,
            target_id="remote-arm",
            target_registration_sha256=kwargs["target_registration_sha256"],
            workspace_sha256="3" * 64,
            workspace_manifest_sha256="4" * 64,
            observed_paths=["README.md"],
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=15),
        )

    monkeypatch.setattr(
        agent_broker_module,
        "resolve_target_adapt_project_evidence_binding",
        resolve,
    )
    broker.project_evidence_artifacts = cast(Any, object())
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["remote-arm"]),
        idempotency_key="agent-open-ssh-adapt-remote-arm",
    )

    receipt = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.SUBMIT_ADAPT,
            target_id="remote-arm",
            project_evidence_job_id=evidence_job_id,
        ),
    )

    assert receipt.status == SessionAgentTurnStatus.SUBMITTED
    assert receipt.job_id is not None
    assert receipt.canonical_cli is not None
    assert "--active-probe none" in receipt.canonical_cli
    assert f"--project-evidence-job-id {evidence_job_id}" in receipt.canonical_cli
    created = jobs.load_job(receipt.job_id)
    spec = broker.adapt_specs.load(created.job.job_id)
    assert spec.parameters.project_root_location == "TARGET"
    assert spec.project_evidence is not None
    assert spec.project_evidence.job_id == evidence_job_id


def test_cancel_and_expiry_stop_further_commands(tmp_path: Path) -> None:
    clock = _Clock()
    broker, _, _ = _broker(tmp_path, clock=clock)
    subject = _subject("target:write")
    cancelled = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"], timeout_s=10),
        idempotency_key="agent-open-cancelled-alpha",
    )
    broker.cancel_session(cancelled.session_id, subject)
    with pytest.raises(RuntimeError, match="cancelled"):
        broker.execute(
            cancelled.session_id,
            subject,
            SessionAgentCommand(sequence=1, action=SessionAgentAction.LIST_TARGETS),
        )

    expiring = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"], timeout_s=10),
        idempotency_key="agent-open-expiring-alpha",
    )
    clock.value += timedelta(seconds=10)
    with pytest.raises(TimeoutError, match="expired"):
        broker.execute(
            expiring.session_id,
            subject,
            SessionAgentCommand(sequence=1, action=SessionAgentAction.LIST_TARGETS),
        )


def test_cancel_interrupts_active_job_across_broker_instances(tmp_path: Path) -> None:
    broker, _, jobs = _broker(tmp_path)
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"], max_tool_calls=2),
        idempotency_key="agent-open-active-cancel-alpha",
    )
    submitted = broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.ASSESS_CONNECTION,
            target_id="alpha",
        ),
    )
    assert submitted.job_id is not None
    entered = threading.Event()

    class _CancellableRunner:
        def run(self, job_id: str, *, cancel_event: object):  # type: ignore[no-untyped-def]
            entered.set()
            assert cast(Any, cancel_event).wait_for_cancel()
            jobs.request_cancel(job_id)
            return jobs.resolve_cancel(job_id, remote_termination_confirmed=True)

    class _PollingCancellation:
        def __init__(self, value: object) -> None:
            self.value = value

        def wait_for_cancel(self) -> bool:
            for _ in range(200):
                if cast(Any, self.value).is_set():
                    return True
                threading.Event().wait(0.01)
            return False

    class _RunnerAdapter:
        def run(self, job_id: str, *, cancel_event: object):  # type: ignore[no-untyped-def]
            return _CancellableRunner().run(
                job_id,
                cancel_event=_PollingCancellation(cancel_event),
            )

    broker.job_runner = cast(TargetDeploymentJobRunner, cast(Any, _RunnerAdapter()))
    cancelling_broker = SessionAgentBroker(
        sessions=SessionAgentSessionStore(broker.sessions.root),
        registrations=broker.registrations,
        jobs=broker.jobs,
        adapt_specs=broker.adapt_specs,
        bootstrap_submissions=broker.bootstrap_submissions,
        job_runner=broker.job_runner,
        workbench=broker.workbench,
        now=broker.now,
    )
    outcome: list[object] = []

    def execute() -> None:
        outcome.append(
            broker.execute(
                session.session_id,
                subject,
                SessionAgentCommand(
                    sequence=2,
                    action=SessionAgentAction.RUN_JOB,
                    job_id=submitted.job_id,
                ),
            )
        )

    worker = threading.Thread(target=execute)
    worker.start()
    assert entered.wait(timeout=2)
    cancelled = cancelling_broker.cancel_session(session.session_id, subject)
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert cancelled.cancelled_at is not None
    assert len(outcome) == 1
    receipt = cast(Any, outcome[0])
    assert receipt.status == SessionAgentTurnStatus.CANCEL_REQUESTED
    persisted = broker.sessions.load(session.session_id)
    assert persisted.cancelled_at is not None
    assert [item.sequence for item in persisted.receipts] == [1, 2]


class _ScriptedProvider:
    def __init__(self, decisions: list[SessionAgentModelDecision]) -> None:
        self.decisions = decisions
        self.observed_sequences: list[int] = []

    def decide(self, *, message: str, catalog: object, session: object):  # type: ignore[no-untyped-def]
        assert message
        assert catalog
        self.observed_sequences.append(session.next_sequence)
        return self.decisions.pop(0)


def test_runtime_lets_provider_choose_commands_without_an_intent_plan(
    tmp_path: Path,
) -> None:
    broker, _, jobs = _broker(tmp_path)
    provider = _ScriptedProvider(
        [
            SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.COMMAND,
                command=SessionAgentCommand(
                    sequence=8,
                    action=SessionAgentAction.ASSESS_CONNECTION,
                    target_id="alpha",
                ),
            ),
            SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.COMMAND,
                command=SessionAgentCommand(
                    sequence=8,
                    action=SessionAgentAction.LIST_TARGETS,
                ),
            ),
            SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.FINAL,
                message="连接评估任务已经建立。",
            ),
        ]
    )
    runtime = SessionAgentRuntime(broker, provider)

    result = runtime.run(
        _subject("target:write"),
        SessionAgentTurnRequest(
            message="评估 alpha 的连接并告诉我结果",
            allowed_target_ids=["alpha"],
            max_tool_calls=3,
        ),
        idempotency_key="agent-runtime-alpha-assess",
    )

    assert result.status == SessionAgentRuntimeStatus.COMPLETED
    assert result.response == "连接评估任务已经建立。"
    assert [item.sequence for item in result.receipts] == [1, 2]
    assert provider.observed_sequences == [1, 2, 3]
    assert len(jobs.list_jobs()) == 1
    repeated = runtime.run(
        _subject("target:write"),
        SessionAgentTurnRequest(
            message="评估 alpha 的连接并告诉我结果",
            allowed_target_ids=["alpha"],
            max_tool_calls=3,
        ),
        idempotency_key="agent-runtime-alpha-assess",
    )
    assert repeated == result
    assert provider.observed_sequences == [1, 2, 3]
    with pytest.raises(ValueError, match="another open request"):
        runtime.run(
            _subject("target:write"),
            SessionAgentTurnRequest(
                message="改为执行另一项工作",
                allowed_target_ids=["alpha"],
                max_tool_calls=3,
            ),
            idempotency_key="agent-runtime-alpha-assess",
        )


def test_runtime_stops_on_clarification_budget_and_provider_failure(
    tmp_path: Path,
) -> None:
    broker, _, _ = _broker(tmp_path)
    subject = _subject()
    clarification = SessionAgentRuntime(
        broker,
        _ScriptedProvider(
            [
                SessionAgentModelDecision(
                    kind=SessionAgentDecisionKind.CLARIFY,
                    message="请选择 alpha 目标。",
                )
            ]
        ),
    ).run(
        subject,
        SessionAgentTurnRequest(message="检查目标", allowed_target_ids=["alpha"]),
        idempotency_key="agent-runtime-clarify",
    )
    assert clarification.status == SessionAgentRuntimeStatus.NEEDS_CLARIFICATION
    assert clarification.receipts == []

    budget = SessionAgentRuntime(
        broker,
        _ScriptedProvider(
            [
                SessionAgentModelDecision(
                    kind=SessionAgentDecisionKind.COMMAND,
                    command=SessionAgentCommand(
                        sequence=1,
                        action=SessionAgentAction.LIST_TARGETS,
                    ),
                ),
                SessionAgentModelDecision(
                    kind=SessionAgentDecisionKind.COMMAND,
                    command=SessionAgentCommand(
                        sequence=2,
                        action=SessionAgentAction.LIST_BLOCKERS,
                    ),
                ),
            ]
        ),
    ).run(
        subject,
        SessionAgentTurnRequest(
            message="持续检查",
            allowed_target_ids=["alpha"],
            max_tool_calls=2,
        ),
        idempotency_key="agent-runtime-budget",
    )
    assert budget.status == SessionAgentRuntimeStatus.ACTION_BUDGET_EXHAUSTED
    assert len(budget.receipts) == 2

    class _FailedProvider:
        def decide(self, **_: object) -> SessionAgentModelDecision:
            raise SessionAgentProviderError(SessionAgentProviderErrorCode.TIMED_OUT)

    failed = SessionAgentRuntime(broker, _FailedProvider()).run(
        subject,
        SessionAgentTurnRequest(message="检查", allowed_target_ids=["alpha"]),
        idempotency_key="agent-runtime-failed",
    )
    assert failed.status == SessionAgentRuntimeStatus.FAILED
    assert failed.provider_error_code == SessionAgentProviderErrorCode.TIMED_OUT
    assert failed.receipts == []


def test_runtime_observes_persisted_cancellation_before_calling_provider(
    tmp_path: Path,
) -> None:
    broker, _, _ = _broker(tmp_path)
    subject = _subject()
    request = SessionAgentTurnRequest(
        message="检查 alpha",
        allowed_target_ids=["alpha"],
    )
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(
            allowed_target_ids=["alpha"],
            conversation_sha256=request.canonical_sha256(),
        ),
        idempotency_key="agent-runtime-cancel-before-provider",
    )
    broker.cancel_session(session.session_id, subject)
    provider = _ScriptedProvider(
        [
            SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.FINAL,
                message="不应调用。",
            )
        ]
    )

    result = SessionAgentRuntime(broker, provider).run(
        subject,
        request,
        idempotency_key="agent-runtime-cancel-before-provider",
    )

    assert result.status == SessionAgentRuntimeStatus.CANCELLED
    assert result.provider_calls == 0
    assert provider.observed_sequences == []


def test_runtime_turn_guard_prevents_duplicate_provider_calls(
    tmp_path: Path,
) -> None:
    broker, _, _ = _broker(tmp_path)
    subject = _subject()
    request = SessionAgentTurnRequest(
        message="列出 alpha",
        allowed_target_ids=["alpha"],
    )
    entered = threading.Event()
    release = threading.Event()
    calls = [0, 0]

    class _BlockingProvider:
        def decide(self, **_: object) -> SessionAgentModelDecision:
            calls[0] += 1
            entered.set()
            assert release.wait(timeout=2)
            return SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.FINAL,
                message="完成。",
            )

    class _DuplicateProvider:
        def decide(self, **_: object) -> SessionAgentModelDecision:
            calls[1] += 1
            raise AssertionError("duplicate runtime must replay the persisted turn")

    runtimes = [
        SessionAgentRuntime(broker, _BlockingProvider()),
        SessionAgentRuntime(broker, _DuplicateProvider()),
    ]
    outcomes: list[object] = []

    def run(runtime: SessionAgentRuntime) -> None:
        outcomes.append(
            runtime.run(
                subject,
                request,
                idempotency_key="agent-runtime-concurrent-replay",
            )
        )

    first = threading.Thread(target=run, args=(runtimes[0],))
    second = threading.Thread(target=run, args=(runtimes[1],))
    first.start()
    assert entered.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=3)
    second.join(timeout=3)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(outcomes) == 2
    assert outcomes[0] == outcomes[1]
    assert calls == [1, 0]


def test_codex_provider_uses_ephemeral_read_only_secret_scrubbed_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _, _ = _broker(tmp_path)
    subject = _subject("target:write")
    session = broker.open_session(
        subject,
        SessionAgentOpenRequest(allowed_target_ids=["alpha"]),
        idempotency_key="agent-provider-isolation",
    )
    broker.execute(
        session.session_id,
        subject,
        SessionAgentCommand(
            sequence=1,
            action=SessionAgentAction.ASSESS_CONNECTION,
            target_id="alpha",
        ),
    )
    session = broker.get_session(session.session_id, subject)
    monkeypatch.setenv("ROLO_API_TOKEN", "must-not-enter-codex")
    monkeypatch.setenv("SSH_PRIVATE_KEY", "must-not-enter-codex")
    observed: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["environment"] = kwargs["env"]
        observed["prompt"] = kwargs["input"]
        observed["workspace"] = kwargs["cwd"]
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.FINAL,
                message="没有需要执行的动作。",
            ).model_dump_json(),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="ignored", stderr="ignored")

    decision = CodexSessionAgentProvider(
        api_key="dedicated-session-agent-key",
        model="gpt-5-codex",
        executable="codex-test",
        process_runner=run,
    ).decide(
        message="列出 alpha",
        catalog=broker.catalog,
        session=session,
    )

    command = cast(list[str], observed["command"])
    environment = cast(dict[str, str], observed["environment"])
    assert decision.kind == SessionAgentDecisionKind.FINAL
    assert command[:2] == ["codex-test", "exec"]
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert 'shell_environment_policy.inherit="none"' in command
    assert environment["ROLO_SESSION_AGENT_API_KEY"] == "dedicated-session-agent-key"
    assert "ROLO_API_TOKEN" not in environment
    assert "SSH_PRIVATE_KEY" not in environment
    assert "approval_decision_available" in cast(str, observed["prompt"])
    assert "robotctl" not in cast(str, observed["prompt"])
    assert not cast(Path, observed["workspace"]).exists()
