from __future__ import annotations

import os
import shutil
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings
from rolo.targets import (
    ApprovalAction,
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    DeploymentJobStore,
    InteractionSurface,
    OrchestratorPlacement,
    TargetAdaptJobSpecStore,
    TargetAdaptProjectEvidenceBinding,
    TargetArchitecture,
    TargetConnectionProfile,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
    TargetPackageBuilder,
    TargetPackageRegistry,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetTransport,
    TargetTrustLevel,
    ed25519_public_key_sha256,
)
from rolo.targets import deployment_api as deployment_api_module
from rolo.targets.agent_broker import SessionAgentAction, SessionAgentCommand
from rolo.targets.agent_runtime import (
    SessionAgentDecisionKind,
    SessionAgentModelDecision,
    SessionAgentRuntime,
)


def _headers(
    *,
    key: str = "deployment-api-request-1",
    principal: str = "operator@example.com",
    permissions: str = "target:write",
) -> dict[str, str]:
    return {
        "Authorization": "Bearer deployment-api-test-token",
        "Idempotency-Key": key,
        "X-Rolo-Principal": principal,
        "X-Rolo-Permissions": permissions,
    }


@pytest.fixture
def deployment_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, Path, str]:
    artifact_root = tmp_path / "artifacts"
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
    release_public = release_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    release_public_path = tmp_path / "release.pub"
    release_public_path.write_bytes(release_public)
    authorization_public_path = tmp_path / "authorization.pub"
    authorization_public_path.write_bytes(
        Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ROLO_API_TOKEN", "deployment-api-test-token")
    monkeypatch.setenv("ROLO_API_TOKEN_PRINCIPAL", "operator@example.com")
    monkeypatch.setenv(
        "ROLO_DEPLOYMENT_AUTHORIZATION_KEY_ID",
        "controller-authorization-2026",
    )
    monkeypatch.setenv(
        "ROLO_DEPLOYMENT_AUTHORIZATION_PUBLIC_KEY_PATH",
        str(authorization_public_path),
    )
    monkeypatch.setenv(
        "ROLO_API_TOKEN_PERMISSIONS",
        "target:write,approval:write",
    )
    shutil.copytree(
        Path("tests/fixtures/robots"),
        tmp_path / "config" / "robots",
    )
    get_settings.cache_clear()
    settings = get_settings()
    target_workspace = tmp_path / "wheeltec_ws"
    target_workspace.mkdir()
    (target_workspace / "README.md").write_text("wheeltec", encoding="utf-8")
    TargetRegistrationService(
        TargetProfileRegistry(settings.target_profile_dir)
    ).register(
        TargetRegistrationRequest(
            target=TargetProfile(
                target_id="wheeltec",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.LOCAL,
                workspace_root=str(target_workspace.absolute()),
                desired_rolo_version="0.1.0",
                trust_level=TargetTrustLevel.STRICT,
                release_signing_key_id="release-key-2026",
                release_signing_public_key_path=str(release_public_path.absolute()),
                release_signing_public_key_sha256=ed25519_public_key_sha256(
                    release_public
                ),
            )
        ),
        principal="fixture",
        idempotency_key="deployment-api-fixture-target",
    )
    source = tmp_path / "runtime-source"
    entrypoint = source / "bin" / "robotctl"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho healthy\n")
    built = TargetPackageBuilder().build(
        source,
        tmp_path / "built-package",
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        signing_key_id="release-key-2026",
        private_key_path=release_private_path,
    )
    registration = TargetRegistrationService(
        TargetProfileRegistry(settings.target_profile_dir)
    ).load("wheeltec")
    package_entry = TargetPackageRegistry(
        settings.target_package_registry_dir
    ).import_package(Path(built.package_root), profile=registration.target)
    with TestClient(app) as client:
        yield client, artifact_root, package_entry.record.package_ref
    get_settings.cache_clear()


def test_mutating_deployment_api_requires_explicit_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.delenv("ROLO_API_TOKEN", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/v1/targets/wheeltec/bootstrap-jobs",
            json={
                "package_ref": "rolo-target@" + "a" * 64,
                "approver_principal": "operator@example.com",
            },
            headers={
                "Idempotency-Key": "deployment-api-request-0",
                "X-Rolo-Principal": "operator@example.com",
                "X-Rolo-Permissions": "target:write",
            },
        )
    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Mutating deployment API requires ROLO_API_TOKEN"


def test_deployment_session_authenticates_without_mutating_state(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, artifact_root, _ = deployment_client

    session = client.get(
        "/v1/deployment-session",
        headers={
            "Authorization": "Bearer deployment-api-test-token",
            "X-Rolo-Principal": "operator@example.com",
        },
    )
    invalid = client.get(
        "/v1/deployment-session",
        headers={
            "Authorization": "Bearer wrong-token",
            "X-Rolo-Principal": "operator@example.com",
        },
    )

    assert session.status_code == 200, session.text
    assert session.headers["cache-control"] == "no-store"
    assert session.json() == {
        "schema_version": "rolo-deployment-api-session/v1",
        "principal": "operator@example.com",
        "permissions": ["approval:write", "target:write"],
        "authentication": "bearer",
        "token_persistence": "client-memory-only",
    }
    assert invalid.status_code == 401
    assert not (artifact_root / "deployment-jobs").exists()


def test_session_agent_api_opens_idempotent_read_session_and_filters_tools(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, artifact_root, _ = deployment_client
    read_headers = {
        "Authorization": "Bearer deployment-api-test-token",
        "X-Rolo-Principal": "operator@example.com",
        "X-Rolo-Permissions": "",
    }

    catalog = client.get("/v1/session-agent/catalog", headers=read_headers)
    first = client.post(
        "/v1/session-agent/sessions",
        json={"allowed_target_ids": ["wheeltec"], "max_tool_calls": 2},
        headers=read_headers | {"Idempotency-Key": "agent-api-open-wheeltec-read"},
    )
    repeated = client.post(
        "/v1/session-agent/sessions",
        json={"allowed_target_ids": ["wheeltec"], "max_tool_calls": 2},
        headers=read_headers | {"Idempotency-Key": "agent-api-open-wheeltec-read"},
    )

    assert catalog.status_code == 200, catalog.text
    assert catalog.headers["cache-control"] == "no-store"
    body = catalog.json()
    assert body["raw_shell_available"] is False
    assert body["approval_decision_available"] is False
    assert body["model_generated_identity_available"] is False
    assert "APPROVAL_DECIDE" not in {item["action"] for item in body["tools"]}
    assert first.status_code == 201, first.text
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == first.json()
    assert "deployment-api-test-token" not in first.text
    assert "credential_ref" not in first.text
    session_id = first.json()["session_id"]

    listed = client.post(
        f"/v1/session-agent/sessions/{session_id}/commands",
        json={"sequence": 1, "action": "LIST_TARGETS"},
        headers=read_headers,
    )
    retried = client.post(
        f"/v1/session-agent/sessions/{session_id}/commands",
        json={"sequence": 1, "action": "LIST_TARGETS"},
        headers=read_headers,
    )
    assert listed.status_code == 200, listed.text
    assert retried.json() == listed.json()
    assert listed.json()["projection"]["rows"][0]["identity"] == "wheeltec"
    assert listed.json()["projection"]["rows"][0]["canonical_cli"] is None
    assert (
        artifact_root
        / "deployment-jobs"
        / "agent-sessions"
        / f"{session_id}.json"
    ).is_file()


def test_session_agent_api_binds_permissions_and_never_accepts_approval_authority(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    base = {
        "Authorization": "Bearer deployment-api-test-token",
        "X-Rolo-Principal": "operator@example.com",
    }
    rejected = client.get(
        "/v1/session-agent/catalog",
        headers=base | {"X-Rolo-Permissions": "approval:write"},
    )
    opened = client.post(
        "/v1/session-agent/sessions",
        json={"allowed_target_ids": ["wheeltec"], "max_tool_calls": 2},
        headers=base
        | {
            "X-Rolo-Permissions": "target:write",
            "Idempotency-Key": "agent-api-open-wheeltec-write",
        },
    )
    assert rejected.status_code == 403
    assert opened.status_code == 201, opened.text
    session_id = opened.json()["session_id"]

    submitted = client.post(
        f"/v1/session-agent/sessions/{session_id}/commands",
        json={
            "sequence": 1,
            "action": "ASSESS_CONNECTION",
            "target_id": "wheeltec",
        },
        headers=base | {"X-Rolo-Permissions": "target:write"},
    )
    downgraded = client.post(
        f"/v1/session-agent/sessions/{session_id}/commands",
        json={"sequence": 2, "action": "LIST_TARGETS"},
        headers=base | {"X-Rolo-Permissions": ""},
    )
    spoofed = client.post(
        f"/v1/session-agent/sessions/{session_id}/commands",
        json={"sequence": 2, "action": "LIST_TARGETS"},
        headers={
            "Authorization": "Bearer deployment-api-test-token",
            "X-Rolo-Principal": "attacker@example.com",
            "X-Rolo-Permissions": "target:write",
        },
    )

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"
    assert submitted.json()["job_id"].startswith("deployment-")
    assert downgraded.status_code == 403
    assert spoofed.status_code == 401


def test_session_agent_turn_api_runs_autonomous_commands_through_broker(
    deployment_client: tuple[TestClient, Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _ = deployment_client

    class _Provider:
        def __init__(self) -> None:
            self.calls = 0

        def decide(self, **_: object) -> SessionAgentModelDecision:
            self.calls += 1
            if self.calls == 1:
                return SessionAgentModelDecision(
                    kind=SessionAgentDecisionKind.COMMAND,
                    command=SessionAgentCommand(
                        sequence=8,
                        action=SessionAgentAction.ASSESS_CONNECTION,
                        target_id="wheeltec",
                    ),
                )
            return SessionAgentModelDecision(
                kind=SessionAgentDecisionKind.FINAL,
                message="连接评估 Job 已建立。",
            )

    provider = _Provider()

    def runtime(request):  # type: ignore[no-untyped-def]
        return SessionAgentRuntime(
            deployment_api_module._session_agent_broker(request),
            provider,
        )

    monkeypatch.setattr(deployment_api_module, "_session_agent_runtime", runtime)
    headers = {
        "Authorization": "Bearer deployment-api-test-token",
        "X-Rolo-Principal": "operator@example.com",
        "X-Rolo-Permissions": "target:write",
        "Idempotency-Key": "agent-api-turn-wheeltec-assess",
    }
    first = client.post(
        "/v1/session-agent/turns",
        json={
            "message": "评估 wheeltec 的连接",
            "allowed_target_ids": ["wheeltec"],
            "max_tool_calls": 2,
        },
        headers=headers,
    )
    repeated = client.post(
        "/v1/session-agent/turns",
        json={
            "message": "评估 wheeltec 的连接",
            "allowed_target_ids": ["wheeltec"],
            "max_tool_calls": 2,
        },
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["status"] == "COMPLETED"
    assert first.json()["response"] == "连接评估 Job 已建立。"
    assert len(first.json()["receipts"]) == 1
    assert repeated.json() == first.json()
    assert provider.calls == 2


def test_session_agent_turn_api_is_fail_closed_until_dedicated_provider_enabled(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    response = client.post(
        "/v1/session-agent/turns",
        json={
            "message": "列出 wheeltec",
            "allowed_target_ids": ["wheeltec"],
        },
        headers={
            "Authorization": "Bearer deployment-api-test-token",
            "X-Rolo-Principal": "operator@example.com",
            "X-Rolo-Permissions": "",
            "Idempotency-Key": "agent-api-turn-disabled",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Session Agent is disabled"


def test_session_agent_readiness_api_is_authenticated_and_not_self_attested(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    unauthorized = client.get("/v1/session-agent/readiness")
    response = client.get(
        "/v1/session-agent/readiness",
        headers={
            "Authorization": "Bearer deployment-api-test-token",
            "X-Rolo-Principal": "operator@example.com",
            "X-Rolo-Permissions": "",
        },
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["production_ready"] is False
    assert any(
        gate["gate_id"] == "LINUX_ARM64_ACCEPTANCE"
        and gate["status"] == "NOT_VERIFIED"
        for gate in payload["gates"]
    )
    assert "deployment-api-test-token" not in response.text


def test_target_registration_and_connection_assessment_are_idempotent(
    deployment_client: tuple[TestClient, Path, str],
    tmp_path: Path,
) -> None:
    client, _, _ = deployment_client
    headers = _headers(key="deployment-api-register-ssh")
    connection = {
        "connection_profile_id": "connection-remote-arm",
        "host": "192.0.2.15",
        "port": 22,
        "user": "robot",
        "credential_ref": "file://ssh/remote-arm",
        "known_hosts_path": str(tmp_path / "known_hosts"),
        "trust_level": "STRICT",
        "expected_host_key_sha256": "SHA256:" + "A" * 43,
    }
    body = {
        "target": {
            "target_id": "remote-arm",
            "orchestrator_placement": "CONTROLLER",
            "transport": "SSH",
            "connection_profile_id": "connection-remote-arm",
            "workspace_root": "/home/robot/ws",
            "desired_rolo_version": "0.1.0",
            "trust_level": "STRICT",
        },
        "connection": connection,
    }

    created = client.post("/v1/targets", json=body, headers=headers)
    repeated = client.post("/v1/targets", json=body, headers=headers)
    conflict = client.post(
        "/v1/targets",
        json=body | {"connection": connection | {"host": "192.0.2.16"}},
        headers=headers,
    )
    listed = client.get(
        "/v1/targets",
        headers={"Authorization": "Bearer deployment-api-test-token"},
    )
    assessment = client.post(
        "/v1/targets/remote-arm/connection-assessments",
        json={"active_probe": "runtime-readonly"},
        headers=_headers(key="deployment-api-assess-remote-arm"),
    )

    assert created.status_code == 201, created.text
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == created.json()
    assert conflict.status_code == 409
    assert listed.status_code == 200
    assert {item["target"]["target_id"] for item in listed.json()} == {
        "wheeltec",
        "remote-arm",
    }
    assert assessment.status_code == 202, assessment.text
    command = assessment.json()["job"]["command"]
    assert command["command"] == "ASSESS_CONNECTION"
    assert command["workspace_root"] is None
    assert command["parameters_sha256"] == created.json()["request_sha256"]


def test_job_api_is_idempotent_strict_and_surface_independent(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, artifact_root, _ = deployment_client
    body = {
        "active_probe": "none",
        "run_adapter_agent": False,
        "timeout_s": 120,
    }
    created = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body,
        headers=_headers(),
    )
    repeated = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body,
        headers=_headers(),
    )

    assert created.status_code == 202, created.text
    assert repeated.status_code == 202, repeated.text
    assert repeated.json()["job"]["job_id"] == created.json()["job"]["job_id"]
    job_id = created.json()["job"]["job_id"]
    spec = TargetAdaptJobSpecStore(
        artifact_root / "deployment-jobs" / "specs"
    ).load(job_id)
    command = DeploymentCommand(
        command=DeploymentCommandKind.ADAPT,
        target_id="wheeltec",
        workspace_root=spec.workspace_root,
        active_probe=spec.active_probe,
        run_adapter_agent=False,
        requested_by="operator@example.com",
        interaction_surface=InteractionSurface.CLI,
        idempotency_key="deployment-api-request-1",
        parameters_sha256=spec.canonical_sha256(),
    )
    assert created.json()["job"]["command_sha256"] == command.canonical_sha256()

    conflict = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body | {"active_probe": "help"},
        headers=_headers(),
    )
    missing_permission = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body,
        headers=_headers(key="deployment-api-request-2", permissions="approval:write"),
    )
    unbound_principal = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body,
        headers=_headers(
            key="deployment-api-request-4",
            principal="attacker@example.com",
        ),
    )
    free_shell = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json=body | {"shell": "sudo sh"},
        headers=_headers(key="deployment-api-request-3"),
    )

    assert conflict.status_code == 409
    assert missing_permission.status_code == 403
    assert unbound_principal.status_code == 401
    assert free_shell.status_code == 422


def test_ssh_adapt_api_binds_resolved_project_evidence(
    deployment_client: tuple[TestClient, Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, artifact_root, _ = deployment_client
    settings = get_settings()
    known_hosts = artifact_root / "remote-known-hosts"
    known_hosts.write_text("remote ssh-ed25519 AAAATEST\n", encoding="utf-8")
    registrations = TargetRegistrationService(
        TargetProfileRegistry(settings.target_profile_dir)
    )
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
        idempotency_key="api-register-remote-arm-for-adapt",
    )
    evidence_job_id = "deployment-" + "b" * 32
    now = datetime.now(timezone.utc)

    def resolve(**kwargs):  # type: ignore[no-untyped-def]
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
        deployment_api_module,
        "resolve_target_adapt_project_evidence_binding",
        resolve,
    )
    response = client.post(
        "/v1/targets/remote-arm/adapt-jobs",
        json={
            "active_probe": "none",
            "run_adapter_agent": False,
            "project_evidence_job_id": evidence_job_id,
        },
        headers=_headers(key="api-ssh-adapt-project-evidence"),
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job"]["job_id"]
    spec = TargetAdaptJobSpecStore(
        artifact_root / "deployment-jobs" / "specs"
    ).load(job_id)
    assert spec.parameters.project_root_location == "TARGET"
    assert spec.parameters.project_root == "/home/robot/ws"
    assert spec.project_evidence is not None
    assert spec.project_evidence.job_id == evidence_job_id


def test_bootstrap_api_resolves_registry_ref_and_creates_bound_approval(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, package_ref = deployment_client
    body = {
        "package_ref": package_ref,
        "approver_principal": "reviewer@example.com",
        "approval_ttl_s": 600,
        "expect_current_present": False,
    }
    headers = _headers(key="deployment-api-bootstrap-public-1")

    created = client.post(
        "/v1/targets/wheeltec/bootstrap-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/wheeltec/bootstrap-jobs",
        json=body,
        headers=headers,
    )
    arbitrary_path = client.post(
        "/v1/targets/wheeltec/bootstrap-jobs",
        json=body | {"package_root": "C:/controller/secrets"},
        headers=_headers(key="deployment-api-bootstrap-public-2"),
    )

    assert created.status_code == 202, created.text
    assert repeated.status_code == 202, repeated.text
    assert repeated.json() == created.json()
    payload = created.json()
    assert payload["package_ref"] == package_ref
    assert len(payload["manifest_sha256"]) == 64
    assert payload["approval"]["authorization_scope_sha256"] == payload["job"][
        "job"
    ]["command"]["parameters_sha256"]
    assert "package_root" not in created.text
    assert "public_key_base64" not in created.text
    assert arbitrary_path.status_code == 422
    workbench = client.get(
        "/v1/deployment-workbench",
        params={"page": "approval", "approval_id": payload["approval"]["approval_id"]},
        headers={"Authorization": "Bearer deployment-api-test-token"},
    )
    approval_list = client.get(
        "/v1/deployment-workbench",
        params={"page": "approval"},
        headers={"Authorization": "Bearer deployment-api-test-token"},
    )
    assert workbench.status_code == 200, workbench.text
    assert approval_list.status_code == 200, approval_list.text
    assert [row["identity"] for row in approval_list.json()["rows"]] == [
        payload["approval"]["approval_id"]
    ]
    assert workbench.json()["schema_version"] == (
        "rolo-target-deployment-workbench-snapshot/v1"
    )
    fields = {
        item["name"]: item["value"] for item in workbench.json()["rows"][0]["fields"]
    }
    assert fields["target"] == "wheeltec"
    assert fields["action"] == "INSTALL_TARGET_RUNTIME"
    assert fields["desired_version"] == "0.1.0"
    assert fields["manifest_sha256"] == payload["manifest_sha256"]
    serialized = workbench.text.casefold()
    assert "credential_ref" not in serialized
    assert "known_hosts_path" not in serialized
    assert "package_root" not in serialized
    assert "public_key_base64" not in serialized


def test_host_provisioning_api_is_authenticated_idempotent_and_secret_closed(
    deployment_client: tuple[TestClient, Path, str],
    tmp_path: Path,
) -> None:
    client, _, _ = deployment_client
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
        idempotency_key="deployment-api-host-provisioning-target",
    )
    body = {
        "bootstrap_public_key": "ssh-ed25519 " + b64encode(b"b" * 32).decode(),
        "runtime_public_key": "ssh-ed25519 " + b64encode(b"r" * 32).decode(),
        "approver_principal": "reviewer@example.com",
        "approval_ttl_s": 600,
    }
    headers = _headers(key="deployment-api-host-provisioning-1")

    created = client.post(
        "/v1/targets/remote-host/host-provisioning-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/remote-host/host-provisioning-jobs",
        json=body,
        headers=headers,
    )

    assert created.status_code == 202, created.text
    assert repeated.status_code == 202, repeated.text
    assert repeated.json() == created.json()
    payload = created.json()
    assert payload["job"]["job"]["command"]["command"] == "PROVISION_HOST"
    assert payload["approval"]["action"] == "USE_SUDO"
    assert len(payload["plan_sha256"]) == 64
    serialized = created.text.casefold()
    assert "provisioning_credential_ref" not in serialized
    assert "known_hosts_path" not in serialized
    assert "authorized_keys" not in serialized
    assert "dispatcher_content" not in serialized

    job_id = payload["job"]["job"]["job_id"]
    store = DeploymentJobStore(settings.rolo_artifact_dir / "deployment-jobs")
    now = datetime.now(timezone.utc)
    store.start_step(
        job_id,
        step_id="provision-host",
        state=DeploymentJobState.BOOTSTRAPPING,
        remote=True,
        now=now,
    )
    store.fail_step(
        job_id,
        step_id="provision-host",
        remote_state_known=False,
        now=now + timedelta(seconds=1),
    )
    reconcile_headers = _headers(key="deployment-api-host-reconciliation-1")
    reconciliation = client.post(
        f"/v1/jobs/{job_id}/host-reconciliation-jobs",
        json={
            "approver_principal": "reviewer@example.com",
            "approval_ttl_s": 600,
        },
        headers=reconcile_headers,
    )
    reconciliation_repeated = client.post(
        f"/v1/jobs/{job_id}/host-reconciliation-jobs",
        json={
            "approver_principal": "reviewer@example.com",
            "approval_ttl_s": 600,
        },
        headers=reconcile_headers,
    )
    assert reconciliation.status_code == 202, reconciliation.text
    assert reconciliation_repeated.json() == reconciliation.json()
    reconciliation_payload = reconciliation.json()
    assert reconciliation_payload["job"]["job"]["command"]["command"] == (
        "RECONCILE_HOST"
    )
    assert reconciliation_payload["approval"]["risk"] == "R2"
    assert reconciliation_payload["original_job_id"] == job_id


def test_runtime_rollback_api_is_authenticated_idempotent_and_secret_free(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    body = {
        "package_id": "rolo-target",
        "expected_current_manifest_sha256": "c" * 64,
        "expected_previous_manifest_sha256": "b" * 64,
        "approver_principal": "reviewer@example.com",
        "approval_ttl_s": 600,
    }
    headers = _headers(key="deployment-api-runtime-rollback-1")

    created = client.post(
        "/v1/targets/wheeltec/runtime-rollback-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/wheeltec/runtime-rollback-jobs",
        json=body,
        headers=headers,
    )
    missing_permission = client.post(
        "/v1/targets/wheeltec/runtime-rollback-jobs",
        json=body,
        headers=_headers(
            key="deployment-api-runtime-rollback-2",
            permissions="approval:write",
        ),
    )
    raw_shell = client.post(
        "/v1/targets/wheeltec/runtime-rollback-jobs",
        json=body | {"shell": "sudo rollback-now"},
        headers=_headers(key="deployment-api-runtime-rollback-3"),
    )

    assert created.status_code == 202, created.text
    assert repeated.json() == created.json()
    payload = created.json()
    assert payload["job"]["job"]["command"]["command"] == (
        "ROLLBACK_TARGET_RUNTIME"
    )
    assert payload["approval"]["action"] == "ROLLBACK_TARGET_RUNTIME"
    assert payload["approval"]["risk"] == "R3"
    assert payload["expected_current_manifest_sha256"] == "c" * 64
    assert payload["expected_previous_manifest_sha256"] == "b" * 64
    assert "public_key_base64" not in created.text
    assert "release_signing_public_key_path" not in created.text
    assert missing_permission.status_code == 403
    assert raw_shell.status_code == 422



def test_connection_assessment_runner_api_completes_profile_only_job(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, artifact_root, _ = deployment_client
    created = client.post(
        "/v1/targets/wheeltec/connection-assessments",
        json={"active_probe": "none"},
        headers=_headers(key="deployment-api-assess-wheeltec-runner"),
    )
    job_id = created.json()["job"]["job_id"]

    executed = client.post(
        f"/v1/jobs/{job_id}/run",
        content=b"",
        headers=_headers(key="deployment-api-run-wheeltec-assessment"),
    )
    repeated = client.post(
        f"/v1/jobs/{job_id}/run",
        content=b"",
        headers=_headers(key="deployment-api-run-wheeltec-assessment"),
    )

    assert created.status_code == 202, created.text
    assert executed.status_code == 200, executed.text
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == executed.json()
    assert executed.json()["job"]["state"] == "COMPLETE"
    assert executed.json()["checkpoints"][0]["status"] == "COMPLETE"
    assert (
        artifact_root
        / "deployment-jobs"
        / "artifacts"
        / job_id
        / "connection-assessment.json"
    ).is_file()


def test_job_reads_sse_and_cancel_are_bounded_and_idempotent(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    created = client.post(
        "/v1/targets/wheeltec/adapt-jobs",
        json={"active_probe": "none", "run_adapter_agent": False},
        headers=_headers(key="deployment-api-bootstrap-1"),
    )
    job_id = created.json()["job"]["job_id"]
    read_headers = {"Authorization": "Bearer deployment-api-test-token"}

    job = client.get(f"/v1/jobs/{job_id}", headers=read_headers)
    events = client.get(f"/v1/jobs/{job_id}/events?limit=10", headers=read_headers)
    sse = client.get(
        f"/v1/jobs/{job_id}/events?format=sse&limit=10",
        headers=read_headers,
    )
    cancelled = client.post(
        f"/v1/jobs/{job_id}/cancel",
        content=b"",
        headers=_headers(key="deployment-api-cancel-1"),
    )
    repeated = client.post(
        f"/v1/jobs/{job_id}/cancel",
        content=b"",
        headers=_headers(key="deployment-api-cancel-1"),
    )
    final_events = client.get(
        f"/v1/jobs/{job_id}/events?limit=10",
        headers=read_headers,
    )

    assert job.status_code == 200
    assert events.status_code == 200
    assert events.json()["items"][0]["sequence"] == 1
    assert sse.status_code == 200
    assert sse.headers["content-type"].startswith("text/event-stream")
    assert "data: {\"event\":" in sse.text
    assert "\"event_id\":\"event-" in sse.text
    assert cancelled.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json()["last_event_sequence"] == cancelled.json()[
        "last_event_sequence"
    ]
    assert len(final_events.json()["items"]) == 2


def test_project_evidence_api_creates_exact_r2_approval_and_replays(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    body = {
        "candidates": [
            {
                "path": "README.md",
                "kind": "DOCUMENTATION",
                "role": "SOURCE",
                "required": False,
            }
        ],
        "approver_principal": "reviewer@example.com",
        "timeout_s": 30,
    }
    headers = _headers(key="deployment-api-project-evidence-wheeltec")

    created = client.post(
        "/v1/targets/wheeltec/project-evidence-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/wheeltec/project-evidence-jobs",
        json=body,
        headers=headers,
    )
    conflict = client.post(
        "/v1/targets/wheeltec/project-evidence-jobs",
        json={
            **body,
            "candidates": [
                {
                    "path": "package.xml",
                    "kind": "ROS_METADATA",
                    "role": "SOURCE",
                    "required": False,
                }
            ],
        },
        headers=headers,
    )

    assert created.status_code == 202, created.text
    assert repeated.status_code == 202, repeated.text
    assert repeated.json() == created.json()
    assert conflict.status_code == 409
    assert created.json()["job"]["job"]["command"]["command"] == (
        "COLLECT_EVIDENCE"
    )
    assert created.json()["approval"]["action"] == "READ_PROJECT_EVIDENCE"
    assert created.json()["approval"]["risk"] == "R2"


def test_source_discovery_api_creates_separate_bounded_r2_approval_and_replays(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    body = {
        "scan_roots": ["."],
        "approver_principal": "reviewer@example.com",
        "timeout_s": 120,
    }
    headers = _headers(key="deployment-api-source-discovery-wheeltec")

    created = client.post(
        "/v1/targets/wheeltec/source-discovery-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/wheeltec/source-discovery-jobs",
        json=body,
        headers=headers,
    )
    conflict = client.post(
        "/v1/targets/wheeltec/source-discovery-jobs",
        json={**body, "scan_roots": ["src"]},
        headers=headers,
    )

    assert created.status_code == 202, created.text
    assert repeated.status_code == 202, repeated.text
    assert repeated.json() == created.json()
    assert conflict.status_code == 409
    assert created.json()["job"]["job"]["command"]["command"] == (
        "COLLECT_EVIDENCE"
    )
    assert created.json()["approval"]["action"] == "ANALYZE_PROJECT_SOURCE"
    assert created.json()["approval"]["risk"] == "R2"
    assert created.json()["spec"]["scan_roots"] == ["."]


def test_runtime_evidence_api_freezes_collector_pin_and_short_r2_window(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, _, _ = deployment_client
    now = datetime.now(timezone.utc)
    configuration = CollectorConfigurationV4()
    enrollment_request = TargetEnrollmentRequest(
        request_id="api-runtime-evidence-enroll",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="wheeltec",
        robot_id="wheeltec",
        challenge_nonce="a" * 32,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        configuration_sha256=configuration.canonical_sha256(),
        configuration=configuration,
        approval_id="approval-" + "b" * 32,
    )
    enrollment_result = TargetEnrollmentService(
        get_settings().target_profile_dir / "api-target-enrollment",
        host_fingerprint_provider=lambda: "c" * 64,
        clock=lambda: now,
    ).execute(enrollment_request)
    CollectorEnrollmentPinRegistry(
        get_settings().target_profile_dir / "enrollment-v4"
    ).apply(enrollment_request, enrollment_result, now=now)
    body = {
        "approver_principal": "reviewer@example.com",
        "approval_ttl_s": 300,
        "timeout_s": 45,
    }
    headers = _headers(key="deployment-api-runtime-evidence-wheeltec")

    created = client.post(
        "/v1/targets/wheeltec/runtime-evidence-jobs",
        json=body,
        headers=headers,
    )
    repeated = client.post(
        "/v1/targets/wheeltec/runtime-evidence-jobs",
        json=body,
        headers=headers,
    )

    assert created.status_code == 202, created.text
    assert repeated.json() == created.json()
    assert created.json()["approval"]["action"] == "COLLECT_RUNTIME_EVIDENCE"
    assert created.json()["approval"]["risk"] == "R2"
    assert created.json()["spec"]["collection_request"]["evidence_request"][
        "requested_layers"
    ] == ["hw", "linux", "ros"]
    assert created.json()["spec"]["collector_descriptor_sha256"] == (
        enrollment_result.descriptor.canonical_sha256()
    )


def test_approval_decision_api_binds_principal_permission_and_idempotency(
    deployment_client: tuple[TestClient, Path, str],
) -> None:
    client, artifact_root, _ = deployment_client
    store = DeploymentJobStore(artifact_root / "deployment-jobs")
    now = datetime.now(timezone.utc)
    job = store.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.ADAPT,
            target_id="wheeltec",
            workspace_root="/home/robot/wheeltec_ws",
            requested_by="session-agent",
            interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
            idempotency_key="deployment-api-approval-job",
        ),
        now=now,
    )
    approval = store.request_approval(
        job.job.job_id,
        action=ApprovalAction.ACTIVATE_RELEASE,
        risk="R3",
        approver_principal="operator@example.com",
        summary="Activate the exact reviewed release.",
        authorization_scope_sha256="b" * 64,
        expires_at=now + timedelta(minutes=10),
        now=now,
        approval_id="approval-" + "7" * 32,
    )
    decision_headers = _headers(
        key="deployment-api-decision-1",
        principal="operator@example.com",
        permissions="approval:write",
    )
    body = {"approve": True, "reason": "Digest and Gate receipt reviewed."}

    decided = client.post(
        f"/v1/approvals/{approval.approval_id}/decisions",
        json=body,
        headers=decision_headers,
    )
    repeated = client.post(
        f"/v1/approvals/{approval.approval_id}/decisions",
        json=body,
        headers=decision_headers,
    )
    conflicting = client.post(
        f"/v1/approvals/{approval.approval_id}/decisions",
        json=body,
        headers=decision_headers | {"Idempotency-Key": "deployment-api-decision-2"},
    )

    assert decided.status_code == 200, decided.text
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == decided.json()
    assert decided.json()["principal"] == "operator@example.com"
    assert decided.json()["status"] == "APPROVED"
    assert conflicting.status_code == 409
