from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from rolo.targets import (
    AdapterReleaseStageRequest,
    ApprovalAction,
    DeploymentAuthorizationGrant,
    DeploymentAuthorizationKeyPin,
    DeploymentAuthorizationKeyRegistry,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobStore,
    InteractionSurface,
    LocalTargetExecutor,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    authorize_deployment_request,
    deployment_request_payload_sha256,
    ed25519_public_key_sha256,
    issue_deployment_authorization,
    verify_deployment_authorization,
)

NOW = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
PAYLOAD_SHA256 = "a" * 64


def _write_private_key(path: Path) -> tuple[Path, bytes]:
    private_key = Ed25519PrivateKey.generate()
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return path, public_key


def _approved_store(
    root: Path,
    *,
    authorization_scope_sha256: str = PAYLOAD_SHA256,
) -> tuple[DeploymentJobStore, str]:
    store = DeploymentJobStore(root)
    job = store.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.BOOTSTRAP_AND_ADAPT,
            target_id="wheeltec",
            workspace_root="/home/robot/wheeltec_ws",
            requested_by="session-agent",
            interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
            idempotency_key="authorization-test-request",
        ),
        now=NOW,
        job_id="deployment-" + "1" * 32,
    )
    approval = store.request_approval(
        job.job.job_id,
        action=ApprovalAction.STAGE_RELEASE,
        risk="R2",
        approver_principal="operator@example.com",
        summary="Stage the reviewed frozen Adapter release.",
        authorization_scope_sha256=authorization_scope_sha256,
        expires_at=NOW + timedelta(minutes=20),
        now=NOW + timedelta(seconds=1),
        approval_id="approval-" + "1" * 32,
    )
    store.decide_approval(
        approval.approval_id,
        principal="operator@example.com",
        approve=True,
        reason="Target, action and release were reviewed.",
        now=NOW + timedelta(seconds=2),
        decision_id="decision-" + "1" * 32,
    )
    return store, approval.approval_id


def _pin(
    public_key: bytes,
    *,
    key_id: str = "controller-auth-2026",
) -> DeploymentAuthorizationKeyPin:
    return DeploymentAuthorizationKeyPin(
        target_id="wheeltec",
        key_id=key_id,
        public_key_base64=b64encode(public_key).decode("ascii"),
        public_key_sha256=ed25519_public_key_sha256(public_key),
        installed_by_approval_id="approval-" + "f" * 32,
        installed_at=NOW,
    )


def test_target_verifies_short_lived_exact_request_capability(tmp_path: Path) -> None:
    store, approval_id = _approved_store(tmp_path / "jobs")
    private_path, public_key = _write_private_key(tmp_path / "authorization.pem")
    with pytest.raises(ValueError, match="scope does not match"):
        issue_deployment_authorization(
            store,
            approval_id=approval_id,
            request_schema_version="rolo-adapter-release-stage-request/v1",
            request_payload_sha256="b" * 64,
            signing_key_id="controller-auth-2026",
            private_key_path=private_path,
            now=NOW + timedelta(minutes=1),
            authorization_id="authorization-" + "0" * 32,
        )
    grant, signature = issue_deployment_authorization(
        store,
        approval_id=approval_id,
        request_schema_version="rolo-adapter-release-stage-request/v1",
        request_payload_sha256=PAYLOAD_SHA256,
        signing_key_id="controller-auth-2026",
        private_key_path=private_path,
        now=NOW + timedelta(minutes=1),
        lifetime_s=300,
        authorization_id="authorization-" + "1" * 32,
    )
    registry = DeploymentAuthorizationKeyRegistry(tmp_path / "pins")
    registry.install_initial(_pin(public_key))

    verify_deployment_authorization(
        grant,
        signature,
        pin=registry.load("wheeltec"),
        expected_target_id="wheeltec",
        expected_action=ApprovalAction.STAGE_RELEASE,
        expected_request_schema_version="rolo-adapter-release-stage-request/v1",
        expected_request_payload_sha256=PAYLOAD_SHA256,
        expected_approval_id=approval_id,
        now=NOW + timedelta(minutes=2),
    )

    wrong_bindings = [
        {"expected_target_id": "other-target"},
        {"expected_action": ApprovalAction.ACTIVATE_RELEASE},
        {"expected_request_schema_version": "rolo-other-request/v1"},
        {"expected_request_payload_sha256": "b" * 64},
        {"expected_approval_id": "approval-" + "2" * 32},
    ]
    base = {
        "expected_target_id": "wheeltec",
        "expected_action": ApprovalAction.STAGE_RELEASE,
        "expected_request_schema_version": "rolo-adapter-release-stage-request/v1",
        "expected_request_payload_sha256": PAYLOAD_SHA256,
        "expected_approval_id": approval_id,
    }
    for update in wrong_bindings:
        with pytest.raises(ValueError, match="mismatch"):
            verify_deployment_authorization(
                grant,
                signature,
                pin=registry.load("wheeltec"),
                now=NOW + timedelta(minutes=2),
                **(base | update),
            )

    with pytest.raises(ValueError, match="expired"):
        verify_deployment_authorization(
            grant,
            signature,
            pin=registry.load("wheeltec"),
            now=NOW + timedelta(minutes=7),
            **base,
        )


def test_target_executor_requires_proof_and_rejects_post_signature_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rolo.targets.deployment_authorization._utc_now",
        lambda: NOW + timedelta(minutes=2),
    )
    private_path, authorization_public_key = _write_private_key(
        tmp_path / "authorization.pem"
    )
    _, release_public_key = _write_private_key(tmp_path / "release.pem")
    approval_id = "approval-" + "1" * 32
    unsigned = AdapterReleaseStageRequest(
        request_id="stage-authorized-release",
        target_id="wheeltec",
        robot_id="wheeltec-robot",
        release_id="release-r1",
        package_id="package-r1",
        manifest_sha256="d" * 64,
        signing_key_id="release-key-2026",
        signing_public_key_base64=b64encode(release_public_key).decode("ascii"),
        signing_public_key_sha256=ed25519_public_key_sha256(release_public_key),
        approval_id=approval_id,
    )
    store, approval_id = _approved_store(
        tmp_path / "jobs",
        authorization_scope_sha256=deployment_request_payload_sha256(unsigned),
    )
    registry = DeploymentAuthorizationKeyRegistry(tmp_path / "pins")
    registry.install_initial(_pin(authorization_public_key))
    executor = LocalTargetExecutor(
        transfer_root=tmp_path / "incoming",
        adapter_install_root=tmp_path / "adapters",
        deployment_authorization_registry=registry,
    )

    denied = executor.stage_adapter_release(unsigned)
    assert denied.execution_status == TargetExecutionStatus.FAILED
    assert denied.error_code == TargetExecutionErrorCode.AUTHORIZATION_FAILED

    authorized = authorize_deployment_request(
        unsigned,
        store,
        approval_id=approval_id,
        signing_key_id="controller-auth-2026",
        private_key_path=private_path,
        now=NOW + timedelta(minutes=1),
        authorization_id="authorization-" + "5" * 32,
    )
    # Authorization now passes; the deliberately absent transfer is the next failed gate.
    missing_transfer = executor.stage_adapter_release(authorized)
    assert missing_transfer.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR

    mutated = authorized.model_copy(update={"release_id": "release-r2"})
    rejected_mutation = executor.stage_adapter_release(mutated)
    assert rejected_mutation.error_code == TargetExecutionErrorCode.AUTHORIZATION_FAILED


def test_target_rejects_tampering_and_request_supplied_alternate_key(
    tmp_path: Path,
) -> None:
    store, approval_id = _approved_store(tmp_path / "jobs")
    private_path, public_key = _write_private_key(tmp_path / "authorization.pem")
    _, alternate_public_key = _write_private_key(tmp_path / "alternate.pem")
    grant, signature = issue_deployment_authorization(
        store,
        approval_id=approval_id,
        request_schema_version="rolo-adapter-release-stage-request/v1",
        request_payload_sha256=PAYLOAD_SHA256,
        signing_key_id="controller-auth-2026",
        private_key_path=private_path,
        now=NOW + timedelta(minutes=1),
        authorization_id="authorization-" + "2" * 32,
    )
    expected = {
        "expected_target_id": "wheeltec",
        "expected_action": ApprovalAction.STAGE_RELEASE,
        "expected_request_schema_version": "rolo-adapter-release-stage-request/v1",
        "expected_request_payload_sha256": PAYLOAD_SHA256,
        "expected_approval_id": approval_id,
        "now": NOW + timedelta(minutes=2),
    }

    with pytest.raises(ValueError, match="signature verification failed"):
        verify_deployment_authorization(
            grant,
            signature.model_copy(
                update={"signature_base64": b64encode(b"\x00" * 64).decode("ascii")}
            ),
            pin=_pin(public_key),
            **expected,
        )
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_deployment_authorization(
            grant,
            signature,
            pin=_pin(alternate_public_key),
            **expected,
        )


def test_target_pin_registry_is_write_once_then_bootstrap_cas(tmp_path: Path) -> None:
    _, first_public = _write_private_key(tmp_path / "first.pem")
    _, second_public = _write_private_key(tmp_path / "second.pem")
    registry = DeploymentAuthorizationKeyRegistry(tmp_path / "pins")
    first = registry.install_initial(_pin(first_public, key_id="auth-first"))

    with pytest.raises(FileExistsError):
        registry.install_initial(_pin(second_public, key_id="auth-second"))
    with pytest.raises(ValueError, match="CAS mismatch"):
        registry.replace(
            _pin(second_public, key_id="auth-second"),
            expected_current_public_key_sha256="0" * 64,
        )
    replaced = registry.replace(
        _pin(second_public, key_id="auth-second"),
        expected_current_public_key_sha256=first.public_key_sha256,
    )
    assert registry.load("wheeltec") == replaced

    with pytest.raises(ValidationError, match="install timestamp must be timezone-aware"):
        DeploymentAuthorizationKeyPin.model_validate(
            {
                **_pin(first_public).model_dump(mode="json"),
                "installed_at": "2026-08-25T16:00:00",
            }
        )


def test_rejected_approval_cannot_issue_and_grant_rejects_naive_time(
    tmp_path: Path,
) -> None:
    store = DeploymentJobStore(tmp_path / "jobs")
    job = store.create_job(
        DeploymentCommand(
            command=DeploymentCommandKind.BOOTSTRAP,
            target_id="wheeltec",
            workspace_root="/home/robot/wheeltec_ws",
            requested_by="session-agent",
            interaction_surface=InteractionSurface.CLI,
            idempotency_key="rejected-authorization-request",
        ),
        now=NOW,
        job_id="deployment-" + "3" * 32,
    )
    approval = store.request_approval(
        job.job.job_id,
        action=ApprovalAction.STAGE_RELEASE,
        risk="R2",
        approver_principal="operator@example.com",
        summary="Rejected stage.",
        authorization_scope_sha256=PAYLOAD_SHA256,
        expires_at=NOW + timedelta(minutes=10),
        now=NOW + timedelta(seconds=1),
        approval_id="approval-" + "3" * 32,
    )
    store.decide_approval(
        approval.approval_id,
        principal="operator@example.com",
        approve=False,
        reason="Release review failed.",
        now=NOW + timedelta(seconds=2),
        decision_id="decision-" + "3" * 32,
    )
    private_path, _ = _write_private_key(tmp_path / "authorization.pem")
    with pytest.raises(ValueError, match="does not authorize"):
        issue_deployment_authorization(
            store,
            approval_id=approval.approval_id,
            request_schema_version="rolo-adapter-release-stage-request/v1",
            request_payload_sha256=PAYLOAD_SHA256,
            signing_key_id="controller-auth-2026",
            private_key_path=private_path,
            now=NOW + timedelta(minutes=1),
            authorization_id="authorization-" + "3" * 32,
        )

    with pytest.raises(ValidationError, match="timezone-aware"):
        DeploymentAuthorizationGrant(
            authorization_id="authorization-" + "4" * 32,
            approval_id="approval-" + "4" * 32,
            decision_id="decision-" + "4" * 32,
            job_id="deployment-" + "4" * 32,
            target_id="wheeltec",
            command_sha256="c" * 64,
            action=ApprovalAction.STAGE_RELEASE,
            approver_principal="operator@example.com",
            request_schema_version="rolo-adapter-release-stage-request/v1",
            request_payload_sha256=PAYLOAD_SHA256,
            issued_at=datetime(2026, 8, 25, 16, 0),
            expires_at=datetime(2026, 8, 25, 16, 5),
        )
