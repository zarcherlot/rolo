from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rolo.targets.bootstrap import (
    TARGET_PACKAGE_SBOM_NAME,
    TargetArchitecture,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageSignature,
)
from rolo.targets.package_installer import (
    PACKAGE_MANIFEST_NAME,
    PACKAGE_SIGNATURE_NAME,
    _write_package_metadata,
)
from rolo.targets.package_sbom import TargetPackageSbom, bind_target_package_sbom
from rolo.targets.package_signing import sign_target_package


class TargetPackageBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-build-result/v1"] = (
        "rolo-target-package-build-result/v1"
    )
    package_root: str = Field(min_length=1, max_length=4096)
    manifest: TargetPackageManifest
    signature: TargetPackageSignature
    sbom: TargetPackageSbom


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _role(path: str, *, entrypoint: str) -> TargetPackageFileRole:
    if path == entrypoint:
        return TargetPackageFileRole.ENTRYPOINT
    if path.startswith("systemd/") or path.startswith("service/"):
        return TargetPackageFileRole.SERVICE
    if path.startswith("config/"):
        return TargetPackageFileRole.CONFIG
    if path.startswith("licenses/") or path.casefold().startswith("license"):
        return TargetPackageFileRole.LICENSE
    return TargetPackageFileRole.RUNTIME


class TargetPackageBuilder:
    """Build a deterministic signed package from an already prepared target runtime tree."""

    def build(
        self,
        source_root: Path,
        output_root: Path,
        *,
        package_id: str,
        package_version: str,
        rolo_version: str,
        architecture: TargetArchitecture,
        python_requires: str,
        entrypoint: str,
        signing_key_id: str,
        private_key_path: Path,
        requires_bubblewrap: bool = True,
        requires_user_namespace: bool = True,
        requires_mount_namespace: bool = True,
        requires_network_namespace: bool = True,
        minimum_address_space_bytes: int = 512 * 1024 * 1024,
        minimum_processes: int = 16,
    ) -> TargetPackageBuildResult:
        source_candidate = source_root.expanduser()
        output_candidate = output_root.expanduser()
        if source_candidate.is_symlink() or output_candidate.is_symlink():
            raise ValueError("target package build roots cannot be symlinks")
        source = source_candidate.resolve()
        output = output_candidate.resolve()
        if not source.is_dir():
            raise ValueError("target package source root is not a directory")
        if output.exists():
            raise FileExistsError("target package output root already exists")
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("target package source and output roots cannot contain each other")
        signing_key = private_key_path.expanduser().resolve()
        if signing_key.is_relative_to(source):
            raise ValueError("target package source cannot contain its private signing key")
        observed: list[Path] = []
        for path in source.rglob("*"):
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                raise ValueError(f"target package source cannot contain symlinks: {relative}")
            if path.is_file():
                observed.append(path)
        if not observed:
            raise ValueError("target package source root contains no files")
        relative_paths = {path.relative_to(source).as_posix() for path in observed}
        generated = {
            PACKAGE_MANIFEST_NAME,
            PACKAGE_SIGNATURE_NAME,
            TARGET_PACKAGE_SBOM_NAME,
        }
        if relative_paths & generated:
            raise ValueError("target package source cannot contain generated metadata")
        files: list[TargetPackageFile] = []
        for path in sorted(observed, key=lambda value: value.relative_to(source).as_posix()):
            relative = path.relative_to(source).as_posix()
            mode = (
                stat.S_IMODE(path.stat().st_mode)
                if os.name == "posix"
                else (0o755 if relative == entrypoint else 0o644)
            )
            if relative == entrypoint:
                mode |= 0o500
            files.append(
                TargetPackageFile(
                    path=relative,
                    sha256=_sha256_file(path),
                    size_bytes=path.stat().st_size,
                    mode=mode,
                    role=_role(relative, entrypoint=entrypoint),
                )
            )
        manifest_without_sbom = TargetPackageManifest(
            package_id=package_id,
            package_version=package_version,
            rolo_version=rolo_version,
            architecture=architecture,
            python_requires=python_requires,
            entrypoint=entrypoint,
            files=files,
            requires_bubblewrap=requires_bubblewrap,
            requires_user_namespace=requires_user_namespace,
            requires_mount_namespace=requires_mount_namespace,
            requires_network_namespace=requires_network_namespace,
            minimum_address_space_bytes=minimum_address_space_bytes,
            minimum_processes=minimum_processes,
        )
        manifest, sbom, sbom_payload = bind_target_package_sbom(
            manifest_without_sbom
        )
        signature = sign_target_package(
            manifest,
            key_id=signing_key_id,
            private_key_path=signing_key,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.parent / f".package-staging-{uuid4().hex}"
        staging.mkdir()
        try:
            for item in manifest.files:
                if item.role == TargetPackageFileRole.SBOM:
                    continue
                source_path = source.joinpath(*Path(item.path).parts)
                destination = staging.joinpath(*Path(item.path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, destination)
                if os.name == "posix":
                    destination.chmod(item.mode)
            (staging / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
            if os.name == "posix":
                (staging / TARGET_PACKAGE_SBOM_NAME).chmod(0o644)
            _write_package_metadata(staging, manifest, signature)
            staging.replace(output)
        except Exception:
            if staging.is_dir() and staging.resolve().is_relative_to(output.parent.resolve()):
                shutil.rmtree(staging)
            raise
        return TargetPackageBuildResult(
            package_root=str(output),
            manifest=manifest,
            signature=signature,
            sbom=sbom,
        )
