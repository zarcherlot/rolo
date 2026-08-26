from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rolo.targets import (
    OrchestratorPlacement,
    TargetConnectionProfile,
    TargetProfile,
    TargetProfileRegistry,
    TargetRegistrationConflict,
    TargetRegistrationRequest,
    TargetRegistrationService,
    TargetRegistrationStatus,
    TargetTransport,
    TargetTrustLevel,
    target_connection_binding_sha256,
)

NOW = datetime(2026, 8, 25, 19, 0, tzinfo=timezone.utc)


def _registration(tmp_path: Path, *, host: str = "192.0.2.15") -> TargetRegistrationRequest:
    connection = TargetConnectionProfile(
        connection_profile_id="connection-wheeltec",
        host=host,
        port=22,
        user="robot",
        credential_ref="file://ssh/wheeltec",
        known_hosts_path=str((tmp_path / "known_hosts").absolute()),
        trust_level=TargetTrustLevel.STRICT,
        expected_host_key_sha256="SHA256:" + "A" * 43,
    )
    target = TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.CONTROLLER,
        transport=TargetTransport.SSH,
        connection_profile_id=connection.connection_profile_id,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.1.0",
        trust_level=TargetTrustLevel.STRICT,
    )
    return TargetRegistrationRequest(target=target, connection=connection)


def test_registration_is_idempotent_and_rejects_key_or_profile_reuse(
    tmp_path: Path,
) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    service = TargetRegistrationService(registry)
    request = _registration(tmp_path)

    created = service.register(
        request,
        principal="operator@example.com",
        idempotency_key="target-registration-wheeltec",
        now=NOW,
    )
    repeated = service.register(
        request,
        principal="operator@example.com",
        idempotency_key="target-registration-wheeltec",
        now=NOW,
    )

    assert created == repeated
    assert created.status == TargetRegistrationStatus.CREATED
    assert registry.get_target("wheeltec") == request.target
    assert registry.get_connection("connection-wheeltec") == request.connection
    assert target_connection_binding_sha256(
        created.target,
        created.connection,
    ) == request.canonical_sha256()

    changed = _registration(tmp_path, host="192.0.2.16")
    with pytest.raises(TargetRegistrationConflict, match="idempotency key"):
        service.register(
            changed,
            principal="operator@example.com",
            idempotency_key="target-registration-wheeltec",
            now=NOW,
        )
    with pytest.raises(TargetRegistrationConflict, match="registered differently"):
        service.register(
            changed,
            principal="operator@example.com",
            idempotency_key="target-registration-wheeltec-changed",
            now=NOW,
        )
    assert registry.get_connection("connection-wheeltec").host == "192.0.2.15"


def test_connection_profile_binds_distinct_bootstrap_and_runtime_identities(
    tmp_path: Path,
) -> None:
    request = _registration(tmp_path)
    connection = request.connection
    assert connection is not None

    split = connection.model_copy(
        update={
            "provisioning_user": "operator",
            "provisioning_credential_ref": "file://ssh/wheeltec-provisioning",
            "runtime_user": "rolo",
            "runtime_credential_ref": "file://ssh/wheeltec-runtime",
        }
    )
    validated = TargetConnectionProfile.model_validate(split.model_dump())

    assert validated.user == "robot"
    assert validated.provisioning_user == "operator"
    assert validated.runtime_user == "rolo"
    assert validated.runtime_credential_ref == "file://ssh/wheeltec-runtime"
    with pytest.raises(ValueError, match="configured together"):
        TargetConnectionProfile.model_validate(
            {**connection.model_dump(), "runtime_user": "rolo"}
        )
    with pytest.raises(ValueError, match="must differ"):
        TargetConnectionProfile.model_validate(
            {
                **connection.model_dump(),
                "runtime_user": connection.user,
                "runtime_credential_ref": connection.credential_ref,
            }
        )
    with pytest.raises(ValueError, match="provisioning SSH user"):
        TargetConnectionProfile.model_validate(
            {**connection.model_dump(), "provisioning_user": "operator"}
        )


def test_registration_recovers_after_connection_only_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    service = TargetRegistrationService(registry)
    request = _registration(tmp_path)
    original_save_target = registry.save_target
    interrupted = False

    def fail_once(profile: TargetProfile) -> Path:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise OSError("injected registration interruption")
        return original_save_target(profile)

    monkeypatch.setattr(registry, "save_target", fail_once)
    with pytest.raises(OSError, match="injected"):
        service.register(
            request,
            principal="operator@example.com",
            idempotency_key="target-registration-interruption",
            now=NOW,
        )
    assert registry.get_connection("connection-wheeltec") == request.connection
    with pytest.raises(FileNotFoundError):
        registry.get_target("wheeltec")

    recovered = service.register(
        request,
        principal="operator@example.com",
        idempotency_key="target-registration-interruption",
        now=NOW,
    )
    assert recovered.status == TargetRegistrationStatus.CREATED
    assert registry.get_target("wheeltec") == request.target


def test_concurrent_registration_produces_one_stable_receipt(tmp_path: Path) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    service = TargetRegistrationService(registry)
    request = _registration(tmp_path)
    barrier = threading.Barrier(2)
    results = []
    errors: list[BaseException] = []

    def register() -> None:
        try:
            barrier.wait(timeout=2.0)
            results.append(
                service.register(
                    request,
                    principal="operator@example.com",
                    idempotency_key="target-registration-concurrent",
                    now=NOW,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=register) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3.0)

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert results[0] == results[1]
