from __future__ import annotations

import json
import os
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner

from rolo.cli import app
from rolo.commands import target as target_commands
from rolo.core.config import get_settings
from rolo.targets import (
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    SessionAgentRuntimeStatus,
    SessionAgentSubject,
    SessionAgentTurnResult,
    SshTargetExecutor,
    TargetAdaptJobSpecStore,
    TargetAdaptProjectEvidenceBinding,
    TargetArchitecture,
    TargetConnectionProfile,
    TargetHostProvisioningExecutionResult,
    TargetHostProvisioningExecutionStatus,
    TargetPackageBuilder,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
)


def _invoke(args: list[str]) -> tuple[int, dict[str, object]]:
    result = CliRunner().invoke(app, args)
    return result.exit_code, json.loads(result.stdout)


def _add_local_target(workspace: Path) -> tuple[int, dict[str, object]]:
    return _invoke(
        [
            "target",
            "add",
            "wheeltec",
            "--local",
            "--workspace",
            str(workspace),
            "--desired-version",
            "0.1.0",
            "--idempotency-key",
            "target-cli-register-wheeltec",
        ]
    )


def test_target_job_cli_is_idempotent_queryable_and_cancellable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    workspace = tmp_path / "wheeltec_ws"
    workspace.mkdir()
    (workspace / "README.md").write_text("wheeltec", encoding="utf-8")
    registration_code, registration = _add_local_target(workspace)
    args = [
        "target",
        "adapt",
        "submit",
        "--target",
        "wheeltec",
        "--idempotency-key",
        "deployment-cli-adapt-1",
        "--requested-by",
        "operator@example.com",
        "--active-probe",
        "none",
        "--no-run-adapter-agent",
    ]

    first_code, first = _invoke(args)
    second_code, second = _invoke(args)
    job_id = first["job"]["job"]["job_id"]  # type: ignore[index]

    get_code, loaded = _invoke(["target", "job", "get", "--job-id", str(job_id)])
    events_code, events = _invoke(
        ["target", "job", "events", "--job-id", str(job_id), "--limit", "10"]
    )
    cancel_code, cancelled = _invoke(
        ["target", "job", "cancel", "--job-id", str(job_id)]
    )
    repeated_cancel_code, repeated_cancel = _invoke(
        ["target", "job", "cancel", "--job-id", str(job_id)]
    )
    assessment_code, assessment = _invoke(
        [
            "target",
            "connect",
            "assess",
            "--target",
            "wheeltec",
            "--idempotency-key",
            "target-cli-assess-wheeltec",
            "--active-probe",
            "none",
        ]
    )
    assessment_job_id = assessment["job"]["job"]["job_id"]  # type: ignore[index]
    run_code, executed = _invoke(
        ["target", "job", "run", "--job-id", str(assessment_job_id)]
    )
    tui = CliRunner().invoke(app, ["target", "tui", "--page", "fleet", "--once"])
    get_settings.cache_clear()

    assert registration_code == 0
    assert registration["status"] == "CREATED"
    assert first_code == second_code == get_code == events_code == cancel_code == 0
    assert repeated_cancel_code == 0
    assert assessment_code == 0
    assert run_code == 0
    assert tui.exit_code == 0
    assert "Rolo Deployment Workbench | Fleet" in tui.stdout
    assert "wheeltec" in tui.stdout
    assert first["status"] == "ACCEPTED"
    assert first["command_sha256"] == second["command_sha256"]
    assert second["job"]["job"]["job_id"] == job_id  # type: ignore[index]
    assert loaded["job"]["job_id"] == job_id  # type: ignore[index]
    assert events["items"][0]["sequence"] == 1  # type: ignore[index]
    assert cancelled["cancel_requested"] is True  # type: ignore[index]
    assert repeated_cancel["last_event_sequence"] == cancelled["last_event_sequence"]
    assert assessment["job"]["job"]["command"]["command"] == "ASSESS_CONNECTION"  # type: ignore[index]
    assert executed["job"]["state"] == "COMPLETE"  # type: ignore[index]
    assert executed["checkpoints"][0]["status"] == "COMPLETE"  # type: ignore[index]


def test_ssh_adapt_cli_accepts_only_a_resolved_project_evidence_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    settings = get_settings()
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("remote ssh-ed25519 AAAATEST\n", encoding="utf-8")
    TargetRegistrationService(TargetProfileRegistry(settings.target_profile_dir)).register(
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
        idempotency_key="cli-register-remote-arm",
    )
    evidence_job_id = "deployment-" + "a" * 32
    now = datetime.now(timezone.utc)

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
            observed_at=now,
            expires_at=now + timedelta(minutes=15),
        )

    monkeypatch.setattr(
        target_commands,
        "resolve_target_adapt_project_evidence_binding",
        resolve,
    )
    code, payload = _invoke(
        [
            "target",
            "adapt",
            "submit",
            "--target",
            "remote-arm",
            "--active-probe",
            "none",
            "--no-run-adapter-agent",
            "--project-evidence-job-id",
            evidence_job_id,
            "--idempotency-key",
            "cli-ssh-adapt-project-evidence",
        ]
    )
    job_id = payload["job"]["job"]["job_id"]  # type: ignore[index]
    spec = TargetAdaptJobSpecStore(
        settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    ).load(str(job_id))
    get_settings.cache_clear()

    assert code == 0
    assert payload["status"] == "ACCEPTED"
    assert spec.parameters.project_root_location == "TARGET"
    assert spec.parameters.project_root == "/home/robot/ws"
    assert spec.project_evidence is not None
    assert spec.project_evidence.job_id == evidence_job_id


def test_target_runtime_rollback_cli_creates_bound_r3_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    workspace = tmp_path / "wheeltec_ws"
    workspace.mkdir()
    public_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "release.pub"
    public_path.write_bytes(public_key)
    register_code, _ = _invoke(
        [
            "target",
            "add",
            "wheeltec",
            "--local",
            "--workspace",
            str(workspace),
            "--desired-version",
            "0.2.0",
            "--release-signing-key-id",
            "release-key-2026",
            "--release-signing-public-key",
            str(public_path),
            "--idempotency-key",
            "target-cli-rollback-register-wheeltec",
        ]
    )
    args = [
        "target",
        "runtime",
        "rollback",
        "--target",
        "wheeltec",
        "--package-id",
        "rolo-target",
        "--expected-current-manifest-sha256",
        "c" * 64,
        "--expected-previous-manifest-sha256",
        "b" * 64,
        "--approver",
        "reviewer@example.com",
        "--requested-by",
        "operator@example.com",
        "--idempotency-key",
        "target-cli-runtime-rollback-wheeltec",
    ]

    first_code, first = _invoke(args)
    repeated_code, repeated = _invoke(args)
    tui = CliRunner().invoke(
        app,
        [
            "target",
            "tui",
            "--submit-runtime-rollback",
            "--target",
            "wheeltec",
            "--requested-by",
            "operator@example.com",
            "--idempotency-key",
            "target-tui-runtime-rollback-wheeltec",
        ],
        input=(
            "rolo-target\n"
            + "c" * 64
            + "\n"
            + "a" * 64
            + "\nreviewer@example.com\ny\n"
        ),
    )
    tui_jobs = DeploymentJobStore(
        get_settings().rolo_artifact_dir / "deployment-jobs"
    ).list_jobs(limit=100)
    get_settings.cache_clear()

    assert register_code == 0
    assert first_code == repeated_code == 0
    assert repeated == first
    assert first["job"]["job"]["command"]["command"] == (  # type: ignore[index]
        "ROLLBACK_TARGET_RUNTIME"
    )
    assert first["approval"]["action"] == "ROLLBACK_TARGET_RUNTIME"  # type: ignore[index]
    assert first["approval"]["risk"] == "R3"  # type: ignore[index]
    assert tui.exit_code == 0, tui.output
    assert "This creates an R3 Approval only" in tui.output
    assert "ROLLBACK_TARGET_RUNTIME" in tui.output
    assert any(
        item.job.command.interaction_surface == InteractionSurface.TUI
        and item.job.command.idempotency_key
        == "target-tui-runtime-rollback-wheeltec"
        for item in tui_jobs
    )


def test_target_project_evidence_cli_creates_bound_r2_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    workspace = tmp_path / "wheeltec_ws"
    workspace.mkdir()
    (workspace / "README.md").write_text("wheeltec", encoding="utf-8")
    register_code, _ = _add_local_target(workspace)
    args = [
        "target",
        "project-evidence",
        "submit",
        "--target",
        "wheeltec",
        "--approver",
        "reviewer@example.com",
        "--requested-by",
        "operator@example.com",
        "--idempotency-key",
        "target-cli-project-evidence-wheeltec",
        "--candidates-json",
        '[{"path":"README.md","kind":"DOCUMENTATION"}]',
    ]

    first_code, first = _invoke(args)
    repeated_code, repeated = _invoke(args)
    get_settings.cache_clear()

    assert register_code == 0
    assert first_code == repeated_code == 0
    assert repeated == first
    assert first["job"]["job"]["command"]["command"] == "COLLECT_EVIDENCE"  # type: ignore[index]
    assert first["approval"]["action"] == "READ_PROJECT_EVIDENCE"  # type: ignore[index]
    assert first["approval"]["risk"] == "R2"  # type: ignore[index]
    assert first["spec"]["candidates"] == [  # type: ignore[index]
        {
            "path": "README.md",
            "kind": "DOCUMENTATION",
            "role": "SOURCE",
            "required": False,
        }
    ]


def test_target_source_discovery_cli_creates_separate_r2_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    workspace = tmp_path / "wheeltec_ws"
    (workspace / "src").mkdir(parents=True)
    register_code, _ = _add_local_target(workspace)
    args = [
        "target",
        "source-discovery",
        "submit",
        "--target",
        "wheeltec",
        "--approver",
        "reviewer@example.com",
        "--requested-by",
        "operator@example.com",
        "--idempotency-key",
        "target-cli-source-discovery-wheeltec",
        "--scan-root",
        "src",
    ]

    first_code, first = _invoke(args)
    repeated_code, repeated = _invoke(args)
    get_settings.cache_clear()

    assert register_code == 0
    assert first_code == repeated_code == 0
    assert repeated == first
    assert first["approval"]["action"] == "ANALYZE_PROJECT_SOURCE"  # type: ignore[index]
    assert first["approval"]["risk"] == "R2"  # type: ignore[index]
    assert first["spec"]["scan_roots"] == ["src"]  # type: ignore[index]


def test_session_agent_cli_has_no_identity_or_shell_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class _Runtime:
        def run(self, subject, request, *, idempotency_key):  # type: ignore[no-untyped-def]
            observed.update(
                subject=subject,
                request=request,
                idempotency_key=idempotency_key,
            )
            return SessionAgentTurnResult(
                session_id="agent-session-" + "a" * 32,
                status=SessionAgentRuntimeStatus.COMPLETED,
                response="无需执行目标动作。",
                catalog_sha256="b" * 64,
                provider_calls=1,
            )

    subject = SessionAgentSubject(
        principal="bound-operator@example.com",
        permissions=["target:write"],
    )
    monkeypatch.setattr(
        target_commands,
        "_session_agent_runtime_cli",
        lambda: (_Runtime(), subject),
    )
    code, body = _invoke(
        [
            "target",
            "agent",
            "run",
            "检查 alpha",
            "--target",
            "alpha",
            "--idempotency-key",
            "agent-cli-alpha-check",
        ]
    )
    rejected = CliRunner().invoke(
        app,
        [
            "target",
            "agent",
            "run",
            "检查 alpha",
            "--target",
            "alpha",
            "--idempotency-key",
            "agent-cli-alpha-shell",
            "--shell",
            "robotctl target approval decide",
        ],
    )

    assert code == 0
    assert body["status"] == "COMPLETED"
    assert observed["subject"] == subject
    assert observed["idempotency_key"] == "agent-cli-alpha-check"
    assert rejected.exit_code != 0


def test_session_agent_cli_is_disabled_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("ROLO_SESSION_AGENT_ENABLED", raising=False)
    monkeypatch.delenv("ROLO_SESSION_AGENT_API_KEY", raising=False)
    get_settings.cache_clear()

    result = CliRunner().invoke(
        app,
        [
            "target",
            "agent",
            "run",
            "检查 alpha",
            "--target",
            "alpha",
            "--idempotency-key",
            "agent-cli-disabled",
        ],
    )
    get_settings.cache_clear()

    assert result.exit_code != 0
    assert "Session Agent is disabled" in (result.stdout + result.stderr)


def test_session_agent_readiness_is_secret_closed_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ROLO_SESSION_AGENT_ENABLED", "true")
    monkeypatch.setenv("ROLO_SESSION_AGENT_API_KEY", "must-not-be-rendered")
    monkeypatch.setenv("ROLO_SESSION_AGENT_EXECUTABLE", "missing-codex-binary")
    get_settings.cache_clear()

    result = CliRunner().invoke(app, ["target", "agent", "readiness"])
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "rolo-session-agent-production-readiness/v1"
    assert payload["production_ready"] is False
    assert "must-not-be-rendered" not in result.stdout
    assert "missing-codex-binary" not in result.stdout
    assert any(
        gate["gate_id"] == "REAL_PROVIDER_ACCEPTANCE"
        and gate["status"] == "NOT_VERIFIED"
        for gate in payload["gates"]
    )


def test_bootstrap_cli_rejects_freeform_or_non_posix_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    runner = CliRunner()
    registration = runner.invoke(
        app,
        [
            "target",
            "add",
            "wheeltec",
            "--local",
            "--workspace",
            "/home/robot/wheeltec_ws",
            "--desired-version",
            "0.1.0",
            "--idempotency-key",
            "target-cli-register-invalid-test",
        ],
    )
    assert registration.exit_code == 0

    invalid_workspace = runner.invoke(
        app,
        [
            "target",
            "bootstrap",
            "submit",
            "--target",
            "wheeltec",
            "--workspace",
            "relative/path",
            "--idempotency-key",
            "deployment-cli-bootstrap-1",
        ],
    )
    free_shell = runner.invoke(
        app,
        [
            "target",
            "bootstrap",
            "submit",
            "--target",
            "wheeltec",
            "--workspace",
            "/home/robot/wheeltec_ws",
            "--idempotency-key",
            "deployment-cli-bootstrap-2",
            "--shell",
            "sudo sh",
        ],
    )
    get_settings.cache_clear()

    assert invalid_workspace.exit_code != 0
    assert free_shell.exit_code != 0
    assert not (tmp_path / "artifacts" / "deployment-jobs" / "jobs").exists()


def test_bootstrap_cli_import_submit_and_approval_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_private = Ed25519PrivateKey.generate()
    release_private_path = tmp_path / "release.pem"
    release_private_path.write_bytes(
        release_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        release_private_path.chmod(0o600)
    release_public_path = tmp_path / "release.pub"
    release_public_path.write_bytes(
        release_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    authorization_public_path = tmp_path / "authorization.pub"
    authorization_public_path.write_bytes(
        Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    source = tmp_path / "runtime-source"
    entrypoint = source / "bin" / "robotctl"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho healthy\n")
    package = TargetPackageBuilder().build(
        source,
        tmp_path / "package",
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        signing_key_id="release-key-2026",
        private_key_path=release_private_path,
    )
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv(
        "ROLO_DEPLOYMENT_AUTHORIZATION_KEY_ID",
        "controller-authorization-2026",
    )
    monkeypatch.setenv(
        "ROLO_DEPLOYMENT_AUTHORIZATION_PUBLIC_KEY_PATH",
        str(authorization_public_path),
    )
    get_settings.cache_clear()
    runner = CliRunner()
    registration = runner.invoke(
        app,
        [
            "target",
            "add",
            "wheeltec",
            "--local",
            "--workspace",
            "/home/robot/wheeltec_ws",
            "--desired-version",
            "0.2.0",
            "--idempotency-key",
            "target-cli-bootstrap-public-register",
            "--release-signing-key-id",
            "release-key-2026",
            "--release-signing-public-key",
            str(release_public_path),
        ],
    )
    imported = runner.invoke(
        app,
        [
            "target",
            "package",
            "import",
            "--target",
            "wheeltec",
            "--source",
            package.package_root,
        ],
    )
    assert registration.exit_code == 0, registration.stdout
    assert imported.exit_code == 0, imported.stdout
    package_ref = json.loads(imported.stdout)["record"]["package_ref"]
    submit_argv = [
        "target",
        "bootstrap",
        "submit",
        "--target",
        "wheeltec",
        "--package-ref",
        package_ref,
        "--idempotency-key",
        "target-cli-bootstrap-public-submit",
        "--requested-by",
        "operator@example.com",
        "--approver",
        "reviewer@example.com",
        "--expected-current-state",
        "absent",
    ]
    submitted = runner.invoke(app, submit_argv)
    repeated = runner.invoke(app, submit_argv)
    assert submitted.exit_code == 0, submitted.stdout
    assert repeated.exit_code == 0, repeated.stdout
    payload = json.loads(submitted.stdout)
    assert json.loads(repeated.stdout) == payload
    approval_id = payload["approval"]["approval_id"]
    decision_argv = [
        "target",
        "approval",
        "decide",
        "--approval-id",
        approval_id,
        "--principal",
        "reviewer@example.com",
        "--idempotency-key",
        "target-cli-bootstrap-public-approval",
        "--reason",
        "Verified exact package and target pin.",
        "--approve",
    ]
    decided = runner.invoke(app, decision_argv)
    decided_again = runner.invoke(app, decision_argv)
    get_settings.cache_clear()

    assert decided.exit_code == 0, decided.stdout
    assert decided_again.exit_code == 0, decided_again.stdout
    assert json.loads(decided.stdout)["status"] == "APPROVED"
    assert json.loads(decided_again.stdout) == json.loads(decided.stdout)


def test_host_provisioning_cli_submit_approve_and_run_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    settings = get_settings()
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("remote ssh-ed25519 AAAATEST\n", encoding="utf-8")
    TargetRegistrationService(TargetProfileRegistry(settings.target_profile_dir)).register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="remote-host",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id="connection-remote-host",
                workspace_root="/var/lib/rolo/workspace",
                desired_rolo_version="0.2.0",
                trust_level=TargetTrustLevel.STRICT,
            ),
            connection=TargetConnectionProfile(
                connection_profile_id="connection-remote-host",
                host="192.0.2.20",
                user="rolo",
                credential_ref="file://ssh/remote-bootstrap",
                provisioning_user="operator",
                provisioning_credential_ref="file://ssh/remote-admin",
                runtime_user="rolo",
                runtime_credential_ref="file://ssh/remote-runtime",
                known_hosts_path=str(known_hosts.absolute()),
                trust_level=TargetTrustLevel.STRICT,
                expected_host_key_sha256="SHA256:" + "A" * 43,
            ),
        ),
        principal="fixture",
        idempotency_key="target-cli-host-provisioning-register",
    )
    bootstrap_key = tmp_path / "bootstrap.pub"
    runtime_key = tmp_path / "runtime.pub"
    bootstrap_key.write_text(
        "ssh-ed25519 " + b64encode(b"b" * 32).decode() + "\n",
        encoding="utf-8",
    )
    runtime_key.write_text(
        "ssh-ed25519 " + b64encode(b"r" * 32).decode() + "\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def provision_host(self, plan, **_):  # type: ignore[no-untyped-def]
        calls.append(plan.canonical_sha256())
        now = datetime.now(timezone.utc)
        return TargetHostProvisioningExecutionResult(
            target_id=plan.target_id,
            plan_sha256=plan.canonical_sha256(),
            status=TargetHostProvisioningExecutionStatus.APPLIED,
            current_plan_sha256=plan.canonical_sha256(),
            started_at=now,
            finished_at=now,
        )

    monkeypatch.setattr(SshTargetExecutor, "provision_host", provision_host)
    runner = CliRunner()
    submit_argv = [
        "target",
        "host",
        "submit",
        "--target",
        "remote-host",
        "--bootstrap-public-key",
        str(bootstrap_key),
        "--runtime-public-key",
        str(runtime_key),
        "--idempotency-key",
        "target-cli-host-provisioning-submit",
        "--requested-by",
        "operator@example.com",
        "--approver",
        "reviewer@example.com",
    ]
    submitted = runner.invoke(app, submit_argv)
    repeated = runner.invoke(app, submit_argv)
    assert submitted.exit_code == 0, submitted.stdout
    assert repeated.exit_code == 0, repeated.stdout
    payload = json.loads(submitted.stdout)
    assert json.loads(repeated.stdout) == payload
    approval_id = payload["approval"]["approval_id"]
    job_id = payload["job"]["job"]["job_id"]
    decided = runner.invoke(
        app,
        [
            "target",
            "approval",
            "decide",
            "--approval-id",
            approval_id,
            "--principal",
            "reviewer@example.com",
            "--idempotency-key",
            "target-cli-host-provisioning-approval",
            "--reason",
            "Reviewed exact paths, modes, digests, users and forced commands.",
            "--approve",
        ],
    )
    executed = runner.invoke(app, ["target", "job", "run", "--job-id", job_id])
    replayed = runner.invoke(app, ["target", "job", "run", "--job-id", job_id])
    get_settings.cache_clear()

    assert decided.exit_code == 0, decided.stdout
    assert executed.exit_code == 0, executed.stdout
    assert replayed.exit_code == 0, replayed.stdout
    assert json.loads(executed.stdout)["job"]["state"] == "COMPLETE"
    assert json.loads(replayed.stdout) == json.loads(executed.stdout)
    assert len(calls) == 1
