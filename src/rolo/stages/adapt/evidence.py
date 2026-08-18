"""Shared bounded filesystem and text-evidence helpers for Adapt discovery."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

BASE_SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
}

_PROTOCOL_PATTERN = re.compile(
    r"(?i)\b(tcp|udp|http|https|grpc|websocket|mqtt|serial|socketcan|can|dbus|"
    r"shared[ _-]?memory)\b"
)


def walk_files(
    roots: Sequence[Path],
    *,
    limit: int,
    skip_directories: set[str],
) -> tuple[list[Path], bool, list[str]]:
    """Walk roots deterministically without following or returning symbolic links."""
    files: list[Path] = []
    warnings: list[str] = []
    for root in roots:
        if root.is_file():
            if not root.is_symlink():
                files.append(root)
                if len(files) >= limit:
                    return files, True, warnings
            continue
        if not root.is_dir():
            warnings.append(f"root is not a file or directory: {root}")
            continue
        for directory, names, filenames in os.walk(root, followlinks=False):
            names[:] = sorted(name for name in names if name not in skip_directories)
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.is_symlink():
                    continue
                files.append(path)
                if len(files) >= limit:
                    return files, True, warnings
    return files, False, warnings


def read_text(
    path: Path,
    limit: int,
    *,
    oversized: Literal["truncate", "reject"] = "truncate",
) -> str | None:
    """Read UTF-8 evidence with an explicit policy for files larger than the limit."""
    try:
        if oversized == "reject" and path.stat().st_size > limit:
            return None
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return None


def extract_protocols(text: str) -> list[str]:
    """Return normalized protocol tokens shared by source and document analysis."""
    protocols: set[str] = set()
    for match in _PROTOCOL_PATTERN.findall(text):
        normalized = match.lower().replace("-", "_").replace(" ", "_")
        protocols.add(normalized)
    return sorted(protocols)
