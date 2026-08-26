from __future__ import annotations

import hashlib
import json
import os
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    BootstrapInstallStatus,
    Ed25519TargetPackageVerifier,
    TargetArchitecture,
    TargetInstallIndex,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageInstaller,
    TargetPackageManifest,
    TargetPackageSignature,
    TargetPlatformFacts,
    bind_target_package_sbom,
    build_target_preflight,
    sign_target_package,
    verify_target_package,
)


class AcceptingVerifier:
    def __init__(self) -> None:
        self.verified: list[str] = []

    def verify(
        self,
        manifest: TargetPackageManifest,
        signature: TargetPackageSignature,
    ) -> None:
        signature.validate_manifest(manifest)
        if signature.key_id != "release-key-2026":
            raise ValueError("untrusted target package signing key")
        self.verified.append(manifest.canonical_sha256())


class VersionHealthChecker:
    def __init__(self, healthy_versions: set[str]) -> None:
        self.healthy_versions = healthy_versions
        self.checked: list[str] = []

    def check(self, entrypoint: Path, manifest: TargetPackageManifest) -> bool:
        assert entrypoint.is_file()
        self.checked.append(manifest.package_version)
        return manifest.package_version in self.healthy_versions


def _package(tmp_path: Path, version: str) -> tuple[Path, TargetPackageManifest]:
    root = tmp_path / f"package-{version}"
    entrypoint = root / "bin/robotctl"
    runtime = root / "share/rolo/runtime.json"
    entrypoint.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    entrypoint.write_bytes(f"#!/bin/sh\necho rolo {version}\n".encode())
    runtime.write_text(json.dumps({"version": version}), encoding="utf-8")

    def declared(path: Path, role: TargetPackageFileRole, mode: int) -> TargetPackageFile:
        payload = path.read_bytes()
        return TargetPackageFile(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mode=mode,
            role=role,
        )

    manifest = TargetPackageManifest(
        package_id="rolo-target",
        package_version=version,
        rolo_version=version,
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        files=sorted(
            [
                declared(entrypoint, TargetPackageFileRole.ENTRYPOINT, 0o755),
                declared(runtime, TargetPackageFileRole.RUNTIME, 0o644),
            ],
            key=lambda item: item.path,
        ),
    )
    manifest, _, sbom_payload = bind_target_package_sbom(manifest)
    (root / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
    signature = TargetPackageSignature(
        key_id="release-key-2026",
        manifest_sha256=manifest.canonical_sha256(),
        signature_base64=b64encode(b"s" * 64).decode("ascii"),
    )
    (root / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return root, manifest


def _preflight(manifest: TargetPackageManifest):  # type: ignore[no-untyped-def]
    return build_target_preflight(
        manifest,
        TargetPlatformFacts(
            os="linux",
            architecture="x86_64",
            python_version="3.12.4",
            bubblewrap_available=True,
            user_namespace_available=True,
            mount_namespace_available=True,
            network_namespace_available=True,
            available_address_space_bytes=8 * 1024 * 1024 * 1024,
            available_processes=256,
            runtime_path_available=True,
            explicit_pythonpath_supported=True,
            virtualenv_supported=True,
        ),
    )


def test_installer_verifies_stages_health_checks_and_atomically_activates(
    tmp_path: Path,
) -> None:
    package, manifest = _package(tmp_path, "0.2.0")
    verifier = AcceptingVerifier()
    health = VersionHealthChecker({"0.2.0"})
    installer = TargetPackageInstaller(tmp_path / "install")

    result = installer.install_and_activate(
        package,
        preflight=_preflight(manifest),
        verifier=verifier,
        health_checker=health,
        expect_current_present=False,
    )
    index = TargetInstallIndex.model_validate_json(
        installer.current_path.read_text(encoding="utf-8")
    )

    assert result.status == BootstrapInstallStatus.ACTIVATED
    assert index.current.manifest_sha256 == manifest.canonical_sha256()
    assert index.previous is None
    assert Path(index.current.install_path, manifest.entrypoint).is_file()
    assert health.checked == ["0.2.0"]
    assert verifier.verified.count(manifest.canonical_sha256()) >= 2
    assert not list(installer.versions.glob(".staging-*"))


def test_verifier_rejects_signed_package_without_sbom(tmp_path: Path) -> None:
    package, manifest = _package(tmp_path, "0.2.0")
    without_sbom = TargetPackageManifest(
        **{
            **manifest.model_dump(mode="python", exclude={"files"}),
            "files": [
                item
                for item in manifest.files
                if item.role != TargetPackageFileRole.SBOM
            ],
        }
    )
    signature = TargetPackageSignature(
        key_id="release-key-2026",
        manifest_sha256=without_sbom.canonical_sha256(),
        signature_base64=b64encode(b"s" * 64).decode("ascii"),
    )
    (package / TARGET_PACKAGE_SBOM_NAME).unlink()
    (package / "target-package.json").write_text(
        without_sbom.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (package / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires one signed SBOM"):
        verify_target_package(package, without_sbom, signature, AcceptingVerifier())


def test_repeated_same_version_and_digest_is_idempotent(tmp_path: Path) -> None:
    package, manifest = _package(tmp_path, "0.2.0")
    verifier = AcceptingVerifier()
    health = VersionHealthChecker({"0.2.0"})
    installer = TargetPackageInstaller(tmp_path / "install")
    first = installer.install_and_activate(
        package,
        preflight=_preflight(manifest),
        verifier=verifier,
        health_checker=health,
    )
    second = installer.install_and_activate(
        package,
        preflight=_preflight(manifest),
        verifier=verifier,
        health_checker=health,
        expect_current_present=True,
        expected_current_manifest_sha256=manifest.canonical_sha256(),
    )

    assert first.status == BootstrapInstallStatus.ACTIVATED
    assert second.status == BootstrapInstallStatus.ALREADY_ACTIVE
    assert second.installed == first.installed
    installed_versions = [
        path for path in installer.versions.iterdir() if not path.name.startswith(".")
    ]
    assert len(installed_versions) == 1


def test_failed_new_health_check_keeps_previous_version_active(tmp_path: Path) -> None:
    package_v1, manifest_v1 = _package(tmp_path, "0.1.0")
    package_v2, manifest_v2 = _package(tmp_path, "0.2.0")
    verifier = AcceptingVerifier()
    health = VersionHealthChecker({"0.1.0"})
    installer = TargetPackageInstaller(tmp_path / "install")
    installer.install_and_activate(
        package_v1,
        preflight=_preflight(manifest_v1),
        verifier=verifier,
        health_checker=health,
    )

    result = installer.install_and_activate(
        package_v2,
        preflight=_preflight(manifest_v2),
        verifier=verifier,
        health_checker=health,
        expected_current_manifest_sha256=manifest_v1.canonical_sha256(),
    )
    index = TargetInstallIndex.model_validate_json(
        installer.current_path.read_text(encoding="utf-8")
    )

    assert result.status == BootstrapInstallStatus.HEALTH_CHECK_FAILED
    assert result.active is not None
    assert result.active.package_version == "0.1.0"
    assert index.current.package_version == "0.1.0"
    assert Path(result.installed.install_path).is_dir()


def test_upgrade_and_rollback_use_digest_compare_and_swap(tmp_path: Path) -> None:
    package_v1, manifest_v1 = _package(tmp_path, "0.1.0")
    package_v2, manifest_v2 = _package(tmp_path, "0.2.0")
    verifier = AcceptingVerifier()
    health = VersionHealthChecker({"0.1.0", "0.2.0"})
    installer = TargetPackageInstaller(tmp_path / "install")
    installer.install_and_activate(
        package_v1,
        preflight=_preflight(manifest_v1),
        verifier=verifier,
        health_checker=health,
    )
    upgraded = installer.install_and_activate(
        package_v2,
        preflight=_preflight(manifest_v2),
        verifier=verifier,
        health_checker=health,
        expected_current_manifest_sha256=manifest_v1.canonical_sha256(),
    )

    with pytest.raises(ValueError, match="previous target package changed"):
        installer.rollback(
            verifier=verifier,
            health_checker=health,
            expected_current_manifest_sha256=manifest_v2.canonical_sha256(),
            expected_previous_package_id=manifest_v1.package_id,
            expected_previous_manifest_sha256="0" * 64,
        )

    rolled_back = installer.rollback(
        verifier=verifier,
        health_checker=health,
        expected_current_manifest_sha256=manifest_v2.canonical_sha256(),
        expected_previous_package_id=manifest_v1.package_id,
        expected_previous_manifest_sha256=manifest_v1.canonical_sha256(),
    )

    assert upgraded.status == BootstrapInstallStatus.ACTIVATED
    assert rolled_back.status == BootstrapInstallStatus.ROLLED_BACK
    assert rolled_back.active is not None
    assert rolled_back.active.package_version == "0.1.0"
    with pytest.raises(ValueError, match="changed before rollback"):
        installer.rollback(
            verifier=verifier,
            health_checker=health,
            expected_current_manifest_sha256=manifest_v2.canonical_sha256(),
            expected_previous_package_id=manifest_v1.package_id,
            expected_previous_manifest_sha256=manifest_v1.canonical_sha256(),
        )


def test_tamper_extra_file_and_copy_interruption_never_activate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, manifest = _package(tmp_path, "0.2.0")
    verifier = AcceptingVerifier()
    health = VersionHealthChecker({"0.2.0"})
    installer = TargetPackageInstaller(tmp_path / "install")
    (package / "undeclared.txt").write_text("smuggled", encoding="utf-8")
    with pytest.raises(ValueError, match="undeclared files"):
        installer.install_and_activate(
            package,
            preflight=_preflight(manifest),
            verifier=verifier,
            health_checker=health,
        )
    assert not installer.current_path.exists()
    (package / "undeclared.txt").unlink()

    def interrupted_copy(source, destination):  # type: ignore[no-untyped-def]
        raise OSError("simulated interrupted offline upload")

    monkeypatch.setattr("rolo.targets.package_installer.shutil.copyfile", interrupted_copy)
    with pytest.raises(OSError, match="interrupted offline upload"):
        installer.install_and_activate(
            package,
            preflight=_preflight(manifest),
            verifier=verifier,
            health_checker=health,
        )
    assert not installer.current_path.exists()
    assert not list(installer.versions.glob(".staging-*"))


def test_ed25519_package_signing_uses_pinned_public_key_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    _, manifest = _package(tmp_path, "0.2.0")
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release-signing.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = sign_target_package(
        manifest,
        key_id="release-key-2026",
        private_key_path=private_path,
    )
    verifier = Ed25519TargetPackageVerifier({"release-key-2026": public_bytes})

    verifier.verify(manifest, signature)

    tampered = manifest.model_copy(update={"rolo_version": "0.2.1"})
    rebound_signature = signature.model_copy(
        update={"manifest_sha256": tampered.canonical_sha256()}
    )
    with pytest.raises(ValueError, match="verification failed"):
        verifier.verify(tampered, rebound_signature)
    with pytest.raises(ValueError, match="not pinned"):
        Ed25519TargetPackageVerifier({"other-key": public_bytes}).verify(
            manifest,
            signature,
        )
