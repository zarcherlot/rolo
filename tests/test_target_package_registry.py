from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    OrchestratorPlacement,
    TargetArchitecture,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageRegistry,
    TargetProfile,
    TargetTransport,
    TargetTrustLevel,
    bind_target_package_sbom,
    ed25519_public_key_sha256,
    sign_target_package,
)


def _signed_package(tmp_path: Path) -> tuple[Path, Path, bytes]:
    root = tmp_path / "source-package"
    entrypoint = root / "bin" / "robotctl"
    runtime = root / "share" / "runtime.json"
    entrypoint.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho healthy\n")
    runtime.write_text('{"version":"0.2.0"}', encoding="utf-8")

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
        package_version="0.2.0",
        rolo_version="0.2.0",
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
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "release.pub"
    public_path.write_bytes(public_key)
    signature = sign_target_package(
        manifest,
        key_id="release-key-2026",
        private_key_path=private_path,
    )
    (root / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return root, public_path, public_key


def _profile(public_path: Path, public_key: bytes) -> TargetProfile:
    return TargetProfile(
        target_id="wheeltec",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/home/robot/wheeltec_ws",
        desired_rolo_version="0.2.0",
        trust_level=TargetTrustLevel.STRICT,
        release_signing_key_id="release-key-2026",
        release_signing_public_key_path=str(public_path.absolute()),
        release_signing_public_key_sha256=ed25519_public_key_sha256(public_key),
    )


def test_registry_import_is_verified_immutable_and_concurrently_idempotent(
    tmp_path: Path,
) -> None:
    source, public_path, public_key = _signed_package(tmp_path)
    profile = _profile(public_path, public_key)
    now = datetime.now(timezone.utc)

    for round_index in range(10):
        registry = TargetPackageRegistry(tmp_path / f"registry-{round_index}")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(
                    registry.import_package,
                    source,
                    profile=profile,
                    now=now + timedelta(seconds=offset),
                )
                for offset in range(4)
            ]
            entries = [future.result() for future in futures]

        assert len({item.record.package_ref for item in entries}) == 1
        assert len({item.record.imported_at for item in entries}) == 1
        entry = registry.resolve(entries[0].record.package_ref, profile=profile)
        package_root = Path(entry.package_root)
        assert package_root.parent.parent.parent == registry.root
        assert str(source.resolve()) not in (
            package_root.parent / "registry-record.json"
        ).read_text(encoding="utf-8")
        assert (package_root / "bin" / "robotctl").read_bytes().startswith(
            b"#!/bin/sh"
        )


def test_registry_rejects_unverified_paths_and_detects_stored_tamper(
    tmp_path: Path,
) -> None:
    source, public_path, public_key = _signed_package(tmp_path)
    profile = _profile(public_path, public_key)
    registry = TargetPackageRegistry(tmp_path / "registry")

    (source / "undeclared.txt").write_text("no", encoding="utf-8")
    with pytest.raises(ValueError, match="undeclared"):
        registry.import_package(source, profile=profile)
    (source / "undeclared.txt").unlink()
    entry = registry.import_package(source, profile=profile)

    with pytest.raises(ValueError, match="invalid target package reference"):
        registry.resolve("../escape@" + "a" * 64, profile=profile)

    (Path(entry.package_root) / "share" / "runtime.json").write_text(
        "tampered",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mismatch"):
        registry.resolve(entry.record.package_ref, profile=profile)


def test_registry_rechecks_current_target_release_pin(tmp_path: Path) -> None:
    source, public_path, public_key = _signed_package(tmp_path)
    registry = TargetPackageRegistry(tmp_path / "registry")
    entry = registry.import_package(source, profile=_profile(public_path, public_key))
    other = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    other_path = tmp_path / "other.pub"
    other_path.write_bytes(other)

    with pytest.raises(ValueError, match="differs from TargetProfile pin"):
        registry.resolve(entry.record.package_ref, profile=_profile(other_path, other))
