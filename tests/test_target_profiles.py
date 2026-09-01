from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.core.hashing import sha256_file
from rolo.product_cli import app
from rolo.target_ref import SshTargetRef, parse_target_ref
from rolo.targets.approvals import approve_bootstrap, request_bootstrap_approval
from rolo.targets.models import BootstrapPlanStatus, TargetBootstrapPlan
from rolo.targets.profiles import (
    CredentialReference,
    HostKeyDecision,
    TargetProfileStore,
    known_hosts_fingerprints,
    validate_host_key_pin,
    validate_ssh_credential,
)
from rolo.targets.signing import sign_companion_manifest, verify_companion_manifest


def _target() -> SshTargetRef:
    target = parse_target_ref("ssh://robot@example.test:2222/home/robot/wheeltec_ws")
    assert isinstance(target, SshTargetRef)
    return target


def _approval_plan() -> TargetBootstrapPlan:
    return TargetBootstrapPlan(
        target=_target(),
        assessment_state="READY",
        status=BootstrapPlanStatus.APPROVAL_REQUIRED,
        required_approvals=["target.bootstrap.execute"],
    )


def test_target_profile_store_persists_non_secret_profile_and_rejects_target_replacement(
    tmp_path: Path,
) -> None:
    store = TargetProfileStore(tmp_path)
    profile = store.create(
        robot_id="wheeltec",
        target=_target(),
        credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
        now=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )

    loaded = store.load("wheeltec")
    assert loaded == profile
    assert loaded.host_key == HostKeyDecision(
        host="example.test",
        port=2222,
    )
    assert "secret" not in json.dumps(loaded.model_dump(mode="json"))
    with pytest.raises(ValueError, match="target is immutable"):
        store.save(
            profile.model_copy(
                update={
                    "target": parse_target_ref("ssh://robot@example.test/home/robot/other")
                }
            )
        )


def test_bootstrap_approval_is_bound_to_plan_and_disallows_self_approval() -> None:
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    plan = _approval_plan()
    request = request_bootstrap_approval(plan, requested_by="agent", now=now)

    decision = approve_bootstrap(
        plan,
        request,
        approved_by="operator",
        now=now + timedelta(seconds=1),
    )
    assert decision.status == "APPROVED"
    assert decision.plan_sha256 == request.plan_sha256
    with pytest.raises(ValueError, match="self-approved"):
        approve_bootstrap(plan, request, approved_by="agent", now=now + timedelta(seconds=1))
    changed = plan.model_copy(update={"required_approvals": ["other.scope"]})
    with pytest.raises(ValueError, match="different plan"):
        approve_bootstrap(changed, request, approved_by="operator", now=now + timedelta(seconds=1))


def test_companion_manifest_verification_checks_hash_and_signature(tmp_path: Path) -> None:
    package = tmp_path / "rolo-target.bin"
    package.write_bytes(b"signed companion payload")
    manifest = sign_companion_manifest(
        package_id="rolo-target",
        package_version="1.0.0",
        architecture="aarch64",
        package_file=package.name,
        package_sha256=sha256_file(package),
        publisher_id="rolo-release",
        verification_key=b"test verification key",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    result = verify_companion_manifest(
        manifest_path,
        package,
        verification_key=b"test verification key",
    )
    assert result.verified is True
    package.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash does not match"):
        verify_companion_manifest(manifest_path, package, verification_key=b"test verification key")


def test_product_cli_profile_init_and_show_do_not_connect(tmp_path: Path) -> None:
    env = {"ROLO_CONFIG_DIR": str(tmp_path / "config")}
    runner = CliRunner()
    created = runner.invoke(
        app,
        [
            "target",
            "profile",
            "init",
            "ssh://robot@example.test/home/robot/workspace",
            "--robot",
            "wheeltec",
        ],
        env=env,
    )
    shown = runner.invoke(app, ["target", "profile", "show", "--robot", "wheeltec"], env=env)

    assert created.exit_code == 0, created.output
    assert json.loads(created.output)["status"] == "PROFILE_READY"
    assert shown.exit_code == 0, shown.output
    payload = json.loads(shown.output)
    assert payload["profile"]["host_key"]["status"] == "PENDING"

    approved = runner.invoke(
        app,
        [
            "target",
            "profile",
            "approve-host-key",
            "--robot",
            "wheeltec",
            "--fingerprint",
            "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "--approver",
            "operator",
        ],
        env=env,
    )
    assert approved.exit_code == 0, approved.output
    approved_payload = json.loads(approved.output)
    assert approved_payload["status"] == "HOST_KEY_APPROVED"
    assert approved_payload["profile"]["host_key"]["status"] == "APPROVED"


def test_ssh_profile_persists_pinned_known_hosts_and_rejects_local_option(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("robot.example ssh-ed25519 AAAA\n", encoding="utf-8")
    runner = CliRunner()
    env = {"ROLO_CONFIG_DIR": str(tmp_path / "config")}
    created = runner.invoke(
        app,
        [
            "target", "profile", "init",
            "ssh://robot@robot.example/opt/rolo",
            "--robot", "ssh-robot", "--known-hosts", str(known_hosts),
        ],
        env=env,
    )
    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    assert payload["profile"]["known_hosts"] == str(known_hosts.resolve())
    assert payload["profile"]["known_hosts_sha256"] == sha256_file(known_hosts)

    rejected = runner.invoke(
        app,
        ["target", "profile", "init", str(tmp_path), "--robot", "local-robot",
         "--known-hosts", str(known_hosts)],
        env=env,
    )
    assert rejected.exit_code != 0
    assert "only valid for SSH" in rejected.output


def test_ssh_profile_rejects_known_hosts_tamper_and_wrong_fingerprint(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(
        "robot.example ssh-ed25519 ZmFrZS1rZXk=\n", encoding="utf-8"
    )
    target = SshTargetRef(host="robot.example", user="robot", workspace="/opt/rolo")
    store = TargetProfileStore(tmp_path / "config")
    profile = store.create(
        robot_id="ssh-robot",
        target=target,
        credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
        known_hosts=known_hosts,
    )
    fingerprint = next(iter(known_hosts_fingerprints(known_hosts, target)))
    approved = profile.model_copy(
        update={
            "host_key": profile.host_key.model_copy(
                update={"status": "APPROVED", "fingerprint": fingerprint}
            )
        }
    )
    validate_host_key_pin(approved)
    known_hosts.write_text(
        "robot.example ssh-ed25519 ZmFrZS1vdGhlci1rZXk=\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="known_hosts content"):
        validate_host_key_pin(approved)

    known_hosts.write_text(
        "robot.example ssh-ed25519 ZmFrZS1rZXk=\n", encoding="utf-8"
    )
    wrong = approved.model_copy(
        update={
            "host_key": approved.host_key.model_copy(
                update={"fingerprint": "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
            )
        }
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_host_key_pin(wrong)


def test_ssh_profile_rejects_unresolved_credential_kind(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(
        "robot.example ssh-ed25519 ZmFrZS1rZXk=\n", encoding="utf-8"
    )
    profile = TargetProfileStore(tmp_path / "config").create(
        robot_id="ssh-robot",
        target=SshTargetRef(host="robot.example", workspace="/opt/rolo"),
        credential=CredentialReference(kind="secret-store", reference="vault:robot"),
        known_hosts=known_hosts,
    )
    with pytest.raises(ValueError, match="ssh-agent:default"):
        validate_ssh_credential(profile)


def test_ssh_profile_pins_optional_identity_file(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(
        "robot.example ssh-ed25519 ZmFrZS1rZXk=\n", encoding="utf-8"
    )
    identity = tmp_path / "id_ed25519"
    identity.write_text("private-key-placeholder\n", encoding="utf-8")
    identity.chmod(0o600)
    profile = TargetProfileStore(tmp_path / "config").create(
        robot_id="ssh-robot",
        target=SshTargetRef(host="robot.example", workspace="/opt/rolo"),
        credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
        known_hosts=known_hosts,
        ssh_identity_file=identity,
    )
    assert profile.ssh_identity_sha256 == sha256_file(identity)
    assert validate_ssh_credential(profile) == identity.resolve()
