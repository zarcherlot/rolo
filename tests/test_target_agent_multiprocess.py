from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any, cast

from rolo.targets import (
    OrchestratorPlacement,
    SessionAgentAction,
    SessionAgentBroker,
    SessionAgentCommand,
    SessionAgentOpenRequest,
    SessionAgentSessionStore,
    SessionAgentSubject,
    TargetAdaptJobSpecStore,
    TargetBootstrapJobSpecStore,
    TargetBootstrapPublicSubmissionService,
    TargetDeploymentJobRunner,
    TargetDeploymentTui,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
)
from rolo.targets.deployment_jobs import DeploymentJobStore


class _UnusedBootstrapSubmission:
    def submit(self, **_: object) -> None:
        raise AssertionError("multiprocess read test must not submit bootstrap")


def _broker(root: Path) -> SessionAgentBroker:
    registrations = TargetRegistrationService(TargetProfileRegistry(root / "profiles"))
    jobs = DeploymentJobStore(root / "jobs")
    bootstrap_specs = TargetBootstrapJobSpecStore(root / "bootstrap-specs")
    return SessionAgentBroker(
        sessions=SessionAgentSessionStore(root / "agent-sessions"),
        registrations=registrations,
        jobs=jobs,
        adapt_specs=TargetAdaptJobSpecStore(root / "adapt-specs"),
        bootstrap_submissions=cast(
            TargetBootstrapPublicSubmissionService,
            cast(Any, _UnusedBootstrapSubmission()),
        ),
        job_runner=TargetDeploymentJobRunner(jobs, registrations, root / "job-artifacts"),
        workbench=TargetDeploymentTui(registrations, jobs, bootstrap_specs),
    )


def _execute_same_command(
    root_text: str,
    session_id: str,
    start: Any,
    output: Any,
) -> None:
    start.wait(timeout=10)
    try:
        receipt = _broker(Path(root_text)).execute(
            session_id,
            SessionAgentSubject(principal="multiprocess-operator", permissions=[]),
            SessionAgentCommand(sequence=1, action=SessionAgentAction.LIST_TARGETS),
        )
        output.put(
            (
                "ok",
                receipt.command_sha256,
                receipt.status.value,
                [row.identity for row in receipt.projection.rows]
                if receipt.projection is not None
                else [],
            )
        )
    except Exception as exc:  # pragma: no cover - asserted in the parent process
        output.put(("error", type(exc).__name__, str(exc)))


def test_two_controller_processes_replay_one_session_command(tmp_path: Path) -> None:
    root = tmp_path / "multiprocess-controller"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    broker = _broker(root)
    broker.registrations.register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="alpha",
                orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
                transport=TargetTransport.LOCAL,
                workspace_root=str(workspace.resolve()),
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            )
        ),
        principal="fixture",
        idempotency_key="w10-multiprocess-register-alpha",
    )
    session = broker.open_session(
        SessionAgentSubject(principal="multiprocess-operator", permissions=[]),
        SessionAgentOpenRequest(allowed_target_ids=["alpha"], max_tool_calls=2),
        idempotency_key="w10-multiprocess-agent-session",
    )
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(
            target=_execute_same_command,
            args=(str(root), session.session_id, start, output),
        )
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(timeout=15)

        assert all(not process.is_alive() for process in processes)
        assert [process.exitcode for process in processes] == [0, 0]
        results = [output.get(timeout=2) for _ in processes]
        assert results[0][0] == results[1][0] == "ok"
        assert results[0][1:] == results[1][1:]
        assert results[0][-1] == ["alpha"]

        persisted = broker.sessions.load(session.session_id)
        assert persisted.next_sequence == 2
        assert len(persisted.receipts) == 1
        receipt = persisted.receipts[0]
        assert receipt.action == SessionAgentAction.LIST_TARGETS
        assert receipt.status.value == "COMPLETED"
        assert receipt.canonical_cli is None
        assert receipt.projection is not None
        assert [row.identity for row in receipt.projection.rows] == ["alpha"]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        output.close()
        output.join_thread()
