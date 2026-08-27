"""Preflight checks for files used by remote bootstrap execution."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def validate_bootstrap_file(path: Path, *, label: str, max_mode: int) -> Path:
    """Require a regular, non-empty file with safe POSIX permissions."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} is missing: {resolved}")
    if resolved.stat().st_size == 0:
        raise ValueError(f"{label} must not be empty")
    if os.name != "nt":
        mode = stat.S_IMODE(resolved.stat().st_mode)
        if mode & ~max_mode:
            raise ValueError(f"{label} permissions are too broad: {oct(mode)}")
    return resolved


def validate_bootstrap_security(known_hosts: Path, verification_key: Path) -> tuple[Path, Path]:
    """Validate pinned host keys and local signing verification material."""
    return (
        validate_bootstrap_file(known_hosts, label="known_hosts", max_mode=0o644),
        validate_bootstrap_file(verification_key, label="verification key", max_mode=0o600),
    )
