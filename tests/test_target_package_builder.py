from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    Ed25519TargetPackageVerifier,
    TargetArchitecture,
    TargetPackageBuilder,
    TargetPackageFileRole,
    TargetPackageSbom,
    TargetPackageSbomFileComponent,
    TargetPackageSbomHash,
    TargetPackageSbomProperty,
    verify_target_package,
    verify_target_package_sbom,
)


def _key_pair(tmp_path: Path) -> tuple[Path, Path]:
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "release.pem"
    public = tmp_path / "release.pub.pem"
    private.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    if os.name == "posix":
        private.chmod(0o600)
    return private, public


def _runtime_tree(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    files = {
        "bin/robotctl": b"#!/bin/sh\necho rolo\n",
        "share/rolo/runtime.bin": bytes(range(128)),
        "systemd/rolo-target.service": b"[Service]\nExecStart=/opt/rolo/bin/robotctl\n",
        "licenses/NOTICE": b"test notice\n",
    }
    for relative, payload in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    if os.name == "posix":
        (root / "bin/robotctl").chmod(0o755)
    return root


def _build(
    builder: TargetPackageBuilder,
    source: Path,
    output: Path,
    private_key: Path,
    architecture: TargetArchitecture,
):  # type: ignore[no-untyped-def]
    return builder.build(
        source,
        output,
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=architecture,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        signing_key_id="release-key-2026",
        private_key_path=private_key,
        minimum_address_space_bytes=2 * 1024 * 1024 * 1024,
        minimum_processes=64,
    )


def test_builder_emits_deterministic_verified_x86_and_arm_packages(tmp_path: Path) -> None:
    source = _runtime_tree(tmp_path)
    private_key, public_key = _key_pair(tmp_path)
    builder = TargetPackageBuilder()
    first = _build(
        builder,
        source,
        tmp_path / "out-x86-a",
        private_key,
        TargetArchitecture.X86_64,
    )
    repeated = _build(
        builder,
        source,
        tmp_path / "out-x86-b",
        private_key,
        TargetArchitecture.X86_64,
    )
    arm = _build(
        builder,
        source,
        tmp_path / "out-arm",
        private_key,
        TargetArchitecture.AARCH64,
    )
    verifier = Ed25519TargetPackageVerifier({"release-key-2026": public_key})

    assert first.manifest == repeated.manifest
    assert first.signature == repeated.signature
    assert first.manifest.canonical_sha256() != arm.manifest.canonical_sha256()
    assert arm.manifest.architecture == TargetArchitecture.AARCH64
    roles = {item.path: item.role for item in first.manifest.files}
    assert roles["bin/robotctl"] == TargetPackageFileRole.ENTRYPOINT
    assert roles["systemd/rolo-target.service"] == TargetPackageFileRole.SERVICE
    assert roles["licenses/NOTICE"] == TargetPackageFileRole.LICENSE
    assert roles[TARGET_PACKAGE_SBOM_NAME] == TargetPackageFileRole.SBOM
    assert first.sbom == repeated.sbom
    assert [component.name for component in first.sbom.components] == sorted(
        path for path in roles if path != TARGET_PACKAGE_SBOM_NAME
    )
    for result in (first, repeated, arm):
        root = Path(result.package_root)
        verify_target_package(root, result.manifest, result.signature, verifier)
        assert TargetPackageSbom.model_validate_json(
            (root / TARGET_PACKAGE_SBOM_NAME).read_text(encoding="utf-8")
        ) == result.sbom
        assert sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        ) == sorted(
            [
                "target-package.json",
                "target-package.sig.json",
                *(item.path for item in result.manifest.files),
            ]
        )
    first_root = Path(first.package_root)
    repeated_root = Path(repeated.package_root)
    for path in first_root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(first_root)
            assert path.read_bytes() == (repeated_root / relative).read_bytes()


def test_sbom_semantics_are_bound_to_the_signed_manifest(tmp_path: Path) -> None:
    source = _runtime_tree(tmp_path)
    private_key, _ = _key_pair(tmp_path)
    result = _build(
        TargetPackageBuilder(),
        source,
        tmp_path / "output",
        private_key,
        TargetArchitecture.X86_64,
    )
    original = result.sbom.components[0]
    tampered = result.sbom.model_copy(
        update={
            "components": [
                TargetPackageSbomFileComponent(
                    bom_ref="file:config/injected.json",
                    name="config/injected.json",
                    hashes=[TargetPackageSbomHash(content="0" * 64)],
                    properties=[
                        TargetPackageSbomProperty(name="rolo:mode", value="0644"),
                        TargetPackageSbomProperty(name="rolo:role", value="CONFIG"),
                        TargetPackageSbomProperty(name="rolo:size-bytes", value="1"),
                    ],
                ),
                *result.sbom.components[1:],
            ]
        }
    )

    assert original.name != tampered.components[0].name
    with pytest.raises(ValueError, match="does not match its signed manifest"):
        verify_target_package_sbom(result.manifest, tampered)


def test_builder_rejects_metadata_collision_existing_output_and_embedded_key(
    tmp_path: Path,
) -> None:
    source = _runtime_tree(tmp_path)
    private_key, _ = _key_pair(tmp_path)
    builder = TargetPackageBuilder()
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        _build(builder, source, output, private_key, TargetArchitecture.X86_64)

    (source / "target-package.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="generated metadata"):
        _build(
            builder,
            source,
            tmp_path / "metadata-output",
            private_key,
            TargetArchitecture.X86_64,
        )
    (source / "target-package.json").unlink()
    (source / TARGET_PACKAGE_SBOM_NAME).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="generated metadata"):
        _build(
            builder,
            source,
            tmp_path / "sbom-output",
            private_key,
            TargetArchitecture.X86_64,
        )
    (source / TARGET_PACKAGE_SBOM_NAME).unlink()
    embedded_key = source / "release.pem"
    embedded_key.write_bytes(private_key.read_bytes())
    if os.name == "posix":
        embedded_key.chmod(0o600)
    with pytest.raises(ValueError, match="private signing key"):
        _build(
            builder,
            source,
            tmp_path / "key-output",
            embedded_key,
            TargetArchitecture.X86_64,
        )


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks may require Windows privilege")
def test_builder_rejects_source_symlink(tmp_path: Path) -> None:
    source = _runtime_tree(tmp_path)
    private_key, _ = _key_pair(tmp_path)
    (source / "linked-runtime").symlink_to(source / "share/rolo/runtime.bin")

    with pytest.raises(ValueError, match="cannot contain symlinks"):
        _build(
            TargetPackageBuilder(),
            source,
            tmp_path / "output",
            private_key,
            TargetArchitecture.X86_64,
        )
