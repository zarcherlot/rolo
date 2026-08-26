from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.bootstrap import (
    BootstrapInstallStatus,
    TargetBootstrapInstallResult,
    TargetInstalledRelease,
    TargetInstallIndex,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageSignature,
    TargetPlatformPreflight,
    TargetPreflightStatus,
)
from rolo.targets.package_sbom import (
    MAX_TARGET_PACKAGE_SBOM_BYTES,
    TargetPackageSbom,
    verify_target_package_sbom,
)

PACKAGE_MANIFEST_NAME = "target-package.json"
PACKAGE_SIGNATURE_NAME = "target-package.sig.json"


class TargetPackageSignatureVerifier(Protocol):
    def verify(
        self,
        manifest: TargetPackageManifest,
        signature: TargetPackageSignature,
    ) -> None: ...


class TargetRuntimeHealthChecker(Protocol):
    def check(self, entrypoint: Path, manifest: TargetPackageManifest) -> bool: ...


class TargetPackageInstallStateConflict(ValueError):
    """The active index no longer matches the caller's compare-and-swap expectation."""


class TargetPackageActiveUnavailable(ValueError):
    """No active release is available for status-dependent operations."""


class TargetPackageRollbackUnavailable(ValueError):
    """No valid previous release is available for rollback."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_file(root: Path, relative: str) -> Path:
    candidate = root / Path(relative)
    if candidate.is_symlink():
        raise ValueError(f"target package file cannot be a symlink: {relative}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"target package file escaped package root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"target package file is unavailable: {relative}")
    return resolved


def load_target_package(
    package_root: Path,
) -> tuple[Path, TargetPackageManifest, TargetPackageSignature]:
    candidate = package_root.expanduser()
    if candidate.is_symlink():
        raise ValueError("target package root cannot be a symlink")
    root = candidate.resolve()
    if not root.is_dir():
        raise ValueError("target package root is not a directory")
    try:
        manifest = TargetPackageManifest.model_validate_json(
            _contained_file(root, PACKAGE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        signature = TargetPackageSignature.model_validate_json(
            _contained_file(root, PACKAGE_SIGNATURE_NAME).read_text(encoding="utf-8")
        )
    except UnicodeError as exc:
        raise ValueError("target package metadata is not UTF-8") from exc
    signature.validate_manifest(manifest)
    return root, manifest, signature


def verify_target_package(
    package_root: Path,
    manifest: TargetPackageManifest,
    signature: TargetPackageSignature,
    verifier: TargetPackageSignatureVerifier,
) -> None:
    root = package_root.expanduser().resolve()
    signature.validate_manifest(manifest)
    verifier.verify(manifest, signature)
    declared = {item.path for item in manifest.files}
    allowed = declared | {PACKAGE_MANIFEST_NAME, PACKAGE_SIGNATURE_NAME}
    observed: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"target package cannot contain symlinks: {relative}")
        if path.is_file():
            observed.add(relative)
    undeclared = sorted(observed - allowed)
    missing = sorted(allowed - observed)
    if undeclared:
        raise ValueError(f"target package contains undeclared files: {undeclared}")
    if missing:
        raise ValueError(f"target package files are missing: {missing}")
    sbom_files = [
        item for item in manifest.files if item.role == TargetPackageFileRole.SBOM
    ]
    if len(sbom_files) != 1:
        raise ValueError("target package requires one signed SBOM")
    if sbom_files[0].size_bytes > MAX_TARGET_PACKAGE_SBOM_BYTES:
        raise ValueError("target package SBOM exceeded its size limit")
    for item in manifest.files:
        path = _contained_file(root, item.path)
        if path.stat().st_size != item.size_bytes:
            raise ValueError(f"target package file size mismatch: {item.path}")
        if _sha256_file(path) != item.sha256:
            raise ValueError(f"target package file digest mismatch: {item.path}")
    sbom_path = _contained_file(root, sbom_files[0].path)
    try:
        sbom = TargetPackageSbom.model_validate_json(
            sbom_path.read_text(encoding="utf-8")
        )
    except UnicodeError as exc:
        raise ValueError("target package SBOM is not UTF-8") from exc
    verify_target_package_sbom(manifest, sbom)


def _write_package_metadata(
    root: Path,
    manifest: TargetPackageManifest,
    signature: TargetPackageSignature,
) -> None:
    atomic_write_text(
        root / PACKAGE_MANIFEST_NAME,
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        acquire_lock=False,
    )
    atomic_write_text(
        root / PACKAGE_SIGNATURE_NAME,
        json.dumps(
            signature.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        acquire_lock=False,
    )


class TargetPackageInstaller:
    """Target-local immutable install and atomic activation transaction."""

    def __init__(self, install_root: Path) -> None:
        self.root = install_root.expanduser().resolve()
        self.versions = self.root / "versions"
        self.current_path = self.root / "current.json"

    def _load_current(self) -> TargetInstallIndex | None:
        if not self.current_path.is_file():
            return None
        index = TargetInstallIndex.model_validate_json(
            self.current_path.read_text(encoding="utf-8")
        )
        self._validate_install_reference(index.current)
        if index.previous is not None:
            self._validate_install_reference(index.previous)
        return index

    def _validate_install_reference(self, release: TargetInstalledRelease) -> Path:
        path = Path(release.install_path).expanduser().resolve()
        versions = self.versions.resolve()
        if not path.is_relative_to(versions) or not path.is_dir():
            raise ValueError("target install index references an invalid version directory")
        return path

    @staticmethod
    def _health(
        root: Path,
        manifest: TargetPackageManifest,
        checker: TargetRuntimeHealthChecker,
    ) -> bool:
        try:
            return bool(checker.check(_contained_file(root, manifest.entrypoint), manifest))
        except (OSError, ValueError):
            return False

    def _installed_reference(
        self,
        manifest: TargetPackageManifest,
        version_root: Path,
    ) -> TargetInstalledRelease:
        return TargetInstalledRelease(
            package_id=manifest.package_id,
            package_version=manifest.package_version,
            manifest_sha256=manifest.canonical_sha256(),
            install_path=str(version_root.resolve()),
        )

    def status(self) -> TargetInstallIndex | None:
        """Return the validated active index under the same lock used by mutations."""

        with interprocess_lock(self.current_path):
            return self._load_current()

    def health_current(
        self,
        *,
        verifier: TargetPackageSignatureVerifier,
        health_checker: TargetRuntimeHealthChecker,
    ) -> tuple[TargetInstallIndex, bool]:
        """Reverify and health-check current without changing activation state."""

        with interprocess_lock(self.current_path):
            current = self._load_current()
            if current is None:
                raise TargetPackageActiveUnavailable(
                    "target package health check has no active version"
                )
            root = self._validate_install_reference(current.current)
            _, manifest, signature = load_target_package(root)
            if manifest.canonical_sha256() != current.current.manifest_sha256:
                raise ValueError("active target package manifest digest mismatch")
            verify_target_package(root, manifest, signature, verifier)
            return current, self._health(root, manifest, health_checker)

    def install_and_activate(
        self,
        package_root: Path,
        *,
        preflight: TargetPlatformPreflight,
        verifier: TargetPackageSignatureVerifier,
        health_checker: TargetRuntimeHealthChecker,
        expect_current_present: bool | None = None,
        expected_current_manifest_sha256: str | None = None,
    ) -> TargetBootstrapInstallResult:
        source, manifest, signature = load_target_package(package_root)
        if preflight.manifest_sha256 != manifest.canonical_sha256():
            raise ValueError("target package preflight manifest digest mismatch")
        if preflight.status != TargetPreflightStatus.READY:
            raise ValueError("target package preflight is blocked")
        verify_target_package(source, manifest, signature, verifier)
        digest = manifest.canonical_sha256()
        version_root = self.versions / f"{manifest.package_version}-{digest[:16]}"
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_lock(self.current_path):
            current = self._load_current()
            if expect_current_present is True and current is None:
                raise TargetPackageInstallStateConflict(
                    "active target package changed before installation"
                )
            if expect_current_present is False and current is not None:
                raise TargetPackageInstallStateConflict(
                    "active target package changed before installation"
                )
            if expected_current_manifest_sha256 is not None and (
                current is None
                or current.current.manifest_sha256 != expected_current_manifest_sha256
            ):
                raise TargetPackageInstallStateConflict(
                    "active target package changed before installation"
                )
            if version_root.exists():
                _, installed_manifest, installed_signature = load_target_package(version_root)
                if installed_manifest.canonical_sha256() != digest:
                    raise ValueError("installed target package version digest mismatch")
                verify_target_package(
                    version_root,
                    installed_manifest,
                    installed_signature,
                    verifier,
                )
            else:
                self.versions.mkdir(parents=True, exist_ok=True)
                staging = self.versions / f".staging-{uuid4().hex}"
                staging.mkdir()
                try:
                    for item in manifest.files:
                        source_path = _contained_file(source, item.path)
                        destination = staging / item.path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source_path, destination)
                        if os.name == "posix":
                            destination.chmod(item.mode)
                    _write_package_metadata(staging, manifest, signature)
                    verify_target_package(staging, manifest, signature, verifier)
                    staging.replace(version_root)
                except Exception:
                    safe_staging = staging.resolve().is_relative_to(self.versions.resolve())
                    if staging.is_dir() and safe_staging:
                        shutil.rmtree(staging)
                    raise
            installed = self._installed_reference(manifest, version_root)
            if (
                current is not None
                and current.current.manifest_sha256 == installed.manifest_sha256
            ):
                healthy = self._health(version_root, manifest, health_checker)
                return TargetBootstrapInstallResult(
                    status=(
                        BootstrapInstallStatus.ALREADY_ACTIVE
                        if healthy
                        else BootstrapInstallStatus.HEALTH_CHECK_FAILED
                    ),
                    installed=installed,
                    active=current.current,
                    previous_preserved=True,
                )
            if not self._health(version_root, manifest, health_checker):
                return TargetBootstrapInstallResult(
                    status=BootstrapInstallStatus.HEALTH_CHECK_FAILED,
                    installed=installed,
                    active=current.current if current is not None else None,
                    previous_preserved=True,
                )
            next_index = TargetInstallIndex(
                current=installed,
                previous=current.current if current is not None else None,
                activated_at=datetime.now(timezone.utc),
            )
            atomic_write_text(
                self.current_path,
                next_index.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
            return TargetBootstrapInstallResult(
                status=BootstrapInstallStatus.ACTIVATED,
                installed=installed,
                active=installed,
                previous_preserved=current is None or next_index.previous == current.current,
            )

    def rollback(
        self,
        *,
        verifier: TargetPackageSignatureVerifier,
        health_checker: TargetRuntimeHealthChecker,
        expected_current_manifest_sha256: str,
        expected_previous_package_id: str,
        expected_previous_manifest_sha256: str,
    ) -> TargetBootstrapInstallResult:
        with interprocess_lock(self.current_path):
            current = self._load_current()
            if current is None or current.previous is None:
                raise TargetPackageRollbackUnavailable(
                    "target package rollback has no previous version"
                )
            if current.current.manifest_sha256 != expected_current_manifest_sha256:
                raise TargetPackageInstallStateConflict(
                    "active target package changed before rollback"
                )
            if (
                current.previous.package_id != expected_previous_package_id
                or current.previous.manifest_sha256
                != expected_previous_manifest_sha256
            ):
                raise TargetPackageInstallStateConflict(
                    "previous target package changed before rollback"
                )
            previous_root = self._validate_install_reference(current.previous)
            _, manifest, signature = load_target_package(previous_root)
            if manifest.canonical_sha256() != current.previous.manifest_sha256:
                raise ValueError("previous target package manifest digest mismatch")
            verify_target_package(previous_root, manifest, signature, verifier)
            if not self._health(previous_root, manifest, health_checker):
                raise TargetPackageRollbackUnavailable(
                    "previous target package failed rollback health check"
                )
            next_index = TargetInstallIndex(
                current=current.previous,
                previous=current.current,
                activated_at=datetime.now(timezone.utc),
            )
            atomic_write_text(
                self.current_path,
                next_index.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
            return TargetBootstrapInstallResult(
                status=BootstrapInstallStatus.ROLLED_BACK,
                installed=current.previous,
                active=current.previous,
                previous_preserved=True,
            )
