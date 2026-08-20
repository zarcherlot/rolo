import getpass
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from rolo.core.hashing import sha256_file
from rolo.core.models import ToolDescriptor
from rolo.invocation_policy import (
    _request_quiescence_lease,
    _request_r3_authorization,
    authorize_content_resource,
    authorize_execution_quiescence,
    authorize_invocation,
    authorize_write_access,
    validate_config_mutation_input,
    validate_config_mutation_result,
    validate_content_result,
    validate_map_import_input,
)


def _descriptor(
    operation: str,
    *,
    risk: str,
    access: str = "write",
    requires_quiescence: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        operation=operation,
        canonical_cli=["robotctl", "tool", "invoke", operation],
        layer="app",
        description="Test operation descriptor",
        risk=risk,
        access=access,
        availability="VERIFIED",
        adapter="bundle:test#invoke",
        contract_lifecycle="GATEABLE",
        contract_version="1.1.0",
        contract_sha256="0" * 64,
        data_classification="INTERNAL" if access == "write" else "SENSITIVE",
        requires_quiescence=requires_quiescence,
    )


def _policy(tmp_path: Path, *, operations: list[str], content: list[dict] | None = None) -> Path:
    path = tmp_path / "invocation-policy.yaml"
    path.write_text(
        json.dumps(
            {
                "schema_version": "rolo-invocation-policy/v1",
                "sensitive": {"allowed_users": [getpass.getuser()]},
                "writes": {
                    "allowed_users": [getpass.getuser()],
                    "allowed_operations": operations,
                },
                "content_resources": content or [],
            }
        ),
        encoding="utf-8",
    )
    if os.name == "posix":
        path.chmod(0o600)
    return path


def test_r1_r2_write_requires_identity_and_exact_operation_allowlist(tmp_path: Path) -> None:
    policy = _policy(tmp_path, operations=["linux.service.restart"])
    audit = tmp_path / "audit.jsonl"
    descriptor = _descriptor("linux.service.restart", risk="R2")

    authorize_write_access(
        descriptor,
        robot_id="robot-1",
        payload={"name": "controller", "secret_input": "not-audited"},
        policy_path=policy,
        audit_path=audit,
        r3_authorizer_path=None,
    )

    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["outcome"] == "ALLOWED"
    assert record["policy_domain"] == "write"
    assert "not-audited" not in audit.read_text(encoding="utf-8")

    denied = _descriptor("linux.service.stop", risk="R2")
    with pytest.raises(ValueError, match="not present in the protected allowlist"):
        authorize_write_access(
            denied,
            robot_id="robot-1",
            payload={"name": "controller"},
            policy_path=policy,
            audit_path=audit,
            r3_authorizer_path=None,
        )


def test_static_policy_cannot_authorize_r3_write(tmp_path: Path) -> None:
    policy = _policy(tmp_path, operations=["app.teleop.velocity"])
    audit = tmp_path / "audit.jsonl"

    with pytest.raises(ValueError, match="R3 authorization provider is missing"):
        authorize_write_access(
            _descriptor("app.teleop.velocity", risk="R3"),
            robot_id="robot-1",
            payload={"linear_x_mps": 0.1, "angular_z_radps": 0.0},
            policy_path=policy,
            audit_path=audit,
            r3_authorizer_path=None,
        )

    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["outcome"] == "DENIED"
    assert record["policy_domain"] == "r3"


def test_sensitive_write_must_pass_both_independent_policy_domains(tmp_path: Path) -> None:
    operation = "app.camera.stream.stop"
    policy = _policy(tmp_path, operations=[operation])
    audit = tmp_path / "audit.jsonl"
    descriptor = _descriptor(operation, risk="R1").model_copy(
        update={"data_classification": "SENSITIVE"}
    )

    authorize_invocation(
        descriptor,
        robot_id="robot-1",
        payload={"session_id": "session-1"},
        policy_path=policy,
        audit_path=audit,
        r3_authorizer_path=None,
    )

    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [record["policy_domain"] for record in records] == ["data", "write"]
    assert all(record["outcome"] == "ALLOWED" for record in records)


def test_r3_provider_capability_is_short_lived_and_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = tmp_path / "authorizer"
    provider.write_text("test provider", encoding="utf-8")
    if os.name == "posix":
        provider.chmod(0o700)
    monkeypatch.setattr(
        "rolo.invocation_policy.validate_protected_file",
        lambda path, **kwargs: path,
    )

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        del args
        request = json.loads(str(kwargs["input"]))
        capability = {
            "schema_version": "rolo-r3-authorization-capability/v1",
            "decision": "ALLOW",
            "authorization_id": "approval-1",
            "request_id": request["request_id"],
            "robot_id": request["robot_id"],
            "operation": request["operation"],
            "input_sha256": request["input_sha256"],
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=60)
            ).isoformat(),
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(capability),
            stderr="",
        )

    monkeypatch.setattr("rolo.invocation_policy.subprocess.run", fake_run)

    capability = _request_r3_authorization(
        provider,
        robot_id="robot-1",
        operation="app.teleop.velocity",
        payload={"linear_x_mps": 0.1, "angular_z_radps": 0.0},
        principal="operator",
    )

    assert capability.authorization_id == "approval-1"
    assert capability.operation == "app.teleop.velocity"


def test_quiescence_provider_returns_bound_lease_covering_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = tmp_path / "quiescence-provider"
    provider.write_text("test provider", encoding="utf-8")
    if os.name == "posix":
        provider.chmod(0o700)
    monkeypatch.setattr(
        "rolo.invocation_policy.validate_protected_file",
        lambda path, **kwargs: path,
    )

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        assert args[-1] == "lease"
        request = json.loads(str(kwargs["input"]))
        now = datetime.now(timezone.utc)
        lease = {
            "schema_version": "rolo-execution-quiescence-lease/v1",
            "decision": "ALLOW",
            "lease_id": "lease-1",
            "request_id": request["request_id"],
            "robot_id": request["robot_id"],
            "operation": request["operation"],
            "input_sha256": request["input_sha256"],
            "scope": "robot_execution",
            "state_revision": "state-7",
            "quiescent_since": (now - timedelta(seconds=5)).isoformat(),
            "expires_at": (
                now + timedelta(seconds=request["requested_lease_s"] + 5)
            ).isoformat(),
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(lease), stderr="")

    monkeypatch.setattr("rolo.invocation_policy.subprocess.run", fake_run)

    lease = _request_quiescence_lease(
        provider,
        robot_id="robot-1",
        operation="app.parameter.set",
        payload={"id": "controller.gain", "value": 1.0},
        principal="operator",
        required_lease_s=30,
    )

    assert lease.lease_id == "lease-1"
    assert lease.scope == "robot_execution"

    monkeypatch.setattr(
        "rolo.invocation_policy._identity",
        lambda: ("operator", {"operator"}, set()),
    )
    audit = tmp_path / "quiescence-audit.jsonl"
    authorize_execution_quiescence(
        _descriptor(
            "app.parameter.set",
            risk="R2",
            requires_quiescence=True,
        ),
        robot_id="robot-1",
        payload={"id": "controller.gain", "value": 1.0},
        audit_path=audit,
        provider_path=provider,
        required_lease_s=30,
    )
    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["policy_domain"] == "quiescence"
    assert record["outcome"] == "ALLOWED"
    assert record["lease_id"] == "lease-1"
    assert "controller.gain" not in audit.read_text(encoding="utf-8")


def test_quiescence_required_write_fails_closed_without_provider(tmp_path: Path) -> None:
    descriptor = _descriptor(
        "app.parameter.set",
        risk="R2",
        requires_quiescence=True,
    )
    audit = tmp_path / "audit.jsonl"

    with pytest.raises(ValueError, match="quiescence provider is missing"):
        authorize_execution_quiescence(
            descriptor,
            robot_id="robot-1",
            payload={"id": "controller.gain"},
            audit_path=audit,
            provider_path=None,
            required_lease_s=30,
        )

    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["policy_domain"] == "quiescence"
    assert record["outcome"] == "DENIED"


def test_content_resource_requires_protected_scope_and_byte_limit(tmp_path: Path) -> None:
    content_root = tmp_path / "classified"
    content_root.mkdir()
    target = content_root / "robot.yaml"
    target.write_text("token: redacted-by-adapter\n", encoding="utf-8")
    policy = _policy(
        tmp_path,
        operations=[],
        content=[
            {
                "operation": "linux.file.read",
                "classification": "SENSITIVE",
                "allowed_roots": [str(content_root)],
                "max_bytes": 4096,
            }
        ],
    )
    audit = tmp_path / "audit.jsonl"
    descriptor = _descriptor("linux.file.read", risk="R0", access="read")

    authorize_content_resource(
        descriptor,
        robot_id="robot-1",
        payload={"path": str(target), "max_bytes": 4096},
        policy_path=policy,
        audit_path=audit,
    )

    with pytest.raises(ValueError, match="outside protected scope or byte limits"):
        authorize_content_resource(
            descriptor,
            robot_id="robot-1",
            payload={"path": str(target), "max_bytes": 4097},
            policy_path=policy,
            audit_path=audit,
        )

    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [record["outcome"] for record in records] == ["ALLOWED", "DENIED"]
    assert all(record["policy_domain"] == "content" for record in records)
    assert "token" not in audit.read_text(encoding="utf-8")


def test_content_result_requires_protected_bounded_artifact_reference() -> None:
    descriptor = _descriptor("linux.file.read", risk="R0", access="read")
    payload = {"path": "/var/log/robot.log", "max_bytes": 4096}

    validate_content_result(
        descriptor,
        payload=payload,
        result={"artifact_ref": "artifact://content/read-1", "bytes": 2048},
    )

    with pytest.raises(ValueError, match="protected artifact"):
        validate_content_result(
            descriptor,
            payload=payload,
            result={"artifact_ref": "file:///tmp/read-1", "bytes": 2048},
        )

    with pytest.raises(ValueError, match="authorized byte limit"):
        validate_content_result(
            descriptor,
            payload=payload,
            result={"artifact_ref": "artifact://content/read-1", "bytes": 4097},
        )


def test_config_apply_requires_digest_pinned_bounded_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "config" / "candidate.yaml"
    artifact.parent.mkdir()
    artifact.write_text("controller: safe\n", encoding="utf-8")
    descriptor = _descriptor("linux.config.apply", risk="R2")
    payload = {
        "target_resource_id": "controller-config",
        "artifact_ref": "artifact://config/candidate.yaml",
        "artifact_sha256": sha256_file(artifact),
        "format": "yaml",
        "max_bytes": 4096,
    }

    validate_config_mutation_input(
        descriptor,
        payload=payload,
        artifact_root=tmp_path,
    )

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_config_mutation_input(
            descriptor,
            payload={**payload, "artifact_sha256": "0" * 64},
            artifact_root=tmp_path,
        )

    with pytest.raises(ValueError, match="byte limit"):
        validate_config_mutation_input(
            descriptor,
            payload={**payload, "max_bytes": 1},
            artifact_root=tmp_path,
        )


def test_map_import_reuses_digest_pinned_artifact_boundary(tmp_path: Path) -> None:
    artifact = tmp_path / "maps" / "candidate.yaml"
    artifact.parent.mkdir()
    artifact.write_text("image: map.pgm\nresolution: 0.05\n", encoding="utf-8")
    descriptor = _descriptor("app.map.import", risk="R2")
    payload = {
        "name": "warehouse",
        "format": "ros_yaml",
        "artifact_ref": "artifact://maps/candidate.yaml",
        "artifact_sha256": sha256_file(artifact),
        "max_bytes": 4096,
    }

    validate_map_import_input(
        descriptor,
        payload=payload,
        artifact_root=tmp_path,
    )

    with pytest.raises(ValueError, match="map import artifact SHA-256 mismatch"):
        validate_map_import_input(
            descriptor,
            payload={**payload, "artifact_sha256": "0" * 64},
            artifact_root=tmp_path,
        )


def test_config_rollback_requires_non_authorizing_system_token() -> None:
    rollback = _descriptor("linux.config.rollback", risk="R2")

    validate_config_mutation_input(
        rollback,
        payload={
            "target_resource_id": "controller-config",
            "rollback_token": "rollback://controller/config-1",
        },
        artifact_root=None,
    )

    with pytest.raises(ValueError, match="system-issued"):
        validate_config_mutation_input(
            rollback,
            payload={
                "target_resource_id": "controller-config",
                "rollback_token": "user-supplied-token",
            },
            artifact_root=None,
        )

    apply = _descriptor("linux.config.apply", risk="R2")
    validate_config_mutation_result(
        apply,
        result={"rollback_token": "rollback://controller/config-1"},
    )
    with pytest.raises(ValueError, match="must return"):
        validate_config_mutation_result(
            apply,
            result={"rollback_token": "opaque-but-unscoped"},
        )
