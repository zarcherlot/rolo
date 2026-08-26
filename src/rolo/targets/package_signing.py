from __future__ import annotations

import hashlib
import os
import stat
from base64 import b64decode, b64encode
from collections.abc import Mapping
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from rolo.targets.bootstrap import TargetPackageManifest, TargetPackageSignature

_MAX_KEY_BYTES = 64 * 1024


def _read_bounded_key(path: Path, *, private: bool) -> bytes:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ValueError("target package signing key is unavailable or is a symlink")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError("target package signing key is unavailable or is a symlink")
    if resolved.stat().st_size > _MAX_KEY_BYTES:
        raise ValueError("target package signing key exceeded its size limit")
    if private and os.name == "posix" and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise ValueError("target package private signing key must not be group/world accessible")
    return resolved.read_bytes()


def sign_target_package(
    manifest: TargetPackageManifest,
    *,
    key_id: str,
    private_key_path: Path,
) -> TargetPackageSignature:
    try:
        key = serialization.load_pem_private_key(
            _read_bounded_key(private_key_path, private=True),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("target package private signing key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("target package private signing key must be Ed25519")
    signature = key.sign(manifest.canonical_json().encode("utf-8"))
    return TargetPackageSignature(
        key_id=key_id,
        manifest_sha256=manifest.canonical_sha256(),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def _load_public_key(payload: bytes, *, key_id: str) -> Ed25519PublicKey:
    try:
        if payload.startswith(b"-----BEGIN"):
            key = serialization.load_pem_public_key(payload)
        else:
            key = Ed25519PublicKey.from_public_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid target package public signing key: {key_id}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"target package public signing key is not Ed25519: {key_id}")
    return key


def ed25519_public_key_sha256(value: bytes | Path) -> str:
    payload = _read_bounded_key(value, private=False) if isinstance(value, Path) else value
    key = _load_public_key(payload, key_id="fingerprint")
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


class Ed25519TargetPackageVerifier:
    """Verify package signatures against a pinned, secret-free public-key set."""

    def __init__(self, public_keys: Mapping[str, bytes | Path]) -> None:
        if not public_keys:
            raise ValueError("at least one target package public signing key is required")
        loaded: dict[str, Ed25519PublicKey] = {}
        fingerprints: dict[str, str] = {}
        for key_id, value in public_keys.items():
            if key_id in loaded:
                raise ValueError(f"duplicate target package signing key: {key_id}")
            payload = _read_bounded_key(value, private=False) if isinstance(value, Path) else value
            key = _load_public_key(payload, key_id=key_id)
            loaded[key_id] = key
            fingerprints[key_id] = ed25519_public_key_sha256(payload)
        self._keys = loaded
        self._fingerprints = fingerprints

    def public_key_sha256(self, key_id: str) -> str:
        try:
            return self._fingerprints[key_id]
        except KeyError as exc:
            raise ValueError("target package signature key is not pinned") from exc

    def verify(
        self,
        manifest: TargetPackageManifest,
        signature: TargetPackageSignature,
    ) -> None:
        signature.validate_manifest(manifest)
        try:
            key = self._keys[signature.key_id]
        except KeyError as exc:
            raise ValueError("target package signature key is not pinned") from exc
        try:
            key.verify(
                b64decode(signature.signature_base64, validate=True),
                manifest.canonical_json().encode("utf-8"),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("target package Ed25519 signature verification failed") from exc
