"""Offline verification for signed minimal target companion packages."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.hashing import sha256_file

_SHA256 = r"^[0-9a-f]{64}$"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


class CompanionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-companion-manifest/v1"] = (
        "rolo-target-companion-manifest/v1"
    )
    package_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    package_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
    platform: Literal["linux"]
    architecture: str = Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")
    package_file: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    package_sha256: str = Field(pattern=_SHA256)
    publisher_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    signature_algorithm: Literal["hmac-sha256-v1"]
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManifestVerificationResult(BaseModel):
    schema_version: Literal["rolo-target-companion-verification/v1"] = (
        "rolo-target-companion-verification/v1"
    )
    package_id: str
    package_version: str
    publisher_id: str
    package_sha256: str
    verified: Literal[True] = True


def sign_companion_manifest(
    *,
    package_id: str,
    package_version: str,
    architecture: str,
    package_file: str,
    package_sha256: str,
    publisher_id: str,
    verification_key: bytes,
) -> CompanionManifest:
    if not verification_key:
        raise ValueError("manifest signing key must not be empty")
    unsigned = CompanionManifest(
        package_id=package_id,
        package_version=package_version,
        platform="linux",
        architecture=architecture,
        package_file=package_file,
        package_sha256=package_sha256,
        publisher_id=publisher_id,
        signature_algorithm="hmac-sha256-v1",
        signature="0" * 64,
    ).model_dump(mode="json")
    unsigned.pop("signature")
    signature = hmac.new(verification_key, _canonical_json(unsigned), hashlib.sha256).hexdigest()
    return CompanionManifest(signature=signature, **unsigned)


def verify_companion_manifest(
    manifest_path: Path,
    package_path: Path,
    *,
    verification_key: bytes,
) -> ManifestVerificationResult:
    if not verification_key:
        raise ValueError("manifest verification key must not be empty")
    manifest_path = manifest_path.expanduser().resolve()
    package_path = package_path.expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"companion manifest is missing: {manifest_path}")
    manifest = CompanionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    expected_package = (manifest_path.parent / manifest.package_file).resolve()
    if expected_package != package_path:
        raise ValueError("companion package path does not match its manifest")
    if not package_path.is_file():
        raise FileNotFoundError(f"companion package is missing: {package_path}")
    actual_digest = sha256_file(package_path)
    if actual_digest != manifest.package_sha256:
        raise ValueError("companion package hash does not match its manifest")
    unsigned = manifest.model_dump(mode="json")
    signature = unsigned.pop("signature")
    expected_signature = hmac.new(
        verification_key,
        _canonical_json(unsigned),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("companion manifest signature verification failed")
    return ManifestVerificationResult(
        package_id=manifest.package_id,
        package_version=manifest.package_version,
        publisher_id=manifest.publisher_id,
        package_sha256=actual_digest,
    )
