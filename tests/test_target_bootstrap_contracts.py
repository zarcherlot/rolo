from __future__ import annotations

from base64 import b64encode

import pytest
from pydantic import ValidationError

from rolo.targets import (
    BootstrapStepKind,
    TargetArchitecture,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageSignature,
    TargetPlatformFacts,
    TargetPreflightStatus,
    build_bootstrap_plan,
    build_target_preflight,
)


def _manifest(**updates: object) -> TargetPackageManifest:
    values: dict[str, object] = {
        "package_id": "rolo-target",
        "package_version": "0.2.0",
        "rolo_version": "0.2.0",
        "architecture": TargetArchitecture.X86_64,
        "python_requires": ">=3.10,<3.14",
        "entrypoint": "bin/robotctl",
        "files": [
            TargetPackageFile(
                path="bin/robotctl",
                sha256="a" * 64,
                size_bytes=1234,
                mode=0o755,
                role=TargetPackageFileRole.ENTRYPOINT,
            ),
            TargetPackageFile(
                path="share/rolo/package.json",
                sha256="b" * 64,
                size_bytes=456,
                mode=0o644,
                role=TargetPackageFileRole.RUNTIME,
            ),
        ],
        "minimum_address_space_bytes": 4 * 1024 * 1024 * 1024,
        "minimum_processes": 128,
    }
    values.update(updates)
    return TargetPackageManifest.model_validate(values)


def _signature(manifest: TargetPackageManifest) -> TargetPackageSignature:
    return TargetPackageSignature(
        key_id="release-key-2026",
        manifest_sha256=manifest.canonical_sha256(),
        signature_base64=b64encode(b"s" * 64).decode("ascii"),
    )


def _facts(**updates: object) -> TargetPlatformFacts:
    values: dict[str, object] = {
        "os": "linux",
        "architecture": "amd64",
        "python_version": "3.12.4",
        "bubblewrap_available": True,
        "user_namespace_available": True,
        "mount_namespace_available": True,
        "network_namespace_available": True,
        "available_address_space_bytes": 8 * 1024 * 1024 * 1024,
        "available_processes": 256,
        "runtime_path_available": True,
        "explicit_pythonpath_supported": True,
        "virtualenv_supported": True,
    }
    values.update(updates)
    return TargetPlatformFacts.model_validate(values)


def test_package_manifest_and_signature_are_deterministic_and_bound() -> None:
    manifest = _manifest()
    repeated = TargetPackageManifest.model_validate(manifest.model_dump(mode="json"))
    signature = _signature(manifest)

    assert manifest.canonical_sha256() == repeated.canonical_sha256()
    signature.validate_manifest(manifest)

    with pytest.raises(ValueError, match="digest mismatch"):
        signature.model_copy(update={"manifest_sha256": "0" * 64}).validate_manifest(manifest)


def test_target_preflight_accepts_supported_x86_64_and_reports_bounded_blockers() -> None:
    manifest = _manifest()
    ready = build_target_preflight(manifest, _facts())
    blocked = build_target_preflight(
        manifest,
        _facts(
            architecture="arm64",
            bubblewrap_available=False,
            available_address_space_bytes=2 * 1024 * 1024 * 1024,
            available_processes=64,
        ),
    )

    assert ready.status == TargetPreflightStatus.READY
    assert ready.normalized_architecture == TargetArchitecture.X86_64
    assert ready.blockers == []
    assert blocked.status == TargetPreflightStatus.BLOCKED
    assert blocked.blockers == sorted(
        [
            "TARGET_ADDRESS_SPACE_BUDGET_INSUFFICIENT",
            "TARGET_ARCHITECTURE_MISMATCH",
            "TARGET_BUBBLEWRAP_UNAVAILABLE",
            "TARGET_PROCESS_BUDGET_INSUFFICIENT",
        ]
    )


def test_bootstrap_plan_lists_mutations_sudo_and_rollback_explicitly() -> None:
    manifest = _manifest()
    signature = _signature(manifest)
    preflight = build_target_preflight(manifest, _facts())

    plan = build_bootstrap_plan(
        target_id="wheeltec",
        manifest=manifest,
        signature=signature,
        signing_public_key_sha256="f" * 64,
        preflight=preflight,
        current_package_version="0.1.0",
        install_requires_sudo=True,
    )

    assert not plan.idempotent_noop
    assert plan.signing_public_key_sha256 == "f" * 64
    assert plan.approval_actions == ["INSTALL_TARGET_RUNTIME", "USE_SUDO"]
    assert [step.kind for step in plan.steps] == [
        BootstrapStepKind.UPLOAD,
        BootstrapStepKind.VERIFY,
        BootstrapStepKind.INSTALL,
        BootstrapStepKind.ACTIVATE,
        BootstrapStepKind.HEALTH_CHECK,
        BootstrapStepKind.ROLLBACK,
    ]
    assert {step.kind for step in plan.steps if step.requires_sudo} == {
        BootstrapStepKind.INSTALL,
        BootstrapStepKind.ACTIVATE,
        BootstrapStepKind.ROLLBACK,
    }


def test_same_current_version_produces_approval_free_idempotent_plan() -> None:
    manifest = _manifest()
    plan = build_bootstrap_plan(
        target_id="wheeltec",
        manifest=manifest,
        signature=_signature(manifest),
        signing_public_key_sha256="f" * 64,
        preflight=build_target_preflight(manifest, _facts()),
        current_package_version=manifest.package_version,
        current_manifest_sha256=manifest.canonical_sha256(),
        install_requires_sudo=True,
    )

    assert plan.idempotent_noop
    assert plan.approval_actions == []
    assert [step.kind for step in plan.steps] == [
        BootstrapStepKind.VERIFY,
        BootstrapStepKind.HEALTH_CHECK,
    ]
    assert all(not step.requires_sudo for step in plan.steps)


def test_package_contract_rejects_path_escape_unknown_fields_and_weak_entrypoint() -> None:
    with pytest.raises(ValidationError, match="normalized and relative"):
        TargetPackageFile(
            path="../escape",
            sha256="a" * 64,
            size_bytes=1,
            mode=0o644,
            role=TargetPackageFileRole.RUNTIME,
        )
    with pytest.raises(ValidationError, match="must be executable"):
        _manifest(
            files=[
                TargetPackageFile(
                    path="bin/robotctl",
                    sha256="a" * 64,
                    size_bytes=1,
                    mode=0o644,
                    role=TargetPackageFileRole.ENTRYPOINT,
                )
            ]
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TargetPackageManifest.model_validate(
            {**_manifest().model_dump(mode="json"), "private_key": "forbidden"}
        )
