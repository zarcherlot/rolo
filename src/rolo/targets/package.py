"""Deterministic minimal companion package builder and manifest signer."""

from __future__ import annotations

import hashlib
from pathlib import Path

from rolo.targets.signing import CompanionManifest, sign_companion_manifest


def build_companion_package(
    output_dir: Path,
    *,
    package_version: str,
    architecture: str,
    publisher_id: str,
    verification_key: bytes,
    package_id: str = "rolo-target",
) -> tuple[Path, Path, CompanionManifest]:
    """Build a self-contained POSIX companion and its signed manifest.

    The generated executable intentionally exposes only ``--version`` until the
    target-side operation surface is released. This keeps the package usable for
    bootstrap health checks while making unsupported actions fail closed.
    """
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_version = package_version.replace("+", "_")
    package_path = output_dir / f"{package_id}-{safe_version}-{architecture}"
    payload = (
        "#!/bin/sh\n"
        "set -eu\n"
        f'if [ "${{1:-}}" = "--version" ]; then '
        f'printf \'%s\\n\' "{package_id} {package_version}"; exit 0; fi\n'
        "printf '%s\\n' 'unsupported rolo-target operation' >&2\n"
        "exit 2\n"
    ).encode()
    package_path.write_bytes(payload)
    package_path.chmod(0o755)
    package_sha256 = hashlib.sha256(payload).hexdigest()
    manifest = sign_companion_manifest(
        package_id=package_id,
        package_version=package_version,
        architecture=architecture,
        package_file=package_path.name,
        package_sha256=package_sha256,
        publisher_id=publisher_id,
        verification_key=verification_key,
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return package_path, manifest_path, manifest
