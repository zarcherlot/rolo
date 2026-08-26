from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.models import TargetProfile
from rolo.targets.package_installer import (
    PACKAGE_MANIFEST_NAME,
    PACKAGE_SIGNATURE_NAME,
    load_target_package,
    verify_target_package,
)
from rolo.targets.package_signing import (
    Ed25519TargetPackageVerifier,
    ed25519_public_key_sha256,
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_PACKAGE_REF = re.compile(
    r"^(?P<package_id>[A-Za-z0-9][A-Za-z0-9_.-]{0,127})@(?P<digest>[0-9a-f]{64})$"
)
_RECORD_NAME = "registry-record.json"
_MAX_PUBLIC_KEY_BYTES = 16 * 1024
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_SIGNATURE_BYTES = 64 * 1024
_MAX_PACKAGE_BYTES = 8 * 1024 * 1024 * 1024


class TargetPackageRegistryRecord(BaseModel):
    """Immutable Controller-side identity for one verified runtime package."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-registry-record/v1"] = (
        "rolo-target-package-registry-record/v1"
    )
    package_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}@[0-9a-f]{64}$")
    package_id: str = Field(pattern=_IDENTIFIER)
    package_version: str = Field(min_length=1, max_length=128)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signing_key_id: str = Field(pattern=_IDENTIFIER)
    signing_public_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    declared_file_count: int = Field(ge=1, le=100_000)
    declared_size_bytes: int = Field(ge=0)
    imported_at: datetime

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


class TargetPackageRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-registry-entry/v1"] = (
        "rolo-target-package-registry-entry/v1"
    )
    record: TargetPackageRegistryRecord
    package_root: str = Field(min_length=1, max_length=4096)


def _release_key(profile: TargetProfile) -> tuple[str, bytes, str]:
    if (
        profile.release_signing_key_id is None
        or profile.release_signing_public_key_path is None
        or profile.release_signing_public_key_sha256 is None
    ):
        raise ValueError("TargetProfile requires a complete release-signing key pin")
    path = Path(profile.release_signing_public_key_path).expanduser()
    if path.is_symlink():
        raise ValueError("release-signing public key pin path is unavailable")
    resolved = path.resolve()
    if not resolved.is_file() or resolved.stat().st_size > _MAX_PUBLIC_KEY_BYTES:
        raise ValueError("release-signing public key pin path is unavailable")
    payload = resolved.read_bytes()
    if ed25519_public_key_sha256(payload) != profile.release_signing_public_key_sha256:
        raise ValueError("release-signing public key pin digest mismatch")
    return profile.release_signing_key_id, payload, profile.release_signing_public_key_sha256


def _copy_regular_file(source_root: Path, destination_root: Path, relative: str) -> None:
    source = source_root / Path(relative)
    if source.is_symlink():
        raise ValueError(f"target package cannot contain symlinks: {relative}")
    resolved = source.resolve()
    if not resolved.is_relative_to(source_root) or not resolved.is_file():
        raise ValueError(f"target package file is unavailable: {relative}")
    destination = destination_root / Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(resolved, destination, follow_symlinks=False)


def _validate_metadata_bounds(root: Path) -> None:
    for name, limit in (
        (PACKAGE_MANIFEST_NAME, _MAX_MANIFEST_BYTES),
        (PACKAGE_SIGNATURE_NAME, _MAX_SIGNATURE_BYTES),
    ):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError(f"target package metadata is unavailable or too large: {name}")


class TargetPackageRegistry:
    """Verified, immutable Controller package store addressed by package identity."""

    def __init__(self, root: Path) -> None:
        candidate = root.expanduser()
        if candidate.is_symlink():
            raise ValueError("target package registry root cannot be a symbolic link")
        candidate = candidate.absolute()
        candidate.mkdir(parents=True, exist_ok=True)
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("target package registry root is unavailable")
        self.root = candidate.resolve()

    @staticmethod
    def parse_ref(package_ref: str) -> tuple[str, str]:
        match = _PACKAGE_REF.fullmatch(package_ref)
        if match is None:
            raise ValueError("invalid target package reference")
        return match.group("package_id"), match.group("digest")

    def _path(self, package_ref: str) -> Path:
        package_id, digest = self.parse_ref(package_ref)
        # Both values are strict single path components. Do not resolve this path before it
        # exists: on Windows a concurrent atomic directory publication can make resolve()
        # transiently observe inconsistent parent state.
        return self.root / package_id / digest

    @staticmethod
    def _load_record(path: Path) -> TargetPackageRegistryRecord:
        record_path = path / _RECORD_NAME
        if record_path.is_symlink() or not record_path.is_file():
            raise ValueError("target package registry record is unavailable")
        if record_path.stat().st_size > 64 * 1024:
            raise ValueError("target package registry record exceeded its size limit")
        return TargetPackageRegistryRecord.model_validate_json(
            record_path.read_text(encoding="utf-8")
        )

    def import_package(
        self,
        source: Path,
        *,
        profile: TargetProfile,
        now: datetime | None = None,
    ) -> TargetPackageRegistryEntry:
        key_id, public_key, public_key_sha256 = _release_key(profile)
        _validate_metadata_bounds(source.expanduser().resolve())
        source_root, manifest, signature = load_target_package(source)
        if signature.key_id != key_id:
            raise ValueError("target package signing key differs from TargetProfile pin")
        verifier = Ed25519TargetPackageVerifier({key_id: public_key})
        verify_target_package(source_root, manifest, signature, verifier)
        if sum(item.size_bytes for item in manifest.files) > _MAX_PACKAGE_BYTES:
            raise ValueError("target package exceeded Controller registry size limit")
        manifest_sha256 = manifest.canonical_sha256()
        package_ref = f"{manifest.package_id}@{manifest_sha256}"
        destination = self._path(package_ref)
        record = TargetPackageRegistryRecord(
            package_ref=package_ref,
            package_id=manifest.package_id,
            package_version=manifest.package_version,
            manifest_sha256=manifest_sha256,
            signing_key_id=key_id,
            signing_public_key_sha256=public_key_sha256,
            declared_file_count=len(manifest.files),
            declared_size_bytes=sum(item.size_bytes for item in manifest.files),
            imported_at=now or datetime.now(timezone.utc),
        )
        lock_target = destination.parent / f".{manifest_sha256}.publish"
        with interprocess_lock(lock_target):
            if destination.exists():
                return self.resolve(package_ref, profile=profile)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.parent.is_symlink():
                raise ValueError("target package registry path cannot be a symbolic link")
            staging = destination.parent / f".s{uuid4().hex[:12]}"
            staging.mkdir()
            try:
                package_staging = staging / "package"
                package_staging.mkdir()
                for relative in (
                    PACKAGE_MANIFEST_NAME,
                    PACKAGE_SIGNATURE_NAME,
                    *(item.path for item in manifest.files),
                ):
                    _copy_regular_file(source_root, package_staging, relative)
                copied_root, copied_manifest, copied_signature = load_target_package(
                    package_staging
                )
                verify_target_package(copied_root, copied_manifest, copied_signature, verifier)
                if (
                    copied_manifest.package_id != manifest.package_id
                    or copied_manifest.canonical_sha256() != manifest_sha256
                    or copied_signature != signature
                ):
                    raise ValueError("target package changed during registry import")
                atomic_write_text(
                    staging / _RECORD_NAME,
                    record.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                    require_absent=True,
                )
                os.replace(staging, destination)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        return self.resolve(package_ref, profile=profile)

    def resolve(
        self,
        package_ref: str,
        *,
        profile: TargetProfile,
    ) -> TargetPackageRegistryEntry:
        destination = self._path(package_ref)
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("target package reference is unavailable")
        resolved_destination = destination.resolve()
        if (
            not resolved_destination.is_relative_to(self.root)
            or resolved_destination != destination
        ):
            raise ValueError("target package reference escaped registry root")
        package_id, manifest_sha256 = self.parse_ref(package_ref)
        record = self._load_record(destination)
        if (
            record.package_ref != package_ref
            or record.package_id != package_id
            or record.manifest_sha256 != manifest_sha256
        ):
            raise ValueError("target package registry record binding mismatch")
        key_id, public_key, public_key_sha256 = _release_key(profile)
        if (
            record.signing_key_id != key_id
            or record.signing_public_key_sha256 != public_key_sha256
        ):
            raise ValueError("target package registry entry differs from TargetProfile pin")
        package_root = destination / "package"
        if package_root.is_symlink():
            raise ValueError("target package registry package cannot be a symbolic link")
        _validate_metadata_bounds(package_root)
        root, manifest, signature = load_target_package(package_root)
        verifier = Ed25519TargetPackageVerifier({key_id: public_key})
        verify_target_package(root, manifest, signature, verifier)
        if (
            signature.key_id != key_id
            or manifest.package_id != package_id
            or manifest.package_version != record.package_version
            or manifest.canonical_sha256() != manifest_sha256
            or len(manifest.files) != record.declared_file_count
            or sum(item.size_bytes for item in manifest.files) != record.declared_size_bytes
        ):
            raise ValueError("target package registry content binding mismatch")
        return TargetPackageRegistryEntry(record=record, package_root=str(root))
